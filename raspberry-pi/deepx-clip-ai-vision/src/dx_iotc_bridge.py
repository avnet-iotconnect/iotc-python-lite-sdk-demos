"""
"Ask the Camera" — /IOTCONNECT bridge for the DEEPX CLIP demo (OpenCV variant).

Runs the stock dx_realtime_demo camera loop unmodified and attaches to it at
two seams:

  1. VideoThread.update_text(text_list, logit_list, alarm_level) is called every
     frame with the live prompt list and running-average scores — we wrap it to
     capture that state for the 1 Hz telemetry loop.
  2. The demo consumes the module-global `global_input` once per loop iteration
     ("del" pops the last prompt, any other string is embedded and appended).
     Cloud commands are queued and fed through that same mechanism.

Usage (from the dx_clip_demo repo root, venv-opencv active, with
iotcDeviceConfig.json + device certs alongside this file):

    python bridge/dx_iotc_bridge.py --camera 0

Commands (device template DXCLIP):
    set-prompt <text...>   replace all prompts with one
    add-prompt <text...>   append a prompt
    del-prompt             remove the most recently added prompt
    clear-prompts          remove all prompts
    set-threshold <0..1>   alert threshold for top_score

Telemetry @1 Hz: top_prompt, top_score, scores (json), fps, npu_temp,
cpu_temp, alert.
"""

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
# When run as a Greengrass component the bridge lives outside the dx_clip_demo
# checkout; DX_CLIP_DEMO_ROOT points at it (defaults to the parent directory
# for the in-tree bridge/ layout).
REPO_ROOT = os.environ.get("DX_CLIP_DEMO_ROOT") or os.path.dirname(BRIDGE_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "clip_demo_app_opencv"))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)  # the demo uses relative asset paths

from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

USE_GREENGRASS = bool(os.environ.get("SVCUID") or os.environ.get("AWS_IOT_THING_NAME"))
if USE_GREENGRASS:
    from avnet.iotconnect.sdk.greengrass import Client, C2dCommand, Callbacks
else:
    from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks

import dx_realtime_demo as demo


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.prompts = []
        self.scores = []
        self.alarm_levels = None   # reference to the demo's alarm-level list
        self.threshold = 0.28
        self.frame_times = []      # update_text call timestamps for FPS
        self.frame = None          # latest annotated panel frame (BGR copy)
        self.last_frame_copy = 0.0
        self.commands = []         # last cloud/terminal commands, newest last

    def record_command(self, source, name, args):
        with self.lock:
            self.commands.append({
                "t": time.strftime("%H:%M:%S"),
                "source": source,
                "name": name,
                "args": " ".join(args) if args else "",
            })
            del self.commands[:-15]

    def snapshot(self):
        with self.lock:
            return list(self.prompts), list(self.scores), self.threshold

    def fps(self):
        with self.lock:
            t = [x for x in self.frame_times if x > time.time() - 5.0]
            self.frame_times = t
        if len(t) < 2:
            return 0.0
        return (len(t) - 1) / max(t[-1] - t[0], 1e-6)


STATE = SharedState()
CMD_QUEUE = queue.Queue()


def _wrap_update_text():
    orig = demo.VideoThread.update_text

    def wrapped(self, text_list, logit_list, gt_text_alarm_level):
        now = time.time()
        with STATE.lock:
            STATE.prompts = list(text_list)
            try:
                STATE.scores = [float(v) for v in logit_list]
            except TypeError:
                STATE.scores = [float(logit_list)]
            STATE.alarm_levels = gt_text_alarm_level
            STATE.frame_times.append(now)
            if now - STATE.last_frame_copy > 0.1 and getattr(self, "view_pannel_frame", None) is not None:
                STATE.frame = self.view_pannel_frame.copy()
                STATE.last_frame_copy = now
        return orig(self, text_list, logit_list, gt_text_alarm_level)

    demo.VideoThread.update_text = wrapped

    orig_empty = demo.VideoThread.empty_text

    def wrapped_empty(self):
        with STATE.lock:
            STATE.prompts = []
            STATE.scores = []
            STATE.frame_times.append(time.time())
        return orig_empty(self)

    demo.VideoThread.empty_text = wrapped_empty


def _feed_demo_input(op: str, timeout=5.0):
    """Hand one op to the demo loop via global_input, waiting for it to be consumed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if demo.global_input == "":
            demo.global_input = op
            # wait for consumption
            while time.time() < deadline:
                if demo.global_input == "":
                    return True
                time.sleep(0.02)
            return False
        time.sleep(0.02)
    return False


def _enable_headless():
    """No-display mode for service/Greengrass use: the OpenCV window calls
    become no-ops and the web pages on --serve are the only UI."""
    demo.cv2.namedWindow = lambda *a, **k: None
    demo.cv2.setWindowProperty = lambda *a, **k: None
    demo.cv2.imshow = lambda *a, **k: None
    demo.cv2.destroyAllWindows = lambda *a, **k: None

    def _wait(ms=1):
        time.sleep(max(ms, 1) / 1000.0)
        return -1
    demo.cv2.waitKey = _wait
    print("[headless] display disabled; web UI only")


def _terminal_input():
    """Replaces the demo's stdin thread; adds `list` for showing all prompts."""
    while True:
        try:
            s = input("prompt> ('list' shows prompts, 'del' removes last, 'quit' exits): ")
        except EOFError:
            return
        cmd = s.strip()
        if cmd.lower() in ("list", "ls"):
            prompts, scores, threshold = STATE.snapshot()
            if not prompts:
                print("  (no prompts)")
            for p, sc in zip(prompts, scores):
                mark = "*" if sc >= threshold else " "
                print("  %s %.4f  %s" % (mark, sc, p))
            continue
        if cmd == "quit":
            demo.global_quit = True
            return
        if cmd:
            STATE.record_command("terminal", "del" if cmd == "del" else "add", [cmd])
            demo.global_input = cmd


def command_worker():
    while True:
        op = CMD_QUEUE.get()
        if op is None:
            return
        _feed_demo_input(op)


def npu_temp():
    try:
        out = subprocess.run(["dxrt-cli", "-s"], capture_output=True, text=True,
                             timeout=5).stdout
        temps = re.findall(r"temperature\s+(-?\d+(?:\.\d+)?)", out)
        if temps:
            return max(float(t) for t in temps)
    except Exception:
        pass
    return -1.0


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return -1.0


BOOTH_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Ask the Camera</title>
<style>
 body{margin:0;background:#0d0d0d;color:#fff;font:15px/1.45 system-ui,sans-serif}
 .wrap{display:flex;flex-wrap:wrap;gap:16px;padding:16px}
 img{max-width:100%;border-radius:8px}
 .video{flex:2;min-width:320px}.side{flex:1;min-width:260px}
 h1{font-size:18px;margin:0 0 10px}
 .bar{height:10px;border-radius:5px;background:#2c2c2a;overflow:hidden;margin:2px 0 10px}
 .bar>div{height:100%;border-radius:5px;background:#898781;transition:width .4s}
 .bar>div.hot{background:#0ca30c}
 .p{margin:0;color:#c3c2b7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .meta{color:#898781;font-size:13px;margin-top:10px}
 .cmd{color:#898781;font-size:13px;border-top:1px solid #2c2c2a;padding-top:6px;margin-top:6px}
</style></head><body><div class="wrap">
 <div class="video"><img src="/stream.mjpg" alt="live camera"></div>
 <div class="side"><h1>Ask the Camera &mdash; live scores</h1>
  <div id="scores"></div><div class="meta" id="meta"></div>
  <div class="cmd" id="cmds"></div></div>
</div><script>
async function tick(){
 try{
  const s = await (await fetch('/state.json')).json();
  document.getElementById('scores').innerHTML = s.prompts.map((p,i)=>{
   const sc = s.scores[i]||0, hot = sc>=s.threshold;
   return `<p class="p">${hot?'&#9679; ':''}${p} &mdash; ${sc.toFixed(3)}</p>
    <div class="bar"><div class="${hot?'hot':''}" style="width:${Math.min(100,sc/0.5*100)}%"></div></div>`;
  }).join('');
  document.getElementById('meta').textContent =
   `fps ${s.fps} · npu ${s.npu_temp}°C · cpu ${s.cpu_temp}°C · threshold ${s.threshold}`;
  document.getElementById('cmds').innerHTML =
   s.commands.slice(-5).reverse().map(c=>`${c.t} [${c.source}] ${c.name} ${c.args}`).join('<br>');
 }catch(e){}
 setTimeout(tick, 1000);
}
tick();
</script></body></html>"""


PAGE_STYLE = """<style>
 body{margin:0;background:#0d0d0d;color:#fff;font:16px/1.5 system-ui,sans-serif;padding:56px 20px 20px}
 h1{font-size:17px;margin:0 0 12px;color:#c3c2b7;font-weight:600}
 .bar{height:12px;border-radius:6px;background:#2c2c2a;overflow:hidden;margin:3px 0 12px}
 .bar>div{height:100%;border-radius:6px;background:#898781;transition:width .4s}
 .bar>div.hot{background:#0ca30c}
 .p{margin:0;color:#e8e7e0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .muted{color:#898781}
 ol{margin:0;padding-left:26px}
 ol li{margin:6px 0;color:#e8e7e0;font-size:18px}
 .hero{font-size:34px;font-weight:700;margin:6px 0;line-height:1.2}
 .heroscore{font-size:56px;font-weight:700}
 .match{color:#0ca30c}.idle{color:#898781}
</style>"""

PROMPTS_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Loaded Prompts</title>""" + PAGE_STYLE + """</head><body>
<h1>LOADED PROMPTS <span class="muted" id="n"></span></h1>
<ol id="list"></ol>
<script>
async function tick(){
 try{
  const s = await (await fetch('/state.json')).json();
  document.getElementById('list').innerHTML =
    s.prompts.map(p=>`<li>${p}</li>`).join('') || '<li class="muted">(none)</li>';
  document.getElementById('n').textContent = s.prompts.length ? `(${s.prompts.length})` : '';
 }catch(e){}
 setTimeout(tick, 1000);
}
tick();
</script></body></html>"""

TOP_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Top Prompt</title><style>
 html,body{height:100%}
 body{margin:0;background:#0d0d0d;color:#fff;font:16px/1.4 system-ui,sans-serif;
      display:flex;flex-direction:column;align-items:center;justify-content:center;
      text-align:center;padding:40px 24px;box-sizing:border-box;transition:background .6s}
 body.match{background:#07270d}
 .emoji{font-size:clamp(80px,26vh,240px);line-height:1.1;opacity:0;transform:scale(.6);transition:all .5s}
 body.match .emoji{opacity:1;transform:scale(1.12)}
 .prompt{font-size:clamp(26px,5.5vw,64px);font-weight:800;margin:2vh 0 1vh;line-height:1.15}
 .score{font-size:clamp(48px,12vh,120px);font-weight:800;color:#898781;transition:color .4s}
 body.match .score{color:#0ca30c;animation:pulse 1.2s infinite}
 @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
 .badge{font-size:clamp(16px,2.5vh,26px);letter-spacing:.35em;color:#898781;margin-top:1vh}
 body.match .badge{color:#0ca30c;font-weight:700}
 .meter{width:min(70%,700px);height:14px;border-radius:7px;background:#2c2c2a;margin-top:3vh;overflow:hidden;position:relative}
 .meter>div{height:100%;border-radius:7px;background:#898781;transition:width .4s}
 body.match .meter>div{background:#0ca30c}
 .thr{position:absolute;top:-4px;bottom:-4px;width:3px;background:#fab219}
</style></head><body>
<div class="emoji" id="pic">&#128064;</div>
<div class="prompt" id="top">waiting&hellip;</div>
<div class="score" id="score">0.000</div>
<div class="badge" id="badge">WATCHING</div>
<div class="meter"><div id="fill" style="width:0%"></div><div class="thr" id="thr" style="left:56%"></div></div>
<script>
const EMOJI = [
 [/wav/i,'\\uD83D\\uDC4B'], [/thumb/i,'\\uD83D\\uDC4D'], [/hands.*(rais|up)|rais.*hand/i,'\\uD83D\\uDE4C'],
 [/phone/i,'\\uD83D\\uDCF1'], [/drink|cup|coffee/i,'\\u2615'], [/safety glass|goggle/i,'\\uD83E\\uDD7D'],
 [/sunglass|glasses/i,'\\uD83D\\uDC53'], [/hard ?hat|helmet/i,'\\u26D1\\uFE0F'], [/hat|cap\\b/i,'\\uD83E\\uDDE2'],
 [/peace/i,'\\u270C\\uFE0F'], [/vest|visibility/i,'\\uD83E\\uDDBA'], [/toolbox|tool/i,'\\uD83E\\uDDF0'],
 [/box|package|cardboard/i,'\\uD83D\\uDCE6'], [/empty|nobody|no one/i,'\\uD83D\\uDEAB'],
 [/crowd|people/i,'\\uD83D\\uDC65'], [/fire|burn|explod/i,'\\uD83D\\uDD25'], [/car\\b/i,'\\uD83D\\uDE97'],
 [/water|gush/i,'\\uD83D\\uDCA7'], [/subway|train/i,'\\uD83D\\uDE87'],
 [/fight|confront|violen|punch|kick/i,'\\uD83E\\uDD4A'], [/terror|shoot|gun/i,'\\u26A0\\uFE0F'],
 [/fall|fallen/i,'\\u26A0\\uFE0F'], [/person|someone|worker/i,'\\uD83E\\uDDCD'],
];
function pick(p){ for(const [re,e] of EMOJI){ if(re.test(p)) return e; } return '\\uD83C\\uDFAF'; }
async function tick(){
 try{
  const s = await (await fetch('/state.json')).json();
  let ti=-1, tv=-1;
  s.scores.forEach((v,i)=>{ if(v>tv){tv=v;ti=i;} });
  const hot = ti>=0 && tv>=s.threshold;
  document.body.className = hot ? 'match' : '';
  document.getElementById('pic').textContent = ti>=0 ? pick(s.prompts[ti]) : '\\uD83D\\uDC40';
  document.getElementById('top').textContent = ti>=0 ? s.prompts[ti] : 'waiting\\u2026';
  document.getElementById('score').textContent = ti>=0 ? tv.toFixed(3) : '0.000';
  document.getElementById('badge').textContent = hot ? '\\u25CF MATCH' : 'WATCHING';
  document.getElementById('fill').style.width = Math.min(100, Math.max(0,tv)/0.5*100) + '%';
  document.getElementById('thr').style.left = Math.min(100, s.threshold/0.5*100) + '%';
 }catch(e){}
 setTimeout(tick, 700);
}
tick();
</script></body></html>"""


CAMERA_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Camera</title><style>
 html,body{margin:0;height:100%;background:#000}
 img{width:100%;height:100%;object-fit:contain;display:block}
</style></head><body><img src="/stream.mjpg" alt="live camera"></body></html>"""


def start_web(port):
    import cv2
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", BOOTH_PAGE.encode())
            elif self.path == "/prompts":
                self._send(200, "text/html; charset=utf-8", PROMPTS_PAGE.encode())
            elif self.path == "/top":
                self._send(200, "text/html; charset=utf-8", TOP_PAGE.encode())
            elif self.path == "/camera":
                self._send(200, "text/html; charset=utf-8", CAMERA_PAGE.encode())
            elif self.path == "/state.json":
                prompts, scores, threshold = STATE.snapshot()
                with STATE.lock:
                    cmds = list(STATE.commands)
                body = json.dumps({
                    "prompts": prompts, "scores": scores, "threshold": threshold,
                    "fps": round(STATE.fps(), 1), "npu_temp": npu_temp(),
                    "cpu_temp": round(cpu_temp(), 1), "commands": cmds,
                }).encode()
                self._send(200, "application/json", body)
            elif self.path == "/stream.mjpg":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    while True:
                        with STATE.lock:
                            frame = None if STATE.frame is None else STATE.frame
                        if frame is not None:
                            ok, jpg = cv2.imencode(".jpg", frame,
                                                   [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if ok:
                                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                                 b"Content-Length: " + str(len(jpg)).encode()
                                                 + b"\r\n\r\n")
                                self.wfile.write(jpg.tobytes())
                                self.wfile.write(b"\r\n")
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self._send(404, "text/plain", b"not found")

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("[web] serving booth page on port %d" % port)
    return srv


def make_command_cb(client_ref):
    def on_command(msg: C2dCommand):
        name = msg.command_name
        args = msg.command_args or []
        STATE.record_command("cloud", name, args)
        ok, note = True, "OK"
        prompts, _, _ = STATE.snapshot()
        if name == "set-prompt" and args:
            for _ in prompts:
                CMD_QUEUE.put("del")
            CMD_QUEUE.put(" ".join(args))
            note = "prompt set"
        elif name == "add-prompt" and args:
            CMD_QUEUE.put(" ".join(args))
            note = "prompt added"
        elif name == "del-prompt":
            if prompts:
                CMD_QUEUE.put("del")
            note = "prompt deleted"
        elif name == "clear-prompts":
            for _ in prompts:
                CMD_QUEUE.put("del")
            note = "prompts cleared"
        elif name == "set-threshold" and args:
            try:
                STATE.threshold = float(args[0])
                note = "threshold=%s" % STATE.threshold
            except ValueError:
                ok, note = False, "bad threshold"
        else:
            ok, note = False, "unknown command"
            if USE_GREENGRASS:
                # another component may service this command; don't fail-ack it
                print("[iotc] cmd %s not ours; ignoring" % name)
                return
        c = client_ref.get("client")
        if c is not None and msg.ack_id is not None:
            c.send_command_ack(
                msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, note)
        print("[iotc] cmd %s %s -> %s" % (name, args, note))
    return on_command


def telemetry_loop(client_ref):
    while True:
        time.sleep(1.0)
        c = client_ref.get("client")
        if c is None or not getattr(c, "is_connected", lambda: True)():
            continue
        prompts, scores, threshold = STATE.snapshot()
        if prompts and scores:
            top_i = max(range(len(scores)), key=lambda i: scores[i])
            top_prompt, top_score = prompts[top_i], scores[top_i]
        else:
            top_prompt, top_score = "", 0.0
        try:
            c.send_telemetry({
                "top_prompt": top_prompt,
                "top_score": round(top_score, 4),
                "scores": json.dumps(
                    {p: round(s, 4) for p, s in zip(prompts, scores)}),
                "fps": round(STATE.fps(), 2),
                "npu_temp": npu_temp(),
                "cpu_temp": cpu_temp(),
                "alert": 1 if top_score >= threshold else 0,
            })
        except Exception as e:
            print("[iotc] telemetry error:", e)


def start_iotc():
    client_ref = {"client": None}
    if USE_GREENGRASS:
        # identity/connection comes from the Greengrass nucleus over IPC
        c = Client(callbacks=Callbacks(command_cb=make_command_cb(client_ref)))
        client_ref["client"] = c
        print("[iotc] greengrass client ready")
        return client_ref
    cfg_json = os.path.join(BRIDGE_DIR, "iotcDeviceConfig.json")
    cert = os.path.join(BRIDGE_DIR, "device-cert.pem")
    pkey = os.path.join(BRIDGE_DIR, "device-pkey.pem")
    if not os.path.isfile(cfg_json):
        print("[iotc] %s not found — running OFFLINE (local demo only)" % cfg_json)
        return client_ref
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=cfg_json,
        device_cert_path=cert if os.path.isfile(cert) else None,
        device_pkey_path=pkey if os.path.isfile(pkey) else None,
    )
    c = Client(config=device_config,
               callbacks=Callbacks(command_cb=make_command_cb(client_ref)))
    c.connect()
    client_ref["client"] = c
    print("[iotc] connected")
    return client_ref


def _resolve_camera(preferred):
    """Return a camera index that actually delivers frames, preferring the
    requested one. USB cameras can renumber after a glitch/replug."""
    import cv2
    try:
        pref = int(preferred)
    except ValueError:
        return preferred  # a file/url path, not an index
    for idx in [pref] + [i for i in range(10) if i != pref]:
        cap = cv2.VideoCapture(idx)
        ok = cap.isOpened() and cap.read()[0]
        cap.release()
        if ok:
            if idx != pref:
                print("[camera] index %d not working, using %d" % (pref, idx))
            return str(idx)
    print("[camera] WARNING: no working camera found, keeping %s" % preferred)
    return str(preferred)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default="0",
                    help="camera index for the demo (features_path)")
    ap.add_argument("--serve", type=int, default=8080,
                    help="port for the booth web page / MJPEG stream (0 disables)")
    ap.add_argument("--headless", action="store_true",
                    help="no OpenCV window (service/Greengrass mode); web UI only")
    args, extra = ap.parse_known_args()

    _wrap_update_text()
    if args.headless or not os.environ.get("DISPLAY"):
        _enable_headless()
    demo.insert_text_in_term = _terminal_input

    if args.serve:
        start_web(args.serve)

    client_ref = start_iotc()
    threading.Thread(target=command_worker, daemon=True).start()
    threading.Thread(target=telemetry_loop, args=(client_ref,), daemon=True).start()

    # Run the stock demo main loop in camera mode.
    sys.argv = [sys.argv[0], "--features_path", _resolve_camera(args.camera)] + extra
    demo.main()


if __name__ == "__main__":
    main()
