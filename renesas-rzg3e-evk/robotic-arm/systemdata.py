"""System telemetry collector — stdlib + /proc/sys only.

The TRIA build of this file used psutil + py-cpuinfo, but the RZ/G3E's
Yocto Python image strips ``resource`` and ``multiprocessing`` from the
stdlib, which breaks both packages. This rewrite reads the same data
directly from /proc and /sys so the demo runs on minimal embedded
images. The public dataclasses and ``collect_data()`` shape are
unchanged so main.py doesn't need to care."""

import glob
import json
import os
import platform
import re
import time
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class CpuUtilization:
    usage_percent: float
    top_process_name: str
    top_process_cmd: str
    top_process_cpu_percent: float


@dataclass(frozen=True)
class MemoryInfo:
    total: str
    available: str
    used: str
    percent: float
    top_process_name: str
    top_process_cmd: str
    top_process_mem: str


@dataclass(frozen=True)
class StorageInfo:
    total: str
    used: str
    free: str
    percent: float


@dataclass(frozen=True)
class SystemInfo:
    cpu_brand: str
    cpu_vendor: str
    cpu_mhz: str
    cpu_physical_cores: int
    architecture: str
    system: str
    release: str
    platform: str


@dataclass(frozen=True)
class SystemData:
    uptime: str
    system_info: SystemInfo
    cpu: CpuUtilization
    memory: MemoryInfo
    storage: StorageInfo
    hostname: str
    cpu_temp: float       # max of all cpu*-thermal zones, °C
    gpu_temp: float       # max of gpu*-thermal zones, °C (0.0 if none)
    memory_temp: float    # ddr/mem-thermal zone, °C (0.0 if none)
    gpu_usage: float      # GPU busy %, currently QCS6490-only via kgsl


def format_bytes(size_in_bytes) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_in_bytes)
    for unit in units:
        if size < 1024:
            return f"{size:.2f}{unit}"
        size /= 1024
    return f"{size:.2f}{units[-1]}"


def to_display_time(seconds, granularity=2) -> str:
    intervals = (
        ('weeks', 604800),
        ('days', 86400),
        ('hours', 3600),
        ('minutes', 60),
        ('seconds', 1),
    )
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append(f"{int(value)} {name}")
    return ', '.join(result[:granularity])


def _read_text(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _read_int_file(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _read_uptime():
    return float(_read_text('/proc/uptime', '0').split()[0] or 0)


def _read_meminfo():
    info = {}
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                parts = v.strip().split()
                if parts and parts[0].isdigit():
                    info[k] = int(parts[0]) * 1024  # values are in kB
    except OSError:
        pass
    return info


def _read_cpu_jiffies():
    """Total + idle jiffies from the aggregate 'cpu' line of /proc/stat."""
    try:
        with open('/proc/stat') as f:
            line = f.readline()
    except OSError:
        return 0, 0
    parts = line.split()[1:]  # skip the 'cpu' header
    nums = [int(x) for x in parts]
    if len(nums) < 4:
        return 0, 0
    idle = nums[3]
    total = sum(nums)
    return total, idle


def _logical_cpu_count():
    return len(glob.glob('/sys/devices/system/cpu/cpu[0-9]*'))


def _physical_cpu_count():
    """Distinct (physical_id, core_id) pairs from /proc/cpuinfo. ARM kernels
    often omit these fields, in which case we fall back to the logical count."""
    pairs = set()
    cur = {}
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                line = line.strip()
                if not line:
                    if 'physical id' in cur and 'core id' in cur:
                        pairs.add((cur['physical id'], cur['core id']))
                    cur = {}
                    continue
                if ':' in line:
                    k, _, v = line.partition(':')
                    cur[k.strip()] = v.strip()
            if 'physical id' in cur and 'core id' in cur:
                pairs.add((cur['physical id'], cur['core id']))
    except OSError:
        pass
    return len(pairs) or _logical_cpu_count()


def _cpu_brand():
    """Best-effort human-readable CPU label.

    /proc/cpuinfo has 'model name' on x86 but not on most ARM kernels;
    /proc/device-tree/model carries the SoC/board name on device-tree
    platforms; otherwise we decode the ARM implementer + part."""
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                if k.strip() == 'model name':
                    return v.strip()
    except OSError:
        pass

    dt_model = _read_text('/proc/device-tree/model').rstrip('\x00')
    if dt_model:
        return dt_model

    impl = part = None
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                k = k.strip()
                if k == 'CPU implementer':
                    impl = v.strip()
                elif k == 'CPU part':
                    part = v.strip()
                if impl and part:
                    break
    except OSError:
        pass
    arm_parts = {'0xd03': 'Cortex-A53', '0xd05': 'Cortex-A55',
                 '0xd07': 'Cortex-A57', '0xd08': 'Cortex-A72',
                 '0xd09': 'Cortex-A73', '0xd0a': 'Cortex-A75',
                 '0xd0b': 'Cortex-A76', '0xd44': 'Cortex-A78'}
    if impl == '0x41' and part in arm_parts:
        return f"ARM {arm_parts[part]}"
    return platform.processor() or platform.machine() or 'unknown'


def _cpu_vendor():
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                if k.strip() == 'vendor_id':
                    return v.strip()
    except OSError:
        pass
    impl = None
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                if k.strip() == 'CPU implementer':
                    impl = v.strip()
                    break
    except OSError:
        pass
    return {'0x41': 'ARM', '0x4e': 'NVIDIA', '0x51': 'Qualcomm'}.get(impl, 'unknown')


def _cpu_mhz():
    """cpu0 max frequency in MHz, falling back to /proc/cpuinfo's 'cpu MHz'."""
    khz = _read_int_file('/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
    if khz:
        return str(int(khz / 1000))
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                k, _, v = line.partition(':')
                if k.strip() == 'cpu MHz':
                    return str(int(float(v.strip())))
    except OSError:
        pass
    return 'N/A'


def get_system_info():
    return SystemInfo(
        cpu_physical_cores=_physical_cpu_count(),
        cpu_brand=_cpu_brand(),
        cpu_vendor=_cpu_vendor(),
        cpu_mhz=_cpu_mhz(),
        architecture=platform.machine(),
        system=platform.system(),
        release=platform.release(),
        platform=platform.platform()
    )


def _iter_processes():
    """Yield (pid_dir, comm, cmdline, jiffies, vmrss_bytes) for every process
    in /proc. Silently skips entries that disappear or refuse access."""
    for pid_dir in glob.glob('/proc/[0-9]*'):
        try:
            stat = _read_text(f'{pid_dir}/stat')
            if not stat:
                continue
            l = stat.index('(')
            r = stat.rindex(')')
            comm = stat[l + 1:r]
            fields = stat[r + 2:].split()
            jiffies = int(fields[11]) + int(fields[12])  # utime + stime
        except (ValueError, IndexError):
            continue
        cmdline = _read_text(f'{pid_dir}/cmdline').replace('\x00', ' ').strip() or comm
        rss = 0
        try:
            with open(f'{pid_dir}/status') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            rss = int(parts[1]) * 1024
                        break
        except OSError:
            pass
        yield pid_dir, comm, cmdline, jiffies, rss


def get_cpu_usage_percent(interval=0.5):
    """Aggregate CPU usage across all cores between two /proc/stat samples."""
    t1, i1 = _read_cpu_jiffies()
    time.sleep(interval)
    t2, i2 = _read_cpu_jiffies()
    dt = t2 - t1
    if dt <= 0:
        return 0.0
    return round((1.0 - (i2 - i1) / dt) * 100, 1)


def get_top_cpu_process(interval=0.5):
    """Sample /proc twice ``interval`` apart, return the process with the
    largest jiffy delta. Returns (name, cmd, percent_of_one_core)."""
    snap1 = {pid_dir: ticks for pid_dir, _, _, ticks, _ in _iter_processes()}
    time.sleep(interval)
    best_name = "N/A"
    best_cmd = "N/A"
    best_delta = 0
    for pid_dir, comm, cmdline, ticks2, _rss in _iter_processes():
        delta = ticks2 - snap1.get(pid_dir, ticks2)
        if delta > best_delta:
            best_delta = delta
            best_name = comm
            best_cmd = cmdline
    try:
        clk_tck = os.sysconf('SC_CLK_TCK')
    except (ValueError, OSError):
        clk_tck = 100
    pct = round(best_delta / (clk_tck * interval) * 100, 1) if best_delta > 0 else 0.0
    return best_name, best_cmd[:100], pct


def get_top_memory_process():
    best_name = "N/A"
    best_cmd = "N/A"
    best_mem = 0
    for _pid_dir, comm, cmdline, _jiffies, rss in _iter_processes():
        if rss > best_mem:
            best_mem = rss
            best_name = comm
            best_cmd = cmdline
    return best_name, best_cmd[:100], format_bytes(best_mem)


def _disk_usage(path='/'):
    try:
        st = os.statvfs(path)
    except OSError:
        return 0, 0, 0, 0.0
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    pct = round((used / total) * 100, 1) if total > 0 else 0.0
    return total, used, free, pct


def _max_thermal_celsius(type_regex):
    """Return the highest temperature in °C across thermal_zones whose
    `type` matches the regex. Returns 0.0 if no zone matches."""
    pattern = re.compile(type_regex)
    best = None
    for zone in glob.glob('/sys/class/thermal/thermal_zone*'):
        zone_type = _read_text(os.path.join(zone, 'type'))
        if not pattern.match(zone_type):
            continue
        temp_mc = _read_int_file(os.path.join(zone, 'temp'))
        if temp_mc is None:
            continue
        if best is None or temp_mc > best:
            best = temp_mc
    return round(best / 1000.0, 1) if best is not None else 0.0


def get_gpu_usage_percent():
    """Adreno GPU busy %. Returns 0.0 on boards without /sys/class/kgsl."""
    try:
        with open('/sys/class/kgsl/kgsl-3d0/gpubusy') as f:
            parts = f.read().strip().split()
        busy, total = int(parts[0]), int(parts[1])
        if total <= 0:
            return 0.0
        return round(min(100.0, busy * 100.0 / total), 1)
    except (OSError, ValueError, IndexError):
        return 0.0


def collect_data() -> SystemData:
    cpu_pct_total = get_cpu_usage_percent()
    cpu_name, cpu_cmd, cpu_pct = get_top_cpu_process()
    mem_name, mem_cmd, mem_used_str = get_top_memory_process()
    mem = _read_meminfo()
    total = mem.get('MemTotal', 0)
    available = mem.get('MemAvailable', mem.get('MemFree', 0))
    used = max(0, total - available)
    mem_pct = round((used / total) * 100, 1) if total > 0 else 0.0
    disk_total, disk_used, disk_free, disk_pct = _disk_usage('/')

    return SystemData(
        uptime=to_display_time(_read_uptime()),
        system_info=get_system_info(),
        cpu=CpuUtilization(
            usage_percent=cpu_pct_total,
            top_process_name=cpu_name,
            top_process_cmd=cpu_cmd,
            top_process_cpu_percent=cpu_pct,
        ),
        memory=MemoryInfo(
            total=format_bytes(total),
            available=format_bytes(available),
            used=format_bytes(used),
            percent=mem_pct,
            top_process_name=mem_name,
            top_process_cmd=mem_cmd,
            top_process_mem=mem_used_str,
        ),
        storage=StorageInfo(
            total=format_bytes(disk_total),
            used=format_bytes(disk_used),
            free=format_bytes(disk_free),
            percent=disk_pct,
        ),
        hostname=os.uname().nodename,
        cpu_temp=_max_thermal_celsius(r'^cpu\d*[-_]?thermal$'),
        gpu_temp=_max_thermal_celsius(r'^gpu\w*[-_]?thermal$'),
        memory_temp=_max_thermal_celsius(r'^(ddr|mem|memory)[-_]?thermal$'),
        gpu_usage=get_gpu_usage_percent(),
    )


if __name__ == "__main__":
    print(json.dumps(asdict(collect_data())))
