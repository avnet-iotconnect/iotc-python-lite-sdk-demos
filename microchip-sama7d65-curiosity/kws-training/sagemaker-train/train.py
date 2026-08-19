# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import tarfile
import tempfile
import urllib.request
import wave
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import boto3
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split

from model import (
    BLOCK_COUNT,
    DCT_COEFFICIENT_COUNT,
    FEATURE_SHAPE,
    INPUT_FEATURES,
    MODEL_ARCHITECTURE,
    STEM_CHANNELS,
    KeywordSpotter,
    example_input,
)

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
SPECIAL_LABELS = {"_silence_", "_unknown_"}
EXCLUDED_COMMAND_LABELS = {"_background_noise_", "_silence_", "_unknown_"}
DEFAULT_RECOMMENDED_COMMANDS = ["deal", "double", "hit", "reset", "stand"]
DEFAULT_SPEECH_COMMANDS_WORDS = [
    "yes",
    "no",
    "up",
    "down",
    "left",
    "right",
    "on",
    "off",
    "stop",
    "go",
]
DEFAULT_SPEECH_COMMANDS_URL = "http://download.tensorflow.org/data/speech_commands_v0.02.tar.gz"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a board-compatible DS-CNN KWS model from the board dataset archive.")
    parser.add_argument("--epochs", type=int, default=int(os.getenv("KWS_TRAIN_EPOCHS", "30")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("KWS_TRAIN_BATCH_SIZE", "32")))
    parser.add_argument("--learning-rate", type=float, default=float(os.getenv("KWS_TRAIN_LEARNING_RATE", "0.0007")))
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
    parser.add_argument("--recommended-commands", default=os.getenv("KWS_RECOMMENDED_WANTED_WORDS", ",".join(DEFAULT_RECOMMENDED_COMMANDS)))
    parser.add_argument("--pretrain-enabled", type=int, default=int(os.getenv("KWS_TRAIN_PRETRAIN_ENABLED", "1")))
    parser.add_argument("--pretrain-required", type=int, default=int(os.getenv("KWS_TRAIN_PRETRAIN_REQUIRED", "0")))
    parser.add_argument("--pretrain-source", default=os.getenv("KWS_TRAIN_PRETRAIN_SOURCE", DEFAULT_SPEECH_COMMANDS_URL))
    parser.add_argument("--pretrain-epochs", type=int, default=int(os.getenv("KWS_TRAIN_PRETRAIN_EPOCHS", "6")))
    parser.add_argument(
        "--pretrain-max-samples-per-label",
        type=int,
        default=int(os.getenv("KWS_TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL", "1800")),
    )
    parser.add_argument("--pretrain-validation-split", type=float, default=float(os.getenv("KWS_TRAIN_PRETRAIN_VALIDATION_SPLIT", "0.1")))
    parser.add_argument("--pretrain-learning-rate", type=float, default=float(os.getenv("KWS_TRAIN_PRETRAIN_LEARNING_RATE", "0.001")))
    parser.add_argument("--pretrain-words", default=os.getenv("KWS_TRAIN_PRETRAIN_WORDS", ",".join(DEFAULT_SPEECH_COMMANDS_WORDS)))
    parser.add_argument("--musan-source", default=os.getenv("KWS_TRAIN_MUSAN_SOURCE", ""))
    parser.add_argument("--musan-max-clips", type=int, default=int(os.getenv("KWS_TRAIN_MUSAN_MAX_CLIPS", "128")))
    return parser.parse_known_args()[0]


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def resample_audio(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    duration = samples.shape[0] / float(source_rate)
    target_length = max(1, int(round(duration * target_rate)))
    source_positions = np.linspace(0.0, 1.0, num=samples.shape[0], endpoint=False, dtype=np.float32)
    target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False, dtype=np.float32)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)


def decode_wav(path: Path, normalize_length: bool) -> np.ndarray:
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
        samples = resample_audio(samples, sample_rate, EXPECTED_SAMPLE_RATE)

    samples /= 32768.0
    samples = np.clip(samples, -1.0, 1.0)

    if normalize_length:
        if samples.shape[0] < EXPECTED_SAMPLES:
            samples = np.pad(samples, (0, EXPECTED_SAMPLES - samples.shape[0]), mode="constant")
        elif samples.shape[0] > EXPECTED_SAMPLES:
            samples = samples[:EXPECTED_SAMPLES]
    return samples.astype(np.float32, copy=False)


def read_wav(path: Path) -> np.ndarray:
    return decode_wav(path, normalize_length=True)


def read_noise_wav(path: Path) -> np.ndarray:
    return decode_wav(path, normalize_length=False)


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
    if not noise_pool or random.random() > 0.45:
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


def parse_word_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def resolve_command_labels(dataset_root: Path, manifest: dict, wanted_words_override: str, recommended_override: str) -> list[str]:
    if wanted_words_override.strip():
        labels = parse_word_list(wanted_words_override)
    else:
        labels = [str(item).strip() for item in manifest.get("wanted_words", []) if str(item).strip()]
    if not labels:
        labels = parse_word_list(recommended_override)
    if not labels:
        labels = sorted(
            child.name for child in dataset_root.iterdir() if child.is_dir() and child.name not in EXCLUDED_COMMAND_LABELS
        )
    existing = [label for label in labels if (dataset_root / label).is_dir()]
    if not existing:
        raise RuntimeError("No training labels were found in the dataset.")
    return existing


def resolve_model_labels(dataset_root: Path, command_labels: list[str]) -> list[str]:
    labels = ["_silence_"]
    unknown_dir = dataset_root / "_unknown_"
    if unknown_dir.is_dir() and any(unknown_dir.glob("*.wav")):
        labels.append("_unknown_")
    labels.extend(command_labels)
    return labels


def list_wav_files(root: Path, limit: Optional[int] = None) -> list[Path]:
    wav_paths = sorted(root.rglob("*.wav"))
    if limit is None or len(wav_paths) <= limit:
        return wav_paths
    random.shuffle(wav_paths)
    selected = wav_paths[:limit]
    selected.sort()
    return selected


def load_noise_pool(dataset_root: Path, external_noise_paths: list[Path]) -> list[np.ndarray]:
    pool: list[np.ndarray] = []
    noise_dir = dataset_root / "_background_noise_"
    if noise_dir.is_dir():
        for wav_path in sorted(noise_dir.glob("*.wav")):
            try:
                pool.append(read_noise_wav(wav_path))
            except Exception:
                continue
    for wav_path in external_noise_paths:
        try:
            pool.append(read_noise_wav(wav_path))
        except Exception:
            continue
    return pool


def resolve_data_source(source: str, cache_root: Path, default_name: str) -> Optional[Path]:
    source = source.strip()
    if not source:
        return None
    parsed = urlparse(source)
    if parsed.scheme == "s3":
        target_path = cache_root / default_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        boto3.client("s3").download_file(parsed.netloc, parsed.path.lstrip("/"), str(target_path))
        return target_path
    if parsed.scheme in {"http", "https"}:
        target_path = cache_root / default_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(source, str(target_path))
        return target_path
    candidate = Path(source)
    if not candidate.exists():
        raise FileNotFoundError(f"Supplemental data source does not exist: {source}")
    return candidate


def extract_archive(archive_path: Path, destination_root: Path) -> Path:
    extracted_root = destination_root / archive_path.stem.replace(".tar", "")
    marker = extracted_root / ".ready"
    if marker.is_file():
        return extracted_root
    if extracted_root.exists():
        shutil.rmtree(extracted_root)
    extracted_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        archive.extractall(extracted_root)
    marker.write_text("ready\n", encoding="utf-8")
    return extracted_root


def find_named_root(root: Path, preferred_names: list[str]) -> Path:
    for name in preferred_names:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    if any(root.glob("*_list.txt")) and any(child.is_dir() for child in root.iterdir()):
        return root
    for child in sorted(root.iterdir()):
        if child.is_dir() and any(child.rglob("*.wav")):
            return child
    return root


def prepare_speech_commands_root(source: str, cache_root: Path) -> Optional[Path]:
    resolved = resolve_data_source(source, cache_root, "speech_commands_v0.02.tar.gz")
    if resolved is None:
        return None
    if resolved.is_dir():
        return resolved
    extracted = extract_archive(resolved, cache_root / "speech-commands")
    return find_named_root(extracted, ["speech_commands_v0.02", "speech_commands"])


def prepare_musan_noise_paths(source: str, cache_root: Path, limit: int) -> list[Path]:
    resolved = resolve_data_source(source, cache_root, "musan.tar.gz")
    if resolved is None:
        return []
    if resolved.is_file():
        extracted = extract_archive(resolved, cache_root / "musan")
        root = find_named_root(extracted, ["musan"])
    else:
        root = resolved
    return list_wav_files(root, limit=max(1, limit) if limit else None)


def sample_paths(paths: list[Path], limit: int) -> list[Path]:
    if len(paths) <= limit:
        return sorted(paths)
    chosen = random.sample(paths, limit)
    chosen.sort()
    return chosen


def build_speech_commands_pretrain_data(
    dataset_root: Path,
    target_words: list[str],
    max_samples_per_label: int,
) -> tuple[list[str], list[tuple[Optional[Path], int]], list[np.ndarray]]:
    labels = ["_silence_", "_unknown_"] + [label for label in target_words if (dataset_root / label).is_dir()]
    if len(labels) <= 2:
        raise RuntimeError("Speech Commands pretraining dataset does not contain the requested target words.")

    samples: list[tuple[Optional[Path], int]] = []
    per_label_counts: list[int] = []
    label_to_index = {label: index for index, label in enumerate(labels)}

    for label in labels:
        if label in SPECIAL_LABELS:
            continue
        wav_paths = sample_paths(sorted((dataset_root / label).glob("*.wav")), max_samples_per_label)
        if not wav_paths:
            continue
        samples.extend((path, label_to_index[label]) for path in wav_paths)
        per_label_counts.append(len(wav_paths))

    unknown_index = label_to_index["_unknown_"]
    unknown_candidates: list[Path] = []
    for child in sorted(dataset_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name in EXCLUDED_COMMAND_LABELS or child.name in target_words:
            continue
        unknown_candidates.extend(sorted(child.glob("*.wav")))
    if unknown_candidates:
        unknown_limit = max(max_samples_per_label, len(target_words) * max_samples_per_label // 2)
        samples.extend((path, unknown_index) for path in sample_paths(unknown_candidates, unknown_limit))

    silence_count = max(32, int(round(sum(per_label_counts) / max(1, len(per_label_counts)))))
    silence_index = label_to_index["_silence_"]
    samples.extend((None, silence_index) for _ in range(silence_count))

    noise_pool = load_noise_pool(dataset_root, external_noise_paths=[])
    return labels, samples, noise_pool


class KeywordDataset(Dataset):
    def __init__(self, samples: list[tuple[Optional[Path], int]], noise_pool: list[np.ndarray], augment: bool):
        self.samples = samples
        self.noise_pool = noise_pool
        self.augment = augment

    def __len__(self) -> int:
        return len(self.samples)

    def _make_silence_waveform(self) -> np.ndarray:
        waveform = np.zeros(EXPECTED_SAMPLES, dtype=np.float32)
        if self.noise_pool:
            noise = random.choice(self.noise_pool)
            if noise.shape[0] > EXPECTED_SAMPLES:
                start = random.randint(0, noise.shape[0] - EXPECTED_SAMPLES)
                noise = noise[start : start + EXPECTED_SAMPLES]
            elif noise.shape[0] < EXPECTED_SAMPLES:
                noise = np.pad(noise, (0, EXPECTED_SAMPLES - noise.shape[0]), mode="constant")
            gain = random.uniform(0.0, 0.025 if self.augment else 0.01)
            waveform = np.clip(noise * gain, -1.0, 1.0)
        return waveform

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path, label_index = self.samples[index]
        if path is None:
            waveform = self._make_silence_waveform()
        else:
            waveform = read_wav(path)
        if self.augment and path is not None:
            waveform = maybe_mix_background(waveform, self.noise_pool)
            waveform *= random.uniform(0.85, 1.15)
            waveform = np.clip(waveform, -1.0, 1.0)
        return feature_from_waveform(waveform), torch.tensor(label_index, dtype=torch.long)


def collect_samples(dataset_root: Path, labels: Iterable[str]) -> list[tuple[Optional[Path], int]]:
    labels_list = list(labels)
    sample_rows: list[tuple[Optional[Path], int]] = []
    real_label_counts: list[int] = []
    for label_index, label in enumerate(labels_list):
        if label == "_silence_":
            continue
        label_dir = dataset_root / label
        if not label_dir.is_dir():
            raise FileNotFoundError(f"Dataset label folder is missing: {label_dir}")
        wav_paths = sorted(label_dir.glob("*.wav"))
        if not wav_paths:
            raise RuntimeError(f"Label folder is empty: {label_dir}")
        sample_rows.extend((wav_path, label_index) for wav_path in wav_paths)
        if label not in SPECIAL_LABELS:
            real_label_counts.append(len(wav_paths))

    if "_silence_" in labels_list:
        silence_index = labels_list.index("_silence_")
        silence_count = max(16, int(round(sum(real_label_counts) / max(1, len(real_label_counts)))))
        sample_rows.extend((None, silence_index) for _ in range(silence_count))
    return sample_rows


def create_data_loaders(
    samples: list[tuple[Optional[Path], int]],
    noise_pool: list[np.ndarray],
    *,
    batch_size: int,
    validation_split: float,
    seed: int,
) -> tuple[DataLoader, DataLoader]:
    generator = torch.Generator().manual_seed(seed)
    validation_items = max(1, int(round(len(samples) * validation_split)))
    validation_items = min(validation_items, max(1, len(samples) - 1))
    training_items = len(samples) - validation_items

    full_training_dataset = KeywordDataset(samples, noise_pool=noise_pool, augment=True)
    full_validation_dataset = KeywordDataset(samples, noise_pool=noise_pool, augment=False)
    training_dataset, validation_dataset = random_split(
        full_training_dataset,
        [training_items, validation_items],
        generator=generator,
    )
    validation_dataset.dataset = full_validation_dataset

    training_loader = DataLoader(training_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    return training_loader, validation_loader


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


def run_training_loop(
    *,
    model: nn.Module,
    training_loader: DataLoader,
    validation_loader: DataLoader,
    device: torch.device,
    epochs: int,
    learning_rate: float,
    log_prefix: str,
) -> tuple[dict[str, torch.Tensor], float, list[dict]]:
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.CrossEntropyLoss()
    best_state = None
    best_accuracy = -1.0
    history: list[dict] = []

    for epoch in range(1, epochs + 1):
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
            f"{log_prefix} epoch={epoch} train_loss={train_loss:.4f} "
            f"validation_loss={validation_loss:.4f} validation_accuracy={validation_accuracy:.4f}",
            flush=True,
        )
        if validation_accuracy >= best_accuracy:
            best_accuracy = validation_accuracy
            best_state = {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError("Training did not produce a model state.")
    return best_state, best_accuracy, history


def load_backbone_state(model: nn.Module, pretrained_state: dict[str, torch.Tensor]) -> list[str]:
    current_state = model.state_dict()
    copied_keys: list[str] = []
    for name, tensor in pretrained_state.items():
        if name.startswith("classifier."):
            continue
        target = current_state.get(name)
        if target is None or target.shape != tensor.shape:
            continue
        current_state[name] = tensor
        copied_keys.append(name)
    model.load_state_dict(current_state)
    return copied_keys


def maybe_pretrain_backbone(args: argparse.Namespace, cache_root: Path) -> dict:
    if not bool(args.pretrain_enabled):
        return {"enabled": False, "status": "disabled"}

    try:
        speech_commands_root = prepare_speech_commands_root(args.pretrain_source, cache_root)
        if speech_commands_root is None:
            raise RuntimeError("No Speech Commands source was configured.")

        pretrain_words = parse_word_list(args.pretrain_words) or list(DEFAULT_SPEECH_COMMANDS_WORDS)
        pretrain_labels, pretrain_samples, pretrain_noise_pool = build_speech_commands_pretrain_data(
            speech_commands_root,
            pretrain_words,
            args.pretrain_max_samples_per_label,
        )
        training_loader, validation_loader = create_data_loaders(
            pretrain_samples,
            pretrain_noise_pool,
            batch_size=args.batch_size,
            validation_split=args.pretrain_validation_split,
            seed=args.seed,
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = KeywordSpotter(num_labels=len(pretrain_labels)).to(device)
        best_state, best_accuracy, history = run_training_loop(
            model=model,
            training_loader=training_loader,
            validation_loader=validation_loader,
            device=device,
            epochs=args.pretrain_epochs,
            learning_rate=args.pretrain_learning_rate,
            log_prefix="pretrain",
        )
        return {
            "enabled": True,
            "status": "completed",
            "labels": pretrain_labels,
            "clip_count": len(pretrain_samples),
            "best_validation_accuracy": round(best_accuracy, 6),
            "epochs": args.pretrain_epochs,
            "history": history,
            "state_dict": best_state,
            "source": args.pretrain_source,
        }
    except Exception as exc:
        if bool(args.pretrain_required):
            raise
        print(f"pretrain skipped: {exc}", flush=True)
        return {"enabled": True, "status": "skipped", "reason": str(exc), "source": args.pretrain_source}


def train_model(args: argparse.Namespace, dataset_root: Path, labels: list[str], manifest: dict) -> dict:
    cache_root = Path(tempfile.mkdtemp(prefix="kws-external-"))
    try:
        external_noise_paths = prepare_musan_noise_paths(args.musan_source, cache_root, args.musan_max_clips)
        samples = collect_samples(dataset_root, labels)
        noise_pool = load_noise_pool(dataset_root, external_noise_paths)
        training_loader, validation_loader = create_data_loaders(
            samples,
            noise_pool,
            batch_size=args.batch_size,
            validation_split=args.validation_split,
            seed=args.seed,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = KeywordSpotter(num_labels=len(labels)).to(device)
        pretraining = maybe_pretrain_backbone(args, cache_root)
        loaded_pretrain_keys: list[str] = []
        if pretraining.get("status") == "completed":
            loaded_pretrain_keys = load_backbone_state(model, pretraining["state_dict"])

        best_state, best_accuracy, history = run_training_loop(
            model=model,
            training_loader=training_loader,
            validation_loader=validation_loader,
            device=device,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            log_prefix="finetune",
        )

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
                "command_labels": [label for label in labels if label not in SPECIAL_LABELS],
                "sample_rate": manifest.get("sample_rate", EXPECTED_SAMPLE_RATE),
                "clip_seconds": manifest.get("clip_seconds", EXPECTED_SECONDS),
                "window_size_ms": 40,
                "window_stride_ms": 20,
                "dct_coefficient_count": DCT_COEFFICIENT_COUNT,
                "input_features": INPUT_FEATURES,
                "feature_shape": list(FEATURE_SHAPE),
                "model_architecture": MODEL_ARCHITECTURE,
                "stem_channels": STEM_CHANNELS,
                "block_count": BLOCK_COUNT,
            },
            state_path,
        )
        traced_model.save(str(weights_path))
        labels_path.write_text("\n".join(labels) + "\n", encoding="utf-8")

        result = {
            "labels": labels,
            "command_labels": [label for label in labels if label not in SPECIAL_LABELS],
            "special_labels": [label for label in labels if label in SPECIAL_LABELS],
            "label_count": len(labels),
            "clip_count": len(samples),
            "sample_rate": manifest.get("sample_rate", EXPECTED_SAMPLE_RATE),
            "clip_seconds": manifest.get("clip_seconds", EXPECTED_SECONDS),
            "window_size_ms": 40,
            "window_stride_ms": 20,
            "dct_coefficient_count": DCT_COEFFICIENT_COUNT,
            "input_features": INPUT_FEATURES,
            "feature_shape": list(FEATURE_SHAPE),
            "model_architecture": MODEL_ARCHITECTURE,
            "stem_channels": STEM_CHANNELS,
            "block_count": BLOCK_COUNT,
            "best_validation_accuracy": round(best_accuracy, 6),
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "device": str(device),
            "weights_file": weights_path.name,
            "state_file": state_path.name,
            "history": history,
            "pretraining": {key: value for key, value in pretraining.items() if key != "state_dict"},
            "loaded_pretrain_key_count": len(loaded_pretrain_keys),
            "musan_noise_clip_count": len(external_noise_paths),
        }
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return {
            "weights_path": weights_path,
            "state_path": state_path,
            "labels_path": labels_path,
            "result_path": result_path,
            "result": result,
        }
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)


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
    command_labels = resolve_command_labels(dataset_root, manifest, args.wanted_words, args.recommended_commands)
    labels = resolve_model_labels(dataset_root, command_labels)

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
