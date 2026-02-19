#!/usr/bin/env python3
"""
Train and export Track-3 TinyML Complex model weights.

This script keeps layer-1 and layer-2 deterministic (fixed feature extractor + fixed hidden projection),
then trains layer-3 (classifier head) as integer perceptron weights. It exports C header arrays consumed
by `main_variations/main.fifo.cpp`.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List, Sequence, Tuple

N_CLASSES = 6
N_SAMPLES = 256
N_FEATURES = 64
N_HIDDEN1 = 96
N_HIDDEN2 = 48
INPUT_AMP = 640

L1_ACC_SHIFT = 3
L2_INPUT_SHIFT = 6
L2_ACC_SHIFT = 1
BIAS_PRE_SHIFT = 8


def clamp_int16(x: int) -> int:
    if x > 32767:
        return 32767
    if x < -32768:
        return -32768
    return int(x)


def iabs32(x: int) -> int:
    return -x if x < 0 else x


def tri_wave(i: int, period: int, amp: int) -> int:
    t = i % period
    half = period // 2
    v = t if t < half else (period - t)
    centered = (v * 2) - half
    return (centered * amp) // half


def square_wave(i: int, period: int, amp: int) -> int:
    return amp if (i % period) < (period // 2) else -amp


def saw_wave(i: int, period: int, amp: int) -> int:
    t = i % period
    centered = (t * 2) - period
    return (centered * amp) // period


def ring_wave(i: int, amp: int, decay_shift: int) -> int:
    seg = i >> 5
    env = amp >> (7 if seg > 7 else seg)
    env = env >> decay_shift
    return tri_wave(i * (3 if (seg & 1) else 2), 32, env)


def lcg_next(state: int) -> int:
    return (state * 1664525 + 1013904223) & 0xFFFFFFFF


def gen_signal(cls: int, seed: int) -> List[int]:
    out = [0] * N_SAMPLES
    state = seed
    for i in range(N_SAMPLES):
        if cls == 0:
            base = tri_wave(i, 64, INPUT_AMP) + tri_wave(i, 16, INPUT_AMP // 6)
        elif cls == 1:
            base = square_wave(i, 32, INPUT_AMP // 2) + tri_wave(i, 48, INPUT_AMP // 2)
        elif cls == 2:
            base = tri_wave(i, 40, INPUT_AMP // 2) + saw_wave(i * 3, 64, INPUT_AMP // 2)
        elif cls == 3:
            burst = INPUT_AMP if (i % 64) < 12 else -(INPUT_AMP // 3)
            base = burst + tri_wave(i, 24, INPUT_AMP // 3)
        elif cls == 4:
            base = ring_wave(i, INPUT_AMP, 1) + tri_wave(i * 5, 32, INPUT_AMP // 4)
        elif cls == 5:
            base = INPUT_AMP if (i % 16) == 0 else (-INPUT_AMP if (i % 16) == 8 else -(INPUT_AMP // 8))
            base += saw_wave(i, 128, INPUT_AMP // 4)
        else:
            base = 0

        state = lcg_next(state)
        noise = (((state >> 16) & 0xFF) - 128) * 2
        out[i] = clamp_int16(base + noise)
    return out


def extract_features(inp: Sequence[int]) -> List[int]:
    feat = [0] * N_FEATURES
    for f in range(N_FEATURES):
        base = f << 2
        x0 = inp[base + 0]
        x1 = inp[base + 1]
        x2 = inp[base + 2]
        x3 = inp[base + 3]

        low = (x0 + x1 + x2 + x3) >> 2
        high = ((x3 - x0) + (x2 - x1)) >> 1
        grad = (x3 + x2) - (x1 + x0)
        energy = (iabs32(x0) + iabs32(x1) + iabs32(x2) + iabs32(x3)) >> 2

        if (f & 3) == 0:
            y = low
        elif (f & 3) == 1:
            y = high
        elif (f & 3) == 2:
            y = grad
        else:
            y = energy - 192
        feat[f] = clamp_int16(y)
    return feat


def w1(h: int, i: int) -> int:
    return ((h * 29) + (i * 17) + ((h ^ i) * 7) + 11) % 127 - 63


def w2(h: int, i: int) -> int:
    return ((h * 19) + (i * 13) + ((h + 3) * (i + 5)) + 23) % 127 - 63


def b1(h: int) -> int:
    return ((h * 7) % 41) - 20


def b2(h: int) -> int:
    return ((h * 11) % 37) - 18


def fixed_hidden(feat: Sequence[int]) -> List[int]:
    h1 = [0] * N_HIDDEN1
    for h in range(N_HIDDEN1):
        acc = b1(h) << BIAS_PRE_SHIFT
        for i in range(N_FEATURES):
            acc += int(feat[i]) * w1(h, i)
        acc >>= L1_ACC_SHIFT
        h1[h] = acc if acc > 0 else 0

    h2 = [0] * N_HIDDEN2
    for h in range(N_HIDDEN2):
        acc = b2(h) << BIAS_PRE_SHIFT
        for i in range(N_HIDDEN1):
            x = h1[i] >> L2_INPUT_SHIFT
            acc += x * w2(h, i)
        acc >>= L2_ACC_SHIFT
        h2[h] = acc if acc > 0 else 0
    return h2


def clamp_int8(x: int) -> int:
    if x > 127:
        return 127
    if x < -127:
        return -127
    return int(x)


def train_head(
    train_data: List[Tuple[List[int], int]],
    epochs: int,
    l3_input_shift: int,
    step_small: int,
    step_large: int,
    large_threshold: int,
    bias_step: int,
) -> Tuple[List[List[int]], List[int], float]:
    w3 = [[0 for _ in range(N_HIDDEN2)] for _ in range(N_CLASSES)]
    b3 = [0 for _ in range(N_CLASSES)]

    for _ in range(epochs):
        random.shuffle(train_data)
        for h2, label in train_data:
            x = [v >> l3_input_shift for v in h2]
            scores = []
            for c in range(N_CLASSES):
                acc = b3[c] << BIAS_PRE_SHIFT
                wc = w3[c]
                for i, xv in enumerate(x):
                    acc += xv * wc[i]
                scores.append(acc)
            pred = max(range(N_CLASSES), key=lambda idx: scores[idx])
            if pred == label:
                continue

            wy = w3[label]
            wp = w3[pred]
            for i, xv in enumerate(x):
                if xv == 0:
                    continue
                step = step_large if abs(xv) >= large_threshold else step_small
                sign = 1 if xv > 0 else -1
                wy[i] = clamp_int8(wy[i] + step * sign)
                wp[i] = clamp_int8(wp[i] - step * sign)

            b3[label] = max(-32768, min(32767, b3[label] + bias_step))
            b3[pred] = max(-32768, min(32767, b3[pred] - bias_step))

    acc = evaluate_accuracy(w3, b3, train_data, l3_input_shift)
    return w3, b3, acc


def evaluate_accuracy(w3: Sequence[Sequence[int]], b3: Sequence[int], data: Sequence[Tuple[List[int], int]], l3_input_shift: int) -> float:
    correct = 0
    for h2, label in data:
        x = [v >> l3_input_shift for v in h2]
        best_idx = 0
        best_score = None
        for c in range(N_CLASSES):
            acc = int(b3[c]) << BIAS_PRE_SHIFT
            wc = w3[c]
            for i, xv in enumerate(x):
                acc += xv * int(wc[i])
            if best_score is None or acc > best_score:
                best_score = acc
                best_idx = c
        if best_idx == label:
            correct += 1
    return float(correct) / float(len(data)) if data else 0.0


def build_dataset(samples_per_class: int, seed_start: int) -> List[Tuple[List[int], int]]:
    data: List[Tuple[List[int], int]] = []
    for cls in range(N_CLASSES):
        for s in range(seed_start, seed_start + samples_per_class):
            sig = gen_signal(cls, s)
            feat = extract_features(sig)
            h2 = fixed_hidden(feat)
            data.append((h2, cls))
    return data


def _format_1d(values: Sequence[int]) -> str:
    return ", ".join(str(int(v)) for v in values)


def _format_2d(rows: Sequence[Sequence[int]]) -> str:
    return ",\n".join("  {" + _format_1d(row) + "}" for row in rows)


def export_header(output_path: Path, w3: Sequence[Sequence[int]], b3: Sequence[int], l3_input_shift: int, train_acc: float, eval_acc: float) -> None:
    b1_vals = [b1(h) for h in range(N_HIDDEN1)]
    b2_vals = [b2(h) for h in range(N_HIDDEN2)]
    w1_vals = [[w1(h, i) for i in range(N_FEATURES)] for h in range(N_HIDDEN1)]
    w2_vals = [[w2(h, i) for i in range(N_HIDDEN1)] for h in range(N_HIDDEN2)]

    with output_path.open("w", encoding="utf-8") as f:
        f.write("#ifndef MODEL_WEIGHTS_H\n#define MODEL_WEIGHTS_H\n\n")
        f.write("// Generated by tools/train_and_export_complex.py\n")
        f.write(f"// Train accuracy: {train_acc:.6f}\n")
        f.write(f"// Eval accuracy:  {eval_acc:.6f}\n\n")
        f.write(f"#define L1_ACC_SHIFT {L1_ACC_SHIFT}\n")
        f.write(f"#define L2_INPUT_SHIFT {L2_INPUT_SHIFT}\n")
        f.write(f"#define L2_ACC_SHIFT {L2_ACC_SHIFT}\n")
        f.write(f"#define L3_INPUT_SHIFT {l3_input_shift}\n")
        f.write(f"#define BIAS_PRE_SHIFT {BIAS_PRE_SHIFT}\n\n")
        f.write("static const int16_t B1[N_HIDDEN1] = {\n  ")
        f.write(_format_1d(b1_vals))
        f.write("\n};\n\n")
        f.write("static const int16_t B2[N_HIDDEN2] = {\n  ")
        f.write(_format_1d(b2_vals))
        f.write("\n};\n\n")
        f.write("static const int16_t B3[N_CLASSES] = {\n  ")
        f.write(_format_1d(b3))
        f.write("\n};\n\n")
        f.write("static const int8_t W1[N_HIDDEN1][N_FEATURES] = {\n")
        f.write(_format_2d(w1_vals))
        f.write("\n};\n\n")
        f.write("static const int8_t W2[N_HIDDEN2][N_HIDDEN1] = {\n")
        f.write(_format_2d(w2_vals))
        f.write("\n};\n\n")
        f.write("static const int8_t W3[N_CLASSES][N_HIDDEN2] = {\n")
        f.write(_format_2d(w3))
        f.write("\n};\n\n")
        f.write("#endif // MODEL_WEIGHTS_H\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and export Track-3 complex model weights.")
    parser.add_argument("--train-samples-per-class", type=int, default=120)
    parser.add_argument("--eval-samples-per-class", type=int, default=200)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--l3-input-shift", type=int, default=7)
    parser.add_argument("--step-small", type=int, default=1)
    parser.add_argument("--step-large", type=int, default=2)
    parser.add_argument("--large-threshold", type=int, default=10)
    parser.add_argument("--bias-step", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument(
        "--output",
        type=Path,
        default=(Path(__file__).resolve().parents[1] / "assets" / "smarthls-module" / "tinyml_complex" / "main_variations" / "model_weights.h"),
    )
    args = parser.parse_args()

    random.seed(args.seed)

    train_data = build_dataset(args.train_samples_per_class, 1)
    eval_data = build_dataset(args.eval_samples_per_class, 2001)

    w3, b3, train_acc = train_head(
        train_data=train_data,
        epochs=args.epochs,
        l3_input_shift=args.l3_input_shift,
        step_small=args.step_small,
        step_large=args.step_large,
        large_threshold=args.large_threshold,
        bias_step=args.bias_step,
    )

    eval_acc = evaluate_accuracy(w3, b3, eval_data, args.l3_input_shift)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_header(
        output_path=args.output,
        w3=w3,
        b3=b3,
        l3_input_shift=args.l3_input_shift,
        train_acc=train_acc,
        eval_acc=eval_acc,
    )

    print(f"Train accuracy: {train_acc:.6f}")
    print(f"Eval accuracy:  {eval_acc:.6f}")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

