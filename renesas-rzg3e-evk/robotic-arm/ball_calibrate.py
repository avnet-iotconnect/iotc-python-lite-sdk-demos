#!/usr/bin/env python3
"""
Ball-color HSV calibrator.

Opens the wrist camera, lets you click on the ball repeatedly. Each click
samples a small patch and expands a running HSV min/max box. A live mask
preview shows what the ball-follow mode will see. Save with 's', reset with
'r', quit (without saving) with 'q' or ESC.

Camera-angle helper: at startup the script prompts before releasing ALL servo
torque so you can free-pose the entire arm to point the camera at where the
ball will sit. SUPPORT THE ARM before pressing Enter — it will swing under
gravity. Press 'h' in the window to re-engage all torque at the current pose,
'w' to release everything again.

Typical use: hold the ball in different parts of the frame / under the
lighting you'll demo in, click 5-10 times, then 's'.
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np
import xarm

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ball_color.json")
PATCH_RADIUS = 3      # 7x7 sample patch around each click
HUE_PAD = 8           # extra hue tolerance on each side
SAT_PAD = 25
VAL_PAD = 25

ALL_SERVO_IDS = [1, 2, 3, 4, 5, 6]  # gripper, wrist_roll, wrist_flex, elbow_flex, shoulder_lift, shoulder_pan

samples = []          # list of (h, s, v) median values, one per click
hsv_frame = None      # latest HSV frame, set in main loop


def on_mouse(event, x, y, flags, param):
    if event != cv2.EVENT_LBUTTONDOWN or hsv_frame is None:
        return
    h, w = hsv_frame.shape[:2]
    x0, x1 = max(0, x - PATCH_RADIUS), min(w, x + PATCH_RADIUS + 1)
    y0, y1 = max(0, y - PATCH_RADIUS), min(h, y + PATCH_RADIUS + 1)
    patch = hsv_frame[y0:y1, x0:x1].reshape(-1, 3)
    med = np.median(patch, axis=0).astype(int)
    samples.append(tuple(med.tolist()))
    print(f"click @({x},{y}) -> H={med[0]} S={med[1]} V={med[2]}  (samples: {len(samples)})")


def current_range():
    """Return (lower, upper) HSV bounds, padded. None if no samples yet."""
    if not samples:
        return None
    arr = np.array(samples)
    h_lo, h_hi = arr[:, 0].min() - HUE_PAD, arr[:, 0].max() + HUE_PAD
    s_lo, s_hi = arr[:, 1].min() - SAT_PAD, arr[:, 1].max() + SAT_PAD
    v_lo, v_hi = arr[:, 2].min() - VAL_PAD, arr[:, 2].max() + VAL_PAD
    lower = np.array([max(0, h_lo), max(0, s_lo), max(0, v_lo)], dtype=np.uint8)
    upper = np.array([min(180, h_hi), min(255, s_hi), min(255, v_hi)], dtype=np.uint8)
    return lower, upper


def release_all(arm):
    try:
        arm.servoOff()
        print("[calib] ALL torque OFF — pose the arm by hand.")
    except Exception as e:
        print(f"[calib] servoOff failed: {e}")


def hold_all(arm):
    try:
        targets = [[sid, int(arm.getPosition(sid))] for sid in ALL_SERVO_IDS]
        arm.setPosition(targets, duration=1500, wait=True)
        print("[calib] torque ON at current pose.")
    except Exception as e:
        print(f"[calib] hold failed: {e}")


def save_range(lower, upper, camera_index):
    payload = {
        "camera_index": int(camera_index),
        "h_min": int(lower[0]), "h_max": int(upper[0]),
        "s_min": int(lower[1]), "s_max": int(upper[1]),
        "v_min": int(lower[2]), "v_max": int(upper[2]),
        "samples": [list(s) for s in samples],
    }
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved {len(samples)} samples to {OUT_PATH}")
    print(f"  HSV lower: {lower.tolist()}")
    print(f"  HSV upper: {upper.tolist()}")


def main():
    global hsv_frame
    parser = argparse.ArgumentParser(description="HSV ball-color calibrator")
    parser.add_argument("--camera", type=int, default=2, help="OpenCV camera index (default 2)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    print("[calib] connecting to xArm...")
    arm = xarm.Controller('USB')

    print("\n" + "=" * 60)
    print(" SAFETY: ALL torque is about to drop. Support the arm with your")
    print(" hand before pressing Enter, or it will swing under gravity.")
    print("=" * 60)
    input("[calib] Holding the arm? Press Enter to release torque... ")
    release_all(arm)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"ERROR: could not open camera {args.camera}", file=sys.stderr)
        hold_all(arm)
        return 1

    win = "Ball Calibrator"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    print("Click the ball in the live view. 's' save, 'r' reset, 'h' hold pose (torque on), 'w' release torque, 'q'/ESC quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] camera read failed", file=sys.stderr)
            break
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        rng = current_range()
        if rng is not None:
            lower, upper = rng
            mask = cv2.inRange(hsv_frame, lower, upper)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            overlay = frame.copy()
            overlay[mask > 0] = (0, 255, 0)
            display = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
            cv2.putText(display, f"samples={len(samples)} H[{lower[0]}-{upper[0]}] S[{lower[1]}-{upper[1]}] V[{lower[2]}-{upper[2]}]",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            display = frame.copy()
            cv2.putText(display, "click the ball...", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(win, display)
        key = cv2.waitKey(10) & 0xFF
        if key in (27, ord('q')):
            print("Quit without saving.")
            break
        if key == ord('r'):
            samples.clear()
            print("Reset samples.")
        if key == ord('h'):
            hold_all(arm)
        if key == ord('w'):
            release_all(arm)
        if key == ord('s'):
            if rng is None:
                print("Nothing to save yet — click the ball first.")
                continue
            save_range(rng[0], rng[1], args.camera)
            break

    cap.release()
    cv2.destroyAllWindows()
    hold_all(arm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
