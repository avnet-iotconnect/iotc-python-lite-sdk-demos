#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Quarantine obviously bad KWS captures without deleting them."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import shutil
import wave
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


EXPECTED_RATE = 16000
EXPECTED_CHANNELS = 1
MIN_DURATION_SECS = 0.85
MAX_DURATION_SECS = 8.0


@dataclass
class Finding:
    path: str
    reason: str
    details: dict
    moved_to: str = ""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_wav(path: Path) -> tuple[float, int, int, int]:
    with contextlib.closing(wave.open(str(path), "rb")) as wav_file:
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        frames = wav_file.getnframes()
        sample_width = wav_file.getsampwidth()
    duration = frames / float(rate or 1)
    return duration, rate, channels, sample_width


def collect_findings(dataset_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    seen_hashes: dict[str, Path] = {}

    for path in sorted(dataset_root.rglob("*.wav")):
        rel_path = path.relative_to(dataset_root)
        try:
            duration, rate, channels, sample_width = inspect_wav(path)
        except Exception as exc:  # pragma: no cover - defensive
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="bad_wav",
                    details={"error": str(exc)},
                )
            )
            continue

        if rate != EXPECTED_RATE:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="wrong_rate",
                    details={"rate": rate, "expected_rate": EXPECTED_RATE},
                )
            )
            continue

        if channels != EXPECTED_CHANNELS:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="wrong_channels",
                    details={"channels": channels, "expected_channels": EXPECTED_CHANNELS},
                )
            )
            continue

        if sample_width != 2:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="wrong_sample_width",
                    details={"sample_width": sample_width},
                )
            )
            continue

        if duration < MIN_DURATION_SECS:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="too_short",
                    details={"duration_secs": round(duration, 3), "min_duration_secs": MIN_DURATION_SECS},
                )
            )
            continue

        if duration > MAX_DURATION_SECS:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="too_long",
                    details={"duration_secs": round(duration, 3), "max_duration_secs": MAX_DURATION_SECS},
                )
            )
            continue

        digest = file_sha256(path)
        original = seen_hashes.get(digest)
        if original is not None:
            findings.append(
                Finding(
                    path=str(rel_path),
                    reason="duplicate",
                    details={"duplicate_of": str(original.relative_to(dataset_root))},
                )
            )
            continue
        seen_hashes[digest] = path

    return findings


def quarantine_findings(dataset_root: Path, findings: list[Finding], dry_run: bool) -> tuple[Path, list[Finding]]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    quarantine_root = dataset_root.parent / "quarantine" / timestamp

    if dry_run:
        return quarantine_root, findings

    for finding in findings:
        source = dataset_root / finding.path
        target = quarantine_root / finding.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        finding.moved_to = str(target)

    return quarantine_root, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default="/root/kws-training/src/datasets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    findings = collect_findings(dataset_root)
    quarantine_root, findings = quarantine_findings(dataset_root, findings, dry_run=args.dry_run)

    print(
        json.dumps(
            {
                "dataset_root": str(dataset_root),
                "dry_run": args.dry_run,
                "quarantine_root": str(quarantine_root),
                "finding_count": len(findings),
                "findings": [asdict(item) for item in findings],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
