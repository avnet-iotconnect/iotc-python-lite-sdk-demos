#!/bin/bash

VIDEO_UPLOAD_LIBS_DIR="${VIDEO_UPLOAD_LIBS_DIR:-$HOME/kvs-libs-imx93}"
SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
STAGING_DIR="/tmp/file-upload-package-staging"
ARCHIVE_LIBS_DIR="$STAGING_DIR/archive-libs"

copy_required_libs() {
  local source_dir="$1"
  local copied=0

  if [ -f "$source_dir/libgstx264.so" ]; then
    cp "$source_dir/libgstx264.so" "$STAGING_DIR/libs/"
    copied=1
  fi

  if ls "$source_dir"/libx264.so* > /dev/null 2>&1; then
    cp "$source_dir"/libx264.so* "$STAGING_DIR/libs/"
    copied=1
  fi

  return $(( copied == 0 ))
}

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

cp -r "$SRC_DIR"/. "$STAGING_DIR/"
find "$STAGING_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$STAGING_DIR" -type f -name "*.pyc" -delete
mkdir -p "$STAGING_DIR/libs"

if copy_required_libs "$VIDEO_UPLOAD_LIBS_DIR"; then
  echo "Bundled $(ls "$STAGING_DIR/libs/" | wc -l) library files from $VIDEO_UPLOAD_LIBS_DIR."
elif [ -f "$ARCHIVE_NAME" ]; then
  echo "Using bundled libraries from existing $ARCHIVE_NAME."
  mkdir -p "$ARCHIVE_LIBS_DIR"
  tar -xzf "$ARCHIVE_NAME" -C "$ARCHIVE_LIBS_DIR" ./libs
  if copy_required_libs "$ARCHIVE_LIBS_DIR/libs"; then
    echo "ERROR: Existing $ARCHIVE_NAME does not contain the required x264 libraries."
    exit 1
  fi
  echo "Bundled $(ls "$STAGING_DIR/libs/" | wc -l) library files from existing archive."
else
  echo "ERROR: No .so files found in $VIDEO_UPLOAD_LIBS_DIR and no existing $ARCHIVE_NAME available."
  exit 1
fi

tar -czf "$ARCHIVE_NAME" -C "$STAGING_DIR" .
cp "$ARCHIVE_NAME" ../../common/

rm -rf "$STAGING_DIR"

echo "Created archive $ARCHIVE_NAME and copied it into the common directory."
