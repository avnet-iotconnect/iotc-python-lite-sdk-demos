# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""
"Ask the Camera" — /IOTCONNECT bridge for the Hailo-8 CLIP demo (hailo-apps).

Wraps hailo-apps' GStreamerClipApp with an /IOTCONNECT cloud surface:
C2D prompt commands in, 1 Hz telemetry out, and self-served booth web
pages (live MJPEG + scores) for dashboard embedded widgets.

Integration seams (all public API, no monkeypatching):
  - `text_image_matcher` singleton: add_text()/set_threshold() for commands;
    entries[i].probability (softmax across prompts) for telemetry.
  - app_callback: captures frames for the MJPEG stream and counts fps.

Run on the board (inside the hailo-apps venv, from this file's directory):

    source ~/hailo-apps/setup_env.sh
    DISPLAY=:0 python hailo_iotc_bridge.py --input /dev/video0

Commands (template HCLIP): set-prompt, add-prompt, del-prompt, clear-prompts,
set-threshold (0..1 softmax probability, default 0.8).
Telemetry @1 Hz: top_prompt, top_score, scores (json), fps, npu_temp,
cpu_temp, alert.
"""

import argparse
import glob
import json
import os
import sys
import threading
import time

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from hailo_apps.python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
from hailo_apps.python.pipeline_apps.clip.clip_pipeline import GStreamerClipApp
from hailo_apps.python.pipeline_apps.clip.text_image_matcher import text_image_matcher

MAX_PROMPTS = 6  # matcher slot count (see TextImageMatcher(max_entries=6))


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None            # latest BGR frame for MJPEG
        self.last_frame_copy = 0.0
        self.frame_times = []
        self.commands = []

    def record_command(self, source, name, args):
        with self.lock:
            self.commands.append({
                "t": time.strftime("%H:%M:%S"),
                "source": source,
                "name": name,
                "args": " ".join(args) if args else "",
            })
            del self.commands[:-15]

    def fps(self):
        with self.lock:
            t = [x for x in self.frame_times if x > time.time() - 5.0]
            self.frame_times = t
        if len(t) < 2:
            return 0.0
        return (len(t) - 1) / max(t[-1] - t[0], 1e-6)


STATE = SharedState()


def snapshot_matcher():
    """Current prompts + softmax probabilities + threshold from the matcher."""
    prompts, scores = [], []
    for entry in text_image_matcher.entries:
        if entry.text != "":
            prompts.append(entry.text)
            scores.append(float(entry.probability))
    return prompts, scores, float(text_image_matcher.threshold)


def app_callback(element, buffer, user_data):
    # invoked via the identity element's "handoff" signal:
    # (identity, Gst.Buffer, user_data)
    if buffer is None or not isinstance(buffer, Gst.Buffer):
        return Gst.PadProbeReturn.OK
    now = time.time()
    with STATE.lock:
        STATE.frame_times.append(now)
        want_frame = now - STATE.last_frame_copy > 0.1
    if want_frame and user_data.use_frame:
        try:
            pad = element.get_static_pad("src") if hasattr(element, "get_static_pad") else element
            fmt, width, height = get_caps_from_pad(pad)
            if fmt is not None:
                frame = get_numpy_from_buffer(buffer, fmt, width, height)
                with STATE.lock:
                    STATE.frame = frame[:, :, ::-1].copy()  # RGB -> BGR for JPEG
                    STATE.last_frame_copy = now
        except Exception:
            pass
    return Gst.PadProbeReturn.OK


# ---------------- commands ----------------

def _free_slot():
    for i, e in enumerate(text_image_matcher.entries):
        if e.text == "":
            return i
    return None


def _clear_all():
    for i in range(len(text_image_matcher.entries)):
        text_image_matcher.add_text("", index=i)


def _del_last():
    used = [i for i, e in enumerate(text_image_matcher.entries) if e.text != ""]
    if used:
        text_image_matcher.add_text("", index=used[-1])


def make_command_cb(client_ref):
    def on_command(msg: C2dCommand):
        name = msg.command_name
        args = msg.command_args or []
        STATE.record_command("cloud", name, args)
        ok, note = True, "OK"
        try:
            if name == "set-prompt" and args:
                _clear_all()
                text_image_matcher.add_text(" ".join(args), index=0)
                note = "prompt set"
            elif name == "add-prompt" and args:
                slot = _free_slot()
                if slot is None:
                    ok, note = False, "all %d prompt slots in use" % MAX_PROMPTS
                else:
                    text_image_matcher.add_text(" ".join(args), index=slot)
                    note = "prompt added (slot %d)" % slot
            elif name == "del-prompt":
                _del_last()
                note = "prompt deleted"
            elif name == "clear-prompts":
                _clear_all()
                note = "prompts cleared"
            elif name == "set-threshold" and args:
                text_image_matcher.set_threshold(float(args[0]))
                note = "threshold=%s" % args[0]
            else:
                ok, note = False, "unknown command"
        except Exception as e:
            ok, note = False, "error: %s" % e
        c = client_ref.get("client")
        if c is not None and msg.ack_id is not None:
            c.send_command_ack(
                msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, note)
        print("[iotc] cmd %s %s -> %s" % (name, args, note))
    return on_command


# ---------------- telemetry ----------------

def npu_temp():
    # the hailo_pci driver exposes an hwmon node on recent versions
    try:
        for hw in glob.glob("/sys/class/hwmon/hwmon*/name"):
            if "hailo" in open(hw).read():
                with open(os.path.join(os.path.dirname(hw), "temp1_input")) as f:
                    return int(f.read().strip()) / 1000.0
    except Exception:
        pass
    return -1.0


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return -1.0


def telemetry_loop(client_ref):
    while True:
        time.sleep(1.0)
        c = client_ref.get("client")
        if c is None or not getattr(c, "is_connected", lambda: True)():
            continue
        prompts, scores, threshold = snapshot_matcher()
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
                "cpu_temp": round(cpu_temp(), 1),
                "alert": 1 if top_score >= threshold else 0,
            })
        except Exception as e:
            print("[iotc] telemetry error:", e)


def start_iotc():
    client_ref = {"client": None}
    cfg_json = os.path.join(BRIDGE_DIR, "iotcDeviceConfig.json")
    if not os.path.isfile(cfg_json):
        print("[iotc] %s not found — running OFFLINE" % cfg_json)
        return client_ref
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=cfg_json,
        device_cert_path=os.path.join(BRIDGE_DIR, "device-cert.pem"),
        device_pkey_path=os.path.join(BRIDGE_DIR, "device-pkey.pem"),
    )
    c = Client(config=device_config,
               callbacks=Callbacks(command_cb=make_command_cb(client_ref)))
    c.connect()
    client_ref["client"] = c
    print("[iotc] connected")
    return client_ref


# ---------------- web pages ----------------

METER_MAX = 1.0  # softmax probability scale

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
  document.getElementById('n').textContent = s.prompts.length ? `(${s.prompts.length}/6)` : '';
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
<div class="meter"><div id="fill" style="width:0%"></div><div class="thr" id="thr" style="left:80%"></div></div>
<script>
const MAX = 1.0;
const EMOJI = [
 [/wav/i,'\\uD83D\\uDC4B'], [/thumb/i,'\\uD83D\\uDC4D'], [/hands.*(rais|up)|rais.*hand/i,'\\uD83D\\uDE4C'],
 [/phone/i,'\\uD83D\\uDCF1'], [/drink|cup|coffee/i,'\\u2615'], [/safety glass|goggle/i,'\\uD83E\\uDD7D'],
 [/sunglass|glasses/i,'\\uD83D\\uDC53'], [/hard ?hat|helmet/i,'\\u26D1\\uFE0F'], [/hat|cap\\b/i,'\\uD83E\\uDDE2'],
 [/peace/i,'\\u270C\\uFE0F'], [/vest|visibility/i,'\\uD83E\\uDDBA'], [/toolbox|tool/i,'\\uD83E\\uDDF0'],
 [/box|package|cardboard/i,'\\uD83D\\uDCE6'], [/empty|nobody|no one/i,'\\uD83D\\uDEAB'],
 [/crowd|people/i,'\\uD83D\\uDC65'], [/fire|burn|explod/i,'\\uD83D\\uDD25'], [/car\\b/i,'\\uD83D\\uDE97'],
 [/water|gush/i,'\\uD83D\\uDCA7'], [/fight|confront|violen|punch|kick/i,'\\uD83E\\uDD4A'],
 [/person|someone|worker/i,'\\uD83E\\uDDCD'],
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
  document.getElementById('fill').style.width = Math.min(100, Math.max(0,tv)/MAX*100) + '%';
  document.getElementById('thr').style.left = Math.min(100, s.threshold/MAX*100) + '%';
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

BOOTH_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Ask the Camera (Hailo)</title>""" + PAGE_STYLE + """</head><body>
<div style="display:flex;flex-wrap:wrap;gap:16px">
 <div style="flex:2;min-width:320px"><img style="max-width:100%;border-radius:8px" src="/stream.mjpg"></div>
 <div style="flex:1;min-width:260px"><h1>LIVE SCORES</h1>
  <div id="scores"></div><div class="muted" id="meta" style="font-size:13px;margin-top:10px"></div>
  <div class="muted" id="cmds" style="font-size:13px;border-top:1px solid #2c2c2a;padding-top:6px;margin-top:6px"></div></div>
</div><script>
async function tick(){
 try{
  const s = await (await fetch('/state.json')).json();
  document.getElementById('scores').innerHTML = s.prompts.map((p,i)=>{
   const sc = s.scores[i]||0, hot = sc>=s.threshold;
   return `<p class="p">${hot?'&#9679; ':''}${p} <span class="muted">${sc.toFixed(3)}</span></p>
    <div class="bar"><div class="${hot?'hot':''}" style="width:${Math.min(100,sc*100)}%"></div></div>`;
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
                prompts, scores, threshold = snapshot_matcher()
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
                            frame = STATE.frame
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
    print("[web] serving booth pages on port %d" % port)
    return srv


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--serve", type=int, default=8080)
    args, passthrough = ap.parse_known_args()

    # hand remaining args (e.g. --input /dev/video0) to the hailo app parser
    sys.argv = [sys.argv[0]] + passthrough + ["--use-frame"]

    client_ref = start_iotc()
    if args.serve:
        start_web(args.serve)
    threading.Thread(target=telemetry_loop, args=(client_ref,), daemon=True).start()

    user_data = app_callback_class()
    app = GStreamerClipApp(app_callback, user_data)
    app.run()


if __name__ == "__main__":
    main()
