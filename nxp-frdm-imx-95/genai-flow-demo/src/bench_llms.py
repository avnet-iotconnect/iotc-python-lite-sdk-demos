#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""One-prompt shootout across every LLM backend/model on the board.

For each combination: set genai-config.json, run the patched app copy in
--test-llm mode (the app's real code paths), parse its METRICS/RESULT output,
and sample CPU%% + memory once a second while it runs.
Results -> /tmp/bench_results.json ; progress -> /tmp/bench.log (this stdout).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import threading
import time

CFG = "/opt/demo/genai-config.json"
APP = "/tmp/bench_app.py"
PROMPT = "What color is an apple?"
RUN_TIMEOUT = 420


def read_cpu():
    with open("/proc/stat") as f:
        p = f.readline().split()[1:8]
    p = [int(x) for x in p]
    return sum(p), p[3]  # total, idle


def read_mem_mb():
    total = avail = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable"):
                avail = int(line.split()[1])
    return (total - avail) / 1024.0


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self.cpu = []
        self.mem = []

    def run(self):
        t0, i0 = read_cpu()
        while not self.stop_flag.wait(1.0):
            t1, i1 = read_cpu()
            dt, di = t1 - t0, i1 - i0
            t0, i0 = t1, i1
            if dt > 0:
                self.cpu.append(100.0 * (dt - di) / dt)
            self.mem.append(read_mem_mb())

    def result(self):
        self.stop_flag.set()
        self.join(timeout=3)
        return (round(sum(self.cpu) / len(self.cpu), 1) if self.cpu else 0.0,
                round(max(self.cpu), 1) if self.cpu else 0.0,
                round(max(self.mem), 1) if self.mem else 0.0)


def set_cfg(**kw):
    d = json.load(open(CFG))
    d.update(kw)
    json.dump(d, open(CFG, "w"), indent=2)


def run_one(label, **cfg):
    print("\n===== %s =====" % label, flush=True)
    set_cfg(**cfg)
    subprocess.run(["pkill", "-f", r"eiq_genai_flow\.py -i keyb"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    mem_before = read_mem_mb()
    s = Sampler()
    s.start()
    t0 = time.monotonic()
    try:
        r = subprocess.run(["python3", APP, "--test-llm", PROMPT],
                           cwd="/opt/demo", timeout=RUN_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = r.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        out += "\n[TIMEOUT after %ds]" % RUN_TIMEOUT
    wall = round(time.monotonic() - t0, 1)
    cpu_avg, cpu_peak, mem_peak = s.result()
    subprocess.run(["pkill", "-f", r"eiq_genai_flow\.py -i keyb"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    metrics, response = {}, ""
    m = re.search(r"^METRICS (\{.*\})", out, re.M)
    if m:
        try:
            metrics = json.loads(m.group(1))
        except ValueError:
            pass
    m = re.search(r"=== RESULT ===\n(.*?)(?:\nMETRICS |\Z)", out, re.S)
    if m:
        response = m.group(1).strip()
    err = ""
    if not response:
        err = out.strip().splitlines()[-1][:300] if out.strip() else "no output"
    row = {
        "label": label,
        "model": metrics.get("llm_model", cfg.get("model", cfg.get("ara2_model", "?"))),
        "backend": metrics.get("llm_backend", cfg.get("backend", "?")),
        "load_s": metrics.get("llm_load_time"),
        "ttft_s": metrics.get("llm_ttft"),
        "gen_s": metrics.get("llm_gen_time"),
        "tps": metrics.get("llm_tps"),
        "tokens": metrics.get("llm_token_count"),
        "wall_s": wall,
        "cpu_avg_pct": cpu_avg,
        "cpu_peak_pct": cpu_peak,
        "mem_peak_mb": mem_peak,
        "mem_before_mb": round(mem_before, 1),
        "response": response[:600],
        "error": err,
    }
    print(json.dumps(row, indent=1), flush=True)
    return row


def main():
    orig = open(CFG).read()
    cfg0 = json.loads(orig)

    # Patch a COPY of the app to dump llm_* telemetry after --test-llm
    src = open("/opt/demo/app.py").read()
    hook = ('print("\\n=== RESULT ===\\n" + answer)\n'
            '        import json as _j; print("METRICS " + _j.dumps('
            '{k: v for k, v in telemetry.items() if k.startswith("llm_")}))')
    patched = src.replace('print("\\n=== RESULT ===\\n" + answer)', hook, 1)
    assert patched != src, "hook anchor not found in app.py"
    open(APP, "w").write(patched)

    combos = []
    # Ara240 models (whatever the connector serves)
    try:
        import urllib.request
        data = json.load(urllib.request.urlopen("http://127.0.0.1:8100/v1/models", timeout=8))
        for mdl in data.get("data", []):
            if mdl.get("ready"):
                combos.append(("ara2 / " + mdl["id"],
                               dict(backend="ara2", ara2_model=mdl["id"])))
    except Exception as e:
        print("connector unavailable:", e, flush=True)
    # Danube on CPU and Neutron NPU
    for b in ("cpu", "neutron"):
        for mdl in ("danube-500M-q8", "danube-500M-q4"):
            combos.append(("%s / %s" % (b, mdl), dict(backend=b, model=mdl)))
    # GGUF models via llama.cpp
    llama_dir = cfg0.get("llama_dir", "/root/llama.cpp")
    for p in sorted(glob.glob(os.path.join(llama_dir, "models", "*.gguf"))):
        name = os.path.splitext(os.path.basename(p))[0]
        combos.append(("cpu-llama.cpp / " + name, dict(backend="cpu", model=name)))

    print("Combos: %d -> %s" % (len(combos), [c[0] for c in combos]), flush=True)
    results = []
    try:
        for label, cfg in combos:
            results.append(run_one(label, **cfg))
    finally:
        open(CFG, "w").write(orig)  # always restore the original config
        json.dump({"prompt": PROMPT, "results": results},
                  open("/tmp/bench_results.json", "w"), indent=1)
        open("/tmp/bench.done", "w").write("done")
        print("\nBENCH DONE - config restored, results in /tmp/bench_results.json", flush=True)


if __name__ == "__main__":
    main()
