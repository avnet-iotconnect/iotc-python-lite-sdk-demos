#!/usr/bin/env python3
"""Calibrate the camera-to-gripper pixel offset for ball_follow.

Why this exists: the wrist camera is mounted a few cm away from the gripper
fingers, so "ball at image center" does NOT mean "gripper over ball". We need
the pixel offset between the optical axis and the gripper tip so the controller
can aim at that pixel instead of the geometric center.

Workflow:
  1. SUPPORT THE ARM — ALL torque is about to drop.
  2. Press Enter to release torque on every servo so you can free-pose the arm.
  3. Place the ball on the table, then physically pose the arm so the gripper
     is directly above the ball at the height it would normally grab from.
  4. The live view shows the detected ball, its (bx, by), and the dx/dy from
     image center. Those dx/dy ARE the offset.
  5. Hold steady, press 's' + Enter — the script averages the last ~30 frames
     and prints the CAM_GRIPPER_OFFSET_X / CAM_GRIPPER_OFFSET_Y values to paste
     into modes/ball_follow.py.
  6. 'h' + Enter re-enables torque at the current pose. 'r' + Enter releases
     torque again. 'q' + Enter quits (re-enables torque first as a safety).
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
from collections import deque

# The stdlib `statistics` module isn't shipped on the RZ/G3E's Yocto python
# image, so reimplement the two functions we need (median, pstdev) inline.
class _stats:
    @staticmethod
    def median(values):
        s = sorted(values)
        n = len(s)
        if n == 0:
            raise ValueError("median of empty sequence")
        mid = n // 2
        return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

    @staticmethod
    def pstdev(values):
        n = len(values)
        if n == 0:
            return 0.0
        mean = sum(values) / n
        return (sum((v - mean) ** 2 for v in values) / n) ** 0.5


statistics = _stats

import cv2
import numpy as np
import xarm
from xarm import Servo

HERE = os.path.dirname(os.path.abspath(__file__))
HSV_PATH = os.path.join(HERE, "ball_color.json")

# Match ball_follow.py detection params so what we measure matches what it sees.
MIN_CONTOUR_AREA = 200
MIN_FILL_RATIO = 0.65
SAMPLE_WINDOW = 30  # frames averaged on snapshot

SERVOS = [Servo(i) for i in range(1, 7)]
_bus_lock = threading.Lock()

arm = None
running = True
latest = {"bx": None, "by": None, "br": None, "frame_w": 0, "frame_h": 0}
recent = deque(maxlen=SAMPLE_WINDOW)


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


def hold_current_pose():
    """Re-enable torque by commanding each servo to its current measured position."""
    with _bus_lock:
        try:
            targets = []
            for s in SERVOS:
                p = int(arm.getPosition(s.servo_id))
                targets.append([s.servo_id, p])
        except Exception as e:
            print(f"[calib] read failed during hold: {e}")
            return
        arm.setPosition(targets, duration=1500, wait=True)


def cleanup(signum=None, frame=None):
    global running
    running = False
    print("\n[calib] re-enabling torque at current pose for safety...")
    try:
        hold_current_pose()
    except Exception as e:
        print(f"[calib] hold failed: {e}")
    sys.exit(0)


def camera_loop(cam_index, width, height, lower, upper):
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not cap.isOpened():
        print(f"[calib] ERROR: could not open camera {cam_index}")
        return

    win = "Camera-Gripper Offset Calibrator"
    cv2.namedWindow(win)
    print(f"[calib] camera open ({cam_index}, {width}x{height})")

    while running:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        h, w = frame.shape[:2]
        latest["frame_w"], latest["frame_h"] = w, h

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

        ball = largest_blob(mask)
        # Flip for display so user sees the same orientation as ball_follow.
        annotated = cv2.flip(frame, 1)
        cx, cy = w // 2, h // 2
        cv2.drawMarker(annotated, (cx, cy), (255, 255, 255),
                       markerType=cv2.MARKER_CROSS, markerSize=20, thickness=1)

        if ball is not None:
            bx, by, br = ball
            latest["bx"], latest["by"], latest["br"] = bx, by, br
            recent.append((bx, by))
            dx = bx - cx
            dy = by - cy
            bx_disp = w - bx
            cv2.circle(annotated, (bx_disp, by), int(br), (0, 255, 0), 2)
            cv2.circle(annotated, (bx_disp, by), 4, (0, 255, 0), -1)
            cv2.putText(annotated, f"bx={bx} by={by} r={int(br)}",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(annotated, f"OFFSET_X={dx:+d}  OFFSET_Y={dy:+d}",
                        (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(annotated, f"samples={len(recent)}/{SAMPLE_WINDOW}",
                        (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (200, 200, 200), 1, cv2.LINE_AA)
        else:
            latest["bx"] = latest["by"] = latest["br"] = None
            cv2.putText(annotated, "no ball detected", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

        cv2.imshow(win, annotated)
        cv2.waitKey(1)

    cap.release()
    cv2.destroyAllWindows()


def snapshot():
    if len(recent) < 5:
        print(f"[calib] not enough samples yet ({len(recent)}/5) — make sure ball is visible and steady")
        return
    xs = [p[0] for p in recent]
    ys = [p[1] for p in recent]
    bx_med = int(statistics.median(xs))
    by_med = int(statistics.median(ys))
    w = latest["frame_w"]
    h = latest["frame_h"]
    cx = w // 2
    cy = h // 2
    off_x = bx_med - cx
    off_y = by_med - cy
    bx_std = statistics.pstdev(xs) if len(xs) > 1 else 0
    by_std = statistics.pstdev(ys) if len(ys) > 1 else 0

    print()
    print("=" * 60)
    print(f"[calib] median over last {len(recent)} frames:")
    print(f"        bx = {bx_med}  (std {bx_std:.1f})")
    print(f"        by = {by_med}  (std {by_std:.1f})")
    print(f"        image center = ({cx}, {cy})")
    print(f"[calib] paste into modes/ball_follow.py:")
    print(f"        CAM_GRIPPER_OFFSET_X = {off_x}")
    print(f"        CAM_GRIPPER_OFFSET_Y = {off_y}")
    print("=" * 60)
    print()


def main():
    global arm
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=2)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    if not os.path.exists(HSV_PATH):
        print(f"[calib] ERROR: {HSV_PATH} not found — run ball_calibrate.py first")
        sys.exit(1)
    with open(HSV_PATH) as f:
        cfg = json.load(f)
    lower = np.array([cfg["h_min"], cfg["s_min"], cfg["v_min"]], dtype=np.uint8)
    upper = np.array([cfg["h_max"], cfg["s_max"], cfg["v_max"]], dtype=np.uint8)
    print(f"[calib] HSV range: lower={lower.tolist()} upper={upper.tolist()}")

    print("[calib] connecting to xArm...")
    arm = xarm.Controller('USB')
    signal.signal(signal.SIGINT, cleanup)

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
        sys.exit(1)

    cam_thread = threading.Thread(
        target=camera_loop,
        args=(args.camera, args.width, args.height, lower, upper),
        daemon=True,
    )
    cam_thread.start()

    print("\n[calib] commands: s = snapshot   h = hold (torque on)   r = release   q = quit")
    while True:
        try:
            cmd = input().strip().lower()
        except EOFError:
            cleanup()
        if cmd == "s":
            snapshot()
        elif cmd == "h":
            print("[calib] re-enabling torque at current pose...")
            hold_current_pose()
        elif cmd == "r":
            try:
                arm.servoOff()
                print("[calib] torque OFF.")
            except Exception as e:
                print(f"[calib] servoOff failed: {e}")
        elif cmd in ("q", "quit", "exit"):
            cleanup()


if __name__ == "__main__":
    main()
