# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Michael Lamp <michael@lamptribe.com> et al.
# -----------------------------------------------------------------------------
# PURPOSE:
#   This script runs on an NXP FRDM i.MX 95 and integrates NXP's eIQ GenAI Flow
#   conversational AI pipeline with Avnet /IOTCONNECT:
#    1) Connects to /IOTCONNECT with your device configuration and credentials.
#    2) Periodically sends system telemetry (CPU %, memory, temperature) along
#       with the latest LLM performance metrics (tokens/sec, time-to-first-token).
#    3) Listens for /IOTCONNECT commands:
#        - "ask-llm <prompt>": runs a one-shot prompt through the on-device LLM
#          (eIQ GenAI Flow, keyboard-in/text-out mode) and reports the response
#          plus measured performance metrics as telemetry.
#        - "run-benchmark [extra args]": runs the official GenAI Flow benchmark
#          mode (-r -b) and reports the metrics from its JSON report.
#        - "set-model <name>": selects the LLM (e.g. danube-500M-q8, danube-500M-q4).
#        - "set-backend <cpu|neutron>": toggles eIQ Neutron NPU acceleration
#          (i.MX 95 B0 silicon only, requires >= 3GB CMA).
#        - "get-ip": returns the device's local IP address.
#        - "file-download <url>": self-update with a new package (also via OTA).
#
#   The eIQ GenAI Flow demonstrator must be installed separately (see README.md):
#   https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator
#
#   NOTE: The Kinara Ara-2 discrete NPU module is not yet supported by this demo.
#   The "backend" config field is designed so an "ara2" option can be added once
#   the module and its runtime are available.
# -----------------------------------------------------------------------------

import glob
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
CONFIG_PATH = "/opt/demo/genai-config.json"

DEFAULT_CONFIG = {
    # Where the eIQ GenAI Flow demonstrator was installed on the board
    "genai_dir": "/root/eiq_genai_flow",
    "python": "python3",
    # danube-500M-q8 (default) or danube-500M-q4
    "model": "danube-500M-q8",
    # Ground LLM answers in the on-device RAG database (rag/src/data/rag_database.pkl).
    # Applies to ask-llm, the voice assistant, and run-benchmark.
    "use_rag": False,
    # "cpu" or "neutron" (i.MX 95 B0 only). "ara2" reserved for future use.
    "backend": "cpu",
    # Seconds with no LLM output before a response is considered complete
    "output_silence_s": 5,
    # Overall per-prompt timeout (model load on first run can be slow)
    "prompt_timeout_s": 600,
    # Overall benchmark timeout
    "benchmark_timeout_s": 3600,
    "telemetry_interval_s": 10,
    # Vision Language Model (the vlm submodule of the GenAI Flow repo)
    "vlm_dir": "/root/vlm",
    "vlm_model": "smolvlm-256M",   # smolvlm-256M or smolvlm-500M
    "vlm_precision": "q8",         # q8 or fp32
    "vlm_timeout_s": 600,
    # V4L2 device of the USB camera used for ask-vlm captures
    "camera_device": "/dev/video52",
    # Voice assistant (voice-start command): tts speaks replies through the
    # playback device; text just streams them to /IOTCONNECT. Empty device
    # strings let GenAI Flow auto-detect (e.g. a USB webcam mic and the MQS
    # 3.5mm jack on the FRDM-IMX95).
    "voice_output": "tts",
    # moonshine-tiny (fastest), moonshine-base, or whisper-small.en (most accurate)
    "stt_model": "moonshine-tiny",
    "capture_device": "",
    "playback_device": ""
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        save_config(cfg)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()

# -----------------------------------------------------------------------------
# TELEMETRY STATE
# -----------------------------------------------------------------------------
telemetry = {
    "sdk_version": SDK_VERSION,
    "genai_status": "idle",       # idle | generating | benchmarking | not-installed | error
    "llm_model": config["model"],
    "llm_backend": config["backend"],
    "llm_rag": "on" if config.get("use_rag") else "off",
    "llm_prompt": "",
    "llm_response": "",
    "llm_load_time": 0.0,         # seconds spent initializing the pipeline
    "llm_ttft": 0.0,              # time to first token (seconds)
    "llm_gen_time": 0.0,          # total generation time (seconds)
    "llm_tps": 0.0,               # tokens per second
    "llm_token_count": 0,
    "voice_status": "off",        # off | starting | listening | capturing | answering | error
    "voice_question": "",         # last transcribed spoken question
    "voice_response": "",         # last spoken/streamed answer
    "voice_exchanges": 0,         # completed question/answer rounds this session
    "vlm_model": "",              # VLM used for the last ask-vlm
    "vlm_question": "",
    "vlm_response": "",
    "vlm_vision_time": 0.0,       # vision encoder time (s)
    "vlm_ttft": 0.0,              # vision + decoder time to first token (s)
    "vlm_tps": 0.0,               # decode speed (tokens/sec)
    "bench_ttfa": 0.0,            # benchmark: time to first audio (s)
    "bench_ttft": 0.0,            # benchmark: LLM time to first token (s)
    "bench_tps": 0.0,             # benchmark: LLM tokens per second
    "bench_cpu_avg": 0.0,         # benchmark: average CPU %
    "bench_mem_avg": 0.0,         # benchmark: average memory (MB)
    "cpu_percent": 0.0,
    "mem_used_mb": 0.0,
    "cpu_temp": 0.0,
    "board_ip": ""
}
telemetry_lock = threading.Lock()

# Only one LLM operation (prompt or benchmark) may run at a time
llm_busy = threading.Lock()


def genai_script_path():
    return os.path.join(config["genai_dir"], "eiq_genai_flow.py")


def genai_installed():
    return os.path.isfile(genai_script_path())


# -----------------------------------------------------------------------------
# SYSTEM METRICS (no external dependencies, read straight from /proc and /sys)
# -----------------------------------------------------------------------------
_last_cpu_sample = None


def read_cpu_percent():
    """Compute total CPU utilization from consecutive /proc/stat samples."""
    global _last_cpu_sample
    try:
        with open("/proc/stat") as f:
            fields = [float(x) for x in f.readline().split()[1:]]
    except (OSError, ValueError, IndexError):
        return 0.0
    idle, total = fields[3] + fields[4], sum(fields)
    if _last_cpu_sample is None:
        _last_cpu_sample = (idle, total)
        return 0.0
    last_idle, last_total = _last_cpu_sample
    _last_cpu_sample = (idle, total)
    d_total = total - last_total
    if d_total <= 0:
        return 0.0
    return round(100.0 * (1.0 - (idle - last_idle) / d_total), 1)


def read_mem_used_mb():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                info[parts[0].rstrip(":")] = int(parts[1])
        return round((info["MemTotal"] - info["MemAvailable"]) / 1024.0, 1)
    except (OSError, KeyError, ValueError, IndexError):
        return 0.0


def read_cpu_temp():
    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            with open(zone) as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except (OSError, ValueError):
            continue
    return 0.0


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# -----------------------------------------------------------------------------
# LLM EXECUTION
# -----------------------------------------------------------------------------
# GenAI Flow's keyb/text mode prints "Please type your question:" when it is
# ready for input (and again after each answer), and streams the answer with
# each LLM token wrapped in its own ANSI color sequence - which gives us a
# reliable ready/done marker and an exact token count.
READY_MARKER = "Please type your question:"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
_TOKEN_RE = re.compile(r"\x1b\[32m\x1b\[22m")

# Patterns to harvest metrics from benchmark stdout if no JSON report is found
_TPS_RE = re.compile(r"([\d.]+)\s*tok(?:en)?s?\s*(?:/|per)\s*s(?:ec)?", re.IGNORECASE)
_TTFT_RE = re.compile(r"ttft\D*([\d.]+)", re.IGNORECASE)


def build_genai_cmd(extra_args):
    cmd = [config["python"], "-u", genai_script_path()] + extra_args
    if config["backend"] == "neutron":
        cmd.append("--use-neutron")
    if config.get("use_rag"):
        cmd.append("--use-rag")
    return cmd


class ProcReader:
    """Reads a subprocess's stdout on a thread as timestamped byte chunks."""

    def __init__(self, proc):
        self.proc = proc
        self.q = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        fd = self.proc.stdout.fileno()
        while True:
            data = os.read(fd, 4096)
            if not data:
                self.q.put((time.monotonic(), None))  # EOF
                return
            self.q.put((time.monotonic(), data))

    def get(self, timeout):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return (time.monotonic(), b"")  # timeout tick


def run_llm_prompt(prompt):
    """
    Run a single prompt through eIQ GenAI Flow in keyboard-input / text-output
    mode, measure load time, TTFT, generation time and tokens/sec, and update
    the telemetry dictionary. Returns the response text (or raises).
    """
    cmd = build_genai_cmd(["-i", "keyb", "-o", "text", "-m", config["model"]])
    print("Running:", " ".join(cmd))
    proc = subprocess.Popen(
        cmd, cwd=config["genai_dir"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=0,
    )
    reader = ProcReader(proc)

    def clean(buf):
        return _ANSI_RE.sub("", buf.decode("utf-8", "replace"))

    try:
        start = time.monotonic()
        deadline = start + config["prompt_timeout_s"]

        # Phase 1: wait for the ready marker (pipeline + model initialized)
        initbuf = b""
        while READY_MARKER not in clean(initbuf):
            if time.monotonic() > deadline:
                raise RuntimeError("Timed out waiting for GenAI Flow to initialize:\n" + clean(initbuf[-2000:]))
            ts, data = reader.get(timeout=5)
            if data is None:
                raise RuntimeError("GenAI Flow exited during startup:\n" + clean(initbuf[-2000:]))
            initbuf += data
        load_time = time.monotonic() - start

        # Phase 2: send the prompt; the marker reappears after the answer
        proc.stdin.write((prompt.strip() + "\n").encode())
        proc.stdin.flush()
        t_prompt = time.monotonic()
        t_first = None
        t_last = t_prompt
        genbuf = b""
        while READY_MARKER not in clean(genbuf):
            if time.monotonic() > deadline:
                break
            ts, data = reader.get(timeout=config["output_silence_s"])
            if data is None:
                break  # process exited
            if data and clean(data).strip():
                if t_first is None:
                    t_first = ts
                t_last = ts
            genbuf += data
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    response = clean(genbuf).split(READY_MARKER)[0]
    # Drop logger lines (timestamps, GStreamer errors, etc.) that can interleave
    # with the streamed answer, e.g. while a voice session holds the audio device.
    response = "\n".join(
        l for l in response.splitlines()
        if not re.match(r"\s*\d{4}-\d{2}-\d{2}[ T]", l) and "Error:" not in l
    ).strip()
    if not response:
        raise RuntimeError("No LLM response captured. Last output:\n" + clean(genbuf[-2000:]))

    gen_time = round(t_last - t_prompt, 2)
    ttft = round((t_first - t_prompt), 2) if t_first else 0.0
    tokens = len(_TOKEN_RE.findall(genbuf.decode("utf-8", "replace")))
    if tokens == 0:
        tokens = max(1, int(len(response) / 4))  # ~4 chars/token fallback
    tps = round(tokens / max(0.01, t_last - (t_first or t_prompt)), 2)

    with telemetry_lock:
        telemetry.update({
            "llm_prompt": prompt[:500],
            "llm_response": response[:1000],
            "llm_load_time": round(load_time, 2),
            "llm_ttft": ttft,
            "llm_gen_time": gen_time,
            "llm_tps": tps,
            "llm_token_count": tokens,
        })
    print("LLM response (%.1fs, ~%.1f tok/s): %s" % (gen_time, tps, response[:200]))
    return response


def _harvest_metrics(obj, out, prefix=""):
    """
    Recursively pull numeric metrics out of a benchmark report dict.
    GenAI Flow reports values as strings (e.g. "llm_avg_tps": "12.92").
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            _harvest_metrics(v, out, (prefix + " " + str(k)).lower())
    elif isinstance(obj, list):
        for v in obj:
            _harvest_metrics(v, out, prefix)
    else:
        try:
            val = float(obj)
        except (TypeError, ValueError):
            return
        if "ttfa" in prefix:
            out.setdefault("bench_ttfa", val)
        elif "ttft" in prefix:
            out.setdefault("bench_ttft", val)
        elif "tps" in prefix:
            out.setdefault("bench_tps", val)
        elif "cpu" in prefix:
            out.setdefault("bench_cpu_avg", val)
        elif "mem" in prefix:
            out.setdefault("bench_mem_avg", val)


# -----------------------------------------------------------------------------
# VOICE ASSISTANT SESSION (voice-start / voice-stop)
# -----------------------------------------------------------------------------
# In vasr mode GenAI Flow waits for the wake word ("Hey NXP"), prints
# "I'm listening!", transcribes speech as an "ASR: <question>" line, then
# streams the LLM answer token-by-token (ANSI-wrapped, same as keyb mode).
_LLM_TOKEN_CONTENT_RE = re.compile(r"\x1b\[32m\x1b\[22m(.*?)\x1b\[0m", re.S)

_voice_stop = threading.Event()
_voice_proc = None


def set_voice_status(status):
    with telemetry_lock:
        telemetry["voice_status"] = status


def voice_session(output_mode):
    """Run the wake-word voice pipeline and publish each exchange as telemetry."""
    global _voice_proc
    cmd = build_genai_cmd(["-i", "vasr", "-o", output_mode, "-m", config["model"]])
    if config.get("stt_model"):
        cmd += ["--stt", config["stt_model"]]
    if config.get("capture_device"):
        cmd += ["--capture-device", config["capture_device"]]
    if output_mode == "tts" and config.get("playback_device"):
        cmd += ["--playback-device", config["playback_device"]]
    print("Starting voice session:", " ".join(cmd))
    proc = subprocess.Popen(
        cmd, cwd=config["genai_dir"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=0,
    )
    _voice_proc = proc
    reader = ProcReader(proc)

    linebuf = ""     # ANSI-stripped text pending newline, for event lines
    rawbuf = b""     # raw bytes since last question, for token extraction
    question = None
    last_token_t = None

    def finalize_exchange():
        nonlocal question, rawbuf, last_token_t
        if question is None:
            return
        tokens = _LLM_TOKEN_CONTENT_RE.findall(rawbuf.decode("utf-8", "replace"))
        answer = "".join(tokens).strip()
        with telemetry_lock:
            telemetry["voice_response"] = answer[:1000]
            telemetry["voice_exchanges"] += 1
        print("Voice exchange #%d: Q: %s | A: %s" % (telemetry["voice_exchanges"], question, answer[:200]))
        question = None
        rawbuf = b""
        last_token_t = None
        set_voice_status("listening")

    try:
        while not _voice_stop.is_set():
            ts, data = reader.get(timeout=1)
            if data is None:
                raise RuntimeError("Voice pipeline exited unexpectedly. Last output:\n"
                                   + _ANSI_RE.sub("", rawbuf[-2000:].decode("utf-8", "replace")))
            if not data:
                # Quiet tick: close out the exchange if the answer stopped streaming
                if question is not None and last_token_t and ts - last_token_t > 3:
                    finalize_exchange()
                continue
            rawbuf += data
            if question is not None and _LLM_TOKEN_CONTENT_RE.search(data.decode("utf-8", "replace")):
                last_token_t = ts

            linebuf += _ANSI_RE.sub("", data.decode("utf-8", "replace"))
            while "\n" in linebuf:
                line, linebuf = linebuf.split("\n", 1)
                if "I'm listening!" in line:
                    set_voice_status("capturing")
                elif "ASR: No speech detected" in line:
                    set_voice_status("listening")
                elif "ASR:" in line:
                    if question is not None:
                        finalize_exchange()
                    question = line.split("ASR:", 1)[1].strip()
                    rawbuf = b""
                    with telemetry_lock:
                        telemetry["voice_question"] = question[:500]
                    set_voice_status("answering")
                elif "Speak the wakeword" in line or "LLM used:" in line:
                    set_voice_status("listening")  # pipeline (fully) initialized
        finalize_exchange()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        _voice_proc = None


def start_voice(output_mode):
    """Voice worker wrapper - holds llm_busy for the whole session."""
    def worker():
        try:
            with telemetry_lock:
                telemetry["genai_status"] = "voice"
                telemetry["voice_exchanges"] = 0
            set_voice_status("starting")
            voice_session(output_mode)
            set_voice_status("off")
            with telemetry_lock:
                telemetry["genai_status"] = "idle"
        except Exception as e:
            print("Voice session failed:", e)
            set_voice_status("error")
            with telemetry_lock:
                telemetry["genai_status"] = "error"
        finally:
            llm_busy.release()
    threading.Thread(target=worker, daemon=True).start()


# -----------------------------------------------------------------------------
# VISION LANGUAGE MODEL (ask-vlm)
# -----------------------------------------------------------------------------
# Perf line printed by the VLM after each answer, e.g.:
#   Vision: 3.31s | TTFT: 3.79s (Decoder 0.48s) | Current decode speed: 12.50tok/s
_VLM_PERF_RE = re.compile(
    r"Vision:\s*([\d.]+)s\s*\|\s*TTFT:\s*([\d.]+)s.*?([\d.]+)\s*tok/s"
)

VLM_FRAME_PATH = "/opt/demo/vlm-frame.jpg"


def vlm_installed():
    return os.path.isdir(os.path.join(config["vlm_dir"], "src", "vlm"))


def capture_frame():
    """Grab a single JPEG frame from the USB camera via GStreamer."""
    if os.path.exists(VLM_FRAME_PATH):
        os.remove(VLM_FRAME_PATH)
    subprocess.run(
        ["gst-launch-1.0", "-q",
         "v4l2src", "device=%s" % config["camera_device"], "num-buffers=1", "!",
         "image/jpeg,width=1280,height=720", "!",
         "filesink", "location=%s" % VLM_FRAME_PATH],
        check=False, timeout=30,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not os.path.isfile(VLM_FRAME_PATH) or os.path.getsize(VLM_FRAME_PATH) == 0:
        raise RuntimeError("Camera capture failed on %s - is the USB camera connected?"
                           % config["camera_device"])
    return VLM_FRAME_PATH


def run_vlm(question):
    """
    Capture a camera frame and run it through SmolVLM (single-shot -q mode).
    The VLM answers, prints its perf line, then exits on stdin EOF.
    """
    frame = capture_frame()
    cmd = [config["python"], "-u", "-m", "vlm", "-ng",
           "-m", config["vlm_model"], "-p", config["vlm_precision"],
           "-im", frame, "-q", question]
    print("Running VLM:", " ".join(cmd))
    result = subprocess.run(
        cmd, cwd=config["vlm_dir"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=config["vlm_timeout_s"],
    )
    out = _ANSI_RE.sub("", result.stdout)

    m = _VLM_PERF_RE.search(out)
    if not m:
        raise RuntimeError("No VLM answer captured. Last output:\n" + out[-2000:])
    vision_t, ttft, tps = (float(x) for x in m.groups())

    # The VLM streams each answer token wrapped in bright-green ANSI (Fore.LIGHTGREEN_EX).
    # Its log lines and perf line use the same color, so filter those out rather than
    # relying on output ordering (stdout/stderr interleaving is not deterministic).
    segments = re.findall(r"\x1b\[92m(.*?)\x1b\[0m", result.stdout, re.S)
    answer = "".join(
        s for s in segments
        if not re.match(r"\s*\d{4}-\d{2}-\d{2}", s)      # log lines
        and "Loading" not in s and "Loaded" not in s      # startup prints
        and "Vision:" not in s                            # perf line
    ).strip()
    if not answer:
        # Fallback: plain text between the image line and the perf line
        answer = out.split("image", 1)[-1].split("Vision:")[0].strip()

    with telemetry_lock:
        telemetry.update({
            "vlm_model": config["vlm_model"],
            "vlm_question": question[:500],
            "vlm_response": answer[:1000],
            "vlm_vision_time": vision_t,
            "vlm_ttft": ttft,
            "vlm_tps": tps,
        })
    print("VLM response (vision %.1fs, %.1f tok/s): %s" % (vision_t, tps, answer[:200]))
    return answer


def harvest_benchmark_reports(newer_than=0):
    """Harvest bench metrics from the most recent benchmark JSON report."""
    metrics = {}
    reports = [
        p for p in glob.glob(os.path.join(config["genai_dir"], "**", "Benchmark_*.json"), recursive=True)
        if os.path.getmtime(p) >= newer_than
    ]
    for report in sorted(reports, key=os.path.getmtime, reverse=True):
        try:
            with open(report) as f:
                _harvest_metrics(json.load(f), metrics)
        except (OSError, json.JSONDecodeError):
            continue
        if metrics:
            print("Harvested benchmark metrics from", report, ":", metrics)
            break
    return metrics


def run_benchmark(extra_args):
    """
    Run the official eIQ GenAI Flow benchmark mode (-r -b) and harvest metrics
    from the JSON report it writes. extra_args lets the /IOTCONNECT command
    override the input mode etc. (default: keyboard/text to avoid requiring
    audio hardware). Passing the single argument "report" skips the run and
    re-publishes the metrics from the most recent existing report.
    """
    if extra_args == ["report"]:
        metrics = harvest_benchmark_reports()
        stdout = ""
    else:
        args = extra_args if extra_args else ["-i", "keyb", "-o", "text"]
        cmd = build_genai_cmd(args + ["-m", config["model"], "-r", "-b"])
        print("Running benchmark:", " ".join(cmd))
        start_time = time.time()
        result = subprocess.run(
            cmd, cwd=config["genai_dir"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            timeout=config["benchmark_timeout_s"],
        )
        print(result.stdout[-3000:])
        metrics = harvest_benchmark_reports(newer_than=start_time)
        stdout = result.stdout

    # Fall back to scraping stdout if no report was found
    if not metrics and stdout:
        m = _TPS_RE.search(stdout)
        if m:
            metrics["bench_tps"] = float(m.group(1))
        m = _TTFT_RE.search(stdout)
        if m:
            metrics["bench_ttft"] = float(m.group(1))

    if not metrics:
        raise RuntimeError("Benchmark finished but no metrics could be harvested")

    with telemetry_lock:
        for k, v in metrics.items():
            telemetry[k] = round(v, 2)
    return metrics


def start_llm_job(job, name, done_msg):
    """Run an LLM operation on a worker thread so the MQTT loop stays responsive."""
    def worker():
        try:
            with telemetry_lock:
                telemetry["genai_status"] = name
            job()
            with telemetry_lock:
                telemetry["genai_status"] = "idle"
            print(done_msg)
        except Exception as e:
            print("LLM job failed:", e)
            with telemetry_lock:
                telemetry["genai_status"] = "error"
        finally:
            llm_busy.release()
    threading.Thread(target=worker, daemon=True).start()


# -----------------------------------------------------------------------------
# SELF-UPDATE SUPPORT (OTA packages / file-download command)
# -----------------------------------------------------------------------------
def extract_and_run_tar_gz(targz_filename):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        script_file_path = os.path.join(os.getcwd(), "install.sh")
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(["bash", script_file_path], check=True)
                print("Successfully executed install.sh")
                return True
            except subprocess.CalledProcessError as e:
                print("Error executing install.sh:", e)
                return False
            finally:
                os.remove(script_file_path)
        else:
            print("install.sh not found in the current directory.")
            return True
    except subprocess.CalledProcessError:
        return False


def exit_and_restart():
    print("")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])


# -----------------------------------------------------------------------------
# COMMAND CALLBACK
# -----------------------------------------------------------------------------
def on_command(msg: C2dCommand):
    global c
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)
    config.update(load_config())  # pick up externally edited genai-config.json

    if msg.command_name == "ask-llm":
        if len(msg.command_args) < 1:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected a prompt argument")
            return
        if not genai_installed():
            with telemetry_lock:
                telemetry["genai_status"] = "not-installed"
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "LLM is busy with another operation")
            return
        prompt = " ".join(msg.command_args)
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "LLM generation started - response will arrive as telemetry")
        start_llm_job(lambda: run_llm_prompt(prompt), "generating", "Prompt complete")

    elif msg.command_name == "voice-start":
        if not genai_installed():
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "LLM/VLM is busy with another operation")
            return
        output_mode = msg.command_args[0] if msg.command_args else config["voice_output"]
        if output_mode not in ("tts", "text"):
            llm_busy.release()
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected tts or text")
            return
        _voice_stop.clear()
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Voice assistant starting (%s output) - say 'Hey NXP' once voice_status is 'listening'"
                           % output_mode)
        start_voice(output_mode)

    elif msg.command_name == "voice-stop":
        if telemetry["voice_status"] in ("off", "error"):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Voice assistant is not running")
        else:
            _voice_stop.set()
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Voice assistant stopping")

    elif msg.command_name == "ask-vlm":
        if not vlm_installed():
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "VLM not found at %s - see demo README" % config["vlm_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "LLM/VLM is busy with another operation")
            return
        question = " ".join(msg.command_args) if msg.command_args else "Describe what you see in this image."
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Capturing camera frame and running VLM - response will arrive as telemetry")
        start_llm_job(lambda: run_vlm(question), "generating", "VLM question complete")

    elif msg.command_name == "run-benchmark":
        if not genai_installed():
            with telemetry_lock:
                telemetry["genai_status"] = "not-installed"
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "LLM is busy with another operation")
            return
        extra = " ".join(msg.command_args).split() if msg.command_args else []
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Benchmark started - metrics will arrive as telemetry (this can take a while)")
        start_llm_job(lambda: run_benchmark(extra), "benchmarking", "Benchmark complete")

    elif msg.command_name == "set-model":
        if len(msg.command_args) == 1:
            config["model"] = msg.command_args[0]
            save_config(config)
            with telemetry_lock:
                telemetry["llm_model"] = config["model"]
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Model set to " + config["model"])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument, e.g. danube-500M-q8")

    elif msg.command_name == "set-rag":
        if len(msg.command_args) == 1 and msg.command_args[0] in ("on", "off"):
            config["use_rag"] = msg.command_args[0] == "on"
            save_config(config)
            with telemetry_lock:
                telemetry["llm_rag"] = msg.command_args[0]
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "RAG " + msg.command_args[0])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument: on or off")

    elif msg.command_name == "set-backend":
        if len(msg.command_args) == 1 and msg.command_args[0] in ("cpu", "neutron"):
            config["backend"] = msg.command_args[0]
            save_config(config)
            with telemetry_lock:
                telemetry["llm_backend"] = config["backend"]
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Backend set to " + config["backend"])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "Expected 1 argument: cpu or neutron (ara2 support coming soon)")

    elif msg.command_name == "get-ip":
        ip_addr = get_local_ip()
        print("The board IP is:", ip_addr)
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "The board IP is: " + ip_addr)

    elif msg.command_name == "file-download":
        if len(msg.command_args) == 1:
            status_message = "Downloading %s to device" % msg.command_args[0]
            response = requests.get(msg.command_args[0])
            if response.status_code == 200:
                with open("package.tar.gz", "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print("File downloaded successfully and saved to package.tar.gz")
            else:
                print("Failed to download the file. Status code:", response.status_code)
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extract_and_run_tar_gz("package.tar.gz")
            print("Download command successful. Will restart the application...")
            exit_and_restart()
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")

    else:
        print("Command %s not implemented!" % msg.command_name)
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


# -----------------------------------------------------------------------------
# OTA CALLBACK
# -----------------------------------------------------------------------------
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
            print("ERROR: Unhandled file format for file %s" % url.file_name)
    if extraction_success is True:
        print("OTA successful. Will restart the application...")
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        exit_and_restart()
    else:
        print("Encountered a download processing error. Not restarting.")


# Set whenever the MQTT connection drops. The underlying client can silently
# re-establish TCP without restoring C2D command subscriptions (observed after
# a DHCP address change), so the main loop restarts the process for a clean
# session once any in-flight LLM/VLM work has finished.
_connection_lost = threading.Event()


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))
    _connection_lost.set()


# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
try:
    telemetry["board_ip"] = get_local_ip()
    if not genai_installed():
        telemetry["genai_status"] = "not-installed"
        print("WARNING: eIQ GenAI Flow not found at %s." % config["genai_dir"])
        print("The ask-llm and run-benchmark commands will fail until it is installed (see README.md).")
    else:
        # Pre-populate bench_* telemetry from the most recent benchmark report
        for k, v in harvest_benchmark_reports().items():
            telemetry[k] = round(v, 2)

    # Discovery/identity are HTTP calls that can fail transiently (e.g. 502s);
    # keep retrying so an unattended boot survives cloud-side blips.
    while True:
        try:
            device_config = DeviceConfig.from_iotc_device_config_json_file(
                device_config_json_path="iotcDeviceConfig.json",
                device_cert_path="device-cert.pem",
                device_pkey_path="device-pkey.pem"
            )
            c = Client(
                config=device_config,
                callbacks=Callbacks(
                    ota_cb=on_ota,
                    command_cb=on_command,
                    disconnected_cb=on_disconnect
                )
            )
            break
        except DeviceConfigError:
            raise  # bad credentials/config - retrying won't help
        except Exception as e:
            print("Client setup failed (%s). Retrying in 30 seconds..." % e)
            time.sleep(30)
    while True:
        if _connection_lost.is_set() and llm_busy.acquire(blocking=False):
            llm_busy.release()
            print("Connection was lost at some point. Restarting for a clean MQTT session...")
            exit_and_restart()

        if not c.is_connected():
            print("(re)connecting...")
            c.connect()
            if not c.is_connected():
                print("Unable to connect. Exiting.")
                sys.exit(2)

        with telemetry_lock:
            telemetry["cpu_percent"] = read_cpu_percent()
            telemetry["mem_used_mb"] = read_mem_used_mb()
            telemetry["cpu_temp"] = read_cpu_temp()
            c.send_telemetry(dict(telemetry))
        time.sleep(config["telemetry_interval_s"])

except DeviceConfigError as dce:
    print(dce)
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    sys.exit(0)
