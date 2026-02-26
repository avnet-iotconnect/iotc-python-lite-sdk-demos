import re
import stat
import subprocess
from pathlib import Path

NO_ACCEL = "tinyml_complex.no_accel.elf"
ACCEL = "tinyml_complex.accel.elf"

RESULT_RE = re.compile(
    r"Tiny-(?:ML|NN|Complex) demo \((?P<exec_mode>sw|hw)\): input_class=(?P<input_class>\d+) pred=(?P<pred>\d+) time=(?P<time_s>[0-9.]+) s"
)
SCORES_RE = re.compile(r"Scores:\s*\[(?P<scores>[^\]]+)\]")
BATCH_RE = re.compile(
    r"Batch:\s*n=(?P<batch_n>\d+)\s+mode_count=(?P<pred_mode_count>\d+)\s+match_count=(?P<match_count>\d+)\s+"
    r"match_rate=(?P<match_rate>[0-9.]+)\s+total_time=(?P<total_time_s>[0-9.]+)\s+avg_time=(?P<avg_time_s>[0-9.]+)"
)


def _elf_path(mode: str) -> Path:
    mode = mode.lower()
    if mode == "sw":
        return Path(__file__).parent / "runtimes" / NO_ACCEL
    if mode == "hw":
        return Path(__file__).parent / "runtimes" / ACCEL
    raise ValueError("mode must be 'sw' or 'hw'")


def _parse_output(output: str) -> dict:
    result_match = RESULT_RE.search(output)
    score_match = SCORES_RE.search(output)
    batch_match = BATCH_RE.search(output)
    if not result_match:
        raise RuntimeError("Unable to parse inference result line from process output.")

    payload = {
        "exec_mode": result_match.group("exec_mode"),
        "input_class": int(result_match.group("input_class")),
        "pred": int(result_match.group("pred")),
        "time_s": float(result_match.group("time_s")),
        "raw": output.strip(),
        "batch_n": 1,
        "pred_mode_count": 1,
        "match_count": 1,
        "match_rate": 1.0,
        "total_time_s": float(result_match.group("time_s")),
        "avg_time_s": float(result_match.group("time_s")),
    }

    if score_match:
        values = [int(v.strip()) for v in score_match.group("scores").split(",") if v.strip()]
        payload["scores"] = values
        for i, v in enumerate(values):
            payload[f"score{i}"] = v
    else:
        payload["scores"] = []

    if batch_match:
        payload["batch_n"] = int(batch_match.group("batch_n"))
        payload["pred_mode_count"] = int(batch_match.group("pred_mode_count"))
        payload["match_count"] = int(batch_match.group("match_count"))
        payload["match_rate"] = float(batch_match.group("match_rate"))
        payload["total_time_s"] = float(batch_match.group("total_time_s"))
        payload["avg_time_s"] = float(batch_match.group("avg_time_s"))
        payload["time_s"] = payload["avg_time_s"]

    return payload


def run_inference(mode: str = "hw", input_class: int = 0, seed: int = 1, batch_n: int = 1, timeout_s: int = 30) -> dict:
    elf = _elf_path(mode)
    if not elf.exists():
        raise FileNotFoundError(f"Missing ELF file: {elf}")
    if not elf.is_file():
        raise RuntimeError(f"ELF path is not a file: {elf}")

    if not elf.stat().st_mode & stat.S_IXUSR:
        elf.chmod(elf.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    effective_batch = max(1, int(batch_n))
    cmd = [str(elf), str(input_class), str(seed), str(effective_batch)]
    effective_timeout = max(int(timeout_s), 30 + (effective_batch // 20))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=effective_timeout, check=False)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

    if proc.returncode != 0:
        raise RuntimeError(f"ELF exited with code {proc.returncode}. Output: {output.strip()}")

    return _parse_output(output)
