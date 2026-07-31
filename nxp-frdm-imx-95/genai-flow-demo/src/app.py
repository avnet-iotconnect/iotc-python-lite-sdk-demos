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
#   Kinara Ara-2 / NXP Ara240 discrete NPU: set backend to "ara2" to run ask-llm
#   on the module via NXP's eIQ AAF Connector (an OpenAI-compatible REST server
#   in front of the Ara240 runtime). Requires the rt-sdk-ara2 runtime + the
#   connector running on the board and an Ara240 model.dvm loaded - see
#   docs/ARA2-ENABLEMENT-REQUEST.md and MODELS.md.
# -----------------------------------------------------------------------------

import glob
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import urllib.parse
import time
import urllib.request

import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta, C2dMessage

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
    # RAG document ingestion (rag-add): where GenAI Flow's RAG package lives
    "rag_dir": "/root/eiq_genai_flow/rag",

    # "cpu", "neutron" (i.MX 95 B0 only), or "ara2" (Kinara Ara-2 / NXP Ara240
    # discrete NPU via the eIQ AAF Connector REST API - see MODELS.md).
    "backend": "cpu",
    # ara2 backend: local eIQ AAF Connector endpoint and the Ara240 model to use
    # (one of the connector's available_models, e.g. a nxp/*-Ara240 model.dvm).
    # Port 8100 keeps clear of the demo's MCP server on 8000 (the connector's
    # own default) - set the connector's --port to match.
    "ara2_aaf_url": "http://127.0.0.1:8100/v1/chat/completions",
    "ara2_model": "Qwen2.5-7B-Instruct",
    "ara2_max_tokens": 200,
    # IOTCONNECT model push (Cloud-to-Device): where a pushed Ara240 model is
    # deployed, and the connector service/config to reload once it lands.
    "model_deploy_dir": "/usr/share/llm",
    "aaf_connector_config": "/usr/share/eiq/aaf-connector/server_config.json",
    "aaf_connector_service": "eiq-aaf-connector",
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
    "agent_idle_timeout_s": 3600,
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
    # The MCX vibration-sensing device (eiq-pdm-vibration demo) the agent can
    # monitor and control over IOTCONNECT (get_vibration / send_motor_command).
    "vibration_duid": "mclMCXvib",
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
    "vlm_load_time": 0.0,         # model load (s); 0 when the warm VLM worker is reused
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
    "disk_free_gb": 0.0,          # free space on / - a model push needs ~2x the model size
    "disk_used_pct": 0.0,         # root filesystem usage, same accounting as df
    # Ara240 presence, so a UI can disable NPU options on boards without one:
    # absent (no card) | present (card, runtime not serving) | ready (models served)
    "ara_status": "absent",
    "ara_models": "",             # comma-separated models the connector serves
    "rag_status": "idle",         # idle | downloading | indexing | ready | error
    "rag_doc": "",                # last document added to the RAG database
    "rag_detail": "",             # progress or error detail
    "rag_docs": "",               # inventory: name:chunks:builtin;... for a UI list
    "rag_chunks": 0,              # total chunks in the RAG database
    "model_deploy_status": "idle",   # idle | downloading | deploying | loading | ready | error
    "model_deploy_name": "",         # name of the model IOTCONNECT last pushed
    "model_deploy_detail": "",       # human-readable progress/error detail
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


def read_disk():
    """
    Root filesystem free GB and used %, using df's accounting (usage is measured
    against the space actually available to us, not the root-reserved blocks).
    The model store lives here, and an IOTCONNECT model push needs roughly twice
    the model size free: it downloads the package next to where it unpacks it.
    """
    try:
        s = os.statvfs("/")
        used = (s.f_blocks - s.f_bfree) * s.f_frsize
        avail = s.f_bavail * s.f_frsize
        return round(avail / float(1 << 30), 1), round(100.0 * used / max(1, used + avail), 1)
    except (OSError, ValueError):
        return 0.0, 0.0


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


def _llama_complete(prompt, max_tokens):
    """Run a prompt through llama.cpp (llama-cli); return
    (response, prompt_tps, gen_tps, total_time). Shared by ask-llm and the agent."""
    model = config["model"]
    cmd = [os.path.join(config["llama_dir"], "src", "build", "bin", "llama-cli"),
           "-m", gguf_model_path(model),
           "-p", prompt,
           "-n", str(max_tokens),
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
    return response, prompt_tps, tps, total_time


def run_llama_prompt(prompt):
    """Run a prompt through llama.cpp (llama-cli) and update llm_* telemetry."""
    model = config["model"]
    response, prompt_tps, tps, total_time = _llama_complete(prompt, config["llama_max_tokens"])
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


def _llama_generate(prompt, max_tokens=200):
    """Text-only llama.cpp completion for the agent (no llm_* telemetry)."""
    return _llama_complete(prompt, max_tokens)[0]


# --- Kinara Ara-2 / NXP Ara240 backend: inference via the eIQ AAF Connector ----
# rt-sdk-ara2 + the eIQ AAF Connector expose an OpenAI-compatible REST API on the
# board (default 127.0.0.1:8000). The ara2 backend POSTs the prompt there and
# streams tokens back, measuring TTFT and tokens/sec the same way the other paths
# do, so ask-llm works unchanged - just on the discrete NPU.
# NOTE: wired to the connector's documented /v1/chat/completions API; end-to-end
# validation is pending the runtime coming up on a matching BSP (needs the uiodma
# driver - see docs/ARA2-ENABLEMENT-REQUEST.md).
def run_ara2_prompt(prompt):
    url = config["ara2_aaf_url"]
    model = config.get("ara2_model", "Qwen2.5-7B-Instruct")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": config.get("ara2_max_tokens", 200),
        "stream": True,
    }
    print("Ara2 request -> %s (model %s)" % (url, model))
    start = time.monotonic()
    t_first = t_last = None
    pieces = []
    with requests.post(url, json=payload, stream=True,
                       timeout=config["prompt_timeout_s"]) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0].get("delta", {})
            except (ValueError, KeyError, IndexError):
                continue
            token = delta.get("content") or ""
            if token:
                now = time.monotonic()
                if t_first is None:
                    t_first = now
                t_last = now
                pieces.append(token)
    response = "".join(pieces).strip()
    if not response:
        raise RuntimeError("No response from the Ara2 AAF connector at %s - is "
                           "`connector` running and a model.dvm loaded?" % url)
    ttft = round(t_first - start, 2) if t_first else 0.0
    gen_time = round((t_last or time.monotonic()) - start, 2)
    tokens = max(1, int(len(response) / 4))  # ~4 chars/token estimate
    tps = round(tokens / max(0.01, (t_last or start) - (t_first or start)), 2)

    with telemetry_lock:
        telemetry.update({
            "llm_model": model,
            "llm_backend": "ara2",
            "llm_prompt": prompt[:500],
            "llm_response": response[:1000],
            "llm_load_time": 0.0,     # model stays resident in the connector
            "llm_ttft": ttft,
            "llm_gen_time": gen_time,
            "llm_tps": tps,
            "llm_token_count": tokens,
        })
    print("Ara2 response (%.1fs, %.1f tok/s): %s" % (gen_time, tps, response[:200]))
    return response


def _ara2_generate(prompt, max_tokens=200):
    """Text-only completion from the Ara connector (no llm_* telemetry) - used by
    the agent so its reasoning runs on the resident Ara240 model, not Danube."""
    payload = {
        "model": config.get("ara2_model", "Qwen2.5-7B-Instruct"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    resp = requests.post(config["ara2_aaf_url"], json=payload,
                         timeout=config["prompt_timeout_s"])
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def run_llm_prompt(prompt):
    """
    Run a single prompt through eIQ GenAI Flow in keyboard-input / text-output
    mode, measure load time, TTFT, generation time and tokens/sec, and update
    the telemetry dictionary. Returns the response text (or raises).
    The Ara2 backend (set-backend ara2) is dispatched to the eIQ AAF Connector;
    GGUF models (see set-model) go to llama.cpp; Danube models use a persistent
    warm GenAI Flow session (run_chat_prompt).
    """
    if config["backend"] == "ara2":
        return run_ara2_prompt(prompt)
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
    agent_llm.stop()  # and the Danube agent session, if it was pre-warmed
    vlm_session.stop()  # release the warm VLM too - a voice session is RAM-heavy
    time.sleep(1)
    # NOTE (future expansion): voice always runs on Danube here. The LLM step is
    # baked into GenAI Flow's vasr pipeline (wake -> STT -> Danube -> TTS), so voice
    # follows set-backend cpu/neutron and Danube q8/q4, but cannot use the Ara240
    # (ara2) or a GGUF without rebuilding the wake/STT/TTS loop around the connector
    # (unlike the agent, which now does). genai_model() falls back to Danube for
    # those selections. See the agent's agent_generate() for the pattern to reuse.
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
                    # through the agent (e.g. "turn on the lights", "inject a
                    # fault"), so the command actually executes while chat replies.
                    # FUTURE UPGRADE: only ACTIONS are bridged and the spoken
                    # reply is still Danube's (the agent's real result goes to
                    # telemetry, not TTS). To answer spoken STATUS reads out loud
                    # - "how's the motor" -> get_vibration, said aloud - bridge
                    # read tools here too AND speak the agent's answer via TTS,
                    # i.e. a wake->STT->agent->TTS path instead of GenAI Flow's
                    # baked-in STT->Danube->TTS. See the voice_session() note.
                    if _is_voice_action(question):
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


def read_mem_total_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def tool_get_memory():
    # Read the total rather than hard-coding it - the reserved Neutron CMA pool
    # makes MemTotal board- and device-tree-dependent.
    return "The board is using %.0f MB of its %.0f MB of RAM, and CPU load is %.1f percent" % (
        read_mem_used_mb(), read_mem_total_mb(), telemetry["cpu_percent"])


def tool_get_disk():
    free_gb, used_pct = read_disk()
    return "The board's flash storage is %.0f percent full, with %.1f GB free" % (
        used_pct, free_gb)


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


# --- MCX vibration device (eiq-pdm-vibration demo): monitor + control ----------
def tool_get_vibration():
    """Read the MCX vibration sensor's latest telemetry from IOTCONNECT."""
    duid = config.get("vibration_duid")
    if not duid:
        raise RuntimeError("No vibration_duid configured")
    data = _mcp_json("telemetry_latest_value", {"duid": duid})
    rows = data.get("attributes") if isinstance(data, dict) else None
    if not rows:
        rows = data if isinstance(data, list) else \
            next((v for v in data.values() if isinstance(v, list)), [])
    vals = {}
    for r in rows or []:
        k = _first_of(r, "attribute", "attributeName", "key", "name")
        v = _first_of(r, "value", "attributeValue", "latestValue")
        if k is not None:
            vals[k] = v

    def _num(x):
        try:
            return round(float(x), 3)
        except (TypeError, ValueError):
            return None

    if not any(k.startswith("vib.") for k in vals):
        return "The %s device is reachable but has not reported vibration data yet" % duid
    # vib.motor is the motor-state classification (idle / balanced / unbalanced /
    # both). vib.state is a health flag that is unreliable here, so it isn't used.
    parts = ["The %s vibration sensor reports the motor is %s"
             % (duid, vals.get("vib.motor") or vals.get("vib.model_class") or "unknown")]
    rms = _num(vals.get("vib.rms_g"))
    if rms is not None:
        parts.append("overall vibration %s g" % rms)
    return ", ".join(parts)


# Natural-language intent -> vibration device command (full template command set)
# Order matters (first match wins). "both" -> run-both (runs the healthy AND the
# faulty motor); a plain start/run/turn-on of the motor -> inject-healthy (the
# healthy motor). "stop"/"off" -> motor-stop is checked before either, and a
# request naming a fault -> inject-fault (the faulty motor) before that.
_MOTOR_COMMANDS = [
    (re.compile(r"threshold", re.I), "set-threshold"),
    (re.compile(r"interval|period|\brate\b", re.I), "set-interval"),
    (re.compile(r"\breboot\b|\brestart\b", re.I), "reboot"),
    (re.compile(r"\b(inject|induce|trigger|simulate|cause|create|add|make|set)\b.*\bfault\b|\bfaulty\b|\bunbalanced\b", re.I), "inject-fault"),
    (re.compile(r"\b(stop|halt|kill|pause)\b|\boff\b", re.I), "motor-stop"),
    (re.compile(r"\bboth\b", re.I), "run-both"),
    (re.compile(r"\bhealthy\b|\bnormal\b|\bfix\b|\brepair\b|\bclear\b|\bheal\b|\b(run|start|spin|resume|go|turn|on)\b", re.I), "inject-healthy"),
]


def tool_send_motor_command(request):
    """ACTION tool: control the MCX vibration device (inject-fault/healthy,
    run-both, motor-stop, set-threshold, set-interval, reboot)."""
    duid = config.get("vibration_duid")
    if not duid:
        raise RuntimeError("No vibration_duid configured")
    cmd = next((c for pat, c in _MOTOR_COMMANDS if pat.search(request)), None)
    if cmd is None:
        raise RuntimeError("Motor command not understood - try 'inject a fault', "
                           "'start the motor' (healthy), 'run both', 'stop', "
                           "'set threshold 0.5', or 'reboot'")
    args = ""
    if cmd in ("set-threshold", "set-interval"):
        m = re.search(r"(\d+(?:\.\d+)?)", request)
        if not m:
            raise RuntimeError("%s needs a number, e.g. 'set threshold to 0.5'" % cmd)
        args = m.group(1)
    _mcp_call("command_send", {"duid": duid, "command_name": cmd, "args": args})
    return "Sent %s%s to the vibration device %s through IOTCONNECT" % (
        cmd, (" = %s" % args) if args else "", duid)


# -----------------------------------------------------------------------------
# RAG DOCUMENT INGESTION (rag-add <url>)
# -----------------------------------------------------------------------------
# Adds a document to the on-device RAG database so the LLM can answer from it.
# The file is fetched from a URL (IOTCONNECT hands out a presigned link when a
# document is uploaded through the console/cockpit), dropped into GenAI Flow's
# input_files, and run through its own pipeline:
#     document_parsing -> rag.preprocessing.generate_chunks
#                      -> rag.preprocessing.generate_embeddings (rebuilds the .pkl)
# Answers are grounded in it as soon as RAG is on (set-rag on).
# Documents are chunked here, in the app, into GenAI Flow's chunked_files format
# ({"doc-id": {"chunks": [...]}}) and only its embedding step is run. That keeps
# ingestion light: GenAI Flow's own chunker pulls in nltk/spacy (and docling for
# PDFs), none of which ship on a demo board - embedding needs only torch, which
# the LLM already requires.
_RAG_TEXT_EXT = (".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".log")
RAG_CHUNK_CHARS = 900          # ~200 tokens; the hand-made chunks run 200-400 chars
RAG_CHUNK_MIN = 120
_RAG_PARA_RE = re.compile(r"\n{3,}")
_RAG_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text, max_chars=RAG_CHUNK_CHARS, min_chars=RAG_CHUNK_MIN):
    """Split a document into retrieval-sized chunks on paragraph, then sentence
    boundaries - short trailing fragments are folded into the previous chunk."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _RAG_PARA_RE.sub("\n\n", text).strip()
    chunks = []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        if len(para) <= max_chars:
            pieces = [para]
        else:  # long paragraph: pack sentences up to the limit
            pieces, cur = [], ""
            for sent in _RAG_SENT_RE.split(para):
                if cur and len(cur) + len(sent) + 1 > max_chars:
                    pieces.append(cur.strip())
                    cur = sent
                else:
                    cur = (cur + " " + sent).strip()
            if cur:
                pieces.append(cur.strip())
        for piece in pieces:
            if chunks and len(piece) < min_chars:
                chunks[-1] = (chunks[-1] + " " + piece).strip()
            else:
                chunks.append(piece)
    return [c for c in chunks if c]


def set_rag_status(status, detail=""):
    with telemetry_lock:
        telemetry["rag_status"] = status
        if detail:
            telemetry["rag_detail"] = detail[:300]
    publish_state()


_RAG_BUILTIN = ("garbage_model", "intent", "FRDM95_hand_made_chunks", "Medical")


def rag_inventory():
    """[(name, chunks, builtin)] for every document in the RAG database."""
    chunk_dir = os.path.join(config["rag_dir"], "src", "data", "chunked_files")
    out = []
    try:
        names = sorted(os.listdir(chunk_dir))
    except OSError:
        return out
    for f in names:
        if not f.endswith(".json"):
            continue
        stem = os.path.splitext(f)[0]
        try:
            with open(os.path.join(chunk_dir, f), encoding="utf-8") as fh:
                doc = json.load(fh)
            n = sum(len(v.get("chunks", [])) for v in doc.values() if isinstance(v, dict))
        except (OSError, ValueError):
            n = 0
        out.append((stem, n, stem in _RAG_BUILTIN))
    return out


def refresh_rag_docs():
    """Publish the database inventory as telemetry so a UI can list it."""
    inv = rag_inventory()
    summary = ";".join("%s:%d:%d" % (n, c, 1 if b else 0) for n, c, b in inv)
    with telemetry_lock:
        telemetry["rag_docs"] = summary[:900]
        telemetry["rag_chunks"] = sum(c for _, c, _ in inv)
    return inv


# Embedding rebuilds the whole database and is memory-hungry: two of them at
# once OOM-killed the app on an 8 GB board, so ingestion is serialized. A second
# document waits its turn rather than running concurrently.
rag_lock = threading.Lock()


def rag_add(url, name=None):
    """Download a document, chunk it, and rebuild the on-device RAG database."""
    rag_dir = config["rag_dir"]
    src_dir = os.path.join(rag_dir, "src")
    chunk_dir = os.path.join(src_dir, "data", "chunked_files")
    input_dir = os.path.join(src_dir, "data", "input_files")
    if not os.path.isdir(chunk_dir):
        raise RuntimeError("RAG data directory not found at %s - is GenAI Flow installed?" % chunk_dir)

    name = name or os.path.basename(urllib.parse.urlparse(url).path) or "document.txt"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    stem, ext = os.path.splitext(name)
    if ext.lower() not in _RAG_TEXT_EXT:
        raise RuntimeError("%s is not a text document - upload .txt, .md, .csv, .json or .log "
                           "(PDF/DOCX need GenAI Flow's docling parser, which is not installed)" % name)

    set_rag_status("downloading", name)
    os.makedirs(input_dir, exist_ok=True)
    dest = os.path.join(input_dir, name)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for part in r.iter_content(chunk_size=65536):
                f.write(part)
    text = open(dest, encoding="utf-8", errors="replace").read()
    chunks = chunk_text(text)
    if not chunks:
        raise RuntimeError("%s has no readable text" % name)
    set_rag_status("indexing", "%s - %d chunks" % (name, len(chunks)))
    with open(os.path.join(chunk_dir, stem + ".json"), "w", encoding="utf-8") as f:
        json.dump({stem: {"chunks": chunks}}, f, indent=4)
    print("RAG: %s -> %d chunks, embedding..." % (name, len(chunks)))

    # generate_embeddings prompts for a one-line description of the database
    # (used by the domain classifier) - feed it rather than block on stdin.
    description = config.get("rag_description") or ("Documents about " + stem.replace("_", " "))
    r = subprocess.run([config["python"], "-m", "rag.preprocessing.generate_embeddings"],
                       cwd=src_dir, input=description + "\n",
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=config.get("rag_timeout_s", 900))
    if r.returncode != 0:
        raise RuntimeError("RAG embedding failed: %s" % (r.stdout or "")[-300:])

    docs = len([f for f in os.listdir(chunk_dir) if f.endswith(".json")])
    with telemetry_lock:
        telemetry["rag_doc"] = name
        telemetry["rag_detail"] = "%d chunks from %s | %d document(s) indexed" % (len(chunks), name, docs)
    refresh_rag_docs()
    set_rag_status("ready")
    chat_llm.stop()   # a rebuilt database only takes effect in a fresh session
    print("RAG: %s indexed (%d chunks, %d docs)" % (name, len(chunks), docs))
    return "Added %s to the RAG database: %d chunks, %d documents indexed" % (name, len(chunks), docs)


AGENT_TOOLS = {
    "get_time": ("the current time or date", tool_get_time),
    "get_temperature": ("the chip or board temperature", tool_get_temperature),
    "get_memory": ("memory usage or CPU load", tool_get_memory),
    "get_disk": ("free flash storage or disk space", tool_get_disk),
    "get_uptime": ("how long the board has been running", tool_get_uptime),
    "get_ip": ("the board's network or IP address", tool_get_ip),
    "get_usb": ("which USB devices are plugged in", tool_get_usb),
    "get_cloud_devices": ("the devices in the IOTCONNECT cloud deployment", tool_get_cloud_devices),
    "get_cloud_health": ("whether this device is healthy and active in the cloud", tool_get_cloud_health),
    "get_cloud_telemetry": ("the latest telemetry the cloud received", tool_get_cloud_telemetry),
    "send_device_command": ("turning a device's LED or light on or off", tool_send_device_command),
    "get_vibration": ("the vibration reading or motor state (idle, balanced, unbalanced) of the MCX vibration sensor", tool_get_vibration),
    "send_motor_command": ("injecting a fault, restoring healthy, running, stopping, or reconfiguring the MCX vibration motor", tool_send_motor_command),
}

# Keyword fallback for when the 500M model's tool pick can't be parsed
_TOOL_KEYWORDS = [
    # Motor CONTROL (action) first - "turn on / start the motor" must control the
    # vibration motor, not fall into the generic device on/off tool below. A bare
    # "motor" with no action verb is a status READ (get_vibration), further down.
    (re.compile(r"\b(inject|induce|trigger|simulate|cause)\b.*\bfault\b|\b(turn|switch|flip|start|run|spin|stop|halt|kill|pause|reboot|restart|resume|drive)\b[\w\s]*\bmotors?\b|\bmotors?\b[\w\s]*\b(on|off|start|run|stop|go)\b|\bmotors?[- ]?(stop|run|off)\b|\b(set|make)\b.*\b(threshold|interval|healthy)\b|\brun\s+both\b|\bboth\s+motors?\b|\bstart\s+both\b", re.I), "send_motor_command"),
    # Device LED / light on-off - requires on/off intent, not just the word
    # "light" (trivia like "what color is light" must not route here).
    (re.compile(r"\b(turn|switch|flip)\b.*\b(on|off)\b|\bled\b\s*(on|off)\b", re.I), "send_device_command"),
    (re.compile(r"\bvibration\b|\banomaly\b|\bmotors?\b|\brms\b", re.I), "get_vibration"),
    (re.compile(r"deployment|fleet|how many devices|other devices|iotconnect|cloud", re.I), "get_cloud_devices"),
    (re.compile(r"telemetry|last reported|received", re.I), "get_cloud_telemetry"),
    (re.compile(r"health|healthy|online|active", re.I), "get_cloud_health"),
    (re.compile(r"usb|plugged|peripheral", re.I), "get_usb"),
    (re.compile(r"time|clock|date|day|today", re.I), "get_time"),
    (re.compile(r"temperature|hot|warm|thermal|cool", re.I), "get_temperature"),
    # Storage before memory: "storage usage" / "disk space" would otherwise be
    # caught by get_memory's "usage" keyword.
    (re.compile(r"\bdisk\b|\bstorage\b|\bflash\b|\bemmc\b|\bspace\b|filesystem", re.I), "get_disk"),
    (re.compile(r"memory|ram|cpu|load|usage", re.I), "get_memory"),
    (re.compile(r"uptime|running|how long", re.I), "get_uptime"),
    (re.compile(r"\bip\b|address|network", re.I), "get_ip"),
]

# The voice -> agent bridge fires for ACTION requests (device / motor control),
# so a spoken "inject a fault" or "turn on the lights" actually executes.
_ACTION_TOOL_NAMES = {"send_device_command", "send_motor_command"}


def _is_voice_action(question):
    return any(pat.search(question) for pat, name in _TOOL_KEYWORDS if name in _ACTION_TOOL_NAMES)


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


def _agent_cmd():
    # The agent's Danube session follows set-model/set-backend like ask-llm, but
    # never uses RAG - the tool router must see only its own instructions.
    cmd = [config["python"], "-u", genai_script_path(),
           "-i", "keyb", "-o", "text", "-m", genai_model()]
    if config["backend"] == "neutron":
        cmd.append("--use-neutron")
    return cmd


agent_llm = PersistentLLM("agent", _agent_cmd)


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
        for sess in (agent_llm, chat_llm, vlm_session):
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


def agent_uses_board_session():
    """True when the agent runs its own Danube keyb session (cpu/neutron + a
    Danube model) rather than the resident Ara connector or a one-shot GGUF."""
    return config["backend"] != "ara2" and not is_gguf_model(config["model"])


def agent_generate(prompt, max_tokens=200):
    """One agent LLM call on whatever set-model/set-backend selects: the Ara240
    connector (ara2), llama.cpp (a GGUF), or the warm Danube session. This is what
    lets the agent reason on the same model ask-llm uses - e.g. the resident 7B on
    the Ara instead of the little Danube router."""
    if config["backend"] == "ara2":
        return _ara2_generate(prompt, max_tokens)
    if is_gguf_model(config["model"]):
        return _llama_generate(prompt, max_tokens)
    if not agent_llm.alive():
        agent_llm.start()
    return agent_llm.ask(prompt)


def invalidate_agent_session():
    """Drop a warm Danube agent session so the next request reloads it with the
    current selection (or skips it entirely for ara2/GGUF)."""
    if agent_llm.alive():
        print("Selection changed - releasing the warm agent session")
        agent_llm.stop()
        with telemetry_lock:
            telemetry["agent_status"] = "off"


def _run_agent_request(request):
    """Route a natural-language request to a board tool and answer from its result.
    The agent's reasoning runs on whatever set-model/set-backend selects (the Ara
    connector, a GGUF, or the Danube session) - the same model ask-llm uses."""
    if agent_uses_board_session():
        if not agent_llm.alive():
            set_agent_status("loading")
            if chat_llm.alive():
                print("Releasing chat session - the board fits one LLM session (no swap)")
                chat_llm.stop()
        else:
            set_agent_status("routing")
    else:
        set_agent_status("routing")  # ara2 connector / GGUF: no board session to warm

    # Prompt formats chosen empirically - danube-500M answers simple Q/A framing
    # reliably but rambles on multi-line instruction menus.
    router_prompt = "Q: Which tool answers '%s'? Options: %s. A:" % (
        request, ", ".join(AGENT_TOOLS))
    reply = agent_generate(router_prompt)
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
        answer = agent_generate("%s. Q: %s? A:" % (tool_result, request.rstrip("?")))
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


def run_agent_request(request):
    """Run the agent, resetting agent_status to 'error' if any step (routing, the
    tool, or phrasing) raises - otherwise a failed request (e.g. a tool that can't
    match a device) leaves the dashboard stuck showing 'executing'."""
    try:
        return _run_agent_request(request)
    except Exception:
        set_agent_status("error")
        raise


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


VLM_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm_worker.py")


class PersistentVLM:
    """
    A warm SmolVLM worker (vlm_worker.py): the model loads once and stays
    resident, then answers many (frame, question) requests - so ask-vlm only
    pays the ~40s load on the first call, and follow-ups answer in seconds.
    Idle-reaped and released for voice like the LLM sessions, to fit board RAM.
    """

    def __init__(self):
        self.proc = None
        self.q = None
        self.signature = None      # (model, precision) the worker was started with
        self.lock = threading.Lock()
        self.last_used = 0.0

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.q.put(line.rstrip("\n"))
        finally:
            self.q.put(None)  # EOF sentinel

    def _readline(self, timeout):
        try:
            return self.q.get(timeout=timeout)  # a str line, or None on EOF
        except queue.Empty:
            return False  # timeout tick

    def start(self, init_frame):
        cmd = [config["python"], "-u", VLM_WORKER,
               config["vlm_model"], config["vlm_precision"], init_frame]
        print("Starting warm VLM:", " ".join(cmd))
        self.proc = subprocess.Popen(
            cmd, cwd=config["vlm_dir"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self.q = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        deadline = time.monotonic() + config["vlm_timeout_s"]
        while True:
            line = self._readline(5)
            if line is None:
                self.stop()
                raise RuntimeError("VLM worker exited before it was ready")
            if line == "VLM_READY":
                break
            if line is False and time.monotonic() > deadline:
                self.stop()
                raise RuntimeError("VLM worker load timed out")
        self.signature = (config["vlm_model"], config["vlm_precision"])
        self.last_used = time.monotonic()

    def ask(self, frame, question):
        """Answer (frame, question). Returns (answer, perf_line, load_time);
        (re)loads the model on first use or a model/precision change."""
        with self.lock:
            sig = (config["vlm_model"], config["vlm_precision"])
            load_time = 0.0
            if not (self.alive() and self.signature == sig):
                self.stop()
                t0 = time.monotonic()
                self.start(frame)
                load_time = round(time.monotonic() - t0, 2)
            self.proc.stdin.write(json.dumps({"image": frame, "question": question}) + "\n")
            self.proc.stdin.flush()
            ans, perf, grab = [], "", False
            deadline = time.monotonic() + config["vlm_timeout_s"]
            while True:
                line = self._readline(5)
                if line is None:
                    raise RuntimeError("VLM worker exited mid-answer")
                if line is False:
                    if time.monotonic() > deadline:
                        raise RuntimeError("VLM worker timed out")
                    continue
                if line == "VLM_ANSWER_BEGIN":
                    grab = True
                elif line == "VLM_ANSWER_END":
                    grab = False
                elif line == "VLM_DONE":
                    break
                elif line.startswith("Vision:") or line.startswith("ERROR"):
                    perf = line
                elif grab:
                    ans.append(line)
            self.last_used = time.monotonic()
        return "\n".join(ans).strip(), perf, load_time

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            self.q = None


vlm_session = PersistentVLM()


def run_vlm(question):
    """
    Capture a camera frame and answer it with SmolVLM via a warm worker
    (vlm_worker.py). The model loads once and stays resident, so only the first
    ask-vlm pays the ~40s load; later questions answer in seconds and
    vlm_load_time reports 0 on that warm path.
    """
    frame = capture_frame()
    answer, perf, load_time = vlm_session.ask(frame, question)
    if not answer:
        raise RuntimeError("No VLM answer captured (perf: %s)" % perf)
    m = _VLM_PERF_RE.search(perf)
    vision_t, ttft, tps = (float(x) for x in m.groups()) if m else (0.0, 0.0, 0.0)
    with telemetry_lock:
        telemetry.update({
            "vlm_model": "%s (%s)" % (config["vlm_model"], config["vlm_precision"]),
            "vlm_question": question[:500],
            "vlm_response": answer[:1000],
            "vlm_load_time": load_time,
            "vlm_vision_time": vision_t,
            "vlm_ttft": ttft,
            "vlm_tps": tps,
        })
    print("VLM response (load %.1fs, ttft %.1fs, %.1f tok/s): %s"
          % (load_time, ttft, tps, answer[:200]))
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
        if config["backend"] == "ara2":
            note = " (reasons on the resident Ara240 model)"
        elif is_gguf_model(config["model"]):
            note = " (loads the GGUF per request)"
        elif agent_llm.alive():
            note = ""
        else:
            note = " (first request loads the model, ~1 min)"
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Agent working - answer will arrive as telemetry" + note)
        start_llm_job(lambda: run_agent_request(request), "agent", "Agent request complete")

    elif msg.command_name == "agent-start":
        # Pre-loading doesn't generate anything, so it deliberately skips the
        # llm_busy lock - it works even while a voice session is running
        # (the agent loads on CPU; concurrency is guarded by agent_llm.lock).
        if not agent_uses_board_session():
            # ara2 -> the connector's model is always resident; GGUF -> loads per
            # request. Either way there is no separate Danube session to preload.
            set_agent_status("ready")
            publish_state()
            which = config.get("ara2_model") if config["backend"] == "ara2" else config["model"]
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                               "Agent uses %s (no separate session to preload)" % which)
            return
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
        # Ara240 models are whatever the eIQ AAF Connector currently serves
        # (e.g. Qwen2.5-7B-Instruct and any pushed model) - selecting one points
        # the ara2 backend at it so ask-llm serves it (both stay resident, so the
        # switch is instant). Danube/GGUF names still select the CPU/Neutron path.
        ara_models = [m.get("id") for m in _connector_models() if m.get("id")]
        valid = ["danube-500M-q8", "danube-500M-q4"] + list_gguf_models() + ara_models
        arg = msg.command_args[0] if len(msg.command_args) == 1 else None
        if arg in ara_models:
            config["ara2_model"] = arg
            config["backend"] = "ara2"
            save_config(config)
            invalidate_agent_session()
            with telemetry_lock:
                telemetry["llm_model"] = arg
                telemetry["llm_backend"] = "ara2"
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                               "Ara240 model set to %s - ask-llm now serves it" % arg)
        elif arg in valid:
            config["model"] = arg
            save_config(config)
            invalidate_agent_session()
            with telemetry_lock:
                telemetry["llm_model"] = arg
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Model set to " + arg)
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

    elif msg.command_name == "rag-add":
        if len(msg.command_args) < 1:
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "Expected a document URL (IOTCONNECT provides one on upload)")
            return
        url = msg.command_args[0]
        name = msg.command_args[1] if len(msg.command_args) > 1 else None
        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                           "Adding the document to the RAG database - watch rag_status")

        def do_rag():
            if not rag_lock.acquire(blocking=False):
                set_rag_status("indexing", "waiting - another document is still indexing")
                rag_lock.acquire()
            try:
                rag_add(url, name)
            except Exception as e:
                print("RAG add failed:", e)
                set_rag_status("error", str(e))
            finally:
                rag_lock.release()
        threading.Thread(target=do_rag, daemon=True).start()

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
        if len(msg.command_args) == 1 and msg.command_args[0] in ("cpu", "neutron", "ara2"):
            config["backend"] = msg.command_args[0]
            save_config(config)
            invalidate_agent_session()
            with telemetry_lock:
                telemetry["llm_backend"] = config["backend"]
            note = " - ask-llm now runs on the Ara240 via the AAF connector" if config["backend"] == "ara2" else ""
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Backend set to " + config["backend"] + note)
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "Expected 1 argument: cpu, neutron, or ara2")

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
# IOTCONNECT MODEL PUSH (Cloud-to-Device model deployment)
# -----------------------------------------------------------------------------
# IOTCONNECT's "Push Model" delivers a model to the device as a download URL,
# carried by the OTA-style module command (C2dMessage.MODULE_COMMAND / ct:2).
# We download the pushed package (a tar of an Ara240 model dir: model.dvm +
# config + tokenizer), extract it into the eIQ AAF Connector's model directory,
# enable it, reload the connector so it loads onto the Ara240, point the ara2
# backend at it, and report progress as model_deploy_* telemetry.
def set_model_deploy_status(status, name=None, detail=""):
    with telemetry_lock:
        telemetry["model_deploy_status"] = status
        if name is not None:
            telemetry["model_deploy_name"] = name
        telemetry["model_deploy_detail"] = str(detail)[:200]
    publish_state()


def _connector_base_url():
    return config["ara2_aaf_url"].rsplit("/v1/", 1)[0]


_ARA_PCI_ID = "1e58:"          # Kinara vendor id - the Ara-2 / NXP Ara240 M.2 card
_ara_cache = {"t": 0.0, "card": False}


def read_ara_status():
    """(status, models) for the Ara240: absent | present | ready.

    The PCI check is cached - the card cannot appear without a reboot, but the
    runtime and its models can come and go while the demo is running."""
    now = time.monotonic()
    if now - _ara_cache["t"] > 300:
        try:
            out = subprocess.run(["lspci", "-d", _ARA_PCI_ID], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, timeout=10).stdout
            _ara_cache["card"] = bool(out.strip())
        except (OSError, subprocess.SubprocessError):
            _ara_cache["card"] = False
        _ara_cache["t"] = now
    if not _ara_cache["card"]:
        return "absent", ""
    models = [m.get("id") for m in _connector_models() if m.get("id")]
    return ("ready", ",".join(models)) if models else ("present", "")


def _connector_models():
    try:
        r = requests.get(_connector_base_url() + "/v1/models", timeout=10)
        return r.json().get("data", [])
    except Exception:
        return []


def _enable_connector_model(name):
    """Enable `name` in the AAF connector's server_config.json (add if new)."""
    cfgp = config["aaf_connector_config"]
    with open(cfgp) as f:
        d = json.load(f)
    models = d.setdefault("available_models", [])
    for m in models:
        if m.get("name") == name:
            m["enabled"] = True
            break
    else:
        models.append({"name": name, "description": "Pushed via IOTCONNECT",
                       "type": "text", "tool_calling": "native", "enabled": True})
    with open(cfgp, "w") as f:
        json.dump(d, f, indent=4)


def _extract_push_entries(raw):
    """
    Extract model entries from a C2D model-push (ct:2) payload. The platform
    sends urls[] with capitalized keys: Url, FileName, Code, guid, version.
    The model NAME comes from the user-set Code, falling back to the file stem.
    """
    entries = []
    for e in (raw.get("urls") or []):
        if not isinstance(e, dict):
            continue
        url = e.get("Url") or e.get("url")
        if not (isinstance(url, str) and url.startswith("http")):
            continue
        fn = e.get("FileName") or e.get("fileName") or e.get("file_name") \
            or os.path.basename(url.split("?")[0]) or "model.tar"
        code = e.get("Code") or e.get("code")
        name = code or os.path.splitext(os.path.basename(fn))[0]
        entries.append({"url": url, "file_name": fn, "name": name})
    return entries


def _ack_model_push(ack_id, status, detail=""):
    """Acknowledge a model push back to IOTCONNECT (OTA-style status on the ct:2)."""
    if not ack_id:
        return
    try:
        c.send_ack(ack_id=ack_id, message_type=C2dMessage.MODULE_COMMAND,
                   status=status, message_str=str(detail)[:200])
    except Exception as e:
        print("Model push ack failed:", e)


def deploy_model(entry):
    """Download a pushed model package and deploy it to the Ara240 connector."""
    import tarfile
    import shutil
    url, file_name, name = entry["url"], entry["file_name"], entry["name"]
    set_model_deploy_status("downloading", name, "downloading from IOTCONNECT")
    print("Model push: downloading %s (%s) from %s" % (name, file_name, url[:80]))
    # download to the models filesystem (disk), never /tmp (may be RAM-backed)
    dl = os.path.join(config["model_deploy_dir"],
                      ".push-download" + (os.path.splitext(file_name)[1] or ".tar"))
    with requests.get(url, stream=True, timeout=1800) as r:
        r.raise_for_status()
        with open(dl, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)

    set_model_deploy_status("deploying", name, "extracting package")
    dest = os.path.join(config["model_deploy_dir"], name)
    os.makedirs(dest, exist_ok=True)

    def _find_dvm():
        for root, _dirs, files in os.walk(dest):
            if "model.dvm" in files:
                return root
        return None

    try:
        # Unwrap nested archives until model.dvm appears - IOTCONNECT wraps the
        # uploaded file in its own .tar, so the payload can be a tar-in-tar.
        current = dl
        for _ in range(3):
            if tarfile.is_tarfile(current):
                with tarfile.open(current) as t:
                    t.extractall(dest)
                if current != dl:
                    os.remove(current)
                if _find_dvm():
                    break
                nested = next((os.path.join(r, fn)
                               for r, _d, fs in os.walk(dest) for fn in fs
                               if fn.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2"))), None)
                if not nested:
                    break
                current = nested
            else:
                shutil.move(current, os.path.join(dest, "model.dvm"))  # raw weights
                break
    finally:
        if os.path.exists(dl):
            os.remove(dl)

    src = _find_dvm()
    if src is None:
        raise RuntimeError("no model.dvm found in pushed package %s" % file_name)
    if os.path.abspath(src) != os.path.abspath(dest):   # flatten if nested
        for fn in os.listdir(src):
            shutil.move(os.path.join(src, fn), os.path.join(dest, fn))

    set_model_deploy_status("loading", name, "loading onto the Ara240")
    _enable_connector_model(name)
    subprocess.run(["systemctl", "restart", config["aaf_connector_service"]], check=False)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if any(m.get("id") == name and m.get("ready") for m in _connector_models()):
            break
        time.sleep(5)
    else:
        raise RuntimeError("model %s did not report ready on the connector" % name)

    config["ara2_model"] = name
    config["backend"] = "ara2"
    save_config(config)
    with telemetry_lock:
        telemetry["llm_model"] = name
        telemetry["llm_backend"] = "ara2"
    set_model_deploy_status("ready", name, "deployed and serving on the Ara240")
    print("Model push: %s deployed to the Ara240 and ready" % name)
    return name


def on_module_command(msg, raw):
    """
    IOTCONNECT model push. The lite SDK maps the module command (ct:2) to type
    UNKNOWN (MODULE_COMMAND is missing from its TYPES map), so this is registered
    under C2dMessage.UNKNOWN and filters on the raw ct. It downloads the pushed
    package, deploys it to the Ara240 connector, and acks the result to the cloud.
    """
    if raw.get("ct") != C2dMessage.MODULE_COMMAND:
        return  # a different unmapped message type - not a model push
    ack_id = raw.get("ack")
    print("Model push received (ct:2). ack=%s payload=%s" % (ack_id, json.dumps(raw)[:800]))
    entries = _extract_push_entries(raw)
    if not entries:
        set_model_deploy_status("error", detail="no download URL in push message")
        _ack_model_push(ack_id, C2dAck.OTA_DOWNLOAD_FAILED, "no download URL in push")
        return

    def worker():
        _ack_model_push(ack_id, C2dAck.OTA_DOWNLOADING, "downloading model")
        try:
            deployed = None
            for entry in entries:
                deployed = deploy_model(entry)
            _ack_model_push(ack_id, C2dAck.OTA_DOWNLOAD_DONE,
                            "deployed %s to the Ara240" % deployed)
        except Exception as e:
            print("Model deploy failed:", e)
            set_model_deploy_status("error", detail=str(e))
            _ack_model_push(ack_id, C2dAck.OTA_DOWNLOAD_FAILED, str(e)[:150])

    threading.Thread(target=worker, daemon=True).start()


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
#   python3 app.py --test-vlm what do you see   (runs twice to show the warm reuse)
#   python3 app.py --test-rag <url>             (add a document to the RAG database)
if len(sys.argv) >= 2 and sys.argv[1] in ("--test-agent", "--test-llm", "--test-vlm", "--test-rag"):
    question = " ".join(sys.argv[2:]) or "What time is it?"
    try:
        if sys.argv[1] == "--test-vlm":
            for i in range(2):
                t = time.monotonic()
                answer = run_vlm(question)
                print("[ask-vlm #%d took %.1fs (load %.1fs)] %s"
                      % (i + 1, time.monotonic() - t, telemetry["vlm_load_time"], answer[:120]))
        elif sys.argv[1] == "--test-rag":
            answer = rag_add(sys.argv[2])
        elif sys.argv[1] == "--test-agent":
            answer = run_agent_request(question)
        else:
            answer = run_llm_prompt(question)
        print("\n=== RESULT ===\n" + answer)
    finally:
        agent_llm.stop()
        vlm_session.stop()
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
                    disconnected_cb=on_disconnect,
                    # IOTCONNECT model push is a module command (ct:2), which the
                    # lite SDK maps to type UNKNOWN - register there, filter on ct.
                    generic_message_callbacks={C2dMessage.UNKNOWN: on_module_command}
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

        if not telemetry["rag_docs"]:
            try:
                refresh_rag_docs()
            except Exception as e:
                print("RAG inventory unavailable:", e)
        with telemetry_lock:
            telemetry["cpu_percent"] = read_cpu_percent()
            telemetry["mem_used_mb"] = read_mem_used_mb()
            telemetry["cpu_temp"] = read_cpu_temp()
            telemetry["disk_free_gb"], telemetry["disk_used_pct"] = read_disk()
            telemetry["ara_status"], telemetry["ara_models"] = read_ara_status()
            c.send_telemetry(dict(telemetry))
        publish_state()
        time.sleep(config["telemetry_interval_s"])

except DeviceConfigError as dce:
    print(dce)
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    sys.exit(0)
