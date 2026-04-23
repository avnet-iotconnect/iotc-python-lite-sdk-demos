#!/bin/bash
set -euo pipefail

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
SW_ELF="${SRC_DIR}/runtimes/tinyml_complex.no_accel.elf"
HW_ELF="${SRC_DIR}/runtimes/tinyml_complex.accel.elf"
S3_BASE="https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files"

if [[ ! -f "${SW_ELF}" || ! -f "${HW_ELF}" ]]; then
  echo "ELF files not found locally. Downloading from S3..."
  mkdir -p "${SRC_DIR}/runtimes"
  wget -q --show-progress -O "${SW_ELF}" "${S3_BASE}/tinyml_complex.no_accel.elf"
  wget -q --show-progress -O "${HW_ELF}" "${S3_BASE}/tinyml_complex.accel.elf"
fi

tar -czf "$ARCHIVE_NAME" -C "$SRC_DIR" .
cp "$ARCHIVE_NAME" ../../common/
echo "Created $ARCHIVE_NAME (also copied to ../../common/)"
