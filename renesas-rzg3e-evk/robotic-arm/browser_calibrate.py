#!/usr/bin/env python3
"""Browser-based ball-color HSV calibrator.

Same output as ball_calibrate.py (writes ball_color.json), but the live
preview is served as MJPEG over HTTP and clicks come from a web page,
not a cv2 window. Built for the RZ/G3E where there's no display server
and we use opencv-python-headless (no cv2.imshow).

Open http://<board-ip>:8000/ in any browser on the same LAN, click the
ball, hit "Save".

Camera-angle helper: at startup the script prompts before releasing all
servo torque so you can free-pose the arm. SUPPORT THE ARM before
pressing Enter — it will swing under gravity. Use the "Hold pose" /
"Release torque" buttons in the page to re-engage / drop torque after
that.
"""

import argparse
import io
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np
import xarm

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ball_color.json")
PATCH_RADIUS = 3      # 7x7 sample patch around each click
HUE_PAD = 8
SAT_PAD = 25
VAL_PAD = 25
ALL_SERVO_IDS = [1, 2, 3, 4, 5, 6]


# ---------------------------- shared state ----------------------------

class State:
    """Thread-safe container for everything the camera thread produces and
    the HTTP handlers consume / mutate."""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame_jpeg = b""             # most recent annotated JPEG
        self.frame_w = 0
        self.frame_h = 0
        self.hsv = None                   # raw HSV frame for click sampling
        self.samples = []                 # list of (h, s, v) median tuples
        self.saved_at = None              # set by /save
        self.quit = False                 # set when user clicks Quit


def current_range(samples):
    if not samples:
        return None
    arr = np.array(samples)
    h_lo, h_hi = arr[:, 0].min() - HUE_PAD, arr[:, 0].max() + HUE_PAD
    s_lo, s_hi = arr[:, 1].min() - SAT_PAD, arr[:, 1].max() + SAT_PAD
    v_lo, v_hi = arr[:, 2].min() - VAL_PAD, arr[:, 2].max() + VAL_PAD
    lower = np.array([max(0, h_lo), max(0, s_lo), max(0, v_lo)], dtype=np.uint8)
    upper = np.array([min(180, h_hi), min(255, s_hi), min(255, v_hi)], dtype=np.uint8)
    return lower, upper


# ---------------------------- camera worker ---------------------------

def camera_loop(state, camera_index, width, height, jpeg_quality=80):
    """Continuously read camera frames, build the annotated overlay, and
    publish the JPEG-encoded frame to State for any active MJPEG client."""
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        print(f"[calib] ERROR: could not open camera {camera_index}", file=sys.stderr)
        state.quit = True
        return

    print(f"[calib] camera {camera_index} opened ({width}x{height})")
    enc_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]

    try:
        while not state.quit:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            with state.lock:
                samples_snapshot = list(state.samples)

            rng = current_range(samples_snapshot)
            if rng is not None:
                lower, upper = rng
                mask = cv2.inRange(hsv, lower, upper)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
                overlay = frame.copy()
                overlay[mask > 0] = (0, 255, 0)
                display = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
                label = (f"samples={len(samples_snapshot)} "
                         f"H[{lower[0]}-{upper[0]}] S[{lower[1]}-{upper[1]}] V[{lower[2]}-{upper[2]}]")
            else:
                display = frame.copy()
                label = "click the ball..."
            cv2.putText(display, label, (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            ok, buf = cv2.imencode(".jpg", display, enc_params)
            if not ok:
                continue
            jpeg = buf.tobytes()
            h, w = display.shape[:2]
            with state.lock:
                state.frame_jpeg = jpeg
                state.hsv = hsv
                state.frame_w = w
                state.frame_h = h
    finally:
        cap.release()
        print("[calib] camera released")


# ---------------------------- HTTP handlers ---------------------------

INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Ball Calibrator</title>
<style>
  body { font: 14px sans-serif; margin: 1em; background: #111; color: #eee; }
  #wrap { display: flex; gap: 1em; flex-wrap: wrap; }
  #stream { display: block; cursor: crosshair; max-width: 100%; }
  #panel { min-width: 280px; }
  button { margin: 0.2em 0.4em 0.2em 0; padding: 0.5em 0.9em; font-size: 14px; cursor: pointer; }
  pre { background: #222; padding: 0.6em; border-radius: 4px; max-height: 300px; overflow: auto; }
  .sav { color: #6f6; }
  .err { color: #f66; }
</style></head>
<body>
<h2>Ball-color HSV calibrator (RZ/G3E)</h2>
<div id="wrap">
  <div>
    <img id="stream" src="/stream" alt="(camera stream)">
    <p>Click the ball in the image. Each click samples a 7x7 HSV patch.</p>
  </div>
  <div id="panel">
    <div>
      <button id="savequit" style="background:#2a7;color:white;font-weight:bold;">Save &amp; Quit</button>
      <button id="save">Save (s)</button>
      <button id="reset">Reset (r)</button>
      <button id="hold">Hold pose (h)</button>
      <button id="release">Release torque (w)</button>
      <button id="quit">Quit</button>
    </div>
    <p id="status">samples: 0</p>
    <pre id="log">(no clicks yet)</pre>
  </div>
</div>
<script>
const img = document.getElementById('stream');
const status = document.getElementById('status');
const log = document.getElementById('log');

img.addEventListener('click', async (ev) => {
  const r = img.getBoundingClientRect();
  // Convert displayed-pixel click into the natural image coordinate.
  const sx = img.naturalWidth / r.width;
  const sy = img.naturalHeight / r.height;
  const x = Math.round((ev.clientX - r.left) * sx);
  const y = Math.round((ev.clientY - r.top) * sy);
  const res = await fetch('/click', {method: 'POST', body: JSON.stringify({x, y})});
  const data = await res.json();
  // A new sample makes the on-disk file stale.
  saved = false;
  refresh(data);
});

async function action(path) {
  const res = await fetch(path, {method: 'POST'});
  const data = await res.json();
  // Reset clears in-memory samples — the on-disk file (if any) is now stale.
  if (path === '/reset') saved = false;
  refresh(data);
  if (data.message) log.textContent = data.message + '\\n' + log.textContent;
}

// Tracks whether the most recently sampled state has been written to disk.
// Cleared on /reset and on every new click (since a new sample makes the
// on-disk file stale relative to current samples).
let saved = false;

async function saveAndQuit() {
  const r = await fetch('/save', {method: 'POST'});
  const d = await r.json();
  refresh(d);
  if (d.saved) action('/quit');
}

document.getElementById('savequit').onclick = saveAndQuit;
document.getElementById('save').onclick    = () => action('/save');
document.getElementById('reset').onclick   = () => action('/reset');
document.getElementById('hold').onclick    = () => action('/hold');
document.getElementById('release').onclick = () => action('/release');
document.getElementById('quit').onclick    = () => {
  const msg = saved ? 'Quit?' : 'You have unsaved samples. Quit anyway?';
  if (confirm(msg)) action('/quit');
};

document.addEventListener('keydown', (ev) => {
  if (ev.target.tagName === 'INPUT') return;
  if (ev.key === 's') action('/save');
  if (ev.key === 'r') action('/reset');
  if (ev.key === 'h') action('/hold');
  if (ev.key === 'w') action('/release');
});

function refresh(data) {
  if (!data) return;
  let s = `samples: ${data.count}`;
  if (data.range) s += `  HSV [${data.range.lower}] - [${data.range.upper}]`;
  if (data.saved) {
    s += `  <span class="sav">SAVED -> ${data.saved}</span>`;
    saved = true;
  }
  status.innerHTML = s;
  if (data.samples_log) log.textContent = data.samples_log;
}

// Poll status every second so external state changes (CLI quit, errors) are visible.
setInterval(async () => {
  try { refresh(await (await fetch('/state')).json()); } catch(e) {}
}, 1000);
</script>
</body></html>
"""


def _sample_at(state, x, y):
    """Sample a 7x7 HSV patch around (x, y) and append the median to samples."""
    with state.lock:
        if state.hsv is None:
            return None
        h, w = state.hsv.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None
        x0, x1 = max(0, x - PATCH_RADIUS), min(w, x + PATCH_RADIUS + 1)
        y0, y1 = max(0, y - PATCH_RADIUS), min(h, y + PATCH_RADIUS + 1)
        patch = state.hsv[y0:y1, x0:x1].reshape(-1, 3)
        med = np.median(patch, axis=0).astype(int)
        sample = tuple(int(v) for v in med.tolist())
        state.samples.append(sample)
        return sample


def _state_payload(state, message=None, saved=None):
    with state.lock:
        samples = list(state.samples)
    rng = current_range(samples)
    payload = {"count": len(samples)}
    if rng is not None:
        lo, hi = rng
        payload["range"] = {"lower": lo.tolist(), "upper": hi.tolist()}
    if message is not None:
        payload["message"] = message
    if saved is not None:
        payload["saved"] = saved
    payload["samples_log"] = "\n".join(
        f"#{i + 1}: H={s[0]} S={s[1]} V={s[2]}" for i, s in enumerate(samples)
    ) or "(no clicks yet)"
    return payload


def make_handler(state, arm, camera_index):

    class Handler(BaseHTTPRequestHandler):
        # Quiet the default access log — too noisy for an MJPEG stream.
        def log_message(self, fmt, *args):
            return

        def _json(self, payload, code=200):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                body = INDEX_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if url.path == "/state":
                self._json(_state_payload(state))
                return

            if url.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=FRAME")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                try:
                    last = None
                    while not state.quit:
                        with state.lock:
                            buf = state.frame_jpeg
                        if buf and buf is not last:
                            self.wfile.write(b"--FRAME\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(
                                f"Content-Length: {len(buf)}\r\n\r\n".encode())
                            self.wfile.write(buf)
                            self.wfile.write(b"\r\n")
                            last = buf
                        time.sleep(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""

            if self.path == "/click":
                try:
                    data = json.loads(raw or b"{}")
                    x = int(data.get("x"))
                    y = int(data.get("y"))
                except (ValueError, TypeError):
                    self._json({"error": "bad coords"}, code=400)
                    return
                sample = _sample_at(state, x, y)
                msg = (f"click @({x},{y}) -> H={sample[0]} S={sample[1]} V={sample[2]}"
                       if sample else f"click @({x},{y}) -> out of bounds")
                print(f"[calib] {msg}")
                self._json(_state_payload(state, message=msg))
                return

            if self.path == "/reset":
                with state.lock:
                    state.samples.clear()
                print("[calib] samples reset")
                self._json(_state_payload(state, message="samples reset"))
                return

            if self.path == "/save":
                with state.lock:
                    samples_copy = list(state.samples)
                rng = current_range(samples_copy)
                if rng is None:
                    self._json(_state_payload(
                        state, message="nothing to save — click the ball first"))
                    return
                lower, upper = rng
                payload = {
                    "camera_index": int(camera_index),
                    "h_min": int(lower[0]), "h_max": int(upper[0]),
                    "s_min": int(lower[1]), "s_max": int(upper[1]),
                    "v_min": int(lower[2]), "v_max": int(upper[2]),
                    "samples": [list(s) for s in samples_copy],
                }
                with open(OUT_PATH, "w") as f:
                    json.dump(payload, f, indent=2)
                print(f"[calib] SAVED {len(samples_copy)} samples to {OUT_PATH}")
                print(f"  HSV lower: {lower.tolist()}")
                print(f"  HSV upper: {upper.tolist()}")
                self._json(_state_payload(
                    state, message=f"saved {len(samples_copy)} samples", saved=OUT_PATH))
                return

            if self.path == "/hold":
                try:
                    targets = [[sid, int(arm.getPosition(sid))] for sid in ALL_SERVO_IDS]
                    arm.setPosition(targets, duration=1500, wait=True)
                    msg = "torque ON at current pose"
                except Exception as e:
                    msg = f"hold failed: {e}"
                print(f"[calib] {msg}")
                self._json(_state_payload(state, message=msg))
                return

            if self.path == "/release":
                try:
                    arm.servoOff()
                    msg = "ALL torque OFF — pose the arm by hand"
                except Exception as e:
                    msg = f"release failed: {e}"
                print(f"[calib] {msg}")
                self._json(_state_payload(state, message=msg))
                return

            if self.path == "/quit":
                state.quit = True
                self._json(_state_payload(state, message="exiting"))
                return

            self.send_response(404)
            self.end_headers()

    return Handler


def _local_ip_hint():
    """Best-effort guess at the LAN IP to print in the URL hint."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "0.0.0.0"


def main():
    parser = argparse.ArgumentParser(description="Browser HSV ball-color calibrator")
    parser.add_argument("--camera", type=int, default=0,
                        help="OpenCV camera index (default 0 — RZ/G3E /dev/video0)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--port", type=int, default=8000, help="HTTP listen port")
    parser.add_argument("--no-arm", action="store_true",
                        help="Skip xArm connection (camera-only test mode)")
    args = parser.parse_args()

    arm = None
    if not args.no_arm:
        print("[calib] connecting to xArm...")
        arm = xarm.Controller("USB")
        print("\n" + "=" * 60)
        print(" SAFETY: ALL torque is about to drop. Support the arm with your")
        print(" hand before pressing Enter, or it will swing under gravity.")
        print("=" * 60)
        input("[calib] Holding the arm? Press Enter to release torque... ")
        try:
            arm.servoOff()
            print("[calib] ALL torque OFF — pose the arm by hand.")
        except Exception as e:
            print(f"[calib] servoOff failed: {e}")
    else:
        print("[calib] --no-arm: running camera-only (no torque control)")

    state = State()
    cam_thread = threading.Thread(
        target=camera_loop,
        args=(state, args.camera, args.width, args.height),
        daemon=True,
    )
    cam_thread.start()

    handler = make_handler(state, arm, args.camera)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"\n[calib] HTTP listening on http://{_local_ip_hint()}:{args.port}/  (Ctrl-C to quit)")

    try:
        while not state.quit:
            server.handle_request()
    except KeyboardInterrupt:
        print("\n[calib] interrupted")
    finally:
        state.quit = True
        cam_thread.join(timeout=2.0)
        if arm is not None:
            try:
                targets = [[sid, int(arm.getPosition(sid))] for sid in ALL_SERVO_IDS]
                arm.setPosition(targets, duration=1500, wait=True)
                print("[calib] re-engaged torque at current pose on exit")
            except Exception as e:
                print(f"[calib] final hold failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
