# SPDX-License-Identifier: MIT
#
# Cloud-driven Complex-NN demo for PolarFire SoC Discovery Kit.
# Command: "classify" (e.g. args: ["hw", "4", "42"] or ["mode=hw","class=4","seed=42"])

import json
import multiprocessing
import os
import pathlib
import random
import shutil
import sys
import threading
import time
import urllib.request

import requests
from avnet.iotconnect.sdk.lite import Callbacks, C2dCommand, Client, DeviceConfig, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

import ml_runner

COMMAND_CLASSIFY = "classify"
COMMAND_FILE_DOWNLOAD = "file-download"
COMMAND_STATUS = "status"
COMMAND_LED = "led"
COMMAND_LEDS = "leds"
COMMAND_BENCH = "bench"
COMMAND_LOAD = "load"

c = None
LAST_STATUS_TS = 0.0
STATUS_PERIOD_S = 15.0
LED_PATTERN_THREAD = None
LED_PATTERN_STOP = None
LOAD_PROCESSES = []
LOAD_STOP_EVENT = None
LOAD_WORKERS = 0
LOAD_DUTY = 0
LOAD_BACKEND = "python-multiprocessing"
JOB_LOCK = threading.Lock()
ACTIVE_JOB = None
MAX_ML_BATCH = 1024
RANDOM_CLASS_CHOICES = (0, 1, 2)
RANDOM_SEED_MIN = 1
RANDOM_SEED_MAX = 1000


def _clean_args(args):
    return [str(a).strip() for a in (args or []) if str(a).strip() != ""]


def _require_args(cmd: str, args, usage: str):
    clean = _clean_args(args)
    if not clean:
        raise ValueError(f"{cmd} requires arguments. Usage: {usage}")
    return clean


def _safe_read(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def _cpu_usage_percent(sample_s: float = 0.15):
    def read_cpu_line():
        line = _safe_read("/proc/stat")
        if not line:
            return None
        first = line.splitlines()[0].split()
        if len(first) < 5 or first[0] != "cpu":
            return None
        vals = [int(x) for x in first[1:8]]
        idle = vals[3] + vals[4]
        total = sum(vals)
        return total, idle

    s0 = read_cpu_line()
    if s0 is None:
        return None
    time.sleep(sample_s)
    s1 = read_cpu_line()
    if s1 is None:
        return None

    dt = s1[0] - s0[0]
    didle = s1[1] - s0[1]
    if dt <= 0:
        return None
    return round((1.0 - (float(didle) / float(dt))) * 100.0, 2)


def _meminfo():
    out = {}
    raw = _safe_read("/proc/meminfo")
    if not raw:
        return out
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        try:
            out[k.strip()] = int(v.strip().split()[0])
        except Exception:
            pass
    return out


def _thermal_readings():
    zones = []
    base = pathlib.Path("/sys/class/thermal")
    for temp_path in sorted(base.glob("thermal_zone*/temp")):
        zone_dir = temp_path.parent
        temp_raw = _safe_read(str(temp_path))
        if temp_raw is None:
            continue
        try:
            t = float(temp_raw)
            temp_c = t / 1000.0 if t > 1000 else t
        except Exception:
            continue
        zones.append(
            {
                "name": zone_dir.name,
                "type": _safe_read(str(zone_dir / "type")) or "unknown",
                "temp_c": round(temp_c, 2),
            }
        )
    return zones


def _led_list():
    leds = []
    base = pathlib.Path("/sys/class/leds")
    if not base.exists():
        return leds
    for idx, led in enumerate(sorted(base.iterdir(), key=lambda p: p.name)):
        if not led.is_dir():
            continue
        brightness = _safe_read(str(led / "brightness"))
        max_brightness = _safe_read(str(led / "max_brightness"))
        trigger = _safe_read(str(led / "trigger"))
        try:
            b = int(brightness) if brightness is not None else None
        except Exception:
            b = None
        try:
            mb = int(max_brightness) if max_brightness is not None else 1
        except Exception:
            mb = 1
        leds.append(
            {
                "index": idx,
                "name": led.name,
                "brightness": b if b is not None else 0,
                "max_brightness": mb,
                "state": "on" if (b is not None and b > 0) else "off",
                "trigger": trigger,
            }
        )
    return leds


def _visible_leds():
    def sort_key(name: str):
        digits = "".join(ch for ch in name if ch.isdigit())
        return (int(digits) if digits else 9999, name)

    leds = _led_list()
    if not leds:
        return []
    named = sorted([x for x in leds if x["name"].lower().startswith("led")], key=lambda x: sort_key(x["name"]))
    if len(named) >= 8:
        return named[:8]
    return sorted(leds, key=lambda x: sort_key(x["name"]))[:8]


def _leds_state_string():
    visible = _visible_leds()
    if len(visible) < 8:
        return None
    bits = []
    for led in visible:
        bits.append("1" if int(led.get("brightness", 0)) > 0 else "0")
    return "".join(bits)


def _set_leds_from_bitstring(bits: str):
    visible = _visible_leds()
    if len(visible) < 8:
        raise RuntimeError("Expected at least 8 visible LEDs")
    b = bits.strip()
    if len(b) != 8 or any(ch not in "01" for ch in b):
        raise ValueError("LED bitstring must be exactly 8 chars of 0/1")
    for idx, ch in enumerate(b):
        led = visible[idx]
        _set_led_state(led["name"], "on" if ch == "1" else "off")
    return _leds_state_string()


def _resolve_led(token: str):
    leds = _led_list()
    if not leds:
        raise RuntimeError("No LED sysfs entries found under /sys/class/leds")
    if token is None or token == "":
        raise ValueError("LED target is required")
    if str(token).isdigit():
        idx = int(token)
        if idx < 0 or idx >= len(leds):
            raise ValueError(f"LED index out of range: {idx}")
        return leds[idx]
    token = str(token).strip()
    for led in leds:
        if led["name"] == token:
            return led
    raise ValueError(f"LED not found: {token}")


def _set_led_state(led_name: str, value: str):
    led_dir = pathlib.Path("/sys/class/leds") / led_name
    trigger_path = led_dir / "trigger"
    bright_path = led_dir / "brightness"
    max_path = led_dir / "max_brightness"
    max_b = _safe_read(str(max_path))
    try:
        max_bi = int(max_b) if max_b is not None else 1
    except Exception:
        max_bi = 1

    if trigger_path.exists():
        try:
            with open(trigger_path, "w", encoding="utf-8") as f:
                f.write("none")
        except Exception:
            pass

    v = str(value).strip().lower()
    if v in ("on", "1", "true", "high"):
        out_b = max_bi
    elif v in ("off", "0", "false", "low"):
        out_b = 0
    elif v in ("toggle",):
        cur = _safe_read(str(bright_path))
        try:
            out_b = 0 if int(cur) > 0 else max_bi
        except Exception:
            out_b = max_bi
    else:
        out_b = int(v)
        if out_b < 0:
            out_b = 0
        if out_b > max_bi:
            out_b = max_bi

    with open(bright_path, "w", encoding="utf-8") as f:
        f.write(str(out_b))

    return {
        "name": led_name,
        "brightness": out_b,
        "max_brightness": max_bi,
        "state": "on" if out_b > 0 else "off",
    }


def _set_led_brightness_raw(led_name: str, brightness: int):
    led_dir = pathlib.Path("/sys/class/leds") / led_name
    trigger_path = led_dir / "trigger"
    bright_path = led_dir / "brightness"
    max_path = led_dir / "max_brightness"
    max_b = _safe_read(str(max_path))
    try:
        max_bi = int(max_b) if max_b is not None else 1
    except Exception:
        max_bi = 1

    if trigger_path.exists():
        try:
            with open(trigger_path, "w", encoding="utf-8") as f:
                f.write("none")
        except Exception:
            pass

    out_b = int(brightness)
    if out_b < 0:
        out_b = 0
    if out_b > max_bi:
        out_b = max_bi
    with open(bright_path, "w", encoding="utf-8") as f:
        f.write(str(out_b))


def _sleep_or_stop(stop_event: threading.Event, seconds: float):
    return stop_event.wait(timeout=max(0.0, seconds))


def _stop_led_pattern():
    global LED_PATTERN_THREAD, LED_PATTERN_STOP
    if LED_PATTERN_STOP is not None:
        LED_PATTERN_STOP.set()
    if LED_PATTERN_THREAD is not None and LED_PATTERN_THREAD.is_alive():
        LED_PATTERN_THREAD.join(timeout=1.5)
    LED_PATTERN_THREAD = None
    LED_PATTERN_STOP = None


def _start_led_pattern(pattern_name: str, cycles: int = 16, interval_ms: int = 120, level: int = None):
    global LED_PATTERN_THREAD, LED_PATTERN_STOP

    leds = _led_list()
    if not leds:
        raise RuntimeError("No LED sysfs entries found under /sys/class/leds")
    if cycles < 1:
        cycles = 1
    if interval_ms < 20:
        interval_ms = 20

    _stop_led_pattern()
    stop_event = threading.Event()
    names = [x["name"] for x in leds]
    max_by_name = {x["name"]: x["max_brightness"] for x in leds}
    interval_s = float(interval_ms) / 1000.0

    def on_level(name: str):
        if level is not None:
            try:
                return max(0, min(int(level), int(max_by_name.get(name, 1))))
            except Exception:
                pass
        return int(max_by_name.get(name, 1))

    def worker():
        try:
            for _ in range(cycles):
                if stop_event.is_set():
                    break

                p = pattern_name.lower()
                if p == "blink":
                    for n in names:
                        _set_led_brightness_raw(n, on_level(n))
                    if _sleep_or_stop(stop_event, interval_s):
                        break
                    for n in names:
                        _set_led_brightness_raw(n, 0)
                    if _sleep_or_stop(stop_event, interval_s):
                        break
                elif p == "alternate":
                    for idx, n in enumerate(names):
                        _set_led_brightness_raw(n, on_level(n) if (idx % 2 == 0) else 0)
                    if _sleep_or_stop(stop_event, interval_s):
                        break
                    for idx, n in enumerate(names):
                        _set_led_brightness_raw(n, on_level(n) if (idx % 2 == 1) else 0)
                    if _sleep_or_stop(stop_event, interval_s):
                        break
                else:  # chase (default)
                    for idx, n in enumerate(names):
                        _set_led_brightness_raw(n, on_level(n) if idx == 0 else 0)
                    for idx in range(len(names)):
                        if stop_event.is_set():
                            break
                        for led_idx, n in enumerate(names):
                            _set_led_brightness_raw(n, on_level(n) if led_idx == idx else 0)
                        if _sleep_or_stop(stop_event, interval_s):
                            break

            for n in names:
                _set_led_brightness_raw(n, 0)
        except Exception as ex:
            print("LED pattern thread failed:", ex)

    LED_PATTERN_STOP = stop_event
    LED_PATTERN_THREAD = threading.Thread(target=worker, name="led-pattern", daemon=True)
    LED_PATTERN_THREAD.start()


def _cpu_load_worker(stop_event, duty_pct: int):
    duty = max(1, min(int(duty_pct), 100))
    period_s = 0.1
    busy_s = period_s * (float(duty) / 100.0)
    idle_s = max(0.0, period_s - busy_s)
    x = 1
    while not stop_event.is_set():
        t0 = time.time()
        while (time.time() - t0) < busy_s and not stop_event.is_set():
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        if idle_s > 0.0 and stop_event.wait(idle_s):
            break


def _load_active():
    global LOAD_PROCESSES, LOAD_STOP_EVENT, LOAD_WORKERS, LOAD_DUTY
    if not LOAD_PROCESSES:
        return False
    alive = [p for p in LOAD_PROCESSES if p.is_alive()]
    if alive:
        LOAD_PROCESSES = alive
        return True
    for p in LOAD_PROCESSES:
        try:
            p.join(timeout=0.05)
        except Exception:
            pass
    LOAD_PROCESSES = []
    LOAD_STOP_EVENT = None
    LOAD_WORKERS = 0
    LOAD_DUTY = 0
    return False


def _stop_load():
    global LOAD_PROCESSES, LOAD_STOP_EVENT, LOAD_WORKERS, LOAD_DUTY
    if LOAD_STOP_EVENT is not None:
        try:
            LOAD_STOP_EVENT.set()
        except Exception:
            pass
    for p in LOAD_PROCESSES:
        try:
            if p.is_alive():
                p.join(timeout=1.5)
            if p.is_alive():
                p.terminate()
                p.join(timeout=1.0)
        except Exception:
            pass
    LOAD_PROCESSES = []
    LOAD_STOP_EVENT = None
    LOAD_WORKERS = 0
    LOAD_DUTY = 0


def _start_load(workers: int, duty_pct: int):
    global LOAD_PROCESSES, LOAD_STOP_EVENT, LOAD_WORKERS, LOAD_DUTY
    w = max(1, min(int(workers), 8))
    d = max(1, min(int(duty_pct), 100))
    _stop_load()
    # Use spawn context to avoid forking a multithreaded process.
    mp_ctx = multiprocessing.get_context("spawn")
    stop_event = mp_ctx.Event()
    procs = []
    for i in range(w):
        p = mp_ctx.Process(
            target=_cpu_load_worker,
            args=(stop_event, d),
            name=f"cpu-load-{i}",
            daemon=True,
        )
        p.start()
        procs.append(p)
    time.sleep(0.1)
    if not any(p.is_alive() for p in procs):
        raise RuntimeError("Python multiprocessing load workers failed to start.")
    LOAD_STOP_EVENT = stop_event
    LOAD_PROCESSES = procs
    LOAD_WORKERS = w
    LOAD_DUTY = d


def parse_load_args(args):
    args = _require_args("load", args, "load <start|stop|status|off> [workers] [duty_pct]")
    action = "status"
    workers = 1
    duty = 95

    if len(args) == 1 and args[0].strip().startswith("{"):
        payload = json.loads(args[0])
        action = str(payload.get("action", action)).lower()
        workers = int(payload.get("workers", workers))
        duty = int(payload.get("duty", payload.get("duty_pct", duty)))
    else:
        positional = []
        for raw in args:
            token = raw.strip().lower()
            if "=" in token:
                k, v = token.split("=", 1)
                if k == "action":
                    action = v
                elif k in ("workers", "w"):
                    workers = int(v)
                elif k in ("duty", "duty_pct"):
                    duty = int(v)
                else:
                    raise ValueError(f"Unsupported load key: {k}")
            else:
                positional.append(token)
        if positional:
            action = positional[0]
        if len(positional) > 1:
            workers = int(positional[1])
        if len(positional) > 2:
            duty = int(positional[2])

    if action in ("off", "disable"):
        action = "stop"
    if action in ("on", "enable"):
        action = "start"
    if action not in ("start", "stop", "status"):
        raise ValueError("load action must be start|stop|status|off")
    return action, workers, duty


def _status_payload(include_leds: bool = False):
    mem = _meminfo()
    thermals = _thermal_readings()
    du = shutil.disk_usage("/")
    uptime = _safe_read("/proc/uptime")
    loadavg = _safe_read("/proc/loadavg")

    payload = {
        "event": "device_status",
        "sdk_version": SDK_VERSION,
        "uptime_s": float(uptime.split()[0]) if uptime else None,
        "load_1m": float(loadavg.split()[0]) if loadavg else None,
        "load_5m": float(loadavg.split()[1]) if loadavg else None,
        "load_15m": float(loadavg.split()[2]) if loadavg else None,
        "cpu_usage_pct": _cpu_usage_percent(),
        "mem_total_kb": mem.get("MemTotal"),
        "mem_available_kb": mem.get("MemAvailable"),
        "mem_free_kb": mem.get("MemFree"),
        "disk_total_mb": round(du.total / (1024 * 1024), 2),
        "disk_free_mb": round(du.free / (1024 * 1024), 2),
        "thermal_zone_count": len(thermals),
    }

    if thermals:
        hottest = max(thermals, key=lambda z: z["temp_c"])
        payload["temp_max_c"] = hottest["temp_c"]
        payload["temp_max_zone"] = hottest["type"]

    if include_leds:
        payload["led_count"] = len(_visible_leds())
        payload["leds"] = _leds_state_string()

    active = _load_active()
    payload["load_active"] = active
    payload["load_workers"] = LOAD_WORKERS if active else 0
    payload["load_duty_pct"] = LOAD_DUTY if active else 0
    payload["load_backend"] = LOAD_BACKEND

    return payload


def parse_status_args(args):
    args = _require_args("status", args, "status <basic|full|include_leds=true|false>")
    include_leds = False

    if len(args) == 1 and args[0].strip().startswith("{"):
        payload = json.loads(args[0])
        include_leds = bool(payload.get("include_leds", include_leds))
        return include_leds

    for raw in args:
        token = raw.strip().lower()
        if token in ("full", "leds", "include_leds"):
            include_leds = True
        elif token in ("basic", "noleds"):
            include_leds = False
        elif token in ("1", "true", "on", "yes"):
            include_leds = True
        elif token in ("0", "false", "off", "no"):
            include_leds = False
        elif token.startswith("include_leds="):
            val = token.split("=", 1)[1]
            include_leds = val in ("1", "true", "yes", "on")
        else:
            raise ValueError("status argument must be basic|full|include_leds=true|false")

    return include_leds


def parse_led_args(args):
    args = _require_args(
        "led",
        args,
        "led <get|set|setbits|pattern|stop|list> ... ; ex: 'led get' or 'led 10101010'",
    )
    action = "get"
    target = None
    value = None
    extra = []

    if len(args) == 1 and args[0].strip().startswith("{"):
        payload = json.loads(args[0])
        action = str(payload.get("action", action)).lower()
        target = payload.get("led", payload.get("name", payload.get("index")))
        value = payload.get("value", payload.get("state"))
        if payload.get("leds") is not None:
            action = "setbits"
            value = str(payload.get("leds"))
        if payload.get("pattern"):
            action = "pattern"
            target = payload.get("pattern")
            value = payload.get("cycles", value)
            if payload.get("interval_ms") is not None:
                extra.append(str(payload.get("interval_ms")))
            if payload.get("level") is not None:
                extra.append(str(payload.get("level")))
        return action, target, value, extra

    positional = []
    for raw in args:
        token = raw.strip()
        if "=" in token:
            k, v = token.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k in ("action", "cmd"):
                action = v.lower()
            elif k in ("led", "name", "index", "target"):
                target = v
            elif k in ("value", "state"):
                value = v
            elif k in ("pattern",):
                action = "pattern"
                target = v
            elif k in ("cycles",):
                value = v
            elif k in ("interval", "interval_ms", "speed"):
                extra.append(v)
            elif k in ("level", "brightness"):
                if len(extra) == 0:
                    extra.append("120")
                extra.append(v)
            else:
                raise ValueError(f"Unsupported LED argument key: {k}")
        else:
            positional.append(token)

    if positional:
        a0 = positional[0].lower()
        if a0 in ("list", "get", "state", "set", "toggle", "pattern", "stop", "on", "off"):
            action = a0
            if len(positional) > 1:
                target = positional[1]
            if len(positional) > 2:
                value = positional[2]
            if len(positional) > 3:
                extra = positional[3:]
        elif len(a0) == 8 and all(ch in "01" for ch in a0):
            action = "setbits"
            value = a0
        else:
            action = "get"
            target = positional[0]
            if len(positional) > 1:
                value = positional[1]

    if action == "state":
        action = "get"
    if action in ("on", "off"):
        value = "11111111" if action == "on" else "00000000"
        action = "setbits"
    if action == "toggle":
        action = "set"
        value = "toggle"
    if action == "set" and target is None and value is not None:
        v = str(value).strip()
        if len(v) == 8 and all(ch in "01" for ch in v):
            action = "setbits"
    if action not in ("list", "get", "set", "setbits", "pattern", "stop"):
        raise ValueError("LED action must be list|get|set|setbits|toggle|pattern|stop")

    return action, target, value, extra


def extract_and_run_tar_gz(targz_filename: str) -> bool:
    import subprocess

    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        script_file_path = os.path.join(os.getcwd(), "install.sh")
        if os.path.isfile(script_file_path):
            subprocess.run(["bash", script_file_path], check=True)
            os.remove(script_file_path)
        return True
    except Exception as e:
        print(f"Package extraction/install failed: {e}")
        return False


def _is_random_arg(value) -> bool:
    return str(value).strip().lower() in ("random", "rand", "rnd")


def parse_classify_args(args):
    args = _require_args("classify", args, "classify <hw|sw> <class|random> <seed|random> [batch] | classify <hw|sw> random <batch>")
    mode = "hw"
    input_class = 0
    seed = 1
    batch = 1
    class_random = False
    seed_random = False
    seed_provided = False

    if len(args) == 1 and args[0].strip().startswith("{"):
        payload = json.loads(args[0])
        mode = str(payload.get("mode", mode)).lower()
        cls_raw = payload.get("class", payload.get("input_class", input_class))
        seed_raw = payload.get("seed", seed)
        if _is_random_arg(cls_raw):
            class_random = True
        else:
            input_class = int(cls_raw)
        if _is_random_arg(seed_raw):
            seed_random = True
            seed_provided = True
        else:
            seed = int(seed_raw)
            seed_provided = True
        batch = int(payload.get("batch", payload.get("loops", batch)))
    else:
        positional_numbers = []
        for raw in args:
            token = raw.strip()
            lower = token.lower()
            if lower in ("sw", "hw"):
                mode = lower
                continue
            if "=" in token:
                k, v = token.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ("mode",):
                    mode = v.lower()
                elif k in ("class", "input_class"):
                    if _is_random_arg(v):
                        class_random = True
                    else:
                        input_class = int(v)
                elif k in ("seed",):
                    seed_provided = True
                    if _is_random_arg(v):
                        seed_random = True
                    else:
                        seed = int(v)
                elif k in ("batch", "loops", "n"):
                    batch = int(v)
                else:
                    raise ValueError(f"Unsupported argument key: {k}")
            else:
                positional_numbers.append(token)

        if positional_numbers:
            if _is_random_arg(positional_numbers[0]):
                class_random = True
                # Shortcut: classify <mode> random <batch>
                if len(positional_numbers) == 2 and not _is_random_arg(positional_numbers[1]):
                    batch = int(positional_numbers[1])
                else:
                    if len(positional_numbers) > 1:
                        seed_provided = True
                        if _is_random_arg(positional_numbers[1]):
                            seed_random = True
                        else:
                            seed = int(positional_numbers[1])
                    if len(positional_numbers) > 2:
                        batch = int(positional_numbers[2])
            else:
                input_class = int(positional_numbers[0])
                if len(positional_numbers) > 1:
                    seed_provided = True
                    if _is_random_arg(positional_numbers[1]):
                        seed_random = True
                    else:
                        seed = int(positional_numbers[1])
                if len(positional_numbers) > 2:
                    batch = int(positional_numbers[2])

    if class_random:
        input_class = random.choice(RANDOM_CLASS_CHOICES)
    if class_random and not seed_provided:
        seed_random = True
    if seed_random:
        seed = random.randint(RANDOM_SEED_MIN, RANDOM_SEED_MAX)

    if mode not in ("sw", "hw"):
        raise ValueError("mode must be 'sw' or 'hw'")
    if input_class < 0 or input_class > 5:
        raise ValueError("class must be in range 0..5")
    if batch < 1 or batch > MAX_ML_BATCH:
        raise ValueError(f"batch must be in range 1..{MAX_ML_BATCH}")

    return mode, input_class, seed, batch


def parse_bench_args(args):
    args = _require_args("bench", args, "bench <both|hw|sw> <class|random> <seed|random> <batch> | bench random [batch]")
    mode = "both"
    input_class = 2
    seed = 11
    batch = 1000
    class_random = False
    seed_random = False
    seed_provided = False

    if len(args) == 1 and args[0].strip().startswith("{"):
        payload = json.loads(args[0])
        mode = str(payload.get("mode", mode)).lower()
        cls_raw = payload.get("class", payload.get("input_class", input_class))
        seed_raw = payload.get("seed", seed)
        if _is_random_arg(cls_raw):
            class_random = True
        else:
            input_class = int(cls_raw)
        if _is_random_arg(seed_raw):
            seed_random = True
            seed_provided = True
        else:
            seed = int(seed_raw)
            seed_provided = True
        batch = int(payload.get("batch", payload.get("loops", batch)))
    else:
        positional = []
        for raw in args:
            token = raw.strip()
            lower = token.lower()
            if lower in ("sw", "hw", "both"):
                mode = lower
                continue
            if "=" in token:
                k, v = token.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ("mode",):
                    if _is_random_arg(v):
                        class_random = True
                        seed_random = True
                    else:
                        mode = v.lower()
                elif k in ("class", "input_class"):
                    if _is_random_arg(v):
                        class_random = True
                    else:
                        input_class = int(v)
                elif k in ("seed",):
                    seed_provided = True
                    if _is_random_arg(v):
                        seed_random = True
                    else:
                        seed = int(v)
                elif k in ("batch", "loops", "n"):
                    batch = int(v)
                else:
                    raise ValueError(f"Unsupported bench key: {k}")
            else:
                positional.append(token)
        if positional:
            if _is_random_arg(positional[0]):
                class_random = True
                # Shortcut: bench [mode] random <batch>
                if len(positional) == 2 and not _is_random_arg(positional[1]):
                    batch = int(positional[1])
                else:
                    if len(positional) > 1:
                        seed_provided = True
                        if _is_random_arg(positional[1]):
                            seed_random = True
                        else:
                            seed = int(positional[1])
                    if len(positional) > 2:
                        batch = int(positional[2])
            else:
                input_class = int(positional[0])
                if len(positional) > 1:
                    seed_provided = True
                    if _is_random_arg(positional[1]):
                        seed_random = True
                    else:
                        seed = int(positional[1])
                if len(positional) > 2:
                    batch = int(positional[2])

    if class_random:
        input_class = random.choice(RANDOM_CLASS_CHOICES)
    if class_random and not seed_provided:
        seed_random = True
    if seed_random:
        seed = random.randint(RANDOM_SEED_MIN, RANDOM_SEED_MAX)

    if mode not in ("sw", "hw", "both"):
        raise ValueError("bench mode must be sw|hw|both")
    if input_class < 0 or input_class > 5:
        raise ValueError("class must be in range 0..5")
    if batch < 1 or batch > MAX_ML_BATCH:
        raise ValueError(f"batch must be in range 1..{MAX_ML_BATCH}")
    return mode, input_class, seed, batch


def _run_batch_inference(mode: str, input_class: int, seed: int, batch: int):
    # Preferred path: one ELF run that executes a full batch. This can map to one HW
    # accelerator invocation and removes per-inference host-side setup overhead.
    result = ml_runner.run_inference(
        mode=mode,
        input_class=input_class,
        seed=seed,
        batch_n=batch,
        timeout_s=max(60, 30 + (batch // 10)),
    )
    result_batch = int(result.get("batch_n", 1))
    if result_batch < 1:
        result_batch = 1

    if result_batch == batch:
        return {
            "requested_mode": mode,
            "exec_mode": result["exec_mode"],
            "input_class": result["input_class"],
            "seed": seed,
            "batch_n": result_batch,
            "pred": result["pred"],
            "pred_mode_count": int(result.get("pred_mode_count", 1)),
            "match_count": int(result.get("match_count", 1 if result["pred"] == input_class else 0)),
            "match_rate": float(result.get("match_rate", 1.0 if result["pred"] == input_class else 0.0)),
            "total_time_s": float(result.get("total_time_s", result["time_s"] * result_batch)),
            "avg_time_s": float(result.get("avg_time_s", result["time_s"])),
            "scores": result.get("scores", []),
        }

    # Backward-compatible fallback for older runtime binaries that only support batch=1.
    total_time_s = float(result["time_s"])
    pred_hist = {i: 0 for i in range(6)}
    score_sums = [0] * 6
    matched = 1 if result["pred"] == input_class else 0
    exec_mode = result["exec_mode"]
    pred_hist[result["pred"]] = pred_hist.get(result["pred"], 0) + 1
    for idx in range(min(6, len(result.get("scores", [])))):
        score_sums[idx] += result["scores"][idx]

    for i in range(1, batch):
        run_seed = seed + i
        result_i = ml_runner.run_inference(mode=mode, input_class=input_class, seed=run_seed, batch_n=1)
        exec_mode = result_i["exec_mode"]
        total_time_s += result_i["time_s"]
        pred_hist[result_i["pred"]] = pred_hist.get(result_i["pred"], 0) + 1
        if result_i["pred"] == input_class:
            matched += 1
        scores = result_i.get("scores", [])
        for idx in range(min(6, len(scores))):
            score_sums[idx] += scores[idx]

    pred_mode = max(pred_hist, key=lambda k: pred_hist[k])
    score_avgs = [int(v / batch) for v in score_sums]
    return {
        "requested_mode": mode,
        "exec_mode": exec_mode,
        "input_class": input_class,
        "seed": seed,
        "batch_n": batch,
        "pred": pred_mode,
        "pred_mode_count": pred_hist[pred_mode],
        "match_count": matched,
        "match_rate": float(matched) / float(batch),
        "total_time_s": total_time_s,
        "avg_time_s": total_time_s / float(batch),
        "scores": score_avgs,
    }


def _attach_mode_timing_fields(telemetry: dict, exec_mode: str, total_time_s: float, avg_time_s: float):
    if str(exec_mode).lower() == "hw":
        telemetry["hw_total_time_s"] = total_time_s
        telemetry["hw_avg_time_s"] = avg_time_s
    else:
        telemetry["sw_total_time_s"] = total_time_s
        telemetry["sw_avg_time_s"] = avg_time_s


def _start_async_job(job_name: str, msg: C2dCommand, worker_fn):
    global ACTIVE_JOB
    if not JOB_LOCK.acquire(blocking=False):
        c.send_telemetry({"event": "job_state", "status": "busy", "active_job": ACTIVE_JOB})
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, f"Busy running: {ACTIVE_JOB}")
        return False

    ACTIVE_JOB = job_name

    def runner():
        global ACTIVE_JOB
        try:
            c.send_telemetry({"event": "job_state", "status": "started", "job": job_name})
            worker_fn()
        except Exception as e:
            print(f"Async job {job_name} failed:", e)
            c.send_telemetry({"event": "job_state", "status": "error", "job": job_name, "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, f"{job_name} failed: {e}")
        finally:
            c.send_telemetry({"event": "job_state", "status": "done", "job": job_name})
            ACTIVE_JOB = None
            JOB_LOCK.release()

    threading.Thread(target=runner, name=f"job-{job_name}", daemon=True).start()
    return True


def on_command(msg: C2dCommand):
    global c
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == COMMAND_CLASSIFY:
        try:
            mode, input_class, seed, batch = parse_classify_args(msg.command_args)

            def classify_worker():
                summary = _run_batch_inference(mode=mode, input_class=input_class, seed=seed, batch=batch)
                if batch == 1:
                    telemetry = {
                        "event": "ml_classify",
                        "status": "ok",
                        "mode": summary["exec_mode"],
                        "input_class": summary["input_class"],
                        "seed": summary["seed"],
                        "batch_n": 1,
                        "pred": summary["pred"],
                        "scores_csv": ",".join(str(x) for x in summary["scores"]),
                        "sdk_version": SDK_VERSION,
                    }
                    _attach_mode_timing_fields(
                        telemetry=telemetry,
                        exec_mode=summary["exec_mode"],
                        total_time_s=summary["total_time_s"],
                        avg_time_s=summary["avg_time_s"],
                    )
                else:
                    telemetry = {
                        "event": "ml_classify_batch",
                        "status": "ok",
                        "mode": summary["exec_mode"],
                        "input_class": summary["input_class"],
                        "seed": summary["seed"],
                        "batch_n": summary["batch_n"],
                        "pred": summary["pred"],
                        "pred_mode_count": summary["pred_mode_count"],
                        "match_count": summary["match_count"],
                        "match_rate": summary["match_rate"],
                        "scores_csv": ",".join(str(x) for x in summary["scores"]),
                        "sdk_version": SDK_VERSION,
                    }
                    _attach_mode_timing_fields(
                        telemetry=telemetry,
                        exec_mode=summary["exec_mode"],
                        total_time_s=summary["total_time_s"],
                        avg_time_s=summary["avg_time_s"],
                    )
                for idx in range(min(6, len(summary["scores"]))):
                    telemetry[f"score{idx}"] = summary["scores"][idx]
                c.send_telemetry(telemetry)
                c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Classification completed")
                print("Classification result:", telemetry)

            # Long batch runs can exceed MQTT keep-alive if handled inline in callback thread.
            if batch >= 300:
                _start_async_job("classify", msg, classify_worker)
            else:
                classify_worker()
        except Exception as e:
            error_msg = f"Classification failed: {e}"
            print(error_msg)
            c.send_telemetry({"event": "ml_classify", "status": "error", "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, error_msg)
        return

    if msg.command_name == COMMAND_BENCH:
        try:
            mode, input_class, seed, batch = parse_bench_args(msg.command_args)

            def bench_worker():
                sw = None
                hw = None
                if mode in ("sw", "both"):
                    sw = _run_batch_inference(mode="sw", input_class=input_class, seed=seed, batch=batch)
                if mode in ("hw", "both"):
                    hw = _run_batch_inference(mode="hw", input_class=input_class, seed=seed, batch=batch)

                telemetry = {
                    "event": "ml_bench",
                    "status": "ok",
                    "mode": mode,
                    "input_class": input_class,
                    "seed": seed,
                    "batch_n": batch,
                    "sdk_version": SDK_VERSION,
                }
                if sw is not None:
                    telemetry["sw_pred"] = sw["pred"]
                    telemetry["sw_avg_time_s"] = sw["avg_time_s"]
                    telemetry["sw_total_time_s"] = sw["total_time_s"]
                    telemetry["sw_match_rate"] = sw["match_rate"]
                if hw is not None:
                    telemetry["hw_pred"] = hw["pred"]
                    telemetry["hw_avg_time_s"] = hw["avg_time_s"]
                    telemetry["hw_total_time_s"] = hw["total_time_s"]
                    telemetry["hw_match_rate"] = hw["match_rate"]
                if sw is not None and hw is not None and hw["avg_time_s"] > 0:
                    telemetry["speedup_sw_over_hw"] = sw["avg_time_s"] / hw["avg_time_s"]
                    telemetry["speedup_hw_over_sw"] = hw["avg_time_s"] / sw["avg_time_s"] if sw["avg_time_s"] > 0 else None

                c.send_telemetry(telemetry)
                c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Benchmark completed")
                print("Benchmark result:", telemetry)

            _start_async_job("bench", msg, bench_worker)
        except Exception as e:
            error_msg = f"Benchmark failed: {e}"
            print(error_msg)
            c.send_telemetry({"event": "ml_bench", "status": "error", "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, error_msg)
        return

    if msg.command_name == COMMAND_STATUS:
        try:
            include_leds = parse_status_args(msg.command_args)
            status = _status_payload(include_leds=include_leds)
            c.send_telemetry(status)
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Status reported")
            print("Status telemetry:", status)
        except Exception as e:
            error_msg = f"Status failed: {e}"
            print(error_msg)
            c.send_telemetry({"event": "device_status", "status": "error", "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, error_msg)
        return

    if msg.command_name in (COMMAND_LED, COMMAND_LEDS):
        try:
            action, target, value, extra = parse_led_args(msg.command_args)
            if action in ("list", "get") and (target is None or str(target).strip() == ""):
                telemetry = {"event": "led_state", "status": "ok", "action": action, "led_count": len(_visible_leds())}
            elif action == "setbits":
                if value is None:
                    raise ValueError("LED bitstring required (example: 10101010)")
                _set_leds_from_bitstring(str(value))
                telemetry = {"event": "led_state", "status": "ok", "action": "setbits", "requested": str(value)}
            elif action == "get":
                led = _resolve_led(str(target))
                telemetry = {"event": "led_state", "status": "ok", "action": "get", "target": led["name"]}
            elif action == "pattern":
                pattern_name = str(target or "chase").lower()
                cycles = int(value) if value is not None else 16
                interval_ms = int(extra[0]) if len(extra) > 0 else 120
                level = int(extra[1]) if len(extra) > 1 else None
                if pattern_name not in ("blink", "chase", "alternate"):
                    raise ValueError("pattern must be blink|chase|alternate")
                _start_led_pattern(pattern_name=pattern_name, cycles=cycles, interval_ms=interval_ms, level=level)
                telemetry = {
                    "event": "led_state",
                    "status": "ok",
                    "action": "pattern",
                    "pattern": pattern_name,
                    "cycles": cycles,
                    "interval_ms": interval_ms,
                    "level": level,
                }
            elif action == "stop":
                _stop_led_pattern()
                telemetry = {
                    "event": "led_state",
                    "status": "ok",
                    "action": "stop",
                }
            else:
                if target is None:
                    raise ValueError("LED target required for set")
                if value is None:
                    raise ValueError("LED value required for set")
                led = _resolve_led(str(target))
                _set_led_state(led["name"], str(value))
                telemetry = {"event": "led_state", "status": "ok", "action": "set", "target": led["name"]}

            telemetry["leds"] = _leds_state_string()

            c.send_telemetry(telemetry)
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "LED command completed")
            print("LED telemetry:", telemetry)
        except Exception as e:
            error_msg = f"LED command failed: {e}"
            print(error_msg)
            c.send_telemetry({"event": "led_state", "status": "error", "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, error_msg)
        return

    if msg.command_name == COMMAND_LOAD:
        try:
            action, workers, duty = parse_load_args(msg.command_args)
            if action == "start":
                _start_load(workers=workers, duty_pct=duty)
            elif action == "stop":
                _stop_load()
            active = _load_active()
            telemetry = {
                "event": "load_state",
                "status": "ok",
                "action": action,
                "load_active": active,
                "load_workers": LOAD_WORKERS if active else 0,
                "load_duty_pct": LOAD_DUTY if active else 0,
                "load_backend": LOAD_BACKEND,
            }
            c.send_telemetry(telemetry)
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Load command completed")
            print("Load telemetry:", telemetry)
        except Exception as e:
            error_msg = f"Load command failed: {e}"
            print(error_msg)
            c.send_telemetry({"event": "load_state", "status": "error", "error": str(e)})
            if msg.ack_id is not None:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, error_msg)
        return

    if msg.command_name == COMMAND_FILE_DOWNLOAD:
        download_args = _clean_args(msg.command_args)
        if len(download_args) != 1:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 URL argument")
            return
        try:
            response = requests.get(download_args[0], timeout=30)
            response.raise_for_status()
            with open("package.tar.gz", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Package downloaded")
            if extract_and_run_tar_gz("package.tar.gz"):
                print("Package install completed, restarting app")
                sys.stdout.flush()
                os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
            else:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, "Package install failed")
        except Exception as e:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, f"Download/install failed: {e}")
        return

    if msg.ack_id is not None:
        c.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


def on_ota(msg: C2dOta):
    global c
    print("Starting OTA downloads for version %s" % msg.version)
    c.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False

    for url in msg.urls:
        print("Downloading OTA file %s from %s" % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print("Encountered download error", e)
            break
        if url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if extraction_success is False:
                break
        else:
            print("Unhandled file format for file %s" % url.file_name)

    if extraction_success:
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        print("OTA successful. Restarting app.")
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
    else:
        print("OTA failed.")


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


def main():
    global c, LAST_STATUS_TS

    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path="iotcDeviceConfig.json",
        device_cert_path="device-cert.pem",
        device_pkey_path="device-pkey.pem",
    )

    c = Client(
        config=device_config,
        callbacks=Callbacks(ota_cb=on_ota, command_cb=on_command, disconnected_cb=on_disconnect),
    )

    while True:
        if not c.is_connected():
            print("(re)connecting...")
            c.connect()
            if not c.is_connected():
                print("Unable to connect. Exiting.")
                sys.exit(2)

        c.send_telemetry(
            {
                "event": "heartbeat",
                "sdk_version": SDK_VERSION,
                "random": random.randint(0, 100),
            }
        )
        now = time.time()
        if (now - LAST_STATUS_TS) >= STATUS_PERIOD_S:
            try:
                c.send_telemetry(_status_payload(include_leds=False))
                LAST_STATUS_TS = now
            except Exception as e:
                print("Status telemetry failed:", e)
        time.sleep(15)


if __name__ == "__main__":
    try:
        main()
    except DeviceConfigError as dce:
        print(dce)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Exiting.")
        sys.exit(0)
    finally:
        _stop_led_pattern()
        _stop_load()

