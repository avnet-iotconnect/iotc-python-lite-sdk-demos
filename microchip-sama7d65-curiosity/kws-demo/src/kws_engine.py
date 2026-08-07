# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
"""Keyword spotting runtime for the SAMA7D65 /IOTCONNECT demo."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter  # type: ignore
except ImportError:
    try:
        import tensorflow as tf  # type: ignore

        Interpreter = tf.lite.Interpreter
    except ImportError:
        try:
            from tflite_numpy_interpreter import Interpreter  # type: ignore
        except ImportError:
            Interpreter = None


SPECIAL_LABELS = {"_silence_", "_unknown_"}


class KeywordSpotterError(RuntimeError):
    """Raised when the KWS runtime cannot capture audio or run inference."""


@dataclass
class KwsSettings:
    model_path: Path
    labels_path: Path
    sample_rate: int = 16000
    clip_duration_ms: int = 1000
    window_size_ms: int = 40
    window_stride_ms: int = 20
    dct_coefficient_count: int = 10
    mel_filterbank_channels: int = 40
    lower_frequency_hz: float = 20.0
    upper_frequency_hz: float = 4000.0
    threshold: float = 0.80
    cooldown_secs: float = 2.0
    min_signal_rms: float = 0.003
    arecord_device: Optional[str] = None


@dataclass
class InferenceResult:
    timestamp_utc: str
    label: str
    confidence: float
    class_id: int
    detected: bool
    audio_device: str


class KeywordSpotter:
    def __init__(self, settings: KwsSettings):
        if Interpreter is None:
            raise KeywordSpotterError(
                "No TensorFlow Lite interpreter is available. Install tflite-runtime "
                "or provide a TensorFlow build with tf.lite.Interpreter."
            )

        self.settings = settings
        self.labels = self._load_labels(settings.labels_path)
        self.threshold = settings.threshold
        self.cooldown_secs = settings.cooldown_secs
        self._state_lock = threading.Lock()
        self._last_detected_word = ""
        self._last_detected_confidence = 0.0
        self._last_detected_at = ""
        self._last_detected_monotonic = 0.0
        self._inference_count = 0
        self._detection_count = 0
        self._audio_device = settings.arecord_device or self._detect_arecord_device()

        self._interpreter = Interpreter(model_path=str(settings.model_path))
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()[0]
        self._output_details = self._interpreter.get_output_details()[0]
        self._input_scale, self._input_zero_point = self._input_details.get("quantization", (0.0, 0))
        self._output_scale, self._output_zero_point = self._output_details.get("quantization", (0.0, 0))

        self.desired_samples = int(settings.sample_rate * settings.clip_duration_ms / 1000)
        self.window_size_samples = int(settings.sample_rate * settings.window_size_ms / 1000)
        self.window_stride_samples = int(settings.sample_rate * settings.window_stride_ms / 1000)
        self.spectrogram_length = 1 + int(
            (self.desired_samples - self.window_size_samples) / self.window_stride_samples
        )
        self.fft_length = 1 << (self.window_size_samples - 1).bit_length()
        self._mel_filterbank = self._build_mel_filterbank()

    @staticmethod
    def _load_labels(labels_path: Path) -> List[str]:
        if not labels_path.exists():
            raise KeywordSpotterError(f"Labels file not found: {labels_path}")
        labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(labels) == 0:
            raise KeywordSpotterError(f"Labels file is empty: {labels_path}")
        return labels

    @staticmethod
    def _hz_to_mel(frequency_hz: Union[np.ndarray, float]) -> np.ndarray:
        values = np.asarray(frequency_hz, dtype=np.float32)
        return 2595.0 * np.log10(1.0 + (values / 700.0))

    @staticmethod
    def _mel_to_hz(mel_values: np.ndarray) -> np.ndarray:
        return 700.0 * (np.power(10.0, mel_values / 2595.0) - 1.0)

    def _build_mel_filterbank(self) -> np.ndarray:
        num_spectrogram_bins = (self.fft_length // 2) + 1
        max_frequency_hz = min(self.settings.upper_frequency_hz, self.settings.sample_rate / 2.0)

        mel_edges = np.linspace(
            self._hz_to_mel(self.settings.lower_frequency_hz),
            self._hz_to_mel(max_frequency_hz),
            self.settings.mel_filterbank_channels + 2,
            dtype=np.float32,
        )
        hz_edges = self._mel_to_hz(mel_edges)
        bin_frequencies = np.linspace(
            0.0,
            self.settings.sample_rate / 2.0,
            num_spectrogram_bins,
            dtype=np.float32,
        )

        filters = np.zeros((self.settings.mel_filterbank_channels, num_spectrogram_bins), dtype=np.float32)
        for index in range(self.settings.mel_filterbank_channels):
            left_hz = hz_edges[index]
            center_hz = hz_edges[index + 1]
            right_hz = hz_edges[index + 2]

            lower_slope = (bin_frequencies - left_hz) / max(center_hz - left_hz, 1e-6)
            upper_slope = (right_hz - bin_frequencies) / max(right_hz - center_hz, 1e-6)
            filters[index] = np.maximum(0.0, np.minimum(lower_slope, upper_slope))

        return filters

    def _detect_arecord_device(self) -> Optional[str]:
        if shutil.which("arecord") is None:
            return None

        try:
            result = subprocess.run(
                ["arecord", "-l"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return None

        matches = re.findall(r"card\s+(\d+):.*?device\s+(\d+):", result.stdout, flags=re.IGNORECASE)
        if not matches:
            return None

        card_id, device_id = matches[0]
        return f"plughw:{card_id},{device_id}"

    def audio_device_name(self) -> str:
        return self._audio_device or "default"

    def set_threshold(self, new_threshold: float):
        with self._state_lock:
            self.threshold = float(new_threshold)

    def set_audio_device(self, device_name: str):
        with self._state_lock:
            self._audio_device = device_name.strip() or None

    def _capture_audio_clip(self) -> np.ndarray:
        if shutil.which("arecord") is None:
            raise KeywordSpotterError("arecord is not installed. Install alsa-utils on the board.")

        with tempfile.NamedTemporaryFile(prefix="kws-", suffix=".wav", delete=False) as handle:
            wav_path = Path(handle.name)

        command = [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-r",
            str(self.settings.sample_rate),
            "-d",
            str(max(1, int(round(self.settings.clip_duration_ms / 1000.0)))),
            "-t",
            "wav",
            str(wav_path),
        ]

        if self._audio_device:
            command[1:1] = ["-D", self._audio_device]

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(10, int(self.settings.clip_duration_ms / 1000.0) + 5),
            )
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
                raise KeywordSpotterError(f"Audio capture failed: {message}")

            audio = self._load_audio_from_wav(wav_path)
            return self._normalize_audio_length(audio)
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _load_audio_from_wav(self, wav_path: Path) -> np.ndarray:
        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                frame_count = wav_file.getnframes()
                raw_audio = wav_file.readframes(frame_count)
        except wave.Error as exc:
            raise KeywordSpotterError(f"Unable to read captured WAV file: {exc}") from exc

        if sample_width != 2:
            raise KeywordSpotterError(f"Unsupported sample width: {sample_width * 8} bits")

        pcm = np.frombuffer(raw_audio, dtype=np.int16)
        if channels > 1:
            pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)

        if sample_rate != self.settings.sample_rate:
            raise KeywordSpotterError(
                f"Captured audio sample rate {sample_rate} does not match expected {self.settings.sample_rate}"
            )

        return (pcm.astype(np.float32) / 32768.0).clip(-1.0, 1.0)

    def _normalize_audio_length(self, audio: np.ndarray) -> np.ndarray:
        if audio.shape[0] > self.desired_samples:
            return audio[: self.desired_samples]
        if audio.shape[0] < self.desired_samples:
            return np.pad(audio, (0, self.desired_samples - audio.shape[0]), mode="constant")
        return audio

    def _frame_audio(self, audio: np.ndarray) -> np.ndarray:
        frames = np.zeros((self.spectrogram_length, self.window_size_samples), dtype=np.float32)
        for index in range(self.spectrogram_length):
            start = index * self.window_stride_samples
            end = start + self.window_size_samples
            frames[index, :] = audio[start:end]
        return frames

    def _compute_mfcc(self, audio: np.ndarray) -> np.ndarray:
        frames = self._frame_audio(audio)
        frames *= np.hamming(self.window_size_samples).astype(np.float32)

        spectrum = np.fft.rfft(frames, n=self.fft_length, axis=1)
        power_spectrum = (np.abs(spectrum) ** 2).astype(np.float32)

        mel_energies = np.maximum(power_spectrum @ self._mel_filterbank.T, 1e-12)
        log_mel = np.log(mel_energies)
        mfcc = self._dct_type_ii(log_mel, self.settings.dct_coefficient_count)
        return mfcc.reshape(1, -1).astype(np.float32)

    @staticmethod
    def _dct_type_ii(values: np.ndarray, coefficient_count: int) -> np.ndarray:
        filter_count = values.shape[1]
        n = np.arange(filter_count, dtype=np.float32)
        k = np.arange(coefficient_count, dtype=np.float32)[:, None]
        basis = np.cos((np.pi / filter_count) * (n + 0.5) * k)
        transformed = values @ basis.T
        transformed[:, 0] *= np.sqrt(1.0 / filter_count)
        if coefficient_count > 1:
            transformed[:, 1:] *= np.sqrt(2.0 / filter_count)
        return transformed

    def _quantize_input(self, input_tensor: np.ndarray) -> np.ndarray:
        input_dtype = self._input_details["dtype"]

        if input_dtype == np.float32:
            return input_tensor.astype(np.float32)

        if input_dtype == np.int8:
            if self._input_scale == 0:
                return input_tensor.astype(np.int8)
            quantized = np.round(input_tensor / self._input_scale + self._input_zero_point)
            return np.clip(quantized, -128, 127).astype(np.int8)

        if input_dtype == np.uint8:
            if self._input_scale == 0:
                return np.clip(input_tensor, 0, 255).astype(np.uint8)
            quantized = np.round(input_tensor / self._input_scale + self._input_zero_point)
            return np.clip(quantized, 0, 255).astype(np.uint8)

        raise KeywordSpotterError(f"Unsupported input dtype: {input_dtype}")

    def _dequantize_output(self, output_tensor: np.ndarray) -> np.ndarray:
        output_dtype = self._output_details["dtype"]

        if output_dtype == np.float32:
            return output_tensor.astype(np.float32)

        if output_dtype in (np.int8, np.uint8):
            if self._output_scale == 0:
                return output_tensor.astype(np.float32)
            return (output_tensor.astype(np.float32) - self._output_zero_point) * self._output_scale

        raise KeywordSpotterError(f"Unsupported output dtype: {output_dtype}")

    @staticmethod
    def _softmax(scores: np.ndarray) -> np.ndarray:
        shifted = scores.astype(np.float32) - np.max(scores.astype(np.float32))
        exp_values = np.exp(np.clip(shifted, -60.0, 0.0))
        total = float(np.sum(exp_values))
        if total <= 0.0:
            return np.zeros_like(exp_values, dtype=np.float32)
        return exp_values / total

    def run_once(self) -> InferenceResult:
        audio = self._capture_audio_clip()
        signal_rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        if signal_rms < self.settings.min_signal_rms:
            with self._state_lock:
                self._inference_count += 1
            return InferenceResult(
                timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                label="_silence_",
                confidence=0.0,
                class_id=-1,
                detected=False,
                audio_device=self.audio_device_name(),
            )

        features = self._compute_mfcc(audio)
        quantized_input = self._quantize_input(features)

        self._interpreter.set_tensor(self._input_details["index"], quantized_input)
        self._interpreter.invoke()
        output_tensor = self._interpreter.get_tensor(self._output_details["index"])[0]
        scores = self._softmax(self._dequantize_output(output_tensor))

        class_id = int(np.argmax(scores))
        confidence = float(scores[class_id])
        label = self.labels[class_id] if class_id < len(self.labels) else f"class_{class_id}"
        detected = self._update_detection_state(label, confidence)

        with self._state_lock:
            self._inference_count += 1

        return InferenceResult(
            timestamp_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            label=label,
            confidence=confidence,
            class_id=class_id,
            detected=detected,
            audio_device=self.audio_device_name(),
        )

    def _update_detection_state(self, label: str, confidence: float) -> bool:
        if label in SPECIAL_LABELS:
            return False

        with self._state_lock:
            threshold = self.threshold
            cooldown_secs = self.cooldown_secs
            last_detected_monotonic = self._last_detected_monotonic

        if confidence < threshold:
            return False

        now_monotonic = time.monotonic()
        if (now_monotonic - last_detected_monotonic) < cooldown_secs:
            return False

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._state_lock:
            self._last_detected_word = label
            self._last_detected_confidence = confidence
            self._last_detected_at = timestamp
            self._last_detected_monotonic = now_monotonic
            self._detection_count += 1
        return True

    def state_snapshot(self) -> dict:
        with self._state_lock:
            return {
                "audio_device": self.audio_device_name(),
                "detection_count": self._detection_count,
                "inference_count": self._inference_count,
                "last_detected_at": self._last_detected_at,
                "last_detected_confidence": self._last_detected_confidence,
                "last_detected_word": self._last_detected_word,
                "threshold": self.threshold,
            }
