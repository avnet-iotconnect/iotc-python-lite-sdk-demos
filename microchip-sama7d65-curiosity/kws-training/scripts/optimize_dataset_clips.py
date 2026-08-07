#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Trim KWS speech clips, keep small margins, and re-pad them to a fixed length."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import shutil
import wave
from array import array
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


EXPECTED_SAMPLE_RATE = 16000
EXPECTED_CHANNELS = 1
EXPECTED_SAMPLE_WIDTH = 2
DEFAULT_TARGET_SECONDS = 1.0
DEFAULT_FRAME_MS = 10.0
DEFAULT_MIN_RMS = 0.02
DEFAULT_RELATIVE_THRESHOLD = 0.2
DEFAULT_MIN_SPEECH_MS = 60.0
DEFAULT_MAX_GAP_MS = 80.0
DEFAULT_PRE_MS = 60.0
DEFAULT_POST_MS = 120.0
EXCLUDED_LABELS = {"_background_noise_"}


@dataclass
class ClipResult:
    path: str
    label: str
    status: str
    reason: str = ""
    original_samples: int = 0
    optimized_samples: int = 0
    speech_start_sample: int = 0
    speech_end_sample: int = 0
    start_sample: int = 0
    end_sample: int = 0
    leading_trim_samples: int = 0
    trailing_trim_samples: int = 0
    peak_rms: float = 0.0
    threshold_rms: float = 0.0
    backup_path: str = ""


def positive_ms_to_samples(value_ms: float, sample_rate: int) -> int:
    return max(1, int(round((value_ms / 1000.0) * sample_rate)))


def read_wav(path: Path) -> tuple[int, int, int, array]:
    with contextlib.closing(wave.open(str(path), "rb")) as handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())

    if sample_width != EXPECTED_SAMPLE_WIDTH:
        raise ValueError(f"Expected 16-bit PCM WAV: {path}")

    samples = array("h")
    samples.frombytes(frames)
    if channels != EXPECTED_CHANNELS:
        raise ValueError(f"Expected mono WAV: {path}")
    return sample_rate, channels, sample_width, samples


def write_wav(path: Path, sample_rate: int, samples: array) -> None:
    with contextlib.closing(wave.open(str(path), "wb")) as handle:
        handle.setnchannels(EXPECTED_CHANNELS)
        handle.setsampwidth(EXPECTED_SAMPLE_WIDTH)
        handle.setframerate(sample_rate)
        handle.writeframes(samples.tobytes())


def frame_rms_values(samples: array, frame_samples: int) -> list[float]:
    if not samples:
        return []

    values: list[float] = []
    total_samples = len(samples)
    for start in range(0, total_samples, frame_samples):
        end = min(total_samples, start + frame_samples)
        chunk_len = end - start
        if chunk_len <= 0:
            continue
        total = 0.0
        for index in range(start, end):
            sample = samples[index]
            total += float(sample) * float(sample)
        values.append(math.sqrt(total / chunk_len) / 32768.0)
    return values


def fill_short_gaps(flags: list[bool], max_gap_frames: int) -> list[bool]:
    if max_gap_frames <= 0:
        return flags[:]

    result = flags[:]
    index = 0
    length = len(result)
    while index < length:
        if result[index]:
            index += 1
            continue
        gap_start = index
        while index < length and not result[index]:
            index += 1
        gap_end = index
        if gap_start > 0 and gap_end < length and (gap_end - gap_start) <= max_gap_frames:
            for gap_index in range(gap_start, gap_end):
                result[gap_index] = True
    return result


def drop_short_regions(flags: list[bool], min_region_frames: int) -> list[bool]:
    if min_region_frames <= 1:
        return flags[:]

    result = flags[:]
    index = 0
    length = len(result)
    while index < length:
        if not result[index]:
            index += 1
            continue
        region_start = index
        while index < length and result[index]:
            index += 1
        region_end = index
        if (region_end - region_start) < min_region_frames:
            for region_index in range(region_start, region_end):
                result[region_index] = False
    return result


def detect_speech_bounds(
    samples: array,
    sample_rate: int,
    frame_ms: float,
    min_rms: float,
    relative_threshold: float,
    min_speech_ms: float,
    max_gap_ms: float,
) -> tuple[int, int, float, float]:
    frame_samples = positive_ms_to_samples(frame_ms, sample_rate)
    rms_values = frame_rms_values(samples, frame_samples)
    if not rms_values:
        return 0, 0, 0.0, 0.0

    peak_rms = max(rms_values)
    threshold_rms = max(min_rms, peak_rms * relative_threshold)
    flags = [value >= threshold_rms for value in rms_values]
    flags = fill_short_gaps(flags, max(0, int(round(max_gap_ms / frame_ms))))
    flags = drop_short_regions(flags, max(1, int(round(min_speech_ms / frame_ms))))

    try:
        first_index = flags.index(True)
    except ValueError:
        return 0, 0, peak_rms, threshold_rms

    last_index = len(flags) - 1 - flags[::-1].index(True)
    start_sample = first_index * frame_samples
    end_sample = min(len(samples), (last_index + 1) * frame_samples)
    return start_sample, end_sample, peak_rms, threshold_rms


def allocate_margins(
    active_start: int,
    active_end: int,
    sample_count: int,
    target_samples: int,
    requested_pre: int,
    requested_post: int,
) -> tuple[int, int] | None:
    active_span = active_end - active_start
    if active_span <= 0:
        return None
    if active_span > target_samples:
        return None

    requested_pre = min(requested_pre, active_start)
    requested_post = min(requested_post, sample_count - active_end)
    remaining = target_samples - active_span

    if requested_pre + requested_post <= remaining:
        pre = requested_pre
        post = requested_post
    else:
        total_requested = max(1, requested_pre + requested_post)
        pre = min(requested_pre, int(round(remaining * (requested_pre / total_requested))))
        post = min(requested_post, remaining - pre)
        spare = remaining - pre - post
        if spare > 0:
            extra_pre = min(spare, requested_pre - pre)
            pre += extra_pre
            spare -= extra_pre
        if spare > 0:
            post += min(spare, requested_post - post)

    start_sample = active_start - pre
    end_sample = active_end + post
    if end_sample - start_sample > target_samples:
        end_sample = start_sample + target_samples
    return start_sample, end_sample


def optimize_samples(
    samples: array,
    sample_rate: int,
    target_seconds: float,
    frame_ms: float,
    min_rms: float,
    relative_threshold: float,
    min_speech_ms: float,
    max_gap_ms: float,
    pre_ms: float,
    post_ms: float,
) -> tuple[array | None, ClipResult]:
    target_samples = int(round(target_seconds * sample_rate))
    speech_start, speech_end, peak_rms, threshold_rms = detect_speech_bounds(
        samples=samples,
        sample_rate=sample_rate,
        frame_ms=frame_ms,
        min_rms=min_rms,
        relative_threshold=relative_threshold,
        min_speech_ms=min_speech_ms,
        max_gap_ms=max_gap_ms,
    )

    result = ClipResult(
        path="",
        label="",
        status="unchanged",
        original_samples=len(samples),
        optimized_samples=len(samples),
        speech_start_sample=speech_start,
        speech_end_sample=speech_end,
        peak_rms=round(peak_rms, 6),
        threshold_rms=round(threshold_rms, 6),
    )

    if speech_end <= speech_start:
        result.status = "skipped"
        result.reason = "no_speech_detected"
        return None, result

    bounds = allocate_margins(
        active_start=speech_start,
        active_end=speech_end,
        sample_count=len(samples),
        target_samples=target_samples,
        requested_pre=positive_ms_to_samples(pre_ms, sample_rate),
        requested_post=positive_ms_to_samples(post_ms, sample_rate),
    )
    if bounds is None:
        result.status = "skipped"
        result.reason = "speech_span_exceeds_target"
        return None, result

    start_sample, end_sample = bounds
    trimmed = array("h", samples[start_sample:end_sample])
    if len(trimmed) > target_samples:
        trimmed = array("h", trimmed[:target_samples])
    elif len(trimmed) < target_samples:
        trimmed.extend([0] * (target_samples - len(trimmed)))

    result.start_sample = start_sample
    result.end_sample = end_sample
    result.leading_trim_samples = start_sample
    result.trailing_trim_samples = max(0, len(samples) - end_sample)
    result.optimized_samples = len(trimmed)

    if trimmed.tobytes() == samples.tobytes():
        result.status = "unchanged"
        result.reason = "already_optimized"
        return None, result

    result.status = "optimized"
    return trimmed, result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default="/root/kws-training/src/datasets")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-seconds", type=float, default=DEFAULT_TARGET_SECONDS)
    parser.add_argument("--frame-ms", type=float, default=DEFAULT_FRAME_MS)
    parser.add_argument("--min-rms", type=float, default=DEFAULT_MIN_RMS)
    parser.add_argument("--relative-threshold", type=float, default=DEFAULT_RELATIVE_THRESHOLD)
    parser.add_argument("--min-speech-ms", type=float, default=DEFAULT_MIN_SPEECH_MS)
    parser.add_argument("--max-gap-ms", type=float, default=DEFAULT_MAX_GAP_MS)
    parser.add_argument("--pre-ms", type=float, default=DEFAULT_PRE_MS)
    parser.add_argument("--post-ms", type=float, default=DEFAULT_POST_MS)
    parser.add_argument("--include-background-noise", action="store_true")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--backup-root", default="")
    return parser


def write_report(report_path: Path, payload: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(args.backup_root).resolve() if args.backup_root else dataset_root.parent / "optimized-backups" / timestamp
    report_path = Path(args.report_path).resolve() if args.report_path else backup_root / "optimize-report.json"

    results: list[ClipResult] = []
    label_change_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    skip_reason_counts: Counter[str] = Counter()

    for wav_path in sorted(dataset_root.rglob("*.wav")):
        rel_path = wav_path.relative_to(dataset_root)
        label = rel_path.parts[0] if rel_path.parts else ""
        if label in EXCLUDED_LABELS and not args.include_background_noise:
            results.append(
                ClipResult(
                    path=str(rel_path),
                    label=label,
                    status="skipped",
                    reason="excluded_label",
                )
            )
            status_counts["skipped"] += 1
            skip_reason_counts["excluded_label"] += 1
            continue

        try:
            sample_rate, _channels, _sample_width, samples = read_wav(wav_path)
        except Exception as exc:
            result = ClipResult(
                path=str(rel_path),
                label=label,
                status="skipped",
                reason=f"read_error:{exc}",
            )
            results.append(result)
            status_counts["skipped"] += 1
            skip_reason_counts["read_error"] += 1
            continue

        if sample_rate != EXPECTED_SAMPLE_RATE:
            result = ClipResult(
                path=str(rel_path),
                label=label,
                status="skipped",
                reason=f"unexpected_sample_rate:{sample_rate}",
                original_samples=len(samples),
            )
            results.append(result)
            status_counts["skipped"] += 1
            skip_reason_counts["unexpected_sample_rate"] += 1
            continue

        optimized, result = optimize_samples(
            samples=samples,
            sample_rate=sample_rate,
            target_seconds=args.target_seconds,
            frame_ms=args.frame_ms,
            min_rms=args.min_rms,
            relative_threshold=args.relative_threshold,
            min_speech_ms=args.min_speech_ms,
            max_gap_ms=args.max_gap_ms,
            pre_ms=args.pre_ms,
            post_ms=args.post_ms,
        )
        result.path = str(rel_path)
        result.label = label

        if result.status == "optimized":
            label_change_counts[label] += 1
            if not args.dry_run and optimized is not None:
                backup_path = backup_root / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(wav_path), str(backup_path))
                result.backup_path = str(backup_path)
                write_wav(wav_path, sample_rate, optimized)
        elif result.status == "skipped":
            skip_reason_counts[result.reason] += 1

        status_counts[result.status] += 1
        results.append(result)

    payload = {
        "dataset_root": str(dataset_root),
        "dry_run": args.dry_run,
        "backup_root": str(backup_root),
        "report_path": str(report_path),
        "summary": {
            "scanned_files": len(results),
            "optimized_files": status_counts["optimized"],
            "unchanged_files": status_counts["unchanged"],
            "skipped_files": status_counts["skipped"],
            "optimized_by_label": dict(sorted(label_change_counts.items())),
            "skip_reasons": dict(sorted(skip_reason_counts.items())),
        },
        "settings": {
            "target_seconds": args.target_seconds,
            "frame_ms": args.frame_ms,
            "min_rms": args.min_rms,
            "relative_threshold": args.relative_threshold,
            "min_speech_ms": args.min_speech_ms,
            "max_gap_ms": args.max_gap_ms,
            "pre_ms": args.pre_ms,
            "post_ms": args.post_ms,
            "include_background_noise": args.include_background_noise,
        },
        "results": [asdict(item) for item in results],
    }
    write_report(report_path, payload)

    print(
        json.dumps(
            {
                "dataset_root": str(dataset_root),
                "dry_run": args.dry_run,
                "backup_root": str(backup_root),
                "report_path": str(report_path),
                **payload["summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
