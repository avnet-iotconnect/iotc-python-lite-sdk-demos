#!/bin/bash
# Launch the IoTConnect XArm vision demo on the Renesas RZ/G3E EVK.
# The base RZ/G3E image uses system python3 (no conda), so this is
# stripped down compared to the TRIA variant.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/run.log"
echo "===== START $(date -u +%FT%TZ) =====" | tee "$LOG"
echo "Logging to $LOG" | tee -a "$LOG"

# python3 -u gives unbuffered I/O on its own (the busybox image used by the
# RZ/G3E doesn't ship stdbuf, and python -u is sufficient for line-buffered
# log output via tee).
exec python3 -u main.py "$@" 2>&1 | tee -a "$LOG"
