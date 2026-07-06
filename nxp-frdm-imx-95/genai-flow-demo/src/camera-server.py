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

import http.server
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
        dev = json.load(open(CONFIG_PATH)).get("camera_device", "/dev/video52")
    except Exception:
        dev = "/dev/video52"
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

RESPONSES_HTML = b"""<!DOCTYPE html>
<html><head><title>FRDM i.MX 95 - GenAI Responses</title><meta charset="utf-8">
<style>
 body{margin:0;padding:48px 14px 14px;background:#10151c;color:#e8edf2;font-family:'Segoe UI',Roboto,sans-serif}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
 .card{background:#1a2230;border-radius:10px;padding:12px 16px;border-left:5px solid #4a90d9;min-height:70px}
 .card h2{margin:0 0 6px;font-size:15px;color:#7fb2e5;text-transform:uppercase;letter-spacing:1px}
 .q{color:#9aa7b4;font-size:14px;margin:2px 0}
 .a{font-size:17px;line-height:1.45;margin:4px 0;white-space:pre-wrap}
 .meta{color:#5d6b7a;font-size:12px;margin-top:6px}
 .badges{margin-bottom:12px}
 .badge{display:inline-block;background:#243247;border-radius:14px;padding:4px 14px;margin-right:8px;font-size:14px}
 .badge b{color:#7ed321}
 .agent{border-left-color:#7ed321}.vlm{border-left-color:#f5a623}.voice{border-left-color:#bd10e0}
</style></head><body>
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

    def _send(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
