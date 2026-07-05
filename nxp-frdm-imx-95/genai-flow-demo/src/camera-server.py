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
        print("ERROR: cannot open camera index", idx, flush=True)
        sys.exit(1)
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


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/live"):
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
