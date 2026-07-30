#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# -----------------------------------------------------------------------------
# LLM shootout web UI - benchmark any prompt across selectable backend/model
# combinations, live from a browser: http://<board-ip>:8090
#
# Runs each selected combination sequentially through the demo's real ask-llm
# code paths (a patched copy of app.py in --test-llm mode), samples CPU% and
# memory at 1 Hz during each run, and streams results to the page as they
# complete: load time, TTFT, generation time, tok/s, token count, wall time,
# CPU avg/peak, peak memory - plus the model's verbatim response.
#
# Stdlib only. The device config (genai-config.json) is flipped per run and
# always restored afterwards, so the /IOTCONNECT demo is untouched.
#
# Install (see README): copy next to app.py and run as the genai-bench service.
# -----------------------------------------------------------------------------
import glob
import http.server
import json
import os
import re
import subprocess
import threading
import time
import urllib.request

PORT = int(os.environ.get("BENCH_PORT", "8090"))
DEMO_DIR = "/opt/demo"
CFG = os.path.join(DEMO_DIR, "genai-config.json")
APP_SRC = os.path.join(DEMO_DIR, "app.py")
APP_COPY = "/tmp/bench_app.py"
AAF_URL = "http://127.0.0.1:8100/v1/models"
RUN_TIMEOUT = 420

job_lock = threading.Lock()
job = {"state": "idle", "prompt": "", "current": "", "queue": [], "results": []}

# --- expected-duration estimates ----------------------------------------------
# Defaults come from measured runs (docs/BENCHMARKS.md); after every run the
# actual wall time is remembered per combo and used for future estimates.
EST_FILE = "/tmp/bench_est.json"


def default_est(combo_id):
    if combo_id.startswith("ara2|"):
        return 15 if "7B" in combo_id else 5
    if combo_id.startswith("cpu|"):
        return 55 if "q8" in combo_id else 45
    if combo_id.startswith("neutron|"):
        return 135 if "q8" in combo_id else 155
    if combo_id.startswith("gguf|"):
        return 25
    return 30


def load_estimates():
    try:
        return json.load(open(EST_FILE))
    except Exception:
        return {}


def save_estimate(combo_id, wall_s):
    est = load_estimates()
    est[combo_id] = round(wall_s, 1)
    try:
        json.dump(est, open(EST_FILE, "w"))
    except Exception:
        pass


# --- combo discovery ----------------------------------------------------------
def list_combos():
    combos = []
    try:
        data = json.load(urllib.request.urlopen(AAF_URL, timeout=6))
        for m in data.get("data", []):
            if m.get("ready"):
                combos.append({"id": "ara2|" + m["id"],
                               "label": "Ara240 NPU / " + m["id"],
                               "group": "Ara240 (discrete NPU)",
                               "cfg": {"backend": "ara2", "ara2_model": m["id"]}})
    except Exception:
        pass
    for b, gname in (("cpu", "CPU (GenAI Flow)"), ("neutron", "Neutron NPU (GenAI Flow)")):
        for m in ("danube-500M-q8", "danube-500M-q4"):
            combos.append({"id": "%s|%s" % (b, m), "label": "%s / %s" % (gname, m),
                           "group": gname, "cfg": {"backend": b, "model": m}})
    try:
        llama_dir = json.load(open(CFG)).get("llama_dir", "/root/llama.cpp")
    except Exception:
        llama_dir = "/root/llama.cpp"
    for p in sorted(glob.glob(os.path.join(llama_dir, "models", "*.gguf"))):
        name = os.path.splitext(os.path.basename(p))[0]
        combos.append({"id": "gguf|" + name, "label": "CPU (llama.cpp) / " + name,
                       "group": "CPU (llama.cpp)", "cfg": {"backend": "cpu", "model": name}})
    learned = load_estimates()
    for c in combos:
        c["est_s"] = learned.get(c["id"], default_est(c["id"]))
    return combos


# --- system sampling ----------------------------------------------------------
def read_cpu():
    with open("/proc/stat") as f:
        p = [int(x) for x in f.readline().split()[1:8]]
    return sum(p), p[3]


def read_mem_mb():
    total = avail = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable"):
                avail = int(line.split()[1])
    return (total - avail) / 1024.0


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self.cpu, self.mem = [], []

    def run(self):
        t0, i0 = read_cpu()
        while not self.stop_flag.wait(1.0):
            t1, i1 = read_cpu()
            dt, di = t1 - t0, i1 - i0
            t0, i0 = t1, i1
            if dt > 0:
                self.cpu.append(100.0 * (dt - di) / dt)
            self.mem.append(read_mem_mb())

    def finish(self):
        self.stop_flag.set()
        self.join(timeout=3)
        return (round(sum(self.cpu) / len(self.cpu), 1) if self.cpu else 0.0,
                round(max(self.cpu), 1) if self.cpu else 0.0,
                round(max(self.mem), 1) if self.mem else 0.0)


# --- benchmark worker ---------------------------------------------------------
def patch_app_copy():
    src = open(APP_SRC).read()
    hook = ('print("\\n=== RESULT ===\\n" + answer)\n'
            '        import json as _j; print("METRICS " + _j.dumps('
            '{k: v for k, v in telemetry.items() if k.startswith("llm_")}))')
    patched = src.replace('print("\\n=== RESULT ===\\n" + answer)', hook, 1)
    if patched == src:
        raise RuntimeError("metrics hook anchor not found in app.py")
    open(APP_COPY, "w").write(patched)


def kill_stray_sessions():
    subprocess.run(["pkill", "-f", r"eiq_genai_flow\.py -i keyb"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_combo(combo, prompt):
    d = json.load(open(CFG))
    d.update(combo["cfg"])
    json.dump(d, open(CFG, "w"), indent=2)
    kill_stray_sessions()
    time.sleep(2)
    s = Sampler()
    s.start()
    t0 = time.monotonic()
    out = ""
    try:
        r = subprocess.run(["python3", APP_COPY, "--test-llm", prompt],
                           cwd=DEMO_DIR, timeout=RUN_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = r.stdout or ""
    except subprocess.TimeoutExpired as e:
        out = (e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes)
               else (e.stdout or "")) + "\n[TIMEOUT after %ds]" % RUN_TIMEOUT
    wall = round(time.monotonic() - t0, 1)
    cpu_avg, cpu_peak, mem_peak = s.finish()
    kill_stray_sessions()

    metrics, response = {}, ""
    m = re.search(r"^METRICS (\{.*\})", out, re.M)
    if m:
        try:
            metrics = json.loads(m.group(1))
        except ValueError:
            pass
    m = re.search(r"=== RESULT ===\n(.*?)(?:\nMETRICS |\Z)", out, re.S)
    if m:
        response = m.group(1).strip()
    return {
        "label": combo["label"],
        "load_s": metrics.get("llm_load_time"),
        "ttft_s": metrics.get("llm_ttft"),
        "gen_s": metrics.get("llm_gen_time"),
        "tps": metrics.get("llm_tps"),
        "tokens": metrics.get("llm_token_count"),
        "wall_s": wall,
        "cpu_avg_pct": cpu_avg,
        "cpu_peak_pct": cpu_peak,
        "mem_peak_mb": mem_peak,
        "response": response[:1500],
        "error": "" if response else (out.strip().splitlines()[-1][:300] if out.strip() else "no output"),
    }


def worker(selected, prompt):
    orig = open(CFG).read()
    try:
        patch_app_copy()
        for combo in selected:
            with job_lock:
                job["current"] = combo["label"]
                job["current_est_s"] = combo.get("est_s", 30)
                job["current_started"] = time.time()
            result = run_combo(combo, prompt)
            if not result.get("error"):
                save_estimate(combo["id"], result["wall_s"])
            with job_lock:
                job["results"].append(result)
                job["queue"] = [q for q in job["queue"] if q != combo["label"]]
    except Exception as e:
        with job_lock:
            job["results"].append({"label": "harness", "error": str(e)[:300]})
    finally:
        open(CFG, "w").write(orig)
        kill_stray_sessions()
        with job_lock:
            job["state"] = "done"
            job["current"] = ""


# --- web ----------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>i.MX95 LLM Shootout</title>
<style>
 :root{--bg:#101418;--card:#1a2129;--line:#2a3441;--fg:#e6edf3;--dim:#8b98a5;--acc:#33b5e5;--ok:#3fb950;--warn:#d29922;--err:#f85149}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1080px;margin:0 auto;padding:20px}
 h1{font-size:1.4rem;margin:.2rem 0 .1rem}h1 small{color:var(--dim);font-weight:400;font-size:.9rem}
 .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
 textarea{width:100%;background:#0d1117;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit;resize:vertical;min-height:56px}
 .groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
 fieldset{border:1px solid var(--line);border-radius:8px;margin:0;padding:8px 12px}
 legend{color:var(--acc);font-size:.85rem;padding:0 4px}
 label.cb{display:block;cursor:pointer;padding:2px 0;color:var(--fg)}
 label.cb input{accent-color:var(--acc);margin-right:7px}
 button{background:var(--acc);color:#04131b;border:0;border-radius:8px;padding:10px 22px;font:600 1rem inherit;cursor:pointer}
 button:disabled{background:#2a3441;color:var(--dim);cursor:default}
 .bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px}
 #status{color:var(--dim)}
 .spin{display:inline-block;width:14px;height:14px;border:2px solid var(--acc);border-top-color:transparent;border-radius:50%;animation:r 0.9s linear infinite;vertical-align:-2px}
 @keyframes r{to{transform:rotate(360deg)}}
 .tblwrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.88rem}
 th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:right;white-space:nowrap}
 th:first-child,td:first-child{text-align:left;white-space:normal}
 th{color:var(--dim);font-weight:600}
 td.best{color:var(--ok);font-weight:700}
 .resp{border-left:3px solid var(--acc);margin:10px 0;padding:8px 12px;background:#0d1117;border-radius:0 8px 8px 0}
 .resp h3{margin:0 0 4px;font-size:.95rem}.resp p{margin:0;white-space:pre-wrap;color:#c9d1d9}
 .resp .err{color:var(--err)}
 .note{color:var(--dim);font-size:.82rem}
</style></head><body><div class="wrap">
<h1>LLM Shootout <small>&mdash; FRDM i.MX 95 + Ara240 &middot; same prompt, your choice of engines</small></h1>
<div class="card">
 <textarea id="prompt" placeholder="Type any prompt...">What color is an apple?</textarea>
 <div class="groups" id="groups" style="margin-top:10px"></div>
 <div class="bar">
  <button id="run">Run shootout</button>
  <label class="cb"><input type="checkbox" id="selall"> select all</label>
  <span id="est" style="color:var(--warn);font-weight:600"></span>
  <span id="status"></span>
 </div>
 <div class="note">Runs are sequential on the board. Estimates come from each combination's <em>last measured</em> run on this board (defaults from docs/BENCHMARKS.md until a combo has run once). Device config is restored after every run &mdash; the /IOTCONNECT demo is untouched.</div>
</div>
<div class="card" id="resultscard" style="display:none">
 <div class="tblwrap"><table id="tbl"><thead><tr>
  <th>Backend / Model</th><th>Load s</th><th>TTFT s</th><th>Gen s</th><th>Tok/s</th><th>Tokens</th><th>Wall s</th><th>CPU avg %</th><th>CPU pk %</th><th>Mem pk MB</th>
 </tr></thead><tbody></tbody></table></div>
 <div id="resps"></div>
</div>
<script>
let combos=[],estById={},estByLabel={};
function fmtDur(s){s=Math.max(0,Math.round(s));return s<60?('~'+s+' s'):('~'+Math.floor(s/60)+' min '+(s%60)+' s')}
function updateEst(){
 const sel=[...document.querySelectorAll('#groups input:checked')];
 const total=sel.reduce((a,i)=>a+(estById[i.value]||30),0);
 document.getElementById('est').textContent=sel.length?('Estimated wait: '+fmtDur(total)):'';
}
async function loadCombos(){
 combos=await (await fetch('api/combos')).json();
 estById={};estByLabel={};combos.forEach(c=>{estById[c.id]=c.est_s;estByLabel[c.label]=c.est_s});
 const groups={};combos.forEach(c=>{(groups[c.group]=groups[c.group]||[]).push(c)});
 const gd=document.getElementById('groups');gd.innerHTML='';
 for(const[g,list]of Object.entries(groups)){
  const fs=document.createElement('fieldset');fs.innerHTML='<legend>'+g+'</legend>';
  list.forEach(c=>{const l=document.createElement('label');l.className='cb';
   l.innerHTML='<input type="checkbox" value="'+c.id+'" '+(c.id.startsWith('ara2')?'checked':'')+'>'+c.label.replace(g+' / ','')
    +' <span style="color:var(--dim);font-size:.8rem">'+fmtDur(c.est_s)+'</span>';
   fs.appendChild(l)});
  gd.appendChild(fs);}
 gd.addEventListener('change',updateEst);updateEst();
}
document.getElementById('selall').onchange=e=>{document.querySelectorAll('#groups input').forEach(i=>i.checked=e.target.checked);updateEst()};
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function fmt(v){return v==null?'–':v}
function render(j){
 const tb=document.querySelector('#tbl tbody');tb.innerHTML='';
 const cols=['load_s','ttft_s','gen_s','tps','tokens','wall_s','cpu_avg_pct','cpu_peak_pct','mem_peak_mb'];
 const best={};cols.forEach(c=>{const vals=j.results.filter(r=>r[c]!=null&&!r.error).map(r=>r[c]);
  if(vals.length>1)best[c]=(c==='tps'||c==='tokens')?Math.max(...vals):Math.min(...vals);});
 j.results.forEach(r=>{const tr=document.createElement('tr');
  tr.innerHTML='<td>'+esc(r.label)+'</td>'+cols.map(c=>'<td class="'+(best[c]!==undefined&&r[c]===best[c]?'best':'')+'">'+fmt(r[c])+'</td>').join('');
  tb.appendChild(tr)});
 const rd=document.getElementById('resps');rd.innerHTML='';
 j.results.forEach(r=>{const d=document.createElement('div');d.className='resp';
  d.innerHTML='<h3>'+esc(r.label)+'</h3>'+(r.error?'<p class="err">'+esc(r.error)+'</p>':'<p>'+esc(r.response)+'</p>');
  rd.appendChild(d)});
 document.getElementById('resultscard').style.display=j.results.length?'':'none';
}
let poller=null;
async function poll(){
 const j=await (await fetch('api/status')).json();render(j);
 const st=document.getElementById('status');
 if(j.state==='running'){
  const elapsed=j.current_started?(Date.now()/1000-j.current_started):0;
  const remCur=Math.max(0,(j.current_est_s||30)-elapsed);
  const remQ=j.queue.reduce((a,l)=>a+(estByLabel[l]||30),0);
  st.innerHTML='<span class="spin"></span> running: <b>'+esc(j.current)+'</b> &middot; '+j.results.length+' done, '+j.queue.length+' queued &middot; <b style="color:var(--warn)">'+fmtDur(remCur+remQ)+' left</b>';
  document.getElementById('run').disabled=true;}
 else{st.textContent=j.results.length?'done — '+j.results.length+' result(s)':'';
  document.getElementById('run').disabled=false;
  if(poller){clearInterval(poller);poller=null;loadCombos();}}
}
document.getElementById('run').onclick=async()=>{
 const sel=[...document.querySelectorAll('#groups input:checked')].map(i=>i.value);
 const prompt=document.getElementById('prompt').value.trim();
 if(!sel.length||!prompt){alert('Pick at least one combination and a prompt');return}
 const r=await fetch('api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:prompt,combos:sel})});
 if(!r.ok){alert(await r.text());return}
 document.getElementById('run').disabled=true;
 if(!poller)poller=setInterval(poll,2000);poll();
};
loadCombos();poll();
</script></div></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path == "/api/combos":
            self._send(200, json.dumps(list_combos()))
        elif self.path == "/api/status":
            with job_lock:
                self._send(200, json.dumps(job))
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        if self.path != "/api/run":
            self._send(404, '{"error":"not found"}')
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n) or b"{}")
            prompt = (req.get("prompt") or "").strip()
            ids = req.get("combos") or []
            available = {c["id"]: c for c in list_combos()}
            selected = [available[i] for i in ids if i in available]
            if not prompt or not selected:
                self._send(400, '{"error":"need a prompt and at least one valid combo"}')
                return
        except Exception as e:
            self._send(400, json.dumps({"error": str(e)[:200]}))
            return
        with job_lock:
            if job["state"] == "running":
                self._send(409, '{"error":"a shootout is already running"}')
                return
            job.update(state="running", prompt=prompt, current="",
                       queue=[c["label"] for c in selected], results=[])
        threading.Thread(target=worker, args=(selected, prompt), daemon=True).start()
        self._send(200, '{"started":true}')


def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("LLM shootout UI on http://0.0.0.0:%d" % PORT, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
