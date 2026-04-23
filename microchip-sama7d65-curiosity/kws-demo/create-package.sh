#!/bin/bash

set -e

SRC_DIR="./src"
ARCHIVE_NAME="package.zip"
STAGING_DIR="/tmp/sama7d65-kws-package"
PACKAGES_DIR="./packages"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

cp -r "$SRC_DIR"/. "$STAGING_DIR/"
find "$STAGING_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$STAGING_DIR" -type f -name "*.pyc" -delete

python3 - <<PY
from pathlib import Path
import zipfile

staging_dir = Path("$STAGING_DIR")
archive_path = Path("$ARCHIVE_NAME")

with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(staging_dir.rglob("*")):
        if path.is_dir():
            continue
        archive.write(path, arcname=path.relative_to(staging_dir).as_posix())
PY

cp "./$ARCHIVE_NAME" ../../common/
mkdir -p "$PACKAGES_DIR"
cp "./$ARCHIVE_NAME" "$PACKAGES_DIR/kws-demo-package.zip"

rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the repo common and local packages directories."
