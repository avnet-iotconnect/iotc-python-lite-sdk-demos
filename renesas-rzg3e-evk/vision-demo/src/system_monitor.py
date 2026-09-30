# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""System metrics for the RZ/G3E — reads /proc and /sys directly (no psutil on Yocto)."""

import os
import time


def _read_cpu_stat():
    with open('/proc/stat') as f:
        fields = f.readline().split()
    idle = int(fields[4])
    iowait = int(fields[5])
    total = sum(int(x) for x in fields[1:])
    return idle + iowait, total


def get_cpu_percent(interval: float = 0.2) -> float:
    """Overall CPU usage percentage over a short sample interval."""
    idle1, total1 = _read_cpu_stat()
    time.sleep(interval)
    idle2, total2 = _read_cpu_stat()
    delta_total = total2 - total1
    if delta_total == 0:
        return 0.0
    return round(100.0 * (1.0 - (idle2 - idle1) / delta_total), 1)


def _meminfo() -> dict:
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(':')] = int(parts[1])
    return info


def get_memory() -> tuple:
    """Return (used_percent, used_mb)."""
    info = _meminfo()
    total = info.get('MemTotal', 1)
    available = info.get('MemAvailable', total)
    used = total - available
    return round(100.0 * used / total, 1), round(used / 1024.0, 1)


def get_cpu_temp() -> float:
    """Cortex-A55 cluster temperature (thermal_zone0 = cpu-thermal on the RZ/G3E)."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return 0.0


def get_load_1m() -> float:
    try:
        return round(os.getloadavg()[0], 2)
    except Exception:
        return 0.0


def get_all_metrics() -> dict:
    mem_pct, mem_mb = get_memory()
    return {
        'cpu_percent': get_cpu_percent(),
        'memory_percent': mem_pct,
        'memory_used_mb': mem_mb,
        'cpu_temp_c': get_cpu_temp(),
        'load_1m': get_load_1m(),
    }
