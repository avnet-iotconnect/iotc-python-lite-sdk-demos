#!/bin/bash

set -euo pipefail

if [[ -z "${BOARD_IP:-}" ]]; then
  echo "Error: BOARD_IP is not set. Example: export BOARD_IP=192.168.1.123" >&2
  exit 1
fi

run_shls() {
  if command -v shls >/dev/null 2>&1; then
    shls "$@"
    return
  fi

  local shls_bat="${SHLS_BAT:-}"
  if [[ -z "$shls_bat" && -n "${SHLS_BIN:-}" ]]; then
    shls_bat="$SHLS_BIN/shls.bat"
  fi
  if [[ -z "$shls_bat" ]]; then
    shls_bat="/c/Microchip/Libero_SoC_2025.1/SmartHLS/SmartHLS/bin/shls.bat"
  fi

  if [[ -f "$shls_bat" ]]; then
    local shls_bat_win
    shls_bat_win="$(cygpath -w "$shls_bat" 2>/dev/null || echo "$shls_bat")"
    cmd.exe /c "\"$shls_bat_win\" $*"
    return
  fi

  echo "Error: shls not found. Add shls to PATH or set SHLS_BAT/SHLS_BIN." >&2
  exit 1
}

echo "---------------------"
echo "Run SW-only"
RISCV_BINARY_NAME=invert_and_threshold.no_accel.elf run_shls -s soc_accel_proj_run -r invert_and_threshold.no_accel.elf

echo "---------------------"
echo "Run w/HW module"
RISCV_BINARY_NAME=invert_and_threshold.accel.elf run_shls -s soc_accel_proj_run -r invert_and_threshold.accel.elf
