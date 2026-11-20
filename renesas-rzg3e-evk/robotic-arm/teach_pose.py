#!/usr/bin/env python3
"""Teach mode: turn off servo torque so the arm can be posed by hand,
then continuously print the current servo positions.

Workflow:
  1. SUPPORT THE ARM with your hand before continuing — it will fall when
     torque drops, and a wall/ceiling-mounted arm will swing freely.
  2. Press Enter to disable torque.
  3. Move the arm into the pose you want (camera pointing where you want it).
  4. Hold it still; the printed line that stays stable IS the pose.
  5. Press 's' + Enter to snapshot the current pose to teach_pose.json.
  6. Press 'h' + Enter to re-enable torque (arm will hold its current pose).
  7. Ctrl-C to exit (re-enables torque first as a safety).
"""

import json
import os
import signal
import sys
import threading
import time

import xarm
from xarm import Servo

OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "teach_pose.json")

SERVOS = [
    (6, "shoulder_pan"),
    (5, "shoulder_lift"),
    (4, "elbow_flex"),
    (3, "wrist_flex"),
    (2, "wrist_roll"),
    (1, "gripper"),
]

# Reusable Servo objects for batched read — single USB round-trip for all 6.
_ALL_SERVOS = [Servo(sid) for sid, _ in SERVOS]
_NAME_BY_ID = {sid: name for sid, name in SERVOS}

arm = None
torque_on = True
running = True
last_positions = {}

# Guards USB access so the reader thread can't clash with snapshot/hold ops.
_bus_lock = threading.Lock()


def read_all():
    """Batched read of all servo positions in a single USB round-trip."""
    try:
        with _bus_lock:
            arm.getPosition(_ALL_SERVOS)
        return {_NAME_BY_ID[s.servo_id]: int(s.position) for s in _ALL_SERVOS}
    except Exception as e:
        return {name: f"ERR({e})" for _, name in SERVOS}


def hold_current_pose():
    """Re-enable torque by commanding each servo to its current measured position.

    Batched read + longer move duration avoids the drift+jerk that a per-servo
    read-then-write sequence produces (6 sequential reads take ~60-100 ms, during
    which gravity pulls the arm past the first servo's captured position).
    """
    with _bus_lock:
        try:
            arm.getPosition(_ALL_SERVOS)
        except Exception as e:
            print(f"[teach] batched read failed: {e}")
            return
        targets = [[s.servo_id, int(s.position)] for s in _ALL_SERVOS]
        # Slow move so any small read-to-command drift is absorbed smoothly
        # rather than snapping in 300 ms.
        arm.setPosition(targets, duration=1500, wait=True)


def cleanup(signum=None, frame=None):
    global running
    running = False
    print("\n[teach] re-enabling torque at current pose for safety...")
    try:
        hold_current_pose()
    except Exception as e:
        print(f"[teach] hold failed: {e}")
    sys.exit(0)


def reader_loop():
    global last_positions
    while running:
        last_positions = read_all()
        line = "  ".join(f"{n}={last_positions[n]:>4}" if isinstance(last_positions[n], int)
                         else f"{n}={last_positions[n]}"
                         for _, n in SERVOS)
        print(f"[teach] {line}", flush=True)
        time.sleep(0.5)


def save_snapshot():
    snap = {n: last_positions.get(n) for _, n in SERVOS}
    payload = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "positions": snap,
               "scan_pose_list": [[sid, snap[name]] for sid, name in SERVOS if isinstance(snap[name], int)]}
    with open(OUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\n[teach] saved snapshot to {OUT_FILE}")
    print("[teach] Paste this into modes/ball_follow.py SCAN_POSE:")
    print("SCAN_POSE = [")
    for sid, name in SERVOS:
        v = snap.get(name)
        if isinstance(v, int):
            servo_const = {1: "SERVO_GRIPPER", 2: "SERVO_WRIST_ROLL", 3: "SERVO_WRIST_FLEX",
                           4: "SERVO_ELBOW_FLEX", 5: "SERVO_SHOULDER_LIFT", 6: "SERVO_SHOULDER_PAN"}[sid]
            print(f"    [{servo_const}, {v}],")
    print("]\n")


def main():
    global arm, torque_on
    print("[teach] connecting to xArm...")
    arm = xarm.Controller('USB')
    signal.signal(signal.SIGINT, cleanup)

    print("\n" + "=" * 60)
    print(" SAFETY: This will RELEASE the servos so you can move the arm.")
    print(" Support the arm with your hand BEFORE pressing Enter, or it")
    print(" will swing under gravity and could damage itself or the mount.")
    print("=" * 60)
    input("[teach] Holding the arm? Press Enter to release torque... ")

    try:
        arm.servoOff()
        torque_on = False
        print("[teach] torque OFF — pose the arm by hand.")
    except Exception as e:
        print(f"[teach] servoOff failed: {e}")
        sys.exit(1)

    t = threading.Thread(target=reader_loop, daemon=True)
    t.start()

    print("\n[teach] commands:  s = snapshot   h = hold (torque on)   r = release (torque off)   q = quit")
    while True:
        try:
            cmd = input().strip().lower()
        except EOFError:
            cleanup()
        if cmd == "s":
            save_snapshot()
        elif cmd == "h":
            print("[teach] re-enabling torque at current pose...")
            hold_current_pose()
            torque_on = True
        elif cmd == "r":
            try:
                arm.servoOff()
                torque_on = False
                print("[teach] torque OFF.")
            except Exception as e:
                print(f"[teach] servoOff failed: {e}")
        elif cmd in ("q", "quit", "exit"):
            cleanup()


if __name__ == "__main__":
    main()
