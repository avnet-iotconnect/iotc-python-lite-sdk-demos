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

ssh root@"$BOARD_IP" "rm -f output*.bmp *.elf"
rm -f hls_output/*.elf

echo "Compiling w/HW module"
run_shls -a soc_sw_compile_accel

echo "Compiling SW-only"
run_shls -a soc_sw_compile_no_accel
