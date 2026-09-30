#!/bin/sh
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Fetch the three OpenCV Zoo models the demo needs into ./models (idempotent).
# Uses python3's urllib because the BusyBox wget on the RZ/G3E image does not
# validate TLS certificates and has no resume support.

set -e
cd "$(dirname "$0")"
mkdir -p models

BASE="https://github.com/opencv/opencv_zoo/raw/main/models"

fetch() {
    # $1 = zoo sub-path, $2 = file name, $3 = expected minimum size in bytes
    if [ -f "models/$2" ] && [ "$(wc -c < "models/$2")" -ge "$3" ]; then
        echo "  - $2: present"
        return
    fi
    echo "  - $2: downloading..."
    python3 - "$BASE/$1/$2" "models/$2" "$3" <<'EOF'
import sys, urllib.request, os
url, dst, min_size = sys.argv[1], sys.argv[2], int(sys.argv[3])
tmp = dst + '.part'
with urllib.request.urlopen(url, timeout=60) as r, open(tmp, 'wb') as f:
    total = 0
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
        total += len(chunk)
if total < min_size:
    os.remove(tmp)
    sys.exit(f'download of {url} is too small ({total} bytes) - Git LFS pointer instead of the model?')
os.replace(tmp, dst)
print(f'    {total} bytes')
EOF
}

echo "Fetching OpenCV Zoo models..."
fetch face_detection_yunet    face_detection_yunet_2023mar.onnx      200000
fetch face_recognition_sface  face_recognition_sface_2021dec.onnx  38000000
fetch object_detection_nanodet object_detection_nanodet_2022nov.onnx 3700000
echo "Models ready in $(pwd)/models"
