#!/usr/bin/env python3
"""Browser-based camera-gripper offset + grab-radius calibrator.

Same job as calibrate_cam_offset.py but rendered as MJPEG + a small HTML
page so it works on the RZ/G3E (no display server, opencv-python-headless).
Workflow:

  1. SUPPORT THE ARM — all torque drops on launch.
  2. Open http://<board-ip>:<port>/ in a browser.
  3. Pose the gripper directly over the ball at the height it would normally
     grab from. The live overlay shows the detected ball, its (bx, by, r),
     and the resulting OFFSET_X / OFFSET_Y.
  4. Hold steady, click "Snapshot". The script averages the last ~30 frames
     and prints recommended values for:
        CAM_GRIPPER_OFFSET_X
        CAM_GRIPPER_OFFSET_Y
        TARGET_RADIUS_PX        <-- the ball's apparent radius at grab dist
     Paste these into modes/ball_follow.py.
  5. "Hold pose" re-engages torque. "Release torque" drops it again.
"""

import argparse
import json
import os
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import xarm

HERE = os.path.dirname(os.path.abspath(__file__))
HSV_PATH = os.path.join(HERE, "ball_color.json")

# Match ball_follow.py detection params so what we measure matches what it sees.
MIN_CONTOUR_AREA = 200
MIN_FILL_RATIO = 0.65
SAMPLE_WINDOW = 30
ALL_SERVO_IDS = [1, 2, 3, 4, 5, 6]


def _median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        raise ValueError("median of empty sequence")
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _pstdev(values):
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5


def largest_blob(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_CONTOUR_AREA or area <= best_area:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        if r <= 0:
            continue
        if area / (np.pi * r * r) < MIN_FILL_RATIO:
            continue
        best = (int(x), int(y), float(r))
        best_area = area
    return best


# ---------------------------- shared state ----------------------------

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame_jpeg = b""
        self.frame_w = 0
        self.frame_h = 0
        self.bx = self.by = self.br = None      # latest detection
        self.recent = deque(maxlen=SAMPLE_WINDOW)  # (bx, by, br)
        self.last_snapshot = None               # dict shown on the page
        self.quit = False


# ---------------------------- camera loop -----------------------------

def camera_loop(state, camera_index, width, height, lower, upper, jpeg_quality=80):
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
            h, w = frame.shape[:2]

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

            ball = largest_blob(mask)

            # Annotate. Mirror horizontally so what the user sees matches
            # how ball_follow displays the wrist camera.
            annotated = cv2.flip(frame, 1)
            cx, cy = w // 2, h // 2
            cv2.drawMarker(annotated, (cx, cy), (255, 255, 255),
                           markerType=cv2.MARKER_CROSS, markerSize=20, thickness=1)

            with state.lock:
                state.frame_w, state.frame_h = w, h
                if ball is not None:
                    bx, by, br = ball
                    state.bx, state.by, state.br = bx, by, br
                    state.recent.append((bx, by, br))
                    dx = bx - cx
                    dy = by - cy
                    bx_disp = w - bx
                    cv2.circle(annotated, (bx_disp, by), int(br), (0, 255, 0), 2)
                    cv2.circle(annotated, (bx_disp, by), 4, (0, 255, 0), -1)
                    cv2.putText(annotated, f"bx={bx} by={by} r={int(br)}",
                                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(annotated,
                                f"OFFSET_X={dx:+d}  OFFSET_Y={dy:+d}",
                                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 255), 2, cv2.LINE_AA)
                    cv2.putText(annotated,
                                f"samples={len(state.recent)}/{SAMPLE_WINDOW}",
                                (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (200, 200, 200), 1, cv2.LINE_AA)
                else:
                    state.bx = state.by = state.br = None
                    cv2.putText(annotated, "no ball detected", (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 0, 255), 2, cv2.LINE_AA)

                ok2, buf = cv2.imencode(".jpg", annotated, enc_params)
                if ok2:
                    state.frame_jpeg = buf.tobytes()
    finally:
        cap.release()
        print("[calib] camera released")


# ---------------------------- HTTP plumbing ---------------------------

INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Cam-Gripper Offset Calibrator</title>
<style>
  body { font: 14px sans-serif; margin: 1em; background: #111; color: #eee; }
  #wrap { display: flex; gap: 1em; flex-wrap: wrap; }
  #stream { display: block; max-width: 100%; }
  #panel { min-width: 320px; }
  button { margin: 0.2em 0.4em 0.2em 0; padding: 0.5em 0.9em; font-size: 14px; cursor: pointer; }
  pre { background: #222; padding: 0.6em; border-radius: 4px; max-height: 360px; overflow: auto; white-space: pre-wrap; }
  .hi { color: #6cf; }
</style></head>
<body>
<h2>Camera-gripper offset + grab-radius calibrator</h2>
<div id="wrap">
  <div>
    <img id="stream" src="/stream" alt="(camera stream)">
    <p>Pose the gripper directly above the ball at the height it would normally grab from. Hold steady, click <b>Snapshot</b>.</p>
  </div>
  <div id="panel">
    <div>
      <button id="snap">Snapshot (s)</button>
      <button id="hold">Hold pose (h)</button>
      <button id="release">Release torque (r)</button>
      <button id="quit">Quit</button>
    </div>
    <p id="status">live: (no ball)</p>
    <pre id="result">(no snapshot yet)</pre>
  </div>
</div>
<script>
const status = document.getElementById('status');
const result = document.getElementById('result');

async function action(path) {
  const r = await fetch(path, {method: 'POST'});
  const d = await r.json();
  refresh(d);
}
document.getElementById('snap').onclick    = () => action('/snapshot');
document.getElementById('hold').onclick    = () => action('/hold');
document.getElementById('release').onclick = () => action('/release');
document.getElementById('quit').onclick    = () => { if (confirm('Quit?')) action('/quit'); };

document.addEventListener('keydown', (ev) => {
  if (ev.target.tagName === 'INPUT') return;
  if (ev.key === 's') action('/snapshot');
  if (ev.key === 'h') action('/hold');
  if (ev.key === 'r') action('/release');
});

function refresh(data) {
  if (!data) return;
  if (data.live) {
    if (data.live.bx === null) {
      status.textContent = `live: no ball  (samples ${data.live.samples}/${data.live.sample_window})`;
    } else {
      status.textContent = `live: bx=${data.live.bx} by=${data.live.by} r=${data.live.br}`
        + `  OFFSET_X=${data.live.off_x>=0?'+':''}${data.live.off_x}`
        + `  OFFSET_Y=${data.live.off_y>=0?'+':''}${data.live.off_y}`
        + `  (samples ${data.live.samples}/${data.live.sample_window})`;
    }
  }
  if (data.snapshot) result.textContent = data.snapshot;
  if (data.message) result.textContent = data.message + '\\n\\n' + result.textContent;
}

setInterval(async () => {
  try { refresh(await (await fetch('/state')).json()); } catch(e) {}
}, 500);
</script>
</body></html>
"""


def _live_view(state):
    with state.lock:
        bx, by, br = state.bx, state.by, state.br
        w, h = state.frame_w, state.frame_h
        n = len(state.recent)
    if not w or not h:
        return None
    cx, cy = w // 2, h // 2
    if bx is None:
        return {"bx": None, "by": None, "br": None,
                "off_x": 0, "off_y": 0,
                "samples": n, "sample_window": SAMPLE_WINDOW}
    return {"bx": int(bx), "by": int(by), "br": int(br),
            "off_x": int(bx - cx), "off_y": int(by - cy),
            "samples": n, "sample_window": SAMPLE_WINDOW}


def _state_payload(state, message=None, snapshot_text=None):
    payload = {"live": _live_view(state)}
    with state.lock:
        last = state.last_snapshot
    if snapshot_text is not None:
        payload["snapshot"] = snapshot_text
    elif last is not None:
        payload["snapshot"] = last
    if message is not None:
        payload["message"] = message
    return payload


def _do_snapshot(state):
    with state.lock:
        samples = list(state.recent)
        w, h = state.frame_w, state.frame_h
    if len(samples) < 5:
        return f"not enough samples yet ({len(samples)}/5) — make sure ball is visible and steady"

    xs = [p[0] for p in samples]
    ys = [p[1] for p in samples]
    rs = [p[2] for p in samples]
    bx_med = int(_median(xs))
    by_med = int(_median(ys))
    r_med = float(_median(rs))
    cx, cy = w // 2, h // 2
    off_x = bx_med - cx
    off_y = by_med - cy
    bx_std = _pstdev(xs)
    by_std = _pstdev(ys)
    r_std = _pstdev(rs)

    text = (
        f"=== averaged over last {len(samples)} frames ===\n"
        f"bx = {bx_med}  (std {bx_std:.1f})\n"
        f"by = {by_med}  (std {by_std:.1f})\n"
        f"r  = {r_med:.1f}  (std {r_std:.1f})\n"
        f"image center = ({cx}, {cy})\n\n"
        f"--- paste into modes/ball_follow.py ---\n"
        f"CAM_GRIPPER_OFFSET_X = {off_x}\n"
        f"CAM_GRIPPER_OFFSET_Y = {off_y}\n"
        f"TARGET_RADIUS_PX     = {int(round(r_med))}\n"
        f"# leave RADIUS_TOLERANCE roughly +/-{max(15, int(round(r_std * 3)))} for a safe margin\n"
    )
    with state.lock:
        state.last_snapshot = text
    print()
    print(text)
    return text


def make_handler(state, arm):

    class Handler(BaseHTTPRequestHandler):
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
            if self.path in ("/", "/index.html"):
                body = INDEX_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/state":
                self._json(_state_payload(state))
                return
            if self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=FRAME")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                last = None
                try:
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
            if self.path == "/snapshot":
                text = _do_snapshot(state)
                self._json(_state_payload(state, snapshot_text=text))
                return
            if self.path == "/hold":
                if arm is None:
                    self._json(_state_payload(state, message="--no-arm: hold ignored"))
                    return
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
                if arm is None:
                    self._json(_state_payload(state, message="--no-arm: release ignored"))
                    return
                try:
                    arm.servoOff()
                    msg = "ALL torque OFF — pose the gripper over the ball"
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
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "0.0.0.0"


def main():
    parser = argparse.ArgumentParser(description="Browser cam-gripper offset calibrator")
    parser.add_argument("--camera", type=int, default=0,
                        help="OpenCV camera index (default 0 — RZ/G3E /dev/video0)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--port", type=int, default=8000, help="HTTP listen port")
    parser.add_argument("--no-arm", action="store_true",
                        help="Skip xArm connection (camera-only test mode)")
    args = parser.parse_args()

    if not os.path.exists(HSV_PATH):
        print(f"[calib] ERROR: {HSV_PATH} not found — run ball_calibrate.py first", file=sys.stderr)
        return 1
    with open(HSV_PATH) as f:
        cfg = json.load(f)
    lower = np.array([cfg["h_min"], cfg["s_min"], cfg["v_min"]], dtype=np.uint8)
    upper = np.array([cfg["h_max"], cfg["s_max"], cfg["v_max"]], dtype=np.uint8)
    print(f"[calib] HSV range: lower={lower.tolist()} upper={upper.tolist()}")

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
            print("[calib] torque OFF — pose the gripper directly over the ball.")
        except Exception as e:
            print(f"[calib] servoOff failed: {e}")
    else:
        print("[calib] --no-arm: running camera-only (no torque control)")

    state = State()
    cam_thread = threading.Thread(
        target=camera_loop,
        args=(state, args.camera, args.width, args.height, lower, upper),
        daemon=True,
    )
    cam_thread.start()

    handler = make_handler(state, arm)
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
