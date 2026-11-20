#!/usr/bin/env python3
"""
Discover per-servo mechanical limits on the Hiwonder xArm 1S.

For each servo, starts at 500 and steps slowly toward 0, then back to 500, then
toward 1000. At each step it commands a position, waits, then reads back the
actual position. If the read-back stops following the command (stall against a
mechanical stop), that direction is considered done.

Ctrl-C at any time returns the arm to home (all 500s) and exits. Also pauses
between servos so you can reposition the arm, clear obstacles, or skip a joint.

Run from the HDMI terminal or over SSH — it does not need a display.
"""

import json
import os
import signal
import sys
import time

import xarm

LIMITS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arm_limits.json")

STEP = 40                  # servo units per step (~10 deg)
SETTLE_S = 0.35            # seconds to wait for servo to reach commanded pos
STALL_GAP = 60             # if |commanded - actual| > this for 2 steps, stalled
MOVE_DURATION_MS = 400     # servo move duration per step
SERVOS = [
    (6, "shoulder_pan"),
    (5, "shoulder_lift"),
    (4, "elbow_flex"),
    (3, "wrist_flex"),
    (2, "wrist_roll"),
    (1, "gripper"),
]

arm = None


def goto(servo_id, pos):
    arm.setPosition(servo_id, pos, duration=MOVE_DURATION_MS, wait=True)
    time.sleep(SETTLE_S)
    return arm.getPosition(servo_id)


def sweep_direction(servo_id, direction):
    """direction is +1 (toward 1000) or -1 (toward 0). Returns last non-stalled commanded pos."""
    cmd = 500
    last_good = 500
    consecutive_stalls = 0
    while 0 <= cmd + direction * STEP <= 1000:
        cmd += direction * STEP
        actual = goto(servo_id, cmd)
        gap = abs(cmd - actual)
        print(f"  cmd={cmd:4d}  actual={actual:4d}  gap={gap:3d}")
        if gap > STALL_GAP:
            consecutive_stalls += 1
            if consecutive_stalls >= 2:
                print(f"  -> stall at cmd={cmd}, last_good={last_good}")
                return last_good
        else:
            consecutive_stalls = 0
            last_good = cmd
    print(f"  -> hit library bound, last_good={last_good}")
    return last_good


def home_all():
    print("Homing all servos to 500...")
    positions = [[i, 500] for i in range(1, 7)]
    arm.setPosition(positions, duration=1500, wait=True)
    time.sleep(0.6)


def cleanup(signum=None, frame=None):
    print("\nInterrupted. Returning to home and turning servos off.")
    try:
        home_all()
    except Exception:
        pass
    try:
        arm.servoOff()
    except Exception:
        pass
    sys.exit(0)


def main():
    global arm
    print("Connecting to xArm...")
    arm = xarm.Controller('USB')
    signal.signal(signal.SIGINT, cleanup)

    home_all()

    limits = {}
    for servo_id, name in SERVOS:
        print(f"\n=== Servo {servo_id} ({name}) ===")
        ans = input("Press Enter to sweep, or 's' to skip: ").strip().lower()
        if ans == 's':
            continue

        print(f"Sweeping {name} down toward 0...")
        low = sweep_direction(servo_id, -1)
        goto(servo_id, 500)

        print(f"Sweeping {name} up toward 1000...")
        high = sweep_direction(servo_id, +1)
        goto(servo_id, 500)

        limits[name] = (low, high)
        print(f"{name}: safe range ≈ [{low}, {high}]  (~{(high-low)*0.24:.0f}° total)")

    home_all()
    arm.servoOff()

    print("\n===== SUMMARY =====")
    summary = {}
    for (servo_id, name), (low, high) in (
        (k, limits[k[1]]) for k in SERVOS if k[1] in limits
    ):
        deg = (high - low) * 0.24
        print(f"  servo {servo_id} {name:15s}  [{low:4d}, {high:4d}]  ~{deg:5.1f}°")
        summary[name] = {"servo_id": servo_id, "min": low, "max": high, "range_deg": round(deg, 1)}

    with open(LIMITS_FILE, "w") as f:
        json.dump({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "servos": summary}, f, indent=2)
    print(f"\nSaved limits to {LIMITS_FILE}")


if __name__ == "__main__":
    main()
