#!/bin/sh

# Install the robotic-arm demo dependencies on the RZ/G3E from wheels that
# were transferred by deps-download.sh on the host PC. The base RZ/G3E
# image lacks pip repositories, so this script unzips each wheel directly
# into the system site-packages — the same pattern used by the base
# renesas-rzg3e-evk dependency installer.

set -e

SITE_PACKAGES=$(python3 -c "import sys; print([p for p in sys.path if 'site-packages' in p][0])")

cd ~
installed=0
skipped=0
for wheel in *.whl; do
    if [ ! -f "$wheel" ]; then
        continue
    fi
    echo "  - Installing $wheel..."
    if unzip -o "$wheel" -d "$SITE_PACKAGES/" > /dev/null 2>&1; then
        installed=$((installed + 1))
    else
        echo "    SKIPPED: failed to unpack $wheel"
        skipped=$((skipped + 1))
    fi
done

echo ""
echo "Wheels installed: $installed (skipped: $skipped)"

# Move into the demo directory and download the ASL model file (no-op if
# torch/mediapipe weren't installable — the file just won't be used).
DEMO_DIR=~/robotic-arm
if [ -d "$DEMO_DIR/model" ]; then
    echo ""
    echo "Fetching ASL model into $DEMO_DIR/model ..."
    (cd "$DEMO_DIR/model" && bash ./get_model.sh) || \
        echo "  (model download skipped or failed — ASL mode will not run)"
fi

# Sanity check what's available so the operator knows which mode will work.
echo ""
echo "Module availability check:"
for mod in cv2 numpy xarm hid avnet.iotconnect.sdk.lite torch mediapipe; do
    if python3 -c "import $mod" 2>/dev/null; then
        echo "  OK    : $mod"
    else
        echo "  MISS  : $mod"
    fi
done

echo ""
echo "Done. The demo lives at $DEMO_DIR — see its README for run instructions."
