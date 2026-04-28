#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Build and deploy IoTConnect-patched Renesas RZ/V2H AI SDK demos.
#
# Usage:
#   ./build-and-deploy.sh <board-ip> [demo1 demo2 ...]
#   ./build-and-deploy.sh <board-ip> all
#   ./build-and-deploy.sh  (build only — no IP)
#
# Demo keys (same as the launch_drpai C2D command parameters):
#   q08   — Object Counter           (has deploy.so on SD card)
#   q13   — Analog Meter Reader       (downloads missing yolox deploy.so)
#   q01   — Footfall Counter         (downloads d-yolov3 deploy.so)
#   q02   — Face Authentication      (has deploy.so)
#   q03   — Smart Parking            (downloads tinyyolov2 deploy.so)
#   q04   — Fish Classification       (has deploy.so)
#   q05   — Suspicious Activity       (has deploy.so)
#   q06   — Expiry Date Detection    (downloads deploy.so)
#   q07   — Plant Disease Classification (has deploy.so)
#   q09   — Crack Segmentation        (has deploy.so)
#   q10   — Suspicious Person Detect (downloads deploy.so)
#   q11   — Fish Detection           (downloads deploy.so)
#   q12   — Yoga Pose Estimation     (has deploy.so)
#   r01   — Generic Object Detection (downloads deploy.so)
#
# ENV overrides:
#   SDK_ROOT   — default: $HOME/renesas/rzv2h/ai_sdk_setup
#   SDK_SRC    — default: $SDK_ROOT/rzv_ai_sdk
#   IMAGE      — default: rzv2h_ai_sdk_image
#   CONTAINER  — default: rzv2h_ai_sdk_container
#   SKIP_DOWNLOADS=1 — don't fetch missing deploy.so files

set -e

BOARD_IP="${1:-}"
shift 2>/dev/null || true
DEMOS=("$@")
[[ ${#DEMOS[@]} -eq 0 ]] && DEMOS=(q08)  # default if nothing specified

SDK_ROOT="${SDK_ROOT:-$HOME/renesas/rzv2h/ai_sdk_setup}"
SDK_SRC="${SDK_SRC:-$SDK_ROOT/rzv_ai_sdk}"
IMAGE="${IMAGE:-rzv2h_ai_sdk_image}"
CONTAINER="${CONTAINER:-rzv2h_ai_sdk_container}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if docker info >/dev/null 2>&1; then
    D="docker"
else
    D="sudo docker"
    echo "NOTE: user not in 'docker' group — docker steps will prompt for sudo."
fi

# --- Demo metadata table ------------------------------------------------------
# Columns: key | app_dir | binary | patch_file | deploy_dir | model_download_url | model_target_path
# An empty model_download_url means "no download needed" (already shipped).
DEMO_TABLE=(
    "q08|Q08_object_counter|object_counter|object_counter-iotconnect.patch|/home/weston/tvm_q08||"
    "q13|Q13_analog_meter_reader|analog_reader|analog_meter_reader-iotconnect.patch|/home/weston/Q13_analog_meter_reader/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/Q13_analog_meter_reader_deploy_tvm_v2h-v251.so|Q13_analog_meter_reader/exe_v2h/yolox_model/deploy.so"
    "q01|Q01_footfall_counter|object_tracker|footfall_counter-iotconnect.patch|/home/weston/Q01_footfall_counter/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/Q01_footfall_counter_deploy_tvm_v2h-v251.so|Q01_footfall_counter/exe_v2h/d-yolov3/deploy.so"
    "q02|Q02_face_authentication|face_recognition||/home/weston/Q02_face_authentication/exe_v2h||"
    # Q03 Smart Parking is RZ/V2L-only — no V2H deploy.so exists in the v6.20 release.
    "q04|Q04_fish_classification|fish_classification|fish_classification-iotconnect.patch|/home/weston/Q04_fish_classification/exe_v2h||"
    "q05|Q05_suspicious_activity|suspicious_activity|suspicious_activity-iotconnect.patch|/home/weston/Q05_suspicious_activity/exe_v2h||"
    "q06|Q06_expiry_date_detection|date_extraction||/home/weston/Q06_expiry_date_detection/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/Q06_expiry_date_detection_deploy_tvm_v2h-v251.so|Q06_expiry_date_detection/exe_v2h/expiry_yolov3_onnx/deploy.so"
    "q07|Q07_plant_disease_classification|plant_leaf_disease_classify|plant_disease-iotconnect.patch|/home/weston/Q07_plant_disease_classification/exe_v2h||"
    "q09|Q09_crack_segmentation|crack_segmentation|crack_segmentation-iotconnect.patch|/home/weston/Q09_crack_segmentation/exe_v2h||"
    "q10|Q10_suspicious_person_detection|suspicious_person_detector|suspicious_person-iotconnect.patch|/home/weston/Q10_suspicious_person_detection/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/Q10_suspicious_person_detection_deploy_tvm_v2h-v251.so|Q10_suspicious_person_detection/exe_v2h/suspicious_onnx/deploy.so"
    "q11|Q11_fish_detection|fish_detector|fish_detection-iotconnect.patch|/home/weston/Q11_fish_detection/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/Q11_fish_detection_deploy_tvm_v2h-v251.so|Q11_fish_detection/exe_v2h/fish_detection_model/deploy.so"
    "q12|Q12_yoga_pose_estimation|pose_estimator|yoga_pose-iotconnect.patch|/home/weston/Q12_yoga_pose_estimation/exe_v2h||"
    "r01|R01_object_detection|object_detection|object_detection-iotconnect.patch|/home/weston/R01_object_detection/exe_v2h|https://github.com/renesas-rz/rzv_ai_sdk/releases/download/v6.20/R01_object_detection_deploy_tvm_v2h-v251.so|R01_object_detection/exe_v2h/yolov3_onnx/deploy.so"
)

expand_all() {
    local -a all=()
    for row in "${DEMO_TABLE[@]}"; do
        all+=("${row%%|*}")
    done
    echo "${all[@]}"
}

if [[ "${DEMOS[0]}" == "all" ]]; then
    # shellcheck disable=SC2207
    DEMOS=($(expand_all))
fi

# --- Sanity checks ------------------------------------------------------------
[[ -f "$SDK_ROOT/Dockerfile" ]] || { echo "ERROR: Dockerfile not found at $SDK_ROOT"; exit 1; }
[[ -d "$SDK_SRC" ]] || { echo "ERROR: rzv_ai_sdk tree not found at $SDK_SRC"; exit 1; }

lookup() {
    # $1 = demo key, $2 = column index (0-based)
    local key="$1" idx="$2"
    for row in "${DEMO_TABLE[@]}"; do
        IFS='|' read -r -a cols <<< "$row"
        if [[ "${cols[0]}" == "$key" ]]; then
            echo "${cols[$idx]}"
            return 0
        fi
    done
    return 1
}

for demo in "${DEMOS[@]}"; do
    app=$(lookup "$demo" 1) || { echo "ERROR: unknown demo '$demo'"; exit 1; }
    patch=$(lookup "$demo" 3)
    if [[ -n "$patch" ]] && ! grep -q "IoTConnect" "$SDK_SRC/$app/src"/*.cpp 2>/dev/null; then
        echo "WARNING: patch $patch not applied in $SDK_SRC/$app/src — applying now..."
        (cd "$SDK_SRC" && patch -p1 < "$SCRIPT_DIR/$patch")
    fi
done

# --- Model-weight downloads ---------------------------------------------------
if [[ "${SKIP_DOWNLOADS:-0}" != "1" ]]; then
    for demo in "${DEMOS[@]}"; do
        url=$(lookup "$demo" 5)
        target=$(lookup "$demo" 6)
        [[ -z "$url" || -z "$target" ]] && continue
        full_target="$SDK_SRC/$target"
        if [[ -s "$full_target" && "$(stat -c%s "$full_target")" -gt 1000 ]]; then
            continue  # already downloaded
        fi
        echo ""
        echo "=== Downloading model weights for $demo ==="
        mkdir -p "$(dirname "$full_target")"
        wget -q --show-progress "$url" -O "$full_target"
        echo "wrote $full_target ($(du -h "$full_target" | cut -f1))"
    done
fi

# --- Docker image + container -------------------------------------------------
echo ""
echo "=== Ensure Docker image '$IMAGE' exists ==="
if ! $D image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building image from $SDK_ROOT/Dockerfile (first run: 15-30 min)..."
    (cd "$SDK_ROOT" && $D build -t "$IMAGE" .)
fi

echo ""
echo "=== Ensure container '$CONTAINER' is running ==="
if $D ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    :
elif $D ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    $D start "$CONTAINER"
else
    $D run -itd --name "$CONTAINER" \
        -v "$SDK_SRC:/drp-ai_tvm/data/rzv_ai_sdk" \
        "$IMAGE"
fi

# --- Build function -----------------------------------------------------------
build_one() {
    local demo="$1"
    local app binary
    app=$(lookup "$demo" 1)
    binary=$(lookup "$demo" 2)

    echo ""
    echo "=== Building $binary (from $app) ==="
    $D exec "$CONTAINER" bash -c "
        set -e
        SYSROOTS_DIR=\$(find /opt -maxdepth 5 -name sysroots -type d 2>/dev/null | head -1)
        [[ -z \"\$SYSROOTS_DIR\" ]] && { echo 'ERROR: sysroots not found'; exit 1; }
        export SDK=\"\${SYSROOTS_DIR}/..\"
        export PROJECT_PATH=/drp-ai_tvm/data/rzv_ai_sdk
        cd \$PROJECT_PATH/$app/src
        rm -rf build && mkdir -p build && cd build
        cmake -DCMAKE_TOOLCHAIN_FILE=../toolchain/runtime.cmake -DV2H=ON ..
        make -j\$(nproc)
        ls -la $binary
    "
    local host_bin="$SDK_SRC/$app/src/build/$binary"
    [[ -f "$host_bin" ]] || { echo "ERROR: build produced no binary at $host_bin"; return 1; }
    echo "Built: $host_bin ($(du -h "$host_bin" | cut -f1))"
}

deploy_one() {
    local demo="$1"
    [[ -z "$BOARD_IP" ]] && return 0
    local app binary deploy_dir
    app=$(lookup "$demo" 1)
    binary=$(lookup "$demo" 2)
    deploy_dir=$(lookup "$demo" 4)
    local host_bin="$SDK_SRC/$app/src/build/$binary"
    local model_target model_url full_model_path

    echo ""
    echo "=== Deploying $binary to $BOARD_IP:$deploy_dir ==="
    ssh "root@${BOARD_IP}" "mkdir -p $deploy_dir"
    scp "$host_bin" "root@${BOARD_IP}:${deploy_dir}/${binary}"
    ssh "root@${BOARD_IP}" "chmod +x ${deploy_dir}/${binary}"

    # Also push downloaded model weights if applicable and not already on board
    model_url=$(lookup "$demo" 5)
    model_target=$(lookup "$demo" 6)
    if [[ -n "$model_url" && -n "$model_target" ]]; then
        local rel_model_path="${model_target#*/exe_v2h/}"
        local full_remote_path="${deploy_dir}/${rel_model_path}"
        local full_local_path="$SDK_SRC/$model_target"
        if ssh "root@${BOARD_IP}" "[[ -s '$full_remote_path' && \$(stat -c%s '$full_remote_path') -gt 1000 ]]"; then
            :  # already there
        else
            echo "Uploading model weights → $full_remote_path"
            ssh "root@${BOARD_IP}" "mkdir -p $(dirname "$full_remote_path")"
            scp "$full_local_path" "root@${BOARD_IP}:$full_remote_path"
        fi
    fi
}

# --- Build + deploy loop ------------------------------------------------------
for demo in "${DEMOS[@]}"; do
    build_one "$demo"
done

for demo in "${DEMOS[@]}"; do
    deploy_one "$demo"
done

if [[ -z "$BOARD_IP" ]]; then
    echo ""
    echo "Build-only mode — no deploy."
    exit 0
fi

echo ""
echo "Done. Restart the demo on the board:"
echo "  ssh root@${BOARD_IP} 'pkill -9 -f \"python3 app\"; cd /opt/demo && python3 app.py'"
echo ""
echo "Then from /IOTCONNECT send launch_drpai <key>, e.g. launch_drpai ${DEMOS[0]}"
