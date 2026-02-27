#!/bin/bash
set -euo pipefail

SRC_DIR="./src"
ARCHIVE_NAME="package.tar.gz"
SW_ELF="${SRC_DIR}/runtimes/tinyml_nn.no_accel.elf"
HW_ELF="${SRC_DIR}/runtimes/tinyml_nn.accel.elf"

if [[ ! -f "${SW_ELF}" || ! -f "${HW_ELF}" ]]; then
  echo "ERROR: Missing required NN ELF(s)."
  echo "Expected:"
  echo "  - ${SW_ELF}"
  echo "  - ${HW_ELF}"
  exit 1
fi

tar -czf "$ARCHIVE_NAME" -C "$SRC_DIR" .
cp "$ARCHIVE_NAME" ../../common/
echo "Created $ARCHIVE_NAME (also copied to ../../common/)"
