#!/bin/bash

# Download all wheels needed by the robotic-arm demo on the RZ/G3E and scp
# them to the board, then transfer the demo source. The base RZ/G3E image
# does not ship pip repositories, so dependencies are fetched on the host
# (where pip can reach PyPI) and installed offline on the board.
#
# Usage: bash deps-download.sh <board-ip-address>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <board-ip-address>"
    echo "Example: $0 192.168.1.100"
    exit 1
fi

BOARD_IP=$1
WORK_DIR="/tmp/iotc-robotic-arm-packages"
DEMO_REPO_URL="https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git"
DEMO_REL_PATH="renesas-rzg3e-evk/robotic-arm"

echo ""
echo "Board IP: $BOARD_IP"
echo "Working directory: $WORK_DIR"
echo ""

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Wheels for the arm + vision pipeline. Targeting the RZ/G3E's CPython on
# linux_aarch64 (manylinux2014). torch / mediapipe are best-effort: if no
# matching wheel exists pip will skip them and the ASL mode will be
# unavailable on the board (ball mode still runs).
#
# PY_VER must match the board's `python3 --version` (the shipped image
# uses Python 3.12). Override at the command line if your image differs:
#   PY_VER=cp311 bash deps-download.sh <ip>
PY_VER="${PY_VER:-cp312}"
PLATFORM="manylinux2014_aarch64"

# psutil + py-cpuinfo are intentionally excluded: the RZ/G3E's Yocto
# python image strips the `resource` and `multiprocessing` stdlib
# modules, which both libraries import at top level. systemdata.py
# reads /proc and /sys directly, so neither is needed.
REQUIRED=(
    "xarm>=0.0.4"
    "hidapi>=0.14"
    "opencv-python-headless>=4.5.0"
    "numpy>=1.21.0"
    "requests>=2.25.0"
)

OPTIONAL=(
    "torch>=1.9.0"
    "torchvision>=0.10.0"
    "mediapipe>=0.8.0"
)

echo "Downloading required wheels (arm + ball-follow)..."
pip3 download \
    --only-binary=:all: \
    --platform "$PLATFORM" \
    --python-version "${PY_VER#cp}" \
    --implementation cp \
    --abi "$PY_VER" \
    -d "$WORK_DIR" \
    "${REQUIRED[@]}"

echo ""
echo "Attempting optional wheels (ASL mode — torch / mediapipe)..."
for pkg in "${OPTIONAL[@]}"; do
    if ! pip3 download \
        --only-binary=:all: \
        --platform "$PLATFORM" \
        --python-version "${PY_VER#cp}" \
        --implementation cp \
        --abi "$PY_VER" \
        -d "$WORK_DIR" \
        "$pkg" 2>/dev/null; then
        echo "  - SKIPPED: no aarch64 wheel for '$pkg' (ASL mode will be unavailable)"
    fi
done

echo ""
echo "Checking out demo source..."
if [ -d "iotc-python-lite-sdk-demos" ]; then
    (cd iotc-python-lite-sdk-demos && git pull)
else
    git clone --depth 1 "$DEMO_REPO_URL"
fi

echo ""
echo "Transferring wheels to board..."
scp "$WORK_DIR"/*.whl root@"$BOARD_IP":~

echo ""
echo "Transferring demo source to board (~/robotic-arm)..."
scp -r "$WORK_DIR/iotc-python-lite-sdk-demos/$DEMO_REL_PATH" root@"$BOARD_IP":~/robotic-arm

echo ""
echo "Done. On the board, run:"
echo "  bash ~/robotic-arm/scripts/deps-install.sh"
