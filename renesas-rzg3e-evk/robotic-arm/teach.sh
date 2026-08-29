#!/bin/bash
# Pose the arm by hand, snapshot scan poses, and print SCAN_POSE blocks
# to paste into modes/ball_follow.py.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec python3 -u teach_pose.py "$@"
