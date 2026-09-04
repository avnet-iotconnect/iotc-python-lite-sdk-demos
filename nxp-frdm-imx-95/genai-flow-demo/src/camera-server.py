# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Michael Lamp <michael@lamptribe.com> et al.
#
# Lightweight HTTPS MJPEG camera server for the FRDM i.MX 95 GenAI demo.
# Lets the /IOTCONNECT dashboard's "Embedded" widget show live video from the
# board:   https://<board-ip>:8080/live
#
# It also writes the latest frame to /tmp/camera-latest.jpg so the demo app's
# ask-vlm command can reuse it instead of competing for the camera device.
#
# Run:  nohup python3 camera-server.py > /opt/demo/camera.log 2>&1 &
# Stop: pkill -f 'camera-server'
#
# NOTE: uses a self-signed certificate (generated on first run). Browsers must
# trust it once: open https://<board-ip>:8080 directly and accept the warning,
# after which the dashboard's embedded view works.

import glob
import http.server
import json
import os
import re
import signal
import ssl
import subprocess
import sys
import threading
import time

import cv2

CONFIG_PATH = "/opt/demo/genai-config.json"
CERT = "/opt/demo/web-cert.pem"
KEY = "/opt/demo/web-key.pem"
SHARED_FRAME = "/tmp/camera-latest.jpg"
PORT = int(os.environ.get("CAMERA_PORT", "8080"))
WIDTH, HEIGHT, FPS, JPEG_QUALITY = 960, 540, 10, 70


def camera_index():
    try:
        import json
        dev = json.load(open(CONFIG_PATH)).get("camera_device", "auto")
    except Exception:
        dev = "auto"
    # V4L2 indexes are not stable across reboots - "auto" resolves the first
    # USB camera via its persistent udev path.
    if dev == "auto" or not os.path.exists(dev):
        links = sorted(glob.glob("/dev/v4l/by-id/usb-*-video-index0"))
        if links:
            dev = os.path.realpath(links[0])
    m = re.search(r"(\d+)$", dev)
    return int(m.group(1)) if m else 0


def ensure_cert():
    if not (os.path.isfile(CERT) and os.path.isfile(KEY)):
        subprocess.run(
            ["openssl", "req", "-x509", "-nodes", "-days", "3650",
             "-newkey", "rsa:2048", "-keyout", KEY, "-out", CERT,
             "-subj", "/CN=frdm-imx95-camera"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Generated self-signed certificate", flush=True)


latest = {"jpeg": None, "t": 0.0}
cond = threading.Condition()


def capture_loop():
    idx = camera_index()
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    if not cap.isOpened():
        print("WARNING: cannot open camera index %d - /live disabled, /responses still served" % idx,
              flush=True)
        return
    print("Camera %d open at %dx%d" % (idx, WIDTH, HEIGHT), flush=True)
    last_shared = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.5)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            continue
        data = buf.tobytes()
        with cond:
            latest["jpeg"], latest["t"] = data, time.time()
            cond.notify_all()
        # share a frame for ask-vlm every second (atomic rename)
        if time.time() - last_shared > 1.0:
            try:
                with open(SHARED_FRAME + ".tmp", "wb") as f:
                    f.write(data)
                os.replace(SHARED_FRAME + ".tmp", SHARED_FRAME)
                last_shared = time.time()
            except OSError:
                pass


STATE_PATH = "/tmp/genai-state.json"
LOCAL_CMD_SPOOL = "/tmp/genai-cmd"   # app.py's local_command_watcher consumes this

RESPONSES_HTML = b"""<!DOCTYPE html>
<html><head><title>FRDM i.MX 95 - GenAI Responses</title><meta charset="utf-8">
<style>
 body{margin:0;padding:84px 14px 14px;background:#10151c;color:#e8edf2;font-family:'Segoe UI',Roboto,sans-serif}
 .grid{display:grid;grid-template-columns:1fr;gap:12px}
 .card{background:#171e26;border-radius:10px;padding:12px 16px;border-left:5px solid #41C363;min-height:70px}
 .card h2{margin:0 0 6px;font-size:15px;color:#8fd9a8;text-transform:uppercase;letter-spacing:1px}
 .q{color:#9aa7b4;font-size:14px;margin:2px 0}
 .a{font-size:17px;line-height:1.45;margin:4px 0;white-space:pre-wrap}
 .meta{color:#5d6b7a;font-size:12px;margin-top:6px}
 .badges{margin-bottom:12px}
 .badge{display:inline-block;background:#20342a;border-radius:14px;padding:4px 14px;margin-right:8px;font-size:14px}
 .badge b{color:#7ed321}
 .agent{border-left-color:#7ed321}.vlm{border-left-color:#f5a623}.voice{border-left-color:#bd10e0}

 .brandbar{display:flex;align-items:center;gap:12px;padding:2px 0 15px;margin-bottom:18px;border-bottom:1px solid var(--line)}
 .brandmark{height:25px;width:auto;display:block}
 .brandbar .tag{color:var(--dim);font-size:.85rem;font-weight:600;letter-spacing:.2px}
</style></head><body>
<div class="brandbar"><img class="brandmark" src="data:image/png;base64,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" alt="/IOTCONNECT"><span class="tag">FRDM i.MX 95 &middot; GenAI Responses</span></div>

<div class="badges" id="badges"></div>
<div class="grid">
 <div class="card"><h2>LLM Answer</h2><div class="q" id="llm_q"></div><div class="a" id="llm_a"></div><div class="meta" id="llm_m"></div></div>
 <div class="card vlm"><h2>Vision: What the Camera Sees</h2><div class="q" id="vlm_q"></div><div class="a" id="vlm_a"></div><div class="meta" id="vlm_m"></div></div>
 <div class="card voice"><h2>Voice Assistant</h2><div class="q" id="v_q"></div><div class="a" id="v_a"></div><div class="meta" id="v_m"></div></div>
 <div class="card agent"><h2>Agent: Real Board Data</h2><div class="q" id="a_q"></div><div class="a" id="a_a"></div><div class="meta" id="a_m"></div></div>
</div>
<script>
async function tick(){
 try{
  const r = await fetch('/state.json', {cache:'no-store'});
  const s = await r.json();
  const set = (id, txt) => document.getElementById(id).textContent = txt || '';
  document.getElementById('badges').innerHTML =
   `<span class=badge>status <b>${s.genai_status}</b></span>`+
   `<span class=badge>model <b>${s.llm_model}</b></span>`+
   `<span class=badge>backend <b>${s.llm_backend}</b></span>`+
   `<span class=badge>RAG <b>${s.llm_rag}</b></span>`+
   `<span class=badge>voice <b>${s.voice_status}</b></span>`+
   `<span class=badge>stt <b>${s.voice_stt}</b></span>`+
   `<span class=badge>vlm <b>${s.vlm_model}</b></span>`+
   `<span class=badge>agent <b>${s.agent_status}</b></span>`;
  set('llm_q', s.llm_prompt && 'Q: '+s.llm_prompt); set('llm_a', s.llm_response);
  set('llm_m', s.llm_tps ? `${s.llm_tps} tok/s | TTFT ${s.llm_ttft}s | ${s.llm_token_count} tokens` : '');
  set('vlm_q', s.vlm_question && 'Q: '+s.vlm_question); set('vlm_a', s.vlm_response);
  set('vlm_m', s.vlm_tps ? `vision ${s.vlm_vision_time}s | ${s.vlm_tps} tok/s` : '');
  set('v_q', s.voice_question && 'Heard: '+s.voice_question); set('v_a', s.voice_response);
  set('v_m', s.voice_exchanges ? `${s.voice_exchanges} exchanges this session` : '');
  set('a_q', s.agent_request && 'Q: '+s.agent_request); set('a_a', s.agent_response);
  set('a_m', s.agent_tool ? `tool ${s.agent_tool} -> ${s.agent_tool_result} (router: ${s.agent_router})` : '');
 }catch(e){}
}
tick(); setInterval(tick, 2000);
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, data, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        # CORS preflight for the cockpit's cross-origin POST /command
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        # Local (LAN) command injection: the cockpit, when direct-connected and
        # in "direct" mode, POSTs {cmd, token} here to skip the slow cloud C2D
        # path. The token must match the one app.py publishes in state.json
        # (same-LAN reachability gating, not hardened auth). The command line is
        # spooled for app.py's local_command_watcher to dispatch.
        if not self.path.startswith("/command"):
            self._send(b'{"ok":false,"error":"not found"}', "application/json", 404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            body = {}
        cmd = str(body.get("cmd", "")).strip()
        token = str(body.get("token", ""))
        try:
            want = json.load(open(STATE_PATH)).get("cmd_token", "")
        except (OSError, ValueError):
            want = ""
        if not cmd or not want or token != want:
            self._send(b'{"ok":false,"error":"unauthorized or empty"}', "application/json", 403)
            return
        try:
            os.makedirs(LOCAL_CMD_SPOOL, exist_ok=True)
            path = os.path.join(LOCAL_CMD_SPOOL, "%d.cmd" % time.time_ns())
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                f.write(cmd)
            os.replace(path + ".tmp", path)
        except OSError:
            self._send(b'{"ok":false,"error":"spool"}', "application/json", 500)
            return
        self._send(b'{"ok":true}', "application/json")

    def do_GET(self):
        if self.path.startswith("/responses"):
            self._send(RESPONSES_HTML, "text/html")
        elif self.path.startswith("/state.json"):
            try:
                with open(STATE_PATH, "rb") as f:
                    self._send(f.read(), "application/json")
            except OSError:
                self._send(b"{}", "application/json")
        elif self.path.startswith("/live"):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            try:
                while True:
                    with cond:
                        cond.wait(timeout=5)
                        data = latest["jpeg"]
                    if data is None:
                        continue
                    self.wfile.write(b"--FRAME\r\nContent-Type: image/jpeg\r\n"
                                     + b"Content-Length: %d\r\n\r\n" % len(data))
                    self.wfile.write(data)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                return
        elif self.path.startswith("/snapshot"):
            data = latest["jpeg"] or b""
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            body = (b"<html><head><title>FRDM i.MX 95 Camera</title></head>"
                    b"<body style='margin:0;background:#000'>"
                    b"<img src='/live' style='width:100%'></body></html>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main():
    ensure_cert()
    threading.Thread(target=capture_loop, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print("Camera server on https://0.0.0.0:%d (/live, /snapshot)" % PORT, flush=True)
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    server.serve_forever()


if __name__ == "__main__":
    main()
