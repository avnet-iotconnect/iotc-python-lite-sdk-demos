from __future__ import annotations

import argparse
import json
import os
import random
import tarfile
import tempfile
import wave
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import boto3
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split

from model import DCT_COEFFICIENT_COUNT, INPUT_FEATURES, KeywordSpotter, example_input

EXPECTED_SAMPLE_RATE = 16000
EXPECTED_SECONDS = 1
EXPECTED_SAMPLES = EXPECTED_SAMPLE_RATE * EXPECTED_SECONDS
WINDOW_SIZE_SAMPLES = 640
WINDOW_STRIDE_SAMPLES = 320
MEL_FILTERBANK_CHANNELS = 40
LOWER_FREQUENCY_HZ = 20.0
UPPER_FREQUENCY_HZ = 4000.0
SPECTROGRAM_LENGTH = 1 + int((EXPECTED_SAMPLES - WINDOW_SIZE_SAMPLES) / WINDOW_STRIDE_SAMPLES)
FFT_LENGTH = 1 << (WINDOW_SIZE_SAMPLES - 1).bit_length()
MEL_FILTERBANK: Optional[np.ndarray] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a board-compatible PyTorch KWS model from the board dataset archive.")
    parser.add_argument("--epochs", type=int, default=int(os.getenv("KWS_TRAIN_EPOCHS", "20")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("KWS_TRAIN_BATCH_SIZE", "16")))
    parser.add_argument("--learning-rate", type=float, default=float(os.getenv("KWS_TRAIN_LEARNING_RATE", "0.001")))
    parser.add_argument("--validation-split", type=float, default=float(os.getenv("KWS_TRAIN_VALIDATION_SPLIT", "0.2")))
    parser.add_argument("--seed", type=int, default=int(os.getenv("KWS_TRAIN_SEED", "42")))
    parser.add_argument("--training-dir", default=os.getenv("SM_CHANNEL_TRAINING", "/opt/ml/input/data/training"))
    parser.add_argument("--model-dir", default=os.getenv("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument("--manifest-s3-uri", default=os.getenv("KWS_MANIFEST_S3_URI", ""))
    parser.add_argument("--weights-upload-s3-uri", default=os.getenv("KWS_WEIGHTS_UPLOAD_S3_URI", ""))
    parser.add_argument("--state-upload-s3-uri", default=os.getenv("KWS_STATE_UPLOAD_S3_URI", ""))
    parser.add_argument("--labels-upload-s3-uri", default=os.getenv("KWS_LABELS_UPLOAD_S3_URI", ""))
    parser.add_argument("--results-upload-s3-uri", default=os.getenv("KWS_RESULTS_UPLOAD_S3_URI", ""))
    parser.add_argument("--wanted-words", default=os.getenv("KWS_WANTED_WORDS", ""))
    return parser.parse_known_args()[0]


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        channels = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())

    if sample_width != 2:
        raise ValueError(f"Expected 16-bit PCM WAV: {path}")

    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if sample_rate != EXPECTED_SAMPLE_RATE:
        raise ValueError(f"Expected {EXPECTED_SAMPLE_RATE} Hz audio, found {sample_rate}: {path}")

    if samples.shape[0] < EXPECTED_SAMPLES:
        samples = np.pad(samples, (0, EXPECTED_SAMPLES - samples.shape[0]), mode="constant")
    elif samples.shape[0] > EXPECTED_SAMPLES:
        samples = samples[:EXPECTED_SAMPLES]

    samples /= 32768.0
    return np.clip(samples, -1.0, 1.0)


def hz_to_mel(values: np.ndarray | float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    return 2595.0 * np.log10(1.0 + (array / 700.0))


def mel_to_hz(values: np.ndarray) -> np.ndarray:
    return 700.0 * (np.power(10.0, values / 2595.0) - 1.0)


def build_mel_filterbank() -> np.ndarray:
    num_spectrogram_bins = (FFT_LENGTH // 2) + 1
    max_frequency_hz = min(UPPER_FREQUENCY_HZ, EXPECTED_SAMPLE_RATE / 2.0)

    mel_edges = np.linspace(
        hz_to_mel(LOWER_FREQUENCY_HZ),
        hz_to_mel(max_frequency_hz),
        MEL_FILTERBANK_CHANNELS + 2,
        dtype=np.float32,
    )
    hz_edges = mel_to_hz(mel_edges)
    bin_frequencies = np.linspace(0.0, EXPECTED_SAMPLE_RATE / 2.0, num_spectrogram_bins, dtype=np.float32)
    filters = np.zeros((MEL_FILTERBANK_CHANNELS, num_spectrogram_bins), dtype=np.float32)

    for index in range(MEL_FILTERBANK_CHANNELS):
        left_hz = hz_edges[index]
        center_hz = hz_edges[index + 1]
        right_hz = hz_edges[index + 2]
        lower_slope = (bin_frequencies - left_hz) / max(center_hz - left_hz, 1e-6)
        upper_slope = (right_hz - bin_frequencies) / max(right_hz - center_hz, 1e-6)
        filters[index] = np.maximum(0.0, np.minimum(lower_slope, upper_slope))

    return filters


def mel_filterbank() -> np.ndarray:
    global MEL_FILTERBANK
    if MEL_FILTERBANK is None:
        MEL_FILTERBANK = build_mel_filterbank()
    return MEL_FILTERBANK


def frame_audio(audio: np.ndarray) -> np.ndarray:
    frames = np.zeros((SPECTROGRAM_LENGTH, WINDOW_SIZE_SAMPLES), dtype=np.float32)
    for index in range(SPECTROGRAM_LENGTH):
        start = index * WINDOW_STRIDE_SAMPLES
        end = start + WINDOW_SIZE_SAMPLES
        frames[index, :] = audio[start:end]
    return frames


def dct_type_ii(values: np.ndarray, coefficient_count: int) -> np.ndarray:
    filter_count = values.shape[1]
    n = np.arange(filter_count, dtype=np.float32)
    k = np.arange(coefficient_count, dtype=np.float32)[:, None]
    basis = np.cos((np.pi / filter_count) * (n + 0.5) * k)
    transformed = values @ basis.T
    transformed[:, 0] *= np.sqrt(1.0 / filter_count)
    if coefficient_count > 1:
        transformed[:, 1:] *= np.sqrt(2.0 / filter_count)
    return transformed


def feature_from_waveform(samples: np.ndarray) -> torch.Tensor:
    frames = frame_audio(samples)
    frames *= np.hamming(WINDOW_SIZE_SAMPLES).astype(np.float32)
    spectrum = np.fft.rfft(frames, n=FFT_LENGTH, axis=1)
    power_spectrum = (np.abs(spectrum) ** 2).astype(np.float32)
    mel_energies = np.maximum(power_spectrum @ mel_filterbank().T, 1e-12)
    log_mel = np.log(mel_energies)
    mfcc = dct_type_ii(log_mel, DCT_COEFFICIENT_COUNT)
    flattened = mfcc.reshape(-1).astype(np.float32)
    if flattened.shape[0] != INPUT_FEATURES:
        raise RuntimeError(f"Expected {INPUT_FEATURES} MFCC features, found {flattened.shape[0]}")
    return torch.from_numpy(flattened)


def maybe_mix_background(samples: np.ndarray, noise_pool: list[np.ndarray]) -> np.ndarray:
    if not noise_pool or random.random() > 0.35:
        return samples
    noise = random.choice(noise_pool)
    if noise.shape[0] > EXPECTED_SAMPLES:
        start = random.randint(0, noise.shape[0] - EXPECTED_SAMPLES)
        noise = noise[start : start + EXPECTED_SAMPLES]
    elif noise.shape[0] < EXPECTED_SAMPLES:
        noise = np.pad(noise, (0, EXPECTED_SAMPLES - noise.shape[0]), mode="constant")
    gain = random.uniform(0.02, 0.12)
    return np.clip(samples + (noise * gain), -1.0, 1.0)


def find_dataset_root(training_dir: Path) -> Path:
    direct_dataset = training_dir / "dataset"
    if direct_dataset.is_dir():
        return direct_dataset

    archives = sorted(training_dir.rglob("*.tar.gz"))
    if not archives:
        raise FileNotFoundError(f"No dataset archive found under {training_dir}")

    extract_root = Path(tempfile.mkdtemp(prefix="kws-dataset-"))
    with tarfile.open(archives[0], "r:gz") as archive:
        archive.extractall(extract_root)
    dataset_root = extract_root / "dataset"
    if not dataset_root.is_dir():
        raise FileNotFoundError("Extracted archive did not contain a dataset/ folder")
    return dataset_root


def try_download_manifest(manifest_s3_uri: str, target_dir: Path) -> Optional[Path]:
    if not manifest_s3_uri:
        return None
    parsed = urlparse(manifest_s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        return None
    target = target_dir / "downloaded-manifest.json"
    boto3.client("s3").download_file(parsed.netloc, parsed.path.lstrip("/"), str(target))
    return target


def load_manifest(dataset_root: Path, manifest_s3_uri: str) -> dict:
    manifest_path = dataset_root / "dataset-manifest.json"
    if not manifest_path.is_file():
        downloaded = try_download_manifest(manifest_s3_uri, dataset_root)
        if downloaded is not None:
            manifest_path = downloaded
    if not manifest_path.is_file():
        raise FileNotFoundError("dataset-manifest.json is missing from the archive and could not be downloaded.")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_labels(dataset_root: Path, manifest: dict, wanted_words_override: str) -> list[str]:
    if wanted_words_override.strip():
        labels = [item.strip() for item in wanted_words_override.split(",") if item.strip()]
    else:
        labels = [str(item).strip() for item in manifest.get("wanted_words", []) if str(item).strip()]
    if not labels:
        labels = sorted(
            child.name for child in dataset_root.iterdir() if child.is_dir() and child.name != "_background_noise_"
        )
    if not labels:
        raise RuntimeError("No training labels were found in the dataset.")
    return labels


def load_noise_pool(dataset_root: Path) -> list[np.ndarray]:
    noise_dir = dataset_root / "_background_noise_"
    if not noise_dir.is_dir():
        return []
    pool = []
    for wav_path in sorted(noise_dir.glob("*.wav")):
        try:
            pool.append(read_wav(wav_path))
        except Exception:
            continue
    return pool


class KeywordDataset(Dataset):
    def __init__(self, samples: list[tuple[Path, int]], noise_pool: list[np.ndarray], augment: bool):
        self.samples = samples
        self.noise_pool = noise_pool
        self.augment = augment

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path, label_index = self.samples[index]
        waveform = read_wav(path)
        if self.augment:
            waveform = maybe_mix_background(waveform, self.noise_pool)
            waveform *= random.uniform(0.85, 1.15)
            waveform = np.clip(waveform, -1.0, 1.0)
        return feature_from_waveform(waveform), torch.tensor(label_index, dtype=torch.long)


def collect_samples(dataset_root: Path, labels: Iterable[str]) -> list[tuple[Path, int]]:
    sample_rows: list[tuple[Path, int]] = []
    for label_index, label in enumerate(labels):
        label_dir = dataset_root / label
        if not label_dir.is_dir():
            raise FileNotFoundError(f"Dataset label folder is missing: {label_dir}")
        wav_paths = sorted(label_dir.glob("*.wav"))
        if not wav_paths:
            raise RuntimeError(f"Label folder is empty: {label_dir}")
        sample_rows.extend((wav_path, label_index) for wav_path in wav_paths)
    return sample_rows


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_items = 0
    loss_fn = nn.CrossEntropyLoss()
    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device)
            labels = labels.to(device)
            logits = model(inputs)
            loss = loss_fn(logits, labels)
            total_loss += loss.item() * labels.shape[0]
            total_correct += int((logits.argmax(dim=1) == labels).sum().item())
            total_items += labels.shape[0]
    if total_items == 0:
        return 0.0, 0.0
    return total_loss / total_items, total_correct / total_items


def train_model(args: argparse.Namespace, dataset_root: Path, labels: list[str], manifest: dict) -> dict:
    samples = collect_samples(dataset_root, labels)
    noise_pool = load_noise_pool(dataset_root)

    generator = torch.Generator().manual_seed(args.seed)
    validation_items = max(1, int(round(len(samples) * args.validation_split)))
    validation_items = min(validation_items, max(1, len(samples) - 1))
    training_items = len(samples) - validation_items

    full_training_dataset = KeywordDataset(samples, noise_pool=noise_pool, augment=True)
    full_validation_dataset = KeywordDataset(samples, noise_pool=noise_pool, augment=False)
    training_dataset, validation_dataset = random_split(full_training_dataset, [training_items, validation_items], generator=generator)
    validation_dataset.dataset = full_validation_dataset

    training_loader = DataLoader(training_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = KeywordSpotter(num_labels=len(labels)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    loss_fn = nn.CrossEntropyLoss()

    best_state = None
    best_accuracy = -1.0
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        total_items = 0
        for inputs, batch_labels in training_loader:
            inputs = inputs.to(device)
            batch_labels = batch_labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = loss_fn(logits, batch_labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch_labels.shape[0]
            total_items += batch_labels.shape[0]

        train_loss = epoch_loss / max(1, total_items)
        validation_loss, validation_accuracy = evaluate(model, validation_loader, device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "validation_loss": round(validation_loss, 6),
                "validation_accuracy": round(validation_accuracy, 6),
            }
        )
        print(
            f"epoch={epoch} train_loss={train_loss:.4f} "
            f"validation_loss={validation_loss:.4f} validation_accuracy={validation_accuracy:.4f}",
            flush=True,
        )

        if validation_accuracy >= best_accuracy:
            best_accuracy = validation_accuracy
            best_state = {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError("Training did not produce a model state.")

    model.load_state_dict(best_state)
    model = model.to("cpu").eval()
    traced_model = torch.jit.trace(model, example_input())

    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    state_path = model_dir / "model-state.pt"
    weights_path = model_dir / "model.pt"
    labels_path = model_dir / "labels.txt"
    result_path = model_dir / "training-result.json"

    torch.save(
        {
            "state_dict": best_state,
            "labels": labels,
            "sample_rate": manifest.get("sample_rate", EXPECTED_SAMPLE_RATE),
            "clip_seconds": manifest.get("clip_seconds", EXPECTED_SECONDS),
            "window_size_ms": 40,
            "window_stride_ms": 20,
            "dct_coefficient_count": DCT_COEFFICIENT_COUNT,
            "input_features": INPUT_FEATURES,
            "hidden_sizes": [128, 64],
        },
        state_path,
    )
    traced_model.save(str(weights_path))
    labels_path.write_text("\n".join(labels) + "\n", encoding="utf-8")

    result = {
        "labels": labels,
        "label_count": len(labels),
        "clip_count": len(samples),
        "sample_rate": manifest.get("sample_rate", EXPECTED_SAMPLE_RATE),
        "clip_seconds": manifest.get("clip_seconds", EXPECTED_SECONDS),
        "window_size_ms": 40,
        "window_stride_ms": 20,
        "dct_coefficient_count": DCT_COEFFICIENT_COUNT,
        "input_features": INPUT_FEATURES,
        "best_validation_accuracy": round(best_accuracy, 6),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "device": str(device),
        "weights_file": weights_path.name,
        "state_file": state_path.name,
        "history": history,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return {
        "weights_path": weights_path,
        "state_path": state_path,
        "labels_path": labels_path,
        "result_path": result_path,
        "result": result,
    }


def upload_file_if_requested(local_path: Path, s3_uri: str) -> str:
    if not s3_uri.strip():
        return ""
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    boto3.client("s3").upload_file(str(local_path), parsed.netloc, parsed.path.lstrip("/"))
    return s3_uri


def main():
    args = parse_args()
    set_seed(args.seed)

    training_dir = Path(args.training_dir)
    dataset_root = find_dataset_root(training_dir)
    manifest = load_manifest(dataset_root, args.manifest_s3_uri)
    labels = resolve_labels(dataset_root, manifest, args.wanted_words)

    artifacts = train_model(args, dataset_root, labels, manifest)

    uploaded = {
        "weights_s3_uri": upload_file_if_requested(artifacts["weights_path"], args.weights_upload_s3_uri),
        "state_s3_uri": upload_file_if_requested(artifacts["state_path"], args.state_upload_s3_uri),
        "labels_s3_uri": upload_file_if_requested(artifacts["labels_path"], args.labels_upload_s3_uri),
        "results_s3_uri": upload_file_if_requested(artifacts["result_path"], args.results_upload_s3_uri),
    }
    if any(uploaded.values()):
        result = dict(artifacts["result"])
        result["uploaded"] = uploaded
        artifacts["result_path"].write_text(json.dumps(result, indent=2), encoding="utf-8")
        if uploaded["results_s3_uri"]:
            upload_file_if_requested(artifacts["result_path"], args.results_upload_s3_uri)

    print("Training complete.", flush=True)
    for key, value in uploaded.items():
        if value:
            print(f"{key}={value}", flush=True)


if __name__ == "__main__":
    main()
