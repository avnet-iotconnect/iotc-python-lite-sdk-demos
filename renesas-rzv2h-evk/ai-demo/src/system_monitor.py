# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""System performance monitoring for the RZ/V2H — reads /proc and /sys directly,
no psutil dependency required on the Yocto image."""

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
    """Return overall CPU usage percentage over a short sample interval."""
    idle1, total1 = _read_cpu_stat()
    time.sleep(interval)
    idle2, total2 = _read_cpu_stat()
    delta_total = total2 - total1
    if delta_total == 0:
        return 0.0
    return round(100.0 * (1.0 - (idle2 - idle1) / delta_total), 1)


def get_memory_percent() -> float:
    """Return RAM usage as a percentage of total memory."""
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(':')] = int(parts[1])
    total = info.get('MemTotal', 1)
    available = info.get('MemAvailable', total)
    return round(100.0 * (total - available) / total, 1)


def get_memory_used_mb() -> float:
    """Return used RAM in MB."""
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(':')] = int(parts[1])
    total = info.get('MemTotal', 0)
    available = info.get('MemAvailable', total)
    return round((total - available) / 1024.0, 1)


def get_cpu_temps() -> tuple:
    """Return (temp_zone0_c, temp_zone1_c) in degrees Celsius.

    The RZ/V2H exposes two thermal zones:
        thermal_zone0: cpu-thermal0 (Cortex-A55 cluster)
        thermal_zone1: cpu-thermal1 (Cortex-A76 cluster)
    """
    temps = []
    for i in range(2):
        try:
            with open(f'/sys/class/thermal/thermal_zone{i}/temp') as f:
                temps.append(round(int(f.read().strip()) / 1000.0, 1))
        except Exception:
            temps.append(0.0)
    while len(temps) < 2:
        temps.append(0.0)
    return temps[0], temps[1]


def get_drpai_present() -> bool:
    """Return True if the DRP-AI device node is accessible."""
    return os.path.exists('/dev/drpai0')


def get_all_metrics() -> dict:
    """Collect and return all system metrics in one call."""
    temp0, temp1 = get_cpu_temps()
    return {
        'cpu_percent': get_cpu_percent(),
        'memory_percent': get_memory_percent(),
        'memory_used_mb': get_memory_used_mb(),
        'cpu_temp_0_c': temp0,
        'cpu_temp_1_c': temp1,
        'drpai_present': get_drpai_present(),
    }
