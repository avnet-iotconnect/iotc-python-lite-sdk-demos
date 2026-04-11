# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import wave
import zipfile
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
from avnet.iotconnect.sdk.lite import Callbacks, Client, DeviceConfig, DeviceConfigError, C2dCommand, C2dOta
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck
from tflite_runtime.interpreter import Interpreter


SPECIAL_LABELS = {"_silence_", "_unknown_"}


class KeywordSpotterError(RuntimeError):
    pass


@dataclass
class InferenceResult:
    timestamp_utc: str
    label: str
    confidence: float
    class_id: int
    detected: bool
    audio_device: str


class KeywordSpotter:
    def __init__(self, model_path: Path, labels_path: Path, threshold: float, cooldown_secs: float, audio_device: Optional[str]):
        self.sample_rate = 16000
        self.clip_duration_ms = 1000
        self.window_size_ms = 40
        self.window_stride_ms = 20
        self.dct_coefficient_count = 10
        self.mel_filterbank_channels = 40
        self.lower_frequency_hz = 20.0
        self.upper_frequency_hz = 4000.0
        self.threshold = threshold
        self.cooldown_secs = cooldown_secs
        self._state_lock = threading.Lock()
        self._last_detected_word = ""
        self._last_detected_confidence = 0.0
        self._last_detected_at = ""
        self._last_detected_monotonic = 0.0
        self._inference_count = 0
        self._detection_count = 0
        self._audio_device = audio_device or self._detect_arecord_device()
        self.labels = self._load_labels(labels_path)

        self._interpreter = Interpreter(model_path=str(model_path))
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()[0]
        self._output_details = self._interpreter.get_output_details()[0]
        self._input_scale, self._input_zero_point = self._input_details.get("quantization", (0.0, 0))
        self._output_scale, self._output_zero_point = self._output_details.get("quantization", (0.0, 0))

        self.desired_samples = int(self.sample_rate * self.clip_duration_ms / 1000)
        self.window_size_samples = int(self.sample_rate * self.window_size_ms / 1000)
        self.window_stride_samples = int(self.sample_rate * self.window_stride_ms / 1000)
        self.spectrogram_length = 1 + int((self.desired_samples - self.window_size_samples) / self.window_stride_samples)
        self.fft_length = 1 << (self.window_size_samples - 1).bit_length()
        self._mel_filterbank = self._build_mel_filterbank()

    @staticmethod
    def _load_labels(labels_path: Path) -> List[str]:
        labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not labels:
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
        max_frequency_hz = min(self.upper_frequency_hz, self.sample_rate / 2.0)
        mel_edges = np.linspace(
            self._hz_to_mel(self.lower_frequency_hz),
            self._hz_to_mel(max_frequency_hz),
            self.mel_filterbank_channels + 2,
            dtype=np.float32,
        )
        hz_edges = self._mel_to_hz(mel_edges)
        bin_frequencies = np.linspace(0.0, self.sample_rate / 2.0, num_spectrogram_bins, dtype=np.float32)
        filters = np.zeros((self.mel_filterbank_channels, num_spectrogram_bins), dtype=np.float32)

        for index in range(self.mel_filterbank_channels):
            left_hz = hz_edges[index]
            center_hz = hz_edges[index + 1]
            right_hz = hz_edges[index + 2]
            lower_slope = (bin_frequencies - left_hz) / max(center_hz - left_hz, 1e-6)
            upper_slope = (right_hz - bin_frequencies) / max(right_hz - center_hz, 1e-6)
            filters[index] = np.maximum(0.0, np.minimum(lower_slope, upper_slope))

        return filters

    def _detect_arecord_device(self) -> Optional[str]:
        try:
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5, check=True)
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

    def _capture_audio_clip(self) -> np.ndarray:
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
            str(self.sample_rate),
            "-d",
            "1",
            "-t",
            "wav",
            str(wav_path),
        ]
        if self._audio_device:
            command[1:1] = ["-D", self._audio_device]

        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
                raise KeywordSpotterError(f"Audio capture failed: {message}")
            return self._normalize_audio_length(self._load_audio_from_wav(wav_path))
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _load_audio_from_wav(self, wav_path: Path) -> np.ndarray:
        with wave.open(str(wav_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            raw_audio = wav_file.readframes(frame_count)

        if sample_width != 2:
            raise KeywordSpotterError(f"Unsupported sample width: {sample_width * 8} bits")
        if sample_rate != self.sample_rate:
            raise KeywordSpotterError(f"Expected {self.sample_rate} Hz audio, got {sample_rate} Hz")

        pcm = np.frombuffer(raw_audio, dtype=np.int16)
        if channels > 1:
            pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
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
        mfcc = self._dct_type_ii(log_mel, self.dct_coefficient_count)
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
            return (output_tensor.astype(np.float32) - self._output_zero_point) * self._output_scale
        raise KeywordSpotterError(f"Unsupported output dtype: {output_dtype}")

    def run_once(self) -> InferenceResult:
        audio = self._capture_audio_clip()
        features = self._compute_mfcc(audio)
        self._interpreter.set_tensor(self._input_details["index"], self._quantize_input(features))
        self._interpreter.invoke()
        output_tensor = self._interpreter.get_tensor(self._output_details["index"])[0]
        scores = self._dequantize_output(output_tensor)
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
            if confidence < self.threshold:
                return False
            now_monotonic = time.monotonic()
            if (now_monotonic - self._last_detected_monotonic) < self.cooldown_secs:
                return False
            self._last_detected_word = label
            self._last_detected_confidence = confidence
            self._last_detected_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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


BASE_DIR = Path(os.getenv("KWS_BASE_DIR", Path(__file__).resolve().parent))
CONFIG_DIR = Path(os.getenv("KWS_CONFIG_DIR", "/root"))
MODEL_DIR = Path(os.getenv("KWS_MODEL_DIR", BASE_DIR / "models"))
LISTENING_ENABLED = os.getenv("KWS_AUTOSTART", "1").strip().lower() not in ("0", "false", "no", "off")
TELEMETRY_SECS = max(1.0, float(os.getenv("KWS_TELEMETRY_SECS", "60")))
NEXT_PERIODIC_TELEMETRY = 0.0
last_error = ""
last_result: Optional[InferenceResult] = None
client: Optional[Client] = None
spotter: Optional[KeywordSpotter] = None
active_model_name = ""
active_model_package = ""
active_model_sha256 = ""


def extract_and_run_package(archive_filename: str) -> bool:
    try:
        archive_path = Path(archive_filename)
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(Path.cwd())
        elif archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(Path.cwd())
        else:
            print(f"Unsupported package format: {archive_path.name}")
            return False

        script_file_path = Path.cwd() / "install.sh"
        if not script_file_path.is_file():
            print("install.sh not found in the current directory.")
            return True

        try:
            subprocess.run(["bash", str(script_file_path)], check=True)
            print("Successfully executed install.sh")
            return True
        except subprocess.CalledProcessError as exc:
            print(f"Error executing install.sh: {exc}")
            return False
        except Exception as exc:
            print(f"An error occurred: {exc}")
            return False
    except (subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"Package extraction failed: {exc}")
        return False


def restart_process():
    print("")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def resolve_model_path(model_dir: Path) -> Path:
    requested_name = os.getenv("KWS_MODEL_FILE", "").strip()
    candidate_names = [requested_name, "model.tflite", "ds_cnn_s_quantized.tflite"]
    for candidate_name in candidate_names:
        if not candidate_name:
            continue
        candidate_path = model_dir / candidate_name
        if candidate_path.is_file():
            return candidate_path
    raise FileNotFoundError(f"No supported TensorFlow Lite model found in {model_dir}")


def resolve_labels_path(model_dir: Path) -> Path:
    labels_name = os.getenv("KWS_LABELS_FILE", "labels.txt").strip() or "labels.txt"
    labels_path = model_dir / labels_name
    if labels_path.is_file():
        return labels_path
    raise FileNotFoundError(f"Labels file not found: {labels_path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_package_info(model_dir: Path) -> dict:
    package_info_path = model_dir / "package-info.json"
    if not package_info_path.is_file():
        return {}
    try:
        return json.loads(package_info_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_telemetry() -> dict:
    state = spotter.state_snapshot()
    return {
        "sdk_version": SDK_VERSION,
        "listening": LISTENING_ENABLED,
        "kws_label": last_result.label if last_result is not None else "",
        "kws_confidence": round(last_result.confidence, 6) if last_result is not None else 0.0,
        "kws_class_id": last_result.class_id if last_result is not None else -1,
        "kws_detected": False,
        "inference_count": state["inference_count"],
        "detection_count": state["detection_count"],
        "last_detected_word": state["last_detected_word"],
        "last_detected_confidence": round(state["last_detected_confidence"], 6),
        "last_detected_at": state["last_detected_at"],
        "audio_device": state["audio_device"],
        "model_name": active_model_name,
        "model_package": active_model_package,
        "model_sha256": active_model_sha256,
        "detection_threshold": round(state["threshold"], 4),
        "telemetry_interval": round(TELEMETRY_SECS, 3),
        "last_error": last_error,
    }


def build_detection_telemetry() -> dict:
    state = spotter.state_snapshot()
    return {
        "sdk_version": SDK_VERSION,
        "listening": LISTENING_ENABLED,
        "kws_label": last_result.label if last_result is not None else "",
        "kws_confidence": round(last_result.confidence, 6) if last_result is not None else 0.0,
        "kws_class_id": last_result.class_id if last_result is not None else -1,
        "kws_detected": bool(last_result.detected) if last_result is not None and LISTENING_ENABLED else False,
        "inference_count": state["inference_count"],
        "detection_count": state["detection_count"],
        "last_detected_word": state["last_detected_word"],
        "last_detected_confidence": round(state["last_detected_confidence"], 6),
        "last_detected_at": state["last_detected_at"],
        "audio_device": state["audio_device"],
        "model_name": active_model_name,
        "model_package": active_model_package,
        "model_sha256": active_model_sha256,
        "detection_threshold": round(state["threshold"], 4),
        "telemetry_interval": round(TELEMETRY_SECS, 3),
        "last_error": last_error,
    }


def send_telemetry(reason: str = "periodic", detection_event: bool = False):
    if client is not None and client.is_connected():
        telemetry = build_detection_telemetry() if detection_event else build_telemetry()
        client.send_telemetry(telemetry)
        print(f"Sent {reason} telemetry:", telemetry)


def schedule_next_periodic(now_monotonic: Optional[float] = None):
    global NEXT_PERIODIC_TELEMETRY
    if now_monotonic is None:
        now_monotonic = time.monotonic()
    NEXT_PERIODIC_TELEMETRY = now_monotonic + TELEMETRY_SECS


def on_command(msg: C2dCommand):
    global LISTENING_ENABLED
    global last_error
    global TELEMETRY_SECS
    global NEXT_PERIODIC_TELEMETRY

    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "listen-start":
        LISTENING_ENABLED = True
        last_error = ""
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening started")
        send_telemetry(reason="command")
        return

    if msg.command_name == "listen-stop":
        LISTENING_ENABLED = False
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening stopped")
        send_telemetry(reason="command")
        return

    if msg.command_name == "set-threshold":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return
        try:
            value = float(msg.command_args[0])
            if value < 0.0 or value > 1.0:
                raise ValueError()
            spotter.set_threshold(value)
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Threshold set to {value:.3f}")
            send_telemetry(reason="command")
        except ValueError:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Threshold must be between 0.0 and 1.0")
        return

    if msg.command_name == "set-interval":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return
        try:
            value = float(msg.command_args[0])
            if value <= 0.0:
                raise ValueError()
            TELEMETRY_SECS = max(1.0, value)
            NEXT_PERIODIC_TELEMETRY = 0.0
            if msg.ack_id is not None:
                client.send_command_ack(
                    msg,
                    C2dAck.CMD_SUCCESS_WITH_ACK,
                    f"Telemetry interval set to {TELEMETRY_SECS:g} seconds",
                )
            send_telemetry(reason="command")
            schedule_next_periodic()
        except ValueError:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Interval must be a positive number of seconds")
        return

    if msg.command_name == "get-status":
        status = build_telemetry()
        message = (
            f"listening={status['listening']} label={status['kws_label']} "
            f"confidence={status['kws_confidence']} telemetry_interval={status['telemetry_interval']}"
        )
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, message)
        return

    if msg.ack_id is not None:
        client.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


def on_ota(msg: C2dOta):
    print("Starting OTA downloads for version %s" % msg.version)
    client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False

    for url in msg.urls:
        print("Downloading OTA file %s from %s" % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as exc:
            print("Encountered download error", exc)
            break

        if url.file_name.endswith(".zip") or url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_package(url.file_name)
            if extraction_success is False:
                break
        else:
            print("ERROR: Unhandled file format for file %s" % url.file_name)

    if extraction_success is True:
        print("OTA successful. Restarting the application...")
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        restart_process()
    else:
        print("Encountered a download processing error. Not restarting.")


def ensure_connected():
    if client.is_connected():
        return
    print("(re)connecting...")
    client.connect()
    if not client.is_connected():
        raise RuntimeError("Unable to connect to /IOTCONNECT")


def main():
    global client
    global spotter
    global last_error
    global last_result
    global active_model_name
    global active_model_package
    global active_model_sha256
    model_path: Optional[Path] = None

    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path=str(CONFIG_DIR / "iotcDeviceConfig.json"),
            device_cert_path=str(CONFIG_DIR / "device-cert.pem"),
            device_pkey_path=str(CONFIG_DIR / "device-pkey.pem"),
        )
    except DeviceConfigError as exc:
        print(exc)
        sys.exit(1)

    try:
        model_path = resolve_model_path(MODEL_DIR)
        active_model_name = model_path.name
        active_model_sha256 = sha256_file(model_path)
        active_model_package = read_package_info(MODEL_DIR).get("package_name", "")
        labels_path = resolve_labels_path(MODEL_DIR)
        spotter = KeywordSpotter(
            model_path=model_path,
            labels_path=labels_path,
            threshold=float(os.getenv("KWS_DETECTION_THRESHOLD", "0.80")),
            cooldown_secs=float(os.getenv("KWS_COOLDOWN_SECS", "2.0")),
            audio_device=os.getenv("KWS_ARECORD_DEVICE") or None,
        )
    except Exception as exc:
        print(f"Failed to initialize keyword spotter: {exc}")
        sys.exit(1)

    client = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb=on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect,
        ),
    )

    print("Connecting to /IOTCONNECT...")
    client.connect()
    if not client.is_connected():
        print("Unable to connect. Exiting.")
        sys.exit(2)

    print("Connected to /IOTCONNECT")
    print("Keyword spotter is %s" % ("listening" if LISTENING_ENABLED else "idle"))
    print("Audio device:", spotter.audio_device_name())
    print("Model directory:", MODEL_DIR)
    print("Model:", active_model_name)

    send_telemetry(reason="startup")
    schedule_next_periodic()

    try:
        while True:
            ensure_connected()
            if LISTENING_ENABLED:
                detection_event = False
                try:
                    result = spotter.run_once()
                    last_result = result
                    last_error = ""
                    detection_event = result.detected
                    print(
                        f"[{result.timestamp_utc}] top={result.label} "
                        f"score={result.confidence:.3f} detected={result.detected}"
                    )
                except Exception as exc:
                    last_error = str(exc)
                    print(last_error)
                    time.sleep(2)
                if detection_event:
                    send_telemetry(reason="event", detection_event=True)
                now_monotonic = time.monotonic()
                if now_monotonic >= NEXT_PERIODIC_TELEMETRY:
                    send_telemetry(reason="periodic")
                    schedule_next_periodic(now_monotonic)
                continue

            now_monotonic = time.monotonic()
            if now_monotonic >= NEXT_PERIODIC_TELEMETRY:
                send_telemetry(reason="periodic")
                schedule_next_periodic(now_monotonic)
            time.sleep(0.25)

    except KeyboardInterrupt:
        print("Exiting.")
        try:
            send_telemetry(reason="shutdown")
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
