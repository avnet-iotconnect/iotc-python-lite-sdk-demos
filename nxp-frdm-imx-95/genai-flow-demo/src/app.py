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
    # USB camera for ask-vlm captures: "auto" resolves the first USB camera
    # via /dev/v4l/by-id (V4L2 indexes are not stable across reboots), or set
    # an explicit device like /dev/video2
    "camera_device": "auto",
    # Agent (ask-agent): a persistent CPU LLM session routes requests to real
    # board tools (time, temperature, memory...). Stopped after this idle time.
    "agent_idle_timeout_s": 900,
    # Local IoTConnect MCP server (iotc-mcp-server) for the agent's cloud
    # tools. Authenticate once with: iotconnect-cli configure
    "mcp_url": "http://127.0.0.1:8000/mcp",
    # The ONLY C2D command the agent may send to other devices (safety
    # allowlist). "turn on the lights" -> <led_command> on to the device whose
    # DUID best matches the request.
    "led_command": "board-user-led",
    # Spoken-fragment aliases for devices whose names don't survive speech
    # transcription (e.g. "psoc6" arrives as "p-sock 6"). Checked before the
    # fleet search; keys are lowercase words, values are exact DUIDs.
    "device_aliases": {},
    # llama.cpp integration for larger GGUF models (see set-model)
    "llama_dir": "/opt/llama",
    "llama_threads": 6,
    "llama_max_tokens": 200,
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
    "agent_status": "off",        # off | loading | ready | routing | executing | answering
    "agent_request": "",          # last natural-language request to the agent
    "agent_tool": "",             # tool the agent chose
    "agent_tool_result": "",      # what the tool actually returned
    "agent_response": "",         # agent's final answer, grounded in the tool result
    "agent_router": "",           # llm if the model picked the tool, keyword if fallback
    "voice_stt": config.get("stt_model", ""),  # active speech recognizer
    "voice_status": "off",        # off | starting | listening | capturing | answering | error
    "voice_question": "",         # last transcribed spoken question
    "voice_response": "",         # last spoken/streamed answer
    "voice_exchanges": 0,         # completed question/answer rounds this session
    "vlm_model": "%s (%s)" % (config.get("vlm_model", ""), config.get("vlm_precision", "")),
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


def publish_state():
    """Write current state for camera-server.py's /responses page (atomic)."""
    try:
        with telemetry_lock:
            snapshot = dict(telemetry)
        with open("/tmp/genai-state.json.tmp", "w") as f:
            json.dump(snapshot, f)
        os.replace("/tmp/genai-state.json.tmp", "/tmp/genai-state.json")
    except OSError:
        pass


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


def genai_model():
    """GenAI Flow only runs Danube models - fall back to the default when a
    GGUF (llama.cpp) model is selected, so voice/benchmark never break."""
    return config["model"] if config["model"].startswith("danube") else "danube-500M-q8"


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


# --- llama.cpp integration: run larger GGUF models on the CPU -----------------
def gguf_model_path(name):
    return os.path.join(config["llama_dir"], "models", name + ".gguf")


def is_gguf_model(name):
    return os.path.isfile(gguf_model_path(name))


def list_gguf_models():
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(config["llama_dir"], "models", "*.gguf")))


# llama-cli prints e.g. "[ Prompt: 89.4 t/s | Generation: 14.3 t/s ]" after the answer
_LLAMA_PERF_RE = re.compile(r"\[\s*Prompt:\s*([\d.]+)\s*t/s\s*\|\s*Generation:\s*([\d.]+)\s*t/s\s*\]")


def run_llama_prompt(prompt):
    """Run a prompt through llama.cpp (llama-cli) and update llm_* telemetry."""
    model = config["model"]
    cmd = [os.path.join(config["llama_dir"], "src", "build", "bin", "llama-cli"),
           "-m", gguf_model_path(model),
           "-p", prompt,
           "-n", str(config["llama_max_tokens"]),
           "-t", str(config["llama_threads"]),
           "--single-turn"]
    print("Running:", " ".join(cmd))
    start = time.monotonic()
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=config["prompt_timeout_s"],
    )
    total_time = time.monotonic() - start
    out = result.stdout

    prompt_tps = tps = 0.0
    m = _LLAMA_PERF_RE.search(out)
    if m:
        prompt_tps, tps = float(m.group(1)), float(m.group(2))
        out = out[:m.start()]

    # The answer sits between the echoed "> <prompt>" line and the perf line
    if "\n> " in "\n" + out:
        out = ("\n" + out).split("\n> ", 1)[1]
        out = out.split("\n", 1)[1] if "\n" in out else ""
    out = re.sub(r"[\r\x08]", "", out)                       # spinner uses CR/backspace redraws
    response = out.replace("[end of text]", "").strip()
    response = re.sub(r"^[|\\/\-\s]+", "", response)          # drop leading spinner residue
    if not response:
        raise RuntimeError("No llama.cpp response. Output tail:\n" +
                           (result.stdout[-1000:] + result.stderr[-500:]))

    tokens = max(1, int(len(response) / 4))  # ~4 chars/token estimate
    gen_time = round(tokens / tps, 2) if tps else round(total_time, 2)
    ttft = round((len(prompt) / 4) / prompt_tps, 2) if prompt_tps else 0.0
    load_time = round(total_time - gen_time - ttft, 2)
    tps = round(tps, 2)

    with telemetry_lock:
        telemetry.update({
            "llm_model": model,
            "llm_backend": "cpu-llama.cpp",
            "llm_prompt": prompt[:500],
            "llm_response": response[:1000],
            "llm_load_time": load_time,
            "llm_ttft": ttft,
            "llm_gen_time": gen_time,
            "llm_tps": tps,
            "llm_token_count": tokens,
        })
    print("llama.cpp response (%.1fs, %.1f tok/s): %s" % (gen_time, tps, response[:200]))
    return response


def run_llm_prompt(prompt):
    """
    Run a single prompt through eIQ GenAI Flow in keyboard-input / text-output
    mode, measure load time, TTFT, generation time and tokens/sec, and update
    the telemetry dictionary. Returns the response text (or raises).
    GGUF models (see set-model) are dispatched to llama.cpp instead; Danube
    models use a persistent warm session (run_chat_prompt).
    """
    if is_gguf_model(config["model"]):
        return run_llama_prompt(prompt)
    return run_chat_prompt(prompt)


def _run_llm_prompt_oneshot(prompt):  # retained for reference/manual testing
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


def _voice_action(question):
    """Run a spoken action request through the agent (already own llm_busy)."""
    try:
        run_agent_request(question)
        publish_state()
    except Exception as e:
        print("Voice action failed:", e)
        with telemetry_lock:
            telemetry["agent_response"] = "Action failed: %s" % str(e)[:200]
        publish_state()


def voice_session(output_mode):
    """Run the wake-word voice pipeline and publish each exchange as telemetry."""
    global _voice_proc
    # Reap any stale voice pipeline left over from a previous app run - an
    # orphan holds the ALSA playback device open, silencing the new session.
    subprocess.run(["pkill", "-f", r"eiq_genai_flow\.py -i vasr"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chat_llm.stop()  # release the warm ask-llm session; voice needs the RAM
    time.sleep(1)
    cmd = build_genai_cmd(["-i", "vasr", "-o", output_mode, "-m", genai_model()])
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
        publish_state()
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
                    # Voice -> agent bridge: spoken ACTION requests also run
                    # through the agent (e.g. "turn on the lights"), so the
                    # command actually executes while the chat LLM replies.
                    if _TOOL_KEYWORDS[0][0].search(question):
                        q = question
                        threading.Thread(target=lambda: _voice_action(q), daemon=True).start()
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
# AGENT (ask-agent): LLM + real board tools
# -----------------------------------------------------------------------------
# A small LLM confidently invents times, dates, and temperatures. The agent
# fixes that: the LLM only *chooses* a tool, the board *executes* it, and the
# LLM phrases the final answer from the tool's real output.
#
# The agent keeps one persistent GenAI Flow process alive (CPU backend, no
# RAG), so after the first request each round trip takes seconds instead of
# reloading the model. The session is reaped after agent_idle_timeout_s.
import datetime


def tool_get_time():
    now = datetime.datetime.now().astimezone()
    return "The current date and time is " + now.strftime("%A, %B %d, %Y at %H:%M %Z")


def tool_get_temperature():
    return "The chip temperature is %.1f degrees Celsius" % read_cpu_temp()


def tool_get_memory():
    return "The board is using %.0f MB of its 7936 MB of RAM, and CPU load is %.1f percent" % (
        read_mem_used_mb(), telemetry["cpu_percent"])


def tool_get_uptime():
    with open("/proc/uptime") as f:
        s = float(f.read().split()[0])
    return "The board has been running for %d hours and %d minutes" % (s // 3600, (s % 3600) // 60)


def tool_get_ip():
    return "The board's IP address is " + get_local_ip()


def tool_get_usb():
    out = subprocess.run(["lsusb"], stdout=subprocess.PIPE, text=True, timeout=10).stdout
    devices = [re.sub(r"^Bus \d+ Device \d+: ID \S+\s*", "", line).strip()
               for line in out.splitlines()]
    devices = [d for d in devices if d and "root hub" not in d.lower()]
    if not devices:
        return "No USB devices are plugged in"
    return "The USB devices plugged in are: " + ", ".join(devices)


# --- IoTConnect cloud tools, served by the local MCP server -------------------
def _mcp_call(tool, args):
    """Blocking call to the local iotc-mcp-server (official MCP client)."""
    import asyncio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def run():
        async with streamablehttp_client(config["mcp_url"]) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await asyncio.wait_for(s.call_tool(tool, args), timeout=30)
                return res.content[0].text if res.content else "{}"
    return asyncio.run(asyncio.wait_for(run(), timeout=45))


def _mcp_json(tool, args):
    try:
        text = _mcp_call(tool, args)
    except Exception as e:
        raise RuntimeError("IoTConnect MCP server not reachable at %s (%s) - "
                           "start it with: iotc-mcp-server" % (config["mcp_url"], e))
    if "Not logged in" in text:
        raise RuntimeError("IoTConnect MCP is not authenticated - run: iotconnect-cli configure")
    return json.loads(text)


def _own_duid():
    try:
        return json.load(open("/opt/demo/iotcDeviceConfig.json"))["uid"]
    except Exception:
        return ""


def _first_of(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def tool_get_cloud_devices():
    data = _mcp_json("device_list", {})
    devs = data if isinstance(data, list) else \
        next((v for v in data.values() if isinstance(v, list)), [])
    parts = []
    for d in devs[:6]:
        name = _first_of(d, "uniqueId", "duid", "uid", "displayName") or "?"
        state = _first_of(d, "deviceStatus", "status")
        if state is None and "isActive" in d:
            state = "active" if d["isActive"] else "inactive"
        parts.append("%s (%s)" % (name, state) if state else str(name))
    more = ", and %d more" % (len(devs) - 6) if len(devs) > 6 else ""
    return "The IOTCONNECT deployment has %d device%s: %s%s" % (
        len(devs), "" if len(devs) == 1 else "s", ", ".join(parts), more)


def tool_get_cloud_health():
    duid = _own_duid()
    d = _mcp_json("device_get", {"duid": duid})
    if isinstance(d, dict) and isinstance(d.get("device"), dict):
        d = d["device"]
    state = _first_of(d, "deviceStatus", "status")
    if state is None and "isActive" in d:
        state = "active" if d["isActive"] else "inactive"
    tmpl = _first_of(d, "templateCode", "template", "templateName")
    bits = ["Device %s is %s in IOTCONNECT" % (duid, state or "registered")]
    if tmpl:
        bits.append("using template %s" % tmpl)
    return ", ".join(bits)


def tool_get_cloud_telemetry():
    duid = _own_duid()
    data = _mcp_json("telemetry_latest_value", {"duid": duid})
    rows = data if isinstance(data, list) else \
        next((v for v in data.values() if isinstance(v, list)), [])
    interesting = ("cpu_temp", "cpu_percent", "mem_used_mb", "llm_tps", "llm_model", "llm_backend")
    parts = []
    for r in rows:
        key = _first_of(r, "attribute", "attributeName", "key", "name")
        val = _first_of(r, "value", "attributeValue", "latestValue")
        if key in interesting and val is not None:
            parts.append("%s=%s" % (key, val))
    if not parts:  # fall back to whatever came back
        parts = ["%s=%s" % (_first_of(r, "attribute", "attributeName", "key", "name"),
                            _first_of(r, "value", "attributeValue", "latestValue"))
                 for r in rows[:5]]
    return ("The latest telemetry IOTCONNECT received from %s: " % duid) + ", ".join(parts)[:220]


def _list_cloud_devices():
    data = _mcp_json("device_list", {})
    return data if isinstance(data, list) else \
        next((v for v in data.values() if isinstance(v, list)), [])


def tool_send_device_command(request):
    """
    ACTION tool: send the allowlisted LED command to another IoTConnect device.
    The target is fuzzy-matched from the request (voice transcription never
    reproduces exact DUIDs, so we score word fragments against device names).
    """
    words = [w for w in re.findall(r"[a-z0-9]{3,}", request.lower())
             if w not in ("turn", "the", "device", "board", "please", "can", "you")]
    # Alias map first: spoken fragments that reliably mis-transcribe
    aliases = config.get("device_aliases", {})
    for w in words:
        if w in aliases:
            arg = "off" if re.search(r"\boff\b", request, re.I) else "on"
            cmd = config["led_command"]
            _mcp_call("command_send", {"duid": aliases[w], "command_name": cmd, "args": arg})
            return "Sent command %s %s to device %s through IOTCONNECT" % (cmd, arg, aliases[w])
    # Large fleets paginate device_list, so search server-side per word.
    # Score by word length so a distinctive fragment ("psoc6") outranks a
    # generic one ("led" - which is also a device-name fragment in some fleets).
    candidates = {}
    for w in words[:4]:
        try:
            data = _mcp_json("device_list", {"duid_contains": w})
        except RuntimeError:
            raise
        except Exception:
            continue
        devs = data if isinstance(data, list) else \
            next((v for v in data.values() if isinstance(v, list)), [])
        for d in devs:
            duid = str(_first_of(d, "duid", "uniqueId", "name") or "")
            if duid:
                candidates[duid] = candidates.get(duid, 0) + len(w)
    if not candidates:
        raise RuntimeError("No device matched %r - try including part of the device name, e.g. 'lights'"
                           % " ".join(words))
    best = max(candidates, key=candidates.get)

    arg = "off" if re.search(r"\boff\b", request, re.I) else "on"
    cmd = config["led_command"]
    _mcp_call("command_send", {"duid": best, "command_name": cmd, "args": arg})
    return "Sent command %s %s to device %s through IOTCONNECT" % (cmd, arg, best)


AGENT_TOOLS = {
    "get_time": ("the current time or date", tool_get_time),
    "get_temperature": ("the chip or board temperature", tool_get_temperature),
    "get_memory": ("memory usage or CPU load", tool_get_memory),
    "get_uptime": ("how long the board has been running", tool_get_uptime),
    "get_ip": ("the board's network or IP address", tool_get_ip),
    "get_usb": ("which USB devices are plugged in", tool_get_usb),
    "get_cloud_devices": ("the devices in the IOTCONNECT cloud deployment", tool_get_cloud_devices),
    "get_cloud_health": ("whether this device is healthy and active in the cloud", tool_get_cloud_health),
    "get_cloud_telemetry": ("the latest telemetry the cloud received", tool_get_cloud_telemetry),
    "send_device_command": ("turning a device's LED or light on or off", tool_send_device_command),
}

# Keyword fallback for when the 500M model's tool pick can't be parsed
_TOOL_KEYWORDS = [
    (re.compile(r"turn (on|off)|switch (on|off)|\bled\b|light", re.I), "send_device_command"),
    (re.compile(r"deployment|fleet|how many devices|other devices|iotconnect|cloud", re.I), "get_cloud_devices"),
    (re.compile(r"telemetry|last reported|received", re.I), "get_cloud_telemetry"),
    (re.compile(r"health|healthy|online|active", re.I), "get_cloud_health"),
    (re.compile(r"usb|plugged|peripheral", re.I), "get_usb"),
    (re.compile(r"time|clock|date|day|today", re.I), "get_time"),
    (re.compile(r"temperature|hot|warm|thermal|cool", re.I), "get_temperature"),
    (re.compile(r"memory|ram|cpu|load|usage", re.I), "get_memory"),
    (re.compile(r"uptime|running|how long", re.I), "get_uptime"),
    (re.compile(r"\bip\b|address|network", re.I), "get_ip"),
]


class PersistentLLM:
    """A GenAI Flow keyb/text session kept alive for multi-turn use."""

    def __init__(self, name="agent", cmd_factory=None):
        self.name = name
        self.cmd_factory = cmd_factory
        self.signature = None      # config the session was started with
        self.proc = None
        self.reader = None
        self.lock = threading.Lock()
        self.last_used = 0.0

    def _clean(self, buf):
        return _ANSI_RE.sub("", buf.decode("utf-8", "replace"))

    def start(self):
        if self.cmd_factory:
            cmd = self.cmd_factory()
        else:
            # Agent default: always CPU (41s load vs ~2min NPU compile) and no
            # RAG (the tool router must see only its own instructions).
            cmd = [config["python"], "-u", genai_script_path(),
                   "-i", "keyb", "-o", "text", "-m", "danube-500M-q8"]
        print("Starting %s LLM session: %s" % (self.name, " ".join(cmd)))
        self.proc = subprocess.Popen(
            cmd, cwd=config["genai_dir"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self.reader = ProcReader(self.proc)
        self._read_until_marker(config["prompt_timeout_s"])
        self.last_used = time.monotonic()

    def _read_until_marker(self, timeout):
        buf = b""
        deadline = time.monotonic() + timeout
        while READY_MARKER not in self._clean(buf):
            if time.monotonic() > deadline:
                raise RuntimeError("Agent LLM timed out:\n" + self._clean(buf[-1500:]))
            ts, data = self.reader.get(timeout=5)
            if data is None:
                raise RuntimeError("Agent LLM exited:\n" + self._clean(buf[-1500:]))
            buf += data
        return buf

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ask(self, prompt, timeout=120):
        return self.ask_timed(prompt, timeout)[0]

    def ask_timed(self, prompt, timeout=120):
        """Returns (answer, ttft_s, gen_time_s, token_count)."""
        with self.lock:
            if not self.alive():
                self.start()
            self.proc.stdin.write((prompt.strip() + "\n").encode())
            self.proc.stdin.flush()
            t0 = time.monotonic()
            buf = b""
            t_first = t_last = None
            deadline = t0 + timeout
            while READY_MARKER not in self._clean(buf):
                if time.monotonic() > deadline:
                    raise RuntimeError("%s LLM timed out" % self.name)
                ts, data = self.reader.get(timeout=5)
                if data is None:
                    raise RuntimeError("%s LLM exited:\n" % self.name + self._clean(buf[-1500:]))
                if data and self._clean(data).strip():
                    if t_first is None:
                        t_first = ts
                    t_last = ts
                buf += data
            self.last_used = time.monotonic()
        raw = buf.decode("utf-8", "replace")
        token_list = _LLM_TOKEN_CONTENT_RE.findall(raw)
        answer = "".join(token_list).strip()
        if not answer:  # fall back to plain text before the marker
            answer = self._clean(buf).split(READY_MARKER)[0].strip()
        ttft = round(t_first - t0, 2) if t_first else 0.0
        gen_time = round((t_last - t0), 2) if t_last else 0.0
        return answer, ttft, gen_time, len(token_list)

    def stop(self):
        with self.lock:
            if self.proc:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                self.proc = None


agent_llm = PersistentLLM("agent")


def _chat_cmd():
    return build_genai_cmd(["-i", "keyb", "-o", "text", "-m", genai_model()])


chat_llm = PersistentLLM("chat", _chat_cmd)


def _chat_signature():
    return (genai_model(), config["backend"], bool(config.get("use_rag")))


def run_chat_prompt(prompt):
    """
    ask-llm via a persistent GenAI Flow session: the model loads once per
    configuration (model/backend/RAG) and answers follow-ups in seconds.
    Any set-* change or voice session invalidates it; idle-reaped like the
    agent session.
    """
    sig = _chat_signature()
    load_time = 0.0
    if not (chat_llm.alive() and chat_llm.signature == sig):
        if chat_llm.proc is not None and chat_llm.signature == sig:
            print("chat LLM session died unexpectedly (likely OOM) - reloading")
        chat_llm.stop()
        chat_llm.signature = sig
        if agent_llm.alive():
            print("Releasing agent session - the board fits one LLM session (no swap)")
            agent_llm.stop()
            with telemetry_lock:
                telemetry["agent_status"] = "off"
        t0 = time.monotonic()
        with chat_llm.lock:
            chat_llm.start()
        load_time = round(time.monotonic() - t0, 2)
    answer, ttft, gen_time, tokens = chat_llm.ask_timed(prompt, timeout=config["prompt_timeout_s"])
    # Drop logger lines that can interleave with the token stream
    answer = "\n".join(
        l for l in answer.splitlines()
        if not re.match(r"\s*\d{4}-\d{2}-\d{2}[ T]", l) and "Error:" not in l
    ).strip()
    if not answer:
        raise RuntimeError("No LLM response captured")
    if tokens == 0:
        tokens = max(1, int(len(answer) / 4))
    tps = round(tokens / max(0.01, gen_time - ttft), 2) if gen_time > ttft else 0.0
    with telemetry_lock:
        telemetry.update({
            "llm_model": genai_model(),
            "llm_backend": config["backend"],
            "llm_prompt": prompt[:500],
            "llm_response": answer[:1000],
            "llm_load_time": load_time,
            "llm_ttft": ttft,
            "llm_gen_time": gen_time,
            "llm_tps": tps,
            "llm_token_count": tokens,
        })
    print("LLM response (warm=%s, %.1fs, ~%.1f tok/s): %s" % (load_time == 0.0, gen_time, tps, answer[:200]))
    return answer


def agent_reaper():
    """Stop idle LLM sessions (agent + chat) to reclaim RAM."""
    while True:
        time.sleep(60)
        for sess in (agent_llm, chat_llm):
            if sess.alive() and time.monotonic() - sess.last_used > config["agent_idle_timeout_s"]:
                if llm_busy.acquire(blocking=False):
                    try:
                        print("%s LLM idle - stopping session" % sess.name)
                        sess.stop()
                        if sess is agent_llm:
                            with telemetry_lock:
                                telemetry["agent_status"] = "off"
                    finally:
                        llm_busy.release()


threading.Thread(target=agent_reaper, daemon=True).start()


def set_agent_status(status):
    with telemetry_lock:
        telemetry["agent_status"] = status


def run_agent_request(request):
    """Route a natural-language request to a board tool and answer from its result."""
    if not agent_llm.alive():
        set_agent_status("loading")
        if chat_llm.alive():
            print("Releasing chat session - the board fits one LLM session (no swap)")
            chat_llm.stop()
    else:
        set_agent_status("routing")

    # Prompt formats chosen empirically - danube-500M answers simple Q/A framing
    # reliably but rambles on multi-line instruction menus.
    router_prompt = "Q: Which tool answers '%s'? Options: %s. A:" % (
        request, ", ".join(AGENT_TOOLS))
    reply = agent_llm.ask(router_prompt)
    set_agent_status("routing")

    # The model often echoes the options list before answering, so the chosen
    # tool is the LAST one mentioned. A keyword match on the request overrides
    # a disagreeing LLM pick - tiny models sometimes echo without answering.
    mentions = [(reply.rfind(name), name) for name in AGENT_TOOLS if name in reply]
    llm_pick = max(mentions)[1] if mentions else None
    kw_pick = next((name for pattern, name in _TOOL_KEYWORDS if pattern.search(request)), None)

    if llm_pick and (kw_pick is None or kw_pick == llm_pick):
        tool_name, router = llm_pick, "llm"
    elif kw_pick:
        tool_name, router = kw_pick, ("keyword-override" if llm_pick else "keyword")
    else:
        raise RuntimeError("No tool matches this request (LLM said: %s)" % reply[:120])

    set_agent_status("executing")
    fn = AGENT_TOOLS[tool_name][1]
    tool_result = fn(request) if fn.__code__.co_argcount else fn()
    print("Agent tool %s -> %s" % (tool_name, tool_result))

    set_agent_status("answering")
    if tool_name.startswith("send_"):
        answer = tool_result  # for actions, the confirmation IS the answer
    else:
        answer = agent_llm.ask("%s. Q: %s? A:" % (tool_result, request.rstrip("?")))
    # Sanity check: the answer must actually reuse the tool's data - if the
    # small model wandered off, the tool result itself is the better answer.
    fact_words = {w for w in re.findall(r"[A-Za-z0-9.:]{4,}", tool_result)}
    answer_words = {w for w in re.findall(r"[A-Za-z0-9.:]{4,}", answer)}
    if len(fact_words & answer_words) < 2:
        answer = tool_result

    with telemetry_lock:
        telemetry.update({
            "agent_request": request[:500],
            "agent_tool": tool_name,
            "agent_tool_result": tool_result[:500],
            "agent_response": answer[:1000],
            "agent_router": router,
        })
    set_agent_status("ready")
    print("Agent response (%s via %s): %s" % (tool_name, router, answer[:200]))
    return answer


# -----------------------------------------------------------------------------
# VISION LANGUAGE MODEL (ask-vlm)
# -----------------------------------------------------------------------------
# Perf line printed by the VLM after each answer, e.g.:
#   Vision: 3.31s | TTFT: 3.79s (Decoder 0.48s) | Current decode speed: 12.50tok/s
_VLM_PERF_RE = re.compile(
    r"Vision:\s*([\d.]+)s\s*\|\s*TTFT:\s*([\d.]+)s.*?([\d.]+)\s*tok/s"
)

VLM_FRAME_PATH = "/opt/demo/vlm-frame.jpg"


def camera_device():
    """Resolve the camera device ('auto' = first USB camera by stable udev path)."""
    dev = config.get("camera_device", "auto")
    if dev == "auto" or not os.path.exists(dev):
        links = sorted(glob.glob("/dev/v4l/by-id/usb-*-video-index0"))
        if links:
            return os.path.realpath(links[0])
    return dev


def vlm_installed():
    return os.path.isdir(os.path.join(config["vlm_dir"], "src", "vlm"))


def capture_frame():
    """
    Grab a single JPEG frame from the USB camera. If camera-server.py is
    streaming (it owns the device), reuse its shared frame instead.
    """
    shared = "/tmp/camera-latest.jpg"
    try:
        if time.time() - os.path.getmtime(shared) < 3:
            import shutil
            shutil.copyfile(shared, VLM_FRAME_PATH)
            return VLM_FRAME_PATH
    except OSError:
        pass
    if os.path.exists(VLM_FRAME_PATH):
        os.remove(VLM_FRAME_PATH)
    subprocess.run(
        ["gst-launch-1.0", "-q",
         "v4l2src", "device=%s" % camera_device(), "num-buffers=1", "!",
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
            "vlm_model": "%s (%s)" % (config["vlm_model"], config["vlm_precision"]),
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
        cmd = build_genai_cmd(args + ["-m", genai_model(), "-r", "-b"])
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
            publish_state()
            job()
            with telemetry_lock:
                telemetry["genai_status"] = "idle"
            publish_state()
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
    # Keep -u in the restarted command line: unbuffered logs, and process
    # managers / pkill patterns keep matching the same signature.
    os.execv(sys.executable, [sys.executable, "-u", __file__])


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

    elif msg.command_name == "ask-agent":
        if len(msg.command_args) < 1:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected a request, e.g. what time is it")
            return
        if not genai_installed():
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Busy: %s (voice: %s) - stop that first" % (telemetry["genai_status"], telemetry["voice_status"]))
            return
        request = " ".join(msg.command_args)
        note = "" if agent_llm.alive() else " (first request loads the model, ~1 min)"
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Agent working - answer will arrive as telemetry" + note)
        start_llm_job(lambda: run_agent_request(request), "agent", "Agent request complete")

    elif msg.command_name == "agent-start":
        # Pre-loading doesn't generate anything, so it deliberately skips the
        # llm_busy lock - it works even while a voice session is running
        # (the agent loads on CPU; concurrency is guarded by agent_llm.lock).
        if agent_llm.alive():
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Agent session is already loaded")
            return
        if not genai_installed():
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Agent loading (~1 min) - agent_status shows ready when warm")

        def preload():
            try:
                set_agent_status("loading")
                if chat_llm.alive():
                    # Wait out any in-flight ask-llm before taking its session
                    with llm_busy:
                        print("Releasing chat session - the board fits one LLM session (no swap)")
                        chat_llm.stop()
                with agent_llm.lock:
                    if not agent_llm.alive():
                        agent_llm.start()
                set_agent_status("ready")
                publish_state()
                print("Agent session pre-loaded")
            except Exception as e:
                print("Agent preload failed:", e)
                set_agent_status("error")
        threading.Thread(target=preload, daemon=True).start()

    elif msg.command_name == "agent-stop":
        if agent_llm.alive():
            agent_llm.stop()
            with telemetry_lock:
                telemetry["agent_status"] = "off"
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Agent session stopped")
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Agent session is not running")

    elif msg.command_name == "voice-start":
        if not genai_installed():
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "eIQ GenAI Flow not found at %s - see demo README" % config["genai_dir"])
            return
        if not llm_busy.acquire(blocking=False):
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Busy: %s (voice: %s) - stop that first" % (telemetry["genai_status"], telemetry["voice_status"]))
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
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Busy: %s (voice: %s) - stop that first" % (telemetry["genai_status"], telemetry["voice_status"]))
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
        valid = ["danube-500M-q8", "danube-500M-q4"] + list_gguf_models()
        if len(msg.command_args) == 1 and msg.command_args[0] in valid:
            config["model"] = msg.command_args[0]
            save_config(config)
            with telemetry_lock:
                telemetry["llm_model"] = config["model"]
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Model set to " + config["model"])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Available models: " + ", ".join(valid))

    elif msg.command_name == "set-stt":
        valid_stt = ("moonshine-tiny", "moonshine-base", "whisper-small.en")
        if len(msg.command_args) == 1 and msg.command_args[0] in valid_stt:
            config["stt_model"] = msg.command_args[0]
            save_config(config)
            with telemetry_lock:
                telemetry["voice_stt"] = config["stt_model"]
            note = " - voice-stop / voice-start to apply" if telemetry["voice_status"] not in ("off", "error") else ""
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                               "Speech recognizer set to %s%s" % (config["stt_model"], note))
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Options: " + ", ".join(valid_stt))

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
# Offline test modes - exercise the AI paths without any /IOTCONNECT setup:
#   python3 app.py --test-agent what time is it
#   python3 app.py --test-llm what is an npu
if len(sys.argv) >= 2 and sys.argv[1] in ("--test-agent", "--test-llm"):
    question = " ".join(sys.argv[2:]) or "What time is it?"
    try:
        answer = run_agent_request(question) if sys.argv[1] == "--test-agent" else run_llm_prompt(question)
        print("\n=== RESULT ===\n" + answer)
    finally:
        agent_llm.stop()
    sys.exit(0)

try:
    # Reap keyb LLM sessions orphaned by a previous app instance - they hold
    # RAM (and their answers go nowhere).
    subprocess.run(["pkill", "-f", r"eiq_genai_flow\.py -i keyb"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        publish_state()
        time.sleep(config["telemetry_interval_s"])

except DeviceConfigError as dce:
    print(dce)
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    sys.exit(0)
