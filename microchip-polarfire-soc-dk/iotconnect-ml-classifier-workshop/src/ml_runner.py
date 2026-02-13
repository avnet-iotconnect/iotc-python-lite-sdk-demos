import re
import stat
import subprocess
from pathlib import Path

NO_ACCEL = "invert_and_threshold.no_accel.elf"
ACCEL = "invert_and_threshold.accel.elf"

RESULT_RE = re.compile(
    r"Tiny-ML demo \((?P<exec_mode>sw|hw)\): input_class=(?P<input_class>\d+) pred=(?P<pred>\d+) time=(?P<time_s>[0-9.]+) s"
)
SCORES_RE = re.compile(r"Scores:\s*\[(?P<scores>[^\]]+)\]")


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
    if not result_match:
        raise RuntimeError("Unable to parse Tiny-ML result line from process output.")

    payload = {
        "exec_mode": result_match.group("exec_mode"),
        "input_class": int(result_match.group("input_class")),
        "pred": int(result_match.group("pred")),
        "time_s": float(result_match.group("time_s")),
        "raw": output.strip(),
    }

    if score_match:
        values = [int(v.strip()) for v in score_match.group("scores").split(",") if v.strip()]
        payload["scores"] = values
        for i, v in enumerate(values):
            payload[f"score{i}"] = v
    else:
        payload["scores"] = []

    return payload


def run_inference(mode: str = "hw", input_class: int = 0, seed: int = 1, timeout_s: int = 20) -> dict:
    elf = _elf_path(mode)
    if not elf.exists():
        raise FileNotFoundError(f"Missing ELF file: {elf}")
    if not elf.is_file():
        raise RuntimeError(f"ELF path is not a file: {elf}")

    # Some deployments lose executable permission bits after extraction.
    if not elf.stat().st_mode & stat.S_IXUSR:
        elf.chmod(elf.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    cmd = [str(elf), str(input_class), str(seed)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

    if proc.returncode != 0:
        raise RuntimeError(f"ELF exited with code {proc.returncode}. Output: {output.strip()}")

    return _parse_output(output)
