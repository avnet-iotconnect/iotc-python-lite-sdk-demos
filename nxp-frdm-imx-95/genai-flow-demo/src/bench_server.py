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
 :root{--bg:#101418;--card:#1a2129;--line:#2a3441;--fg:#e6edf3;--dim:#8b98a5;--acc:#41C363;--ok:#3fb950;--warn:#d29922;--err:#f85149}
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

 .brandbar{display:flex;align-items:center;gap:12px;padding:2px 0 15px;margin-bottom:18px;border-bottom:1px solid var(--line)}
 .brandmark{height:25px;width:auto;display:block}
 .brandbar .tag{color:var(--dim);font-size:.85rem;font-weight:600;letter-spacing:.2px}
</style></head><body><div class="wrap">
<div class="brandbar"><img class="brandmark" src="data:image/png;base64,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" alt="/IOTCONNECT"><span class="tag">FRDM i.MX 95 + Ara240</span></div>

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
