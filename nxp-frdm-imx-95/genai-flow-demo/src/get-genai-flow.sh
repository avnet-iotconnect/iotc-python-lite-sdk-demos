#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
#
# Fetch NXP eIQ GenAI Flow (eiq_genai_flow + vlm) straight onto the board -
# no git, no Git LFS, no host PC. Uses only curl and tar (both on the image).
#
#   curl -sL https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/nxp-frdm-imx-95/genai-flow-demo/src/get-genai-flow.sh | bash
#
# Why: GitHub's "Download ZIP" and the source tarball contain 130-byte Git LFS
# *pointer* files in place of the compiled cpython-313 modules and models
# (62 files, ~1.5 GB). Installing from such a tree fails with e.g.
# "No module named 'shared_utils'". This script extracts the source tree and
# then replaces every pointer with the real file from GitHub's LFS media
# endpoint, verifying each file's size against its pointer.
set -e
REPO=nxp-appcodehub/dm-eiq-genai-flow-demonstrator
BRANCH=release/v3.0
MEDIA=https://media.githubusercontent.com/media/$REPO/$BRANCH
DEST=${DEST:-/root}

cd "$DEST"
for d in eiq_genai_flow vlm; do
    if [ -d "$d" ]; then
        echo "moving existing $d aside -> $d.old"
        rm -rf "$d.old"; mv "$d" "$d.old"
    fi
done

echo "downloading source tree ($BRANCH)..."
curl -sL --retry 3 "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" -o egf-src.tgz
tar -xzf egf-src.tgz --wildcards '*/eiq_genai_flow/*' '*/vlm/*'
SRC=$(ls -d dm-eiq-genai-flow-demonstrator-*/ | head -1)
mv "$SRC/eiq_genai_flow" "$SRC/vlm" "$DEST/"
rm -rf "$SRC" egf-src.tgz

fail=0
for d in eiq_genai_flow vlm; do
    cd "$DEST/$d"
    grep -rl '^version https://git-lfs.github.com/spec/v1' . | sort | while read -r f; do
        rel=${f#./}
        want=$(grep '^size ' "$f" | awk '{print $2}')
        curl -sL --retry 3 "$MEDIA/$d/$rel" -o "$f" || true
        got=$(stat -c%s "$f")
        if [ "$got" = "$want" ]; then
            awk -v b="$got" -v n="$d/$rel" 'BEGIN{printf "OK   %8.1f MB  %s\n", b/1048576, n}'
        else
            echo "FAIL $d/$rel (got $got, expected $want bytes)"; touch "$DEST/.egf-fetch-failed"
        fi
    done
done

left=$(grep -rl '^version https://git-lfs.github.com/spec/v1' "$DEST/eiq_genai_flow" "$DEST/vlm" | wc -l)
if [ -f "$DEST/.egf-fetch-failed" ] || [ "$left" != "0" ]; then
    rm -f "$DEST/.egf-fetch-failed"
    echo "!! $left LFS file(s) could not be fetched - check the board's internet access and re-run this script"
    exit 1
fi
echo ""
echo "eIQ GenAI Flow fetched to $DEST/eiq_genai_flow and $DEST/vlm - all LFS files resolved."
echo "Next:  cd /root/eiq_genai_flow && ./install.sh      (then: cd /root/vlm && ./install.sh)"
