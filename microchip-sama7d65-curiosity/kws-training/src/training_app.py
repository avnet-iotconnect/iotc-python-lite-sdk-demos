from __future__ import annotations

import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request

from iotconnect_bridge import IotConnectBridge
from iotconnect_flow import IotConnectNativeUploader, NativeUploadConfig

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None


BASE_DIR = Path(__file__).resolve().parent
HOST = os.getenv("KWS_TRAINING_HOST", "0.0.0.0")
PORT = int(os.getenv("KWS_TRAINING_PORT", "8090"))
DEBUG = os.getenv("KWS_TRAINING_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
DATASET_ROOT = Path(os.getenv("KWS_TRAINING_DATASET_ROOT", BASE_DIR / "datasets"))
EXPORT_ROOT = Path(os.getenv("KWS_TRAINING_EXPORT_ROOT", BASE_DIR / "exports"))
RETIRED_LABELS_ROOT = Path(os.getenv("KWS_TRAINING_RETIRED_ROOT", BASE_DIR / "retired-labels"))
SAMPLE_RATE = int(os.getenv("KWS_TRAINING_SAMPLE_RATE", "16000"))
CHANNELS = int(os.getenv("KWS_TRAINING_CHANNELS", "1"))
CLIP_SECONDS = max(1, int(os.getenv("KWS_TRAINING_CLIP_SECONDS", "1")))
ARECORD_DEVICE = os.getenv("KWS_ARECORD_DEVICE", "").strip()
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
S3_DATA_BUCKET = os.getenv("KWS_TRAINING_DATA_BUCKET", "").strip()
S3_DATA_PREFIX = os.getenv("KWS_TRAINING_DATA_PREFIX", "kws-training/datasets").strip("/")
SAGEMAKER_OUTPUT_BUCKET = os.getenv("KWS_TRAINING_OUTPUT_BUCKET", "").strip()
SAGEMAKER_OUTPUT_PREFIX = os.getenv("KWS_TRAINING_OUTPUT_PREFIX", "kws-training/output").strip("/")
SAGEMAKER_WEIGHTS_PREFIX = os.getenv("KWS_SAGEMAKER_WEIGHTS_PREFIX", "kws-training/weights").strip("/")
SAGEMAKER_ROLE_ARN = os.getenv("KWS_SAGEMAKER_ROLE_ARN", "").strip()
SAGEMAKER_IMAGE_URI = os.getenv("KWS_SAGEMAKER_IMAGE_URI", "").strip()
SAGEMAKER_INSTANCE_TYPE = os.getenv("KWS_SAGEMAKER_INSTANCE_TYPE", "ml.m5.xlarge").strip()
SAGEMAKER_INSTANCE_COUNT = max(1, int(os.getenv("KWS_SAGEMAKER_INSTANCE_COUNT", "1")))
SAGEMAKER_MAX_RUNTIME_SECS = max(3600, int(os.getenv("KWS_SAGEMAKER_MAX_RUNTIME_SECS", "14400")))
SAGEMAKER_TRAIN_EPOCHS = max(1, int(os.getenv("KWS_SAGEMAKER_TRAIN_EPOCHS", "30")))
SAGEMAKER_TRAIN_BATCH_SIZE = max(1, int(os.getenv("KWS_SAGEMAKER_TRAIN_BATCH_SIZE", "32")))
SAGEMAKER_TRAIN_LEARNING_RATE = float(os.getenv("KWS_SAGEMAKER_TRAIN_LEARNING_RATE", "0.0007"))
DEFAULT_TRAINING_LABELS = [item.strip() for item in os.getenv("KWS_TRAINING_DEFAULT_LABELS", "deal,double,hit,reset,stand").split(",") if item.strip()]
TRAIN_PRETRAIN_ENABLED = os.getenv("KWS_TRAIN_PRETRAIN_ENABLED", "1").strip()
TRAIN_PRETRAIN_REQUIRED = os.getenv("KWS_TRAIN_PRETRAIN_REQUIRED", "0").strip()
TRAIN_PRETRAIN_SOURCE = os.getenv(
    "KWS_TRAIN_PRETRAIN_SOURCE",
    "http://download.tensorflow.org/data/speech_commands_v0.02.tar.gz",
).strip()
TRAIN_PRETRAIN_EPOCHS = os.getenv("KWS_TRAIN_PRETRAIN_EPOCHS", "6").strip()
TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL = os.getenv("KWS_TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL", "1800").strip()
TRAIN_PRETRAIN_VALIDATION_SPLIT = os.getenv("KWS_TRAIN_PRETRAIN_VALIDATION_SPLIT", "0.1").strip()
TRAIN_PRETRAIN_LEARNING_RATE = os.getenv("KWS_TRAIN_PRETRAIN_LEARNING_RATE", "0.001").strip()
TRAIN_PRETRAIN_WORDS = os.getenv(
    "KWS_TRAIN_PRETRAIN_WORDS",
    "yes,no,up,down,left,right,on,off,stop,go",
).strip()
TRAIN_MUSAN_SOURCE = os.getenv("KWS_TRAIN_MUSAN_SOURCE", "").strip()
TRAIN_MUSAN_MAX_CLIPS = os.getenv("KWS_TRAIN_MUSAN_MAX_CLIPS", "128").strip()
UPLOAD_MODE = os.getenv("KWS_TRAINING_UPLOAD_MODE", "auto").strip().lower() or "auto"
IOTC_TELEMETRY_SECS = max(5.0, float(os.getenv("KWS_IOTC_TELEMETRY_SECS", "60")))
IOTC_CONFIG_JSON = Path(os.getenv("KWS_IOTC_CONFIG_JSON", "/root/iotcDeviceConfig.json"))
IOTC_DEVICE_CERT = Path(os.getenv("KWS_IOTC_DEVICE_CERT", "/root/device-cert.pem"))
IOTC_DEVICE_KEY = Path(os.getenv("KWS_IOTC_DEVICE_KEY", "/root/device-pkey.pem"))
IOTC_CA_CERT = os.getenv("KWS_IOTC_CA_CERT", "").strip()
IOTC_DISCOVERY_URL = os.getenv("KWS_IOTC_DISCOVERY_URL", "").strip()
IOTC_BUCKET_NAME = os.getenv("KWS_IOTC_BUCKET_NAME", "").strip()
IOTC_FS_URL = os.getenv("KWS_IOTC_FS_URL", "").strip()
IOTC_FS_BUCKETS_JSON = os.getenv("KWS_IOTC_FS_BUCKETS_JSON", "").strip()
IOTC_FILE_TOPIC = os.getenv("KWS_IOTC_FILE_TOPIC", "").strip()
IOTC_MQTT_HOST = os.getenv("KWS_IOTC_MQTT_HOST", "").strip()
IOTC_MQTT_PORT = int((os.getenv("KWS_IOTC_MQTT_PORT", "") or "0").strip())
IOTC_MQTT_USERNAME = os.getenv("KWS_IOTC_MQTT_USERNAME", "").strip()
IOTC_MQTT_CLIENT_ID = os.getenv("KWS_IOTC_MQTT_CLIENT_ID", "").strip()
IOTC_DEVICE_ID = os.getenv("KWS_IOTC_DEVICE_ID", "").strip()
PIPELINE_MODE = os.getenv("KWS_TRAINING_PIPELINE_MODE", "auto").strip().lower() or "auto"
PIPELINE_STATE_MACHINE_ARN = os.getenv("KWS_TRAINING_STATE_MACHINE_ARN", "").strip()
PIPELINE_DISCOVERY_PREFIX = os.getenv("KWS_TRAINING_STATE_MACHINE_PREFIX", "conv-").strip()
PIPELINE_PROJECT_NAME = os.getenv("KWS_TRAINING_PROJECT_NAME", "kws-training").strip()
PIPELINE_IMAGE_URI = os.getenv("KWS_TRAINING_PIPELINE_IMAGE_URI", "").strip()
PIPELINE_INSTANCE_TYPE = os.getenv("KWS_TRAINING_PIPELINE_INSTANCE_TYPE", "ml.m5.xlarge").strip()
PIPELINE_VOLUME_GB = max(1, int(os.getenv("KWS_TRAINING_PIPELINE_VOLUME_GB", "30")))
PIPELINE_OUTPUT_PREFIX = os.getenv("KWS_TRAINING_PIPELINE_OUTPUT_PREFIX", "kws-training/converted").strip("/")
PIPELINE_WEIGHTS_S3_URI = os.getenv("KWS_TRAINING_WEIGHTS_S3_URI", "").strip()
PIPELINE_WEIGHTS_NAME = os.getenv("KWS_TRAINING_WEIGHTS_NAME", "").strip()
PIPELINE_OUTPUT_S3_URI = os.getenv("KWS_TRAINING_PIPELINE_OUTPUT_S3_URI", "").strip()
AUTO_CONVERT_AFTER_TRAIN = os.getenv("KWS_TRAINING_AUTO_CONVERT_AFTER_TRAIN", "1").strip().lower() in {"1", "true", "yes"}
TRAINING_POLL_SECS = max(10, int(os.getenv("KWS_TRAINING_POLL_SECS", "15")))
DEPLOY_ROOT = Path(os.getenv("KWS_TRAINING_DEPLOY_ROOT", "/opt/demo"))
DEPLOY_MODELS_DIR = Path(os.getenv("KWS_TRAINING_DEPLOY_MODELS_DIR", DEPLOY_ROOT / "models"))
MODEL_LIST_LIMIT = max(1, int(os.getenv("KWS_TRAINING_MODEL_LIST_LIMIT", "24")))
MODEL_INSTALL_TIMEOUT_SECS = max(30, int(os.getenv("KWS_TRAINING_MODEL_INSTALL_TIMEOUT_SECS", "900")))
COMMAND_COLLECTION_TARGET = max(1, int(os.getenv("KWS_TRAINING_COMMAND_TARGET", "50")))
COMMAND_COLLECTION_MINIMUM = min(
    COMMAND_COLLECTION_TARGET,
    max(1, int(os.getenv("KWS_TRAINING_COMMAND_MINIMUM", "20"))),
)
UNKNOWN_COLLECTION_TARGET = max(1, int(os.getenv("KWS_TRAINING_UNKNOWN_TARGET", "40")))
NOISE_COLLECTION_TARGET = max(1, int(os.getenv("KWS_TRAINING_NOISE_TARGET", "30")))
COLLECTION_PRIORITY_LIMIT = max(1, int(os.getenv("KWS_TRAINING_COLLECTION_PRIORITY_LIMIT", "6")))

ACTIVE_WORKFLOW_STATES = {
    "direct-sagemaker-running",
    "auto-conversion-running",
    "iotconnect-conversion-running",
}
SUPPORTED_MODEL_ARCHIVES = (".zip", ".tar.gz")
SPECIAL_CAPTURE_GUIDANCE = {
    "_unknown_": {
        "title": "Unknown Spoken Words",
        "target": UNKNOWN_COLLECTION_TARGET,
        "purpose": "Teach the model to reject speech that is not one of the command words.",
        "recording_tip": "Say short words and phrases that are not valid commands. Mix speakers, pace, and distance.",
        "examples": ["hello", "thank you", "cancel that", "what time is it"],
    },
    "_background_noise_": {
        "title": "Background Noise",
        "target": NOISE_COLLECTION_TARGET,
        "purpose": "Teach the model what the room, fan, HVAC, and board environment sound like when nobody is speaking.",
        "recording_tip": "Stay quiet while recording. Capture room tone, keyboard noise, fan noise, and chair movement.",
        "examples": ["silent room", "HVAC hum", "keyboard clicks", "chair movement"],
    },
}
PROTECTED_LABELS = {"_unknown_", "_background_noise_"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_processing_input_uri(s3_uri: str, weights_name: str) -> tuple[str, str]:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {s3_uri}")

    bucket = parsed.netloc
    object_path = parsed.path.lstrip("/")
    explicit_name = weights_name.strip()
    if explicit_name:
        return s3_uri.rstrip("/"), explicit_name

    if object_path.endswith("/"):
        return s3_uri.rstrip("/"), "model-state.pt"

    prefix, file_name = object_path.rsplit("/", 1)
    return f"s3://{bucket}/{prefix}", file_name


def discover_state_machine_arn(session, name_prefix: str) -> str:
    client = session.client("stepfunctions")
    paginator = client.get_paginator("list_state_machines")
    for page in paginator.paginate():
        for item in page.get("stateMachines", []):
            name = str(item.get("name", "")).strip()
            arn = str(item.get("stateMachineArn", "")).strip()
            if name_prefix and not name.startswith(name_prefix):
                continue
            if arn:
                return arn
    raise RuntimeError(f"No Step Functions state machine found with prefix {name_prefix!r}.")


def sanitize_label(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9_-]", "", normalized)
    normalized = normalized.strip("._-")
    if value.strip() in {"_background_noise_", "_unknown_"}:
        return value.strip()
    if not normalized:
        raise ValueError("Voice command must contain letters or numbers.")
    return normalized


def detect_arecord_device() -> str:
    if ARECORD_DEVICE:
        return ARECORD_DEVICE
    if shutil.which("arecord") is None:
        return "unavailable"
    try:
        result = subprocess.run(["arecord", "-l"], check=True, capture_output=True, text=True, timeout=5)
    except Exception:
        return "default"
    match = re.search(r"card\s+(\d+):.*?device\s+(\d+):", result.stdout, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return "default"
    return f"plughw:{match.group(1)},{match.group(2)}"


def create_boto3_session():
    if boto3 is None:
        raise RuntimeError("boto3 is not installed. Install boto3 to use S3 or SageMaker.")
    profile_name = os.getenv("AWS_PROFILE", "").strip() or None
    return boto3.session.Session(profile_name=profile_name, region_name=AWS_REGION)


def standard_aws_credentials_available() -> bool:
    if boto3 is None:
        return False
    try:
        session = create_boto3_session()
        credentials = session.get_credentials()
        if credentials is None:
            return False
        frozen = credentials.get_frozen_credentials()
        return bool(frozen.access_key and frozen.secret_key)
    except Exception:
        return False


def create_native_uploader() -> IotConnectNativeUploader:
    return IotConnectNativeUploader(
        NativeUploadConfig(
            config_path=IOTC_CONFIG_JSON,
            device_cert_path=IOTC_DEVICE_CERT,
            device_key_path=IOTC_DEVICE_KEY,
            ca_cert_path=Path(IOTC_CA_CERT) if IOTC_CA_CERT else None,
            discovery_url=IOTC_DISCOVERY_URL,
            preferred_bucket_name=IOTC_BUCKET_NAME,
            default_region=AWS_REGION,
            fs_url_override=IOTC_FS_URL,
            fs_buckets_override_json=IOTC_FS_BUCKETS_JSON,
            mqtt_host_override=IOTC_MQTT_HOST,
            mqtt_port_override=IOTC_MQTT_PORT,
            mqtt_username_override=IOTC_MQTT_USERNAME,
            mqtt_client_id_override=IOTC_MQTT_CLIENT_ID,
            file_topic_override=IOTC_FILE_TOPIC,
            device_id_override=IOTC_DEVICE_ID,
            debug=DEBUG,
        )
    )


@dataclass
class LabelSummary:
    label: str
    clip_count: int
    latest_capture: str


class TrainingWorkspace:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = deque(maxlen=24)
        self._recording_process: Optional[subprocess.Popen] = None
        self._recording_label = ""
        self._recording_path: Optional[Path] = None
        self._recording_started_at = ""
        self._recording_started_monotonic = 0.0
        self._upload_mode = UPLOAD_MODE
        self._clip_seconds = CLIP_SECONDS
        self._pipeline_mode = PIPELINE_MODE
        self._last_capture_at = ""
        self._last_archive_name = ""
        self._last_archive_s3_uri = ""
        self._last_manifest_s3_uri = ""
        self._last_training_job = ""
        self._last_training_output = ""
        self._last_conversion_job = ""
        self._last_conversion_output = ""
        self._last_installed_model_name = ""
        self._last_installed_model_s3_uri = ""
        self._last_install_at = ""
        self._last_error = ""
        self._hydrate_install_source_marker()
        self._training_status = ""
        self._iotconnect_connected = False
        self._workflow_thread: Optional[threading.Thread] = None
        DATASET_ROOT.mkdir(parents=True, exist_ok=True)
        EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
        RETIRED_LABELS_ROOT.mkdir(parents=True, exist_ok=True)
        self.audio_device = detect_arecord_device()
        self.native_uploader = create_native_uploader()
        self._event("READY", f"Dataset root: {DATASET_ROOT}")
        self._event("UPLOAD", self.native_uploader.status_text())

    def _event(self, title: str, detail: str):
        with self._lock:
            self._events.appendleft({"title": title, "detail": detail, "at": time.strftime("%H:%M:%S")})

    def note_event(self, title: str, detail: str):
        self._event(title, detail)

    def note_error(self, message: str):
        with self._lock:
            self._last_error = message
        self._event("ERROR", message)

    def clear_error(self):
        with self._lock:
            self._last_error = ""

    def set_upload_mode(self, mode: str):
        normalized = str(mode).strip().lower()
        if normalized not in {"auto", "iotconnect", "direct"}:
            raise ValueError("Upload mode must be auto, iotconnect, or direct.")
        with self._lock:
            self._upload_mode = normalized
        self._event("CONFIG", f"Upload mode set to {normalized}")

    def set_audio_device(self, device: str):
        normalized = str(device).strip()
        if not normalized:
            raise ValueError("Audio device cannot be blank.")
        with self._lock:
            self.audio_device = normalized
        self._event("CONFIG", f"Audio device set to {normalized}")

    def set_clip_seconds(self, seconds: int):
        normalized = max(1, int(seconds))
        with self._lock:
            self._clip_seconds = normalized
        self._event("CONFIG", f"Clip seconds set to {normalized}")

    def set_iotconnect_connected(self, connected: bool):
        with self._lock:
            self._iotconnect_connected = bool(connected)

    def event_history(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def native_upload_snapshot(self) -> dict:
        return self.native_uploader.snapshot()

    def upload_summary(self) -> dict:
        native = self.native_upload_snapshot()
        direct_ready = bool(S3_DATA_BUCKET)

        if self._upload_mode == "iotconnect":
            mode = "iotconnect-native"
            ready = native["ready"]
            status = native["status"]
        elif self._upload_mode == "direct":
            mode = "direct-aws"
            ready = direct_ready
            status = "Direct S3 upload is ready." if direct_ready else "Direct S3 upload is not configured."
        elif native["ready"]:
            mode = "iotconnect-native"
            ready = True
            status = native["status"]
        elif direct_ready:
            mode = "direct-aws"
            ready = True
            status = f"Falling back to direct S3 because /IOTCONNECT native upload is unavailable. {native['status']}"
        else:
            mode = "unconfigured"
            ready = False
            status = f"No upload path is ready. {native['status']}"

        return {
            "mode": mode,
            "ready": ready,
            "status": status,
            "direct_ready": direct_ready,
            "bucket": native["selected_bucket"] if mode == "iotconnect-native" else S3_DATA_BUCKET,
        }

    def deployment_summary(self) -> dict:
        credentials_ready = standard_aws_credentials_available() or self.native_uploader.boto3_ready()
        ready = bool(SAGEMAKER_OUTPUT_BUCKET and credentials_ready)
        if ready:
            status = "Converted model packages are ready to browse and install."
        elif not SAGEMAKER_OUTPUT_BUCKET:
            status = "Converted model bucket is not configured. Set KWS_TRAINING_OUTPUT_BUCKET."
        else:
            status = (
                "AWS credentials are unavailable for model browsing. "
                "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or /root/.aws/credentials."
            )
        installed = self.installed_model_summary()
        return {
            "ready": ready,
            "status": status,
            "bucket": SAGEMAKER_OUTPUT_BUCKET,
            "prefix": PIPELINE_OUTPUT_PREFIX,
            "target_root": str(DEPLOY_ROOT),
            "target_models_dir": str(DEPLOY_MODELS_DIR),
            "installed": installed,
        }

    def list_labels(self) -> list[LabelSummary]:
        labels: list[LabelSummary] = []
        for directory in sorted(DATASET_ROOT.iterdir()) if DATASET_ROOT.exists() else []:
            if not directory.is_dir():
                continue
            wav_files = sorted(directory.glob("*.wav"))
            latest = max((path.stat().st_mtime for path in wav_files), default=0)
            labels.append(
                LabelSummary(
                    label=directory.name,
                    clip_count=len(wav_files),
                    latest_capture="" if latest == 0 else datetime.fromtimestamp(latest).isoformat(timespec="seconds"),
                )
            )
        return labels

    def collection_plan(self, summaries: Optional[list[LabelSummary]] = None) -> dict:
        summaries = summaries if summaries is not None else self.list_labels()
        counts = {summary.label: summary.clip_count for summary in summaries}
        command_summaries = [
            summary
            for summary in summaries
            if summary.label not in SPECIAL_CAPTURE_GUIDANCE and summary.label != "_silence_"
        ]
        command_summaries.sort(key=lambda item: (item.clip_count, item.label))

        command_rows: list[dict] = []
        for summary in command_summaries:
            remaining = max(0, COMMAND_COLLECTION_TARGET - summary.clip_count)
            if summary.clip_count < COMMAND_COLLECTION_MINIMUM:
                status = "below-minimum"
                guidance = (
                    "Below the minimum command floor. Add this word before you trust the next retrain."
                )
            elif remaining > 0:
                status = "below-target"
                guidance = "Usable, but still below the recommended command target."
            else:
                status = "ready"
                guidance = "Healthy command folder. Keep it only if you want more speaker variety."
            command_rows.append(
                {
                    "label": summary.label,
                    "kind": "command",
                    "title": summary.label.replace("_", " "),
                    "clip_count": summary.clip_count,
                    "target": COMMAND_COLLECTION_TARGET,
                    "minimum": COMMAND_COLLECTION_MINIMUM,
                    "remaining": remaining,
                    "status": status,
                    "existing": True,
                    "latest_capture": summary.latest_capture,
                    "recording_tip": "Say the real command once per clip with different tone, speed, and mic distance.",
                    "guidance": guidance,
                }
            )

        special_rows: list[dict] = []
        for label, meta in SPECIAL_CAPTURE_GUIDANCE.items():
            clip_count = counts.get(label, 0)
            remaining = max(0, int(meta["target"]) - clip_count)
            if clip_count == 0:
                status = "missing"
            elif remaining > 0:
                status = "growing"
            else:
                status = "ready"
            special_rows.append(
                {
                    "label": label,
                    "kind": "special",
                    "title": str(meta["title"]),
                    "clip_count": clip_count,
                    "target": int(meta["target"]),
                    "remaining": remaining,
                    "status": status,
                    "existing": label in counts,
                    "purpose": str(meta["purpose"]),
                    "recording_tip": str(meta["recording_tip"]),
                    "guidance": str(meta["purpose"]),
                    "examples": list(meta["examples"]),
                }
            )

        commands_below_minimum = [row for row in command_rows if row["clip_count"] < COMMAND_COLLECTION_MINIMUM]
        commands_below_target = [row for row in command_rows if row["remaining"] > 0]
        special_needed = [row for row in special_rows if row["remaining"] > 0]

        priority_rows: list[dict] = []

        def add_priority(row: dict, reason: str):
            if any(existing["label"] == row["label"] for existing in priority_rows):
                return
            prioritized = dict(row)
            prioritized["priority_reason"] = reason
            priority_rows.append(prioritized)

        for row in commands_below_minimum[:3]:
            add_priority(row, "Weakest command folder. Raise this one toward the minimum floor first.")
        for row in special_needed:
            if row["label"] == "_unknown_":
                add_priority(row, "Missing or thin negative speech data. This reduces false positives on unrelated words.")
            elif row["label"] == "_background_noise_":
                add_priority(row, "Missing or thin ambient data. This reduces detections when nobody is speaking.")
        for row in commands_below_target:
            add_priority(row, "Still below the recommended command target. Add more speaker variety here.")

        priority_rows = priority_rows[:COLLECTION_PRIORITY_LIMIT]

        command_clip_total = sum(row["clip_count"] for row in command_rows)
        special_clip_total = sum(row["clip_count"] for row in special_rows)
        if not command_rows:
            readiness = "commands-first"
            summary = (
                "Create your real command folders first. After that, add `_unknown_` and `_background_noise_` "
                "before trusting a retrain."
            )
        elif commands_below_minimum:
            readiness = "needs-commands"
            summary = (
                f"{len(commands_below_minimum)} command folder(s) are still below the minimum floor of "
                f"{COMMAND_COLLECTION_MINIMUM} clips. Fix those first, then add more negative data."
            )
        elif special_needed:
            readiness = "needs-negatives"
            summary = (
                "Your command folders are usable, but the model still needs `_unknown_` and `_background_noise_` "
                "coverage to reject silence and unrelated speech cleanly."
            )
        elif commands_below_target:
            readiness = "needs-balance"
            summary = (
                "Negative data is present. Top off the weaker command folders so the dataset stays balanced across words."
            )
        else:
            readiness = "ready"
            summary = (
                "The dataset looks balanced for another retraining pass. Extra clips now should focus on new speakers "
                "and harder acoustic conditions."
            )

        return {
            "readiness": readiness,
            "summary": summary,
            "targets": {
                "command_target": COMMAND_COLLECTION_TARGET,
                "command_minimum": COMMAND_COLLECTION_MINIMUM,
                "unknown_target": UNKNOWN_COLLECTION_TARGET,
                "background_noise_target": NOISE_COLLECTION_TARGET,
            },
            "stats": {
                "command_labels": len(command_rows),
                "command_clips": command_clip_total,
                "commands_below_minimum": len(commands_below_minimum),
                "commands_below_target": len(commands_below_target),
                "negative_clips": special_clip_total,
                "unknown_clips": counts.get("_unknown_", 0),
                "background_noise_clips": counts.get("_background_noise_", 0),
            },
            "priorities": priority_rows,
            "commands": command_rows,
            "special_labels": special_rows,
        }

    def installed_model_summary(self) -> dict:
        package_info_path = DEPLOY_MODELS_DIR / "package-info.json"
        labels_path = DEPLOY_MODELS_DIR / "labels.txt"
        model_path = DEPLOY_MODELS_DIR / "model.tflite"
        package_info: dict = {}
        if package_info_path.is_file():
            try:
                package_info = json.loads(package_info_path.read_text(encoding="utf-8"))
            except Exception:
                package_info = {}

        labels: list[str] = []
        if labels_path.is_file():
            try:
                labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except Exception:
                labels = []

        latest_mtime = max(
            [
                path.stat().st_mtime
                for path in (package_info_path, labels_path, model_path)
                if path.is_file()
            ],
            default=0.0,
        )
        return {
            "package_name": str(package_info.get("package_name", "")).strip(),
            "display_name": str(package_info.get("display_name", "")).strip(),
            "model_name": model_path.name if model_path.is_file() else "",
            "model_sha256": self._sha256_file(model_path) if model_path.is_file() else "",
            "labels": labels,
            "installed_at": "" if latest_mtime == 0 else datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def _create_model_session(self):
        if not SAGEMAKER_OUTPUT_BUCKET:
            raise RuntimeError("Set KWS_TRAINING_OUTPUT_BUCKET before browsing converted models.")
        if standard_aws_credentials_available():
            return create_boto3_session()
        if self.native_uploader.boto3_ready():
            return self.native_uploader.create_boto3_session()
        raise RuntimeError(
            "No AWS credentials are available for converted model browsing. "
            "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or keep /IOTCONNECT pipeline credentials available."
        )

    def _sha256_file(self, path: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def list_model_packages(self, limit: int = MODEL_LIST_LIMIT) -> list[dict]:
        session = self._create_model_session()
        s3 = session.client("s3")
        prefix = PIPELINE_OUTPUT_PREFIX.rstrip("/") + "/"
        paginator = s3.get_paginator("list_objects_v2")
        packages: list[dict] = []
        for page in paginator.paginate(Bucket=SAGEMAKER_OUTPUT_BUCKET, Prefix=prefix):
            for item in page.get("Contents", []):
                key = str(item.get("Key", "")).strip()
                if not key or not key.endswith(SUPPORTED_MODEL_ARCHIVES):
                    continue
                parts = key.split("/")
                execution_name = parts[-2] if len(parts) >= 2 else ""
                last_modified = item.get("LastModified")
                packages.append(
                    {
                        "package_name": Path(key).name,
                        "execution_name": execution_name,
                        "bucket": SAGEMAKER_OUTPUT_BUCKET,
                        "object_key": key,
                        "s3_uri": f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{key}",
                        "size_bytes": int(item.get("Size", 0)),
                        "last_modified": ""
                        if last_modified is None
                        else last_modified.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    }
                )
        packages.sort(key=lambda item: (item["last_modified"], item["package_name"]), reverse=True)
        return packages[:limit]

    def _resolve_model_package(self, requested_s3_uri: str) -> dict:
        packages = self.list_model_packages(limit=max(MODEL_LIST_LIMIT, 100))
        if not packages:
            raise RuntimeError("No converted model packages were found in S3 yet.")
        if not requested_s3_uri:
            return packages[0]
        for package in packages:
            if package["s3_uri"] == requested_s3_uri:
                return package
        raise RuntimeError(f"Converted model package not found: {requested_s3_uri}")

    def _validate_extract_target(self, destination: Path, member_name: str):
        normalized = member_name.replace("\\", "/").lstrip("/")
        target = (destination / normalized).resolve()
        try:
            target.relative_to(destination.resolve())
        except ValueError as exc:
            raise RuntimeError(f"Package contains an invalid path: {member_name}") from exc

    def _extract_model_package(self, archive_path: Path, destination: Path):
        destination.mkdir(parents=True, exist_ok=True)
        if archive_path.name.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as archive:
                for member in archive.namelist():
                    self._validate_extract_target(destination, member)
                archive.extractall(destination)
            return
        if archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                for member in archive.getmembers():
                    self._validate_extract_target(destination, member.name)
                archive.extractall(destination)
            return
        raise RuntimeError(f"Unsupported package format: {archive_path.name}")

    def _install_source_marker_path(self) -> Path:
        return DEPLOY_MODELS_DIR / ".install-source.json"

    def _write_install_source_marker(self, *, package_name: str, s3_uri: str, installed_at: str) -> None:
        marker = self._install_source_marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "package_name": package_name,
            "s3_uri": s3_uri,
            "installed_at": installed_at,
        }
        marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _hydrate_install_source_marker(self) -> None:
        marker = self._install_source_marker_path()
        if not marker.is_file():
            return
        model_path = DEPLOY_MODELS_DIR / "model.tflite"
        if not model_path.is_file():
            try:
                marker.unlink()
            except OSError:
                pass
            return
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        s3_uri = str(payload.get("s3_uri", "")).strip()
        package_name = str(payload.get("package_name", "")).strip()
        installed_at = str(payload.get("installed_at", "")).strip()
        if not s3_uri:
            return
        with self._lock:
            self._last_installed_model_s3_uri = s3_uri
            if package_name:
                self._last_installed_model_name = package_name
            if installed_at:
                self._last_install_at = installed_at

    def install_model_package(self, requested_s3_uri: str = "") -> dict:
        package = self._resolve_model_package(requested_s3_uri.strip())
        session = self._create_model_session()
        s3 = session.client("s3")
        self._event("DEPLOY", f"Downloading {package['package_name']} from S3")
        with tempfile.TemporaryDirectory(prefix="kws-model-install-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            archive_path = temp_dir / package["package_name"]
            extract_dir = temp_dir / "package"
            s3.download_file(package["bucket"], package["object_key"], str(archive_path))
            self._extract_model_package(archive_path, extract_dir)
            install_script = extract_dir / "install.sh"
            if not install_script.is_file():
                raise RuntimeError("Converted package did not contain install.sh.")
            try:
                result = subprocess.run(
                    ["bash", str(install_script)],
                    cwd=str(extract_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=MODEL_INSTALL_TIMEOUT_SECS,
                )
            except subprocess.CalledProcessError as exc:
                output = "\n".join(part for part in [exc.stdout.strip(), exc.stderr.strip()] if part).strip()
                raise RuntimeError(output or f"install.sh failed with exit code {exc.returncode}") from exc

        installed = self.installed_model_summary()
        installed_at = utc_now()
        installed_name = installed["package_name"] or package["package_name"]
        with self._lock:
            self._last_installed_model_name = installed_name
            self._last_installed_model_s3_uri = package["s3_uri"]
            self._last_install_at = installed_at
            self._last_error = ""
        try:
            self._write_install_source_marker(
                package_name=installed_name,
                s3_uri=package["s3_uri"],
                installed_at=installed_at,
            )
        except OSError as exc:
            self._event("DEPLOY", f"Warning: could not persist install source marker ({exc})")
        self._event("DEPLOY", f"Installed model package {package['package_name']} onto {DEPLOY_MODELS_DIR}")
        return {
            "selected_package": package,
            "installed": installed,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    def ensure_label_dir(self, raw_label: str) -> Path:
        label = sanitize_label(raw_label)
        label_dir = DATASET_ROOT / label
        label_dir.mkdir(parents=True, exist_ok=True)
        return label_dir

    def retire_label(self, raw_label: str) -> dict:
        label = sanitize_label(raw_label)
        if label in PROTECTED_LABELS:
            raise RuntimeError(f"{label} is protected. Keep it for negative-data training.")
        label_dir = DATASET_ROOT / label
        if not label_dir.is_dir():
            raise RuntimeError(f"Label folder does not exist: {label}")

        with self._lock:
            if self._recording_process is not None and self._recording_process.poll() is None:
                raise RuntimeError("Stop the current recording before retiring a label.")
            if self._workflow_in_progress_locked():
                raise RuntimeError("Wait for the current training or conversion workflow to finish before retiring a label.")

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        retirement_dir = RETIRED_LABELS_ROOT / timestamp
        retirement_dir.mkdir(parents=True, exist_ok=True)
        destination = retirement_dir / label_dir.name
        if destination.exists():
            destination = retirement_dir / f"{label_dir.name}-{int(time.time())}"
        shutil.move(str(label_dir), str(destination))
        self._event("DATASET", f"Retired label {label} to {destination}")
        return {
            "label": label,
            "retired_to": str(destination),
        }

    def _clear_recording_locked(self):
        self._recording_process = None
        self._recording_label = ""
        self._recording_path = None
        self._recording_started_at = ""
        self._recording_started_monotonic = 0.0

    def _recording_snapshot_locked(self) -> dict:
        active = self._recording_process is not None and self._recording_process.poll() is None
        if not active and self._recording_process is not None:
            self._clear_recording_locked()
        elapsed = 0.0
        if active:
            elapsed = round(max(0.0, time.monotonic() - self._recording_started_monotonic), 1)
        return {
            "active": active,
            "label": self._recording_label,
            "started_at": self._recording_started_at,
            "output_file": self._recording_path.name if self._recording_path is not None else "",
            "elapsed_seconds": elapsed,
            "recommended_seconds": self._clip_seconds,
        }

    def start_capture(self, raw_label: str) -> dict:
        if shutil.which("arecord") is None:
            raise RuntimeError("arecord is not installed. Install alsa-utils on the board.")

        with self._lock:
            if self._recording_process is not None and self._recording_process.poll() is None:
                raise RuntimeError("A clip is already being recorded. Stop it before starting the next one.")

        label_dir = self.ensure_label_dir(raw_label)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        output_path = label_dir / f"{timestamp}.wav"
        command = [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-c",
            str(CHANNELS),
            "-r",
            str(SAMPLE_RATE),
            "-t",
            "wav",
            str(output_path),
        ]
        if self.audio_device not in {"default", "unavailable"}:
            command[1:1] = ["-D", self.audio_device]

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)
            if process.poll() is not None:
                _stdout, stderr = process.communicate(timeout=1)
                output_path.unlink(missing_ok=True)
                message = stderr.strip() or f"exit code {process.returncode}"
                if "Device or resource busy" in message:
                    raise RuntimeError(
                        f"Microphone is busy on {self.audio_device}. Stop kws-demo, kws-game, or any other arecord user first, then try Start Recording again."
                    )
                raise RuntimeError(f"Audio capture failed to start: {message}")
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"Unable to start audio capture: {exc}") from exc

        started_at = utc_now()
        with self._lock:
            self._recording_process = process
            self._recording_label = label_dir.name
            self._recording_path = output_path
            self._recording_started_at = started_at
            self._recording_started_monotonic = time.monotonic()

        self._event("RECORD", f"Started clip for {label_dir.name}")
        return {"label": label_dir.name, "file_name": output_path.name, "started_at": started_at}

    def stop_capture(self) -> dict:
        with self._lock:
            process = self._recording_process
            label = self._recording_label
            output_path = self._recording_path
            started_at = self._recording_started_at
            started_monotonic = self._recording_started_monotonic

        if process is None or output_path is None or not label:
            raise RuntimeError("No recording is currently in progress.")

        if process.poll() is None:
            try:
                process.send_signal(signal.SIGINT)
            except Exception:
                process.terminate()

        try:
            _stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            _stdout, stderr = process.communicate(timeout=5)

        with self._lock:
            self._clear_recording_locked()

        file_size = output_path.stat().st_size if output_path.exists() else 0
        if file_size <= 44:
            output_path.unlink(missing_ok=True)
            message = (stderr or "").strip() or "The captured clip was empty."
            raise RuntimeError(f"Audio capture failed: {message}")

        duration = round(max(0.0, time.monotonic() - started_monotonic), 2)
        with self._lock:
            self._last_capture_at = utc_now()
        self._event("CAPTURE", f"Saved {output_path.name} for {label} ({duration:.2f}s)")
        return {
            "label": label,
            "file_name": output_path.name,
            "file_path": str(output_path),
            "started_at": started_at,
            "duration_seconds": duration,
            "file_size": file_size,
        }

    def build_dataset_manifest(self, labels: Optional[Iterable[str]] = None) -> dict:
        with self._lock:
            if self._recording_process is not None and self._recording_process.poll() is None:
                raise RuntimeError("Stop the current recording before packaging or uploading the dataset.")
        if labels:
            selected = {sanitize_label(label) for label in labels}
        elif DEFAULT_TRAINING_LABELS:
            selected = {sanitize_label(label) for label in DEFAULT_TRAINING_LABELS}
            selected.update(label for label in PROTECTED_LABELS if (DATASET_ROOT / label).is_dir())
        else:
            selected = None
        label_rows = []
        for summary in self.list_labels():
            if selected is not None and summary.label not in selected:
                continue
            label_rows.append(
                {
                    "label": summary.label,
                    "clip_count": summary.clip_count,
                    "latest_capture": summary.latest_capture,
                }
            )
        wanted_words = [
            row["label"]
            for row in label_rows
            if row["label"] not in {"_background_noise_", "_unknown_", "_silence_"}
        ]
        return {
            "created_at": utc_now(),
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "clip_seconds": self._clip_seconds,
            "labels": label_rows,
            "wanted_words": wanted_words,
        }

    def build_archive(self, labels: Optional[Iterable[str]] = None) -> tuple[Path, dict]:
        manifest = self.build_dataset_manifest(labels)
        selected_labels = {row["label"] for row in manifest["labels"]}
        if not selected_labels:
            raise RuntimeError("No dataset folders are available to export.")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = EXPORT_ROOT / f"kws-dataset-{timestamp}.tar.gz"
        manifest_path = EXPORT_ROOT / f"kws-dataset-{timestamp}.manifest.json"
        with tarfile.open(archive_path, "w:gz") as archive:
            for label in sorted(selected_labels):
                archive.add(DATASET_ROOT / label, arcname=f"dataset/{label}")
            with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
                json.dump(manifest, handle, indent=2)
                temp_manifest_path = Path(handle.name)
            try:
                archive.add(temp_manifest_path, arcname="dataset/dataset-manifest.json")
            finally:
                temp_manifest_path.unlink(missing_ok=True)
        manifest["archive_name"] = archive_path.name
        manifest["archive_path"] = str(archive_path)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._event("PACKAGE", f"Created dataset archive {archive_path.name}")
        return archive_path, manifest

    def _upload_archive_direct(self, archive_path: Path, manifest: dict) -> dict:
        if not S3_DATA_BUCKET:
            raise RuntimeError("Set KWS_TRAINING_DATA_BUCKET before uploading to S3.")
        session = create_boto3_session()
        s3 = session.client("s3")
        object_key = "/".join(part for part in [S3_DATA_PREFIX, archive_path.name] if part)
        s3.upload_file(str(archive_path), S3_DATA_BUCKET, object_key)
        manifest_key = object_key.replace(".tar.gz", ".manifest.json")
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(manifest, handle, indent=2)
            temp_manifest_path = Path(handle.name)
        try:
            s3.upload_file(str(temp_manifest_path), S3_DATA_BUCKET, manifest_key)
        finally:
            temp_manifest_path.unlink(missing_ok=True)
        dataset_uri = f"s3://{S3_DATA_BUCKET}/{object_key}"
        with self._lock:
            self._last_archive_name = archive_path.name
            self._last_archive_s3_uri = dataset_uri
            self._last_manifest_s3_uri = f"s3://{S3_DATA_BUCKET}/{manifest_key}"
            self._last_error = ""
        self._event("UPLOAD", f"Uploaded dataset to {dataset_uri} via direct S3")
        return {
            "mode": "direct-aws",
            "bucket": S3_DATA_BUCKET,
            "object_key": object_key,
            "manifest_key": manifest_key,
            "s3_uri": dataset_uri,
            "manifest_s3_uri": f"s3://{S3_DATA_BUCKET}/{manifest_key}",
            "file_event_published": False,
        }

    def _upload_archive_iotconnect(self, archive_path: Path, manifest: dict) -> dict:
        if not self.native_uploader.ready():
            raise RuntimeError(self.native_uploader.status_text())

        archive_result = self.native_uploader.put_object(archive_path.name, archive_path.read_bytes())
        manifest_name = archive_path.name.replace(".tar.gz", ".manifest.json")
        manifest_result = self.native_uploader.put_object(
            manifest_name,
            json.dumps(manifest, indent=2).encode("utf-8"),
        )
        custom_fields = {
            "assetType": "kws-dataset",
            "archiveName": archive_path.name,
            "bucket": archive_result["bucket"],
            "s3Key": archive_result["object_key"],
            "manifestKey": manifest_result["object_key"],
            "manifestUrl": manifest_result["url_path"],
            "wantedWords": ",".join(manifest["wanted_words"]),
            "labelCount": len(manifest["labels"]),
            "clipCount": sum(int(row["clip_count"]) for row in manifest["labels"]),
            "createdAt": manifest["created_at"],
        }
        publish_result = self.native_uploader.publish_file_event(archive_result["url_path"], custom_fields)
        with self._lock:
            self._last_archive_name = archive_path.name
            self._last_archive_s3_uri = archive_result["s3_uri"]
            self._last_manifest_s3_uri = manifest_result["s3_uri"]
            self._last_error = ""
        self._event("UPLOAD", f"Uploaded dataset to {archive_result['s3_uri']} via /IOTCONNECT")
        if publish_result["published"]:
            self._event("IOTCONNECT", f"Published FILE event on {publish_result['topic']}")
        return {
            "mode": "iotconnect-native",
            "bucket": archive_result["bucket"],
            "object_key": archive_result["object_key"],
            "manifest_key": manifest_result["object_key"],
            "s3_uri": archive_result["s3_uri"],
            "manifest_s3_uri": manifest_result["s3_uri"],
            "file_event_published": publish_result["published"],
            "file_topic": publish_result["topic"],
        }

    def upload_archive(self, archive_path: Path, manifest: dict) -> dict:
        summary = self.upload_summary()
        if summary["mode"] == "iotconnect-native":
            return self._upload_archive_iotconnect(archive_path, manifest)
        if summary["mode"] == "direct-aws":
            return self._upload_archive_direct(archive_path, manifest)
        raise RuntimeError(summary["status"])

    def _discover_state_machine_arn(self) -> str:
        if PIPELINE_STATE_MACHINE_ARN:
            return PIPELINE_STATE_MACHINE_ARN
        session = self._create_conversion_session()
        return discover_state_machine_arn(session, PIPELINE_DISCOVERY_PREFIX)

    def _workflow_in_progress_locked(self) -> bool:
        return self._training_status in ACTIVE_WORKFLOW_STATES

    def _create_conversion_session(self):
        if standard_aws_credentials_available():
            return create_boto3_session()
        if self.native_uploader.boto3_ready():
            return self.native_uploader.create_boto3_session()
        raise RuntimeError(
            "No AWS credentials are available for the conversion pipeline. "
            "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or keep /IOTCONNECT pipeline credentials available."
        )

    def _build_conversion_output_s3_uri(self, execution_name: str, fallback_s3_uri: str) -> str:
        if PIPELINE_OUTPUT_S3_URI:
            return PIPELINE_OUTPUT_S3_URI.rstrip("/") + "/"
        if SAGEMAKER_OUTPUT_BUCKET:
            prefix = "/".join(part for part in [PIPELINE_OUTPUT_PREFIX, execution_name] if part)
            return f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{prefix}/"
        return fallback_s3_uri.rsplit("/", 1)[0] + f"/{execution_name}/"

    def _start_conversion_execution(
        self,
        *,
        weights_s3_uri: str,
        dataset_s3_uri: str,
        manifest_s3_uri: str,
        wanted_words: list[str],
        status_code: str,
        event_detail: str,
    ) -> dict:
        if not PIPELINE_IMAGE_URI:
            raise RuntimeError("Set KWS_TRAINING_PIPELINE_IMAGE_URI to enable conversion after training.")

        session = self._create_conversion_session()
        sfn = session.client("stepfunctions")
        state_machine_arn = self._discover_state_machine_arn()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        execution_name = f"kws-convert-{timestamp}".lower()
        input_s3_uri, weights_name = normalize_processing_input_uri(weights_s3_uri, PIPELINE_WEIGHTS_NAME)
        output_s3_uri = self._build_conversion_output_s3_uri(execution_name, dataset_s3_uri or input_s3_uri)
        payload = {
            "ProjectName": PIPELINE_PROJECT_NAME,
            "ProcessingImageUri": PIPELINE_IMAGE_URI,
            "InstanceType": PIPELINE_INSTANCE_TYPE,
            "VolumeSizeGB": PIPELINE_VOLUME_GB,
            "WeightsName": weights_name,
            "InputS3Uri": input_s3_uri,
            "OutputS3Uri": output_s3_uri,
            "DatasetS3Uri": dataset_s3_uri,
            "ManifestS3Uri": manifest_s3_uri,
            "WantedWords": wanted_words,
        }
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(payload),
        )
        with self._lock:
            self._last_conversion_job = execution_name
            self._last_conversion_output = output_s3_uri
            self._training_status = status_code
            self._last_error = ""
        self._event("TRAIN", event_detail.format(execution_name=execution_name))
        return {
            "mode": "iotconnect-conversion",
            "execution_arn": response["executionArn"],
            "execution_name": execution_name,
            "state_machine_arn": state_machine_arn,
            "output_s3_uri": output_s3_uri,
            "weights_s3_uri": weights_s3_uri,
        }

    def _start_workflow_thread(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        with self._lock:
            self._workflow_thread = thread
        thread.start()

    def _monitor_conversion_execution(self, execution_arn: str, execution_name: str):
        try:
            session = self._create_conversion_session()
            sfn = session.client("stepfunctions")
            while True:
                details = sfn.describe_execution(executionArn=execution_arn)
                status = str(details.get("status", "")).strip().upper()
                if status == "RUNNING":
                    time.sleep(TRAINING_POLL_SECS)
                    continue
                if status == "SUCCEEDED":
                    with self._lock:
                        self._training_status = "auto-conversion-completed"
                        self._last_error = ""
                    self._event("TRAIN", f"Conversion execution {execution_name} completed")
                    return
                error_text = str(details.get("error", "")).strip()
                cause_text = str(details.get("cause", "")).strip()
                message = error_text or cause_text or f"Conversion execution {execution_name} ended with {status}"
                with self._lock:
                    self._training_status = "auto-conversion-failed"
                self.note_error(message)
                return
        except Exception as exc:
            with self._lock:
                self._training_status = "auto-conversion-failed"
            self.note_error(f"Conversion monitor failed: {exc}")
        finally:
            with self._lock:
                self._workflow_thread = None

    def _monitor_training_job(
        self,
        training_job_name: str,
        upload_info: dict,
        manifest: dict,
        state_s3_uri: str,
    ):
        try:
            session = create_boto3_session()
            sm = session.client("sagemaker")
            last_secondary = ""
            while True:
                details = sm.describe_training_job(TrainingJobName=training_job_name)
                status = str(details.get("TrainingJobStatus", "")).strip()
                secondary = str(details.get("SecondaryStatus", "")).strip()
                if secondary and secondary != last_secondary:
                    self._event("TRAIN", f"{training_job_name}: {secondary}")
                    last_secondary = secondary

                if status in {"InProgress", "Stopping"}:
                    time.sleep(TRAINING_POLL_SECS)
                    continue

                if status == "Completed":
                    with self._lock:
                        self._training_status = "direct-sagemaker-completed"
                        self._last_error = ""
                    self._event("TRAIN", f"SageMaker job {training_job_name} completed")

                    if AUTO_CONVERT_AFTER_TRAIN and PIPELINE_IMAGE_URI:
                        conversion = self._start_conversion_execution(
                            weights_s3_uri=state_s3_uri,
                            dataset_s3_uri=upload_info["s3_uri"],
                            manifest_s3_uri=upload_info["manifest_s3_uri"],
                            wanted_words=list(manifest["wanted_words"]),
                            status_code="auto-conversion-running",
                            event_detail="Started auto-conversion execution {execution_name}",
                        )
                        self._monitor_conversion_execution(
                            conversion["execution_arn"],
                            conversion["execution_name"],
                        )
                        return

                    if AUTO_CONVERT_AFTER_TRAIN:
                        self._event(
                            "TRAIN",
                            "SageMaker training completed, but auto-conversion is disabled because "
                            "KWS_TRAINING_PIPELINE_IMAGE_URI is not configured.",
                        )
                    with self._lock:
                        self._workflow_thread = None
                    return

                failure_reason = str(details.get("FailureReason", "")).strip()
                message = failure_reason or f"SageMaker job {training_job_name} ended with status {status}"
                with self._lock:
                    self._training_status = "direct-sagemaker-failed"
                self.note_error(message)
                return
        except Exception as exc:
            with self._lock:
                self._training_status = "direct-sagemaker-failed"
            self.note_error(f"Training monitor failed: {exc}")
        finally:
            with self._lock:
                if self._training_status != "auto-conversion-running":
                    self._workflow_thread = None

    def training_summary(self) -> dict:
        standard_credentials_ready = standard_aws_credentials_available()
        conversion_credentials_ready = standard_credentials_ready or self.native_uploader.boto3_ready()
        conversion_ready = (
            conversion_credentials_ready
            and bool(PIPELINE_IMAGE_URI)
        )
        direct_configured = bool(SAGEMAKER_ROLE_ARN and SAGEMAKER_IMAGE_URI and SAGEMAKER_OUTPUT_BUCKET)
        direct_ready = direct_configured and standard_credentials_ready

        if self._pipeline_mode == "iotconnect":
            ready = conversion_ready
            mode = "iotconnect-conversion"
            status = (
                "IoTConnect conversion pipeline is ready."
                if ready
                else "IoTConnect conversion pipeline needs KWS_TRAINING_PIPELINE_IMAGE_URI and KWS_TRAINING_WEIGHTS_S3_URI."
            )
        elif self._pipeline_mode == "direct":
            ready = direct_ready
            mode = "direct-sagemaker"
            if ready:
                status = "Direct SageMaker training is ready."
            elif direct_configured:
                status = (
                    "Direct SageMaker training is configured, but this board has no AWS credentials. "
                    "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or /root/.aws/credentials."
                )
            else:
                status = "Direct SageMaker training needs role, image URI, and output bucket."
        elif direct_ready:
            ready = True
            mode = "direct-sagemaker"
            status = "Direct SageMaker training is ready."
            if AUTO_CONVERT_AFTER_TRAIN and PIPELINE_IMAGE_URI:
                status += " Auto-conversion is enabled."
            elif AUTO_CONVERT_AFTER_TRAIN:
                status += " Auto-conversion is disabled because KWS_TRAINING_PIPELINE_IMAGE_URI is not set."
        elif conversion_ready:
            ready = True
            mode = "iotconnect-conversion"
            status = "IoTConnect conversion pipeline is ready."
        elif direct_configured:
            ready = False
            mode = "direct-sagemaker"
            status = (
                "Direct SageMaker training is configured, but this board has no AWS credentials. "
                "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or /root/.aws/credentials."
            )
        else:
            ready = False
            mode = "unconfigured"
            status = (
                "No training workflow is ready. "
                "IoTConnect conversion needs image URI plus trained weights in S3; "
                "direct SageMaker needs role, image, and output bucket."
            )

        with self._lock:
            training_status = self._training_status
            last_training_job = self._last_training_job
            last_conversion_job = self._last_conversion_job
            last_error = self._last_error

        in_progress = training_status in ACTIVE_WORKFLOW_STATES
        if training_status == "direct-sagemaker-running":
            status = f"SageMaker job {last_training_job} is running."
            ready = False
        elif training_status == "direct-sagemaker-completed":
            status = f"SageMaker job {last_training_job} completed."
        elif training_status == "direct-sagemaker-failed" and last_error:
            status = last_error
        elif training_status == "auto-conversion-running":
            status = f"Conversion execution {last_conversion_job} is running."
            ready = False
            in_progress = True
        elif training_status == "auto-conversion-completed":
            status = f"Conversion execution {last_conversion_job} completed."
        elif training_status == "auto-conversion-failed" and last_error:
            status = last_error
        elif training_status == "iotconnect-conversion-running":
            status = f"Conversion execution {last_conversion_job} is running."
            ready = False
            in_progress = True

        return {
            "mode": mode,
            "ready": ready,
            "status": status,
            "direct_ready": direct_ready,
            "direct_configured": direct_configured,
            "standard_credentials_ready": standard_credentials_ready,
            "conversion_ready": conversion_ready,
            "auto_convert_after_train": AUTO_CONVERT_AFTER_TRAIN,
            "in_progress": in_progress,
        }

    def start_iotconnect_conversion_pipeline(self, upload_info: dict, manifest: dict) -> dict:
        if not PIPELINE_IMAGE_URI or not PIPELINE_WEIGHTS_S3_URI:
            raise RuntimeError(
                "IoTConnect conversion pipeline requires KWS_TRAINING_PIPELINE_IMAGE_URI and KWS_TRAINING_WEIGHTS_S3_URI."
            )
        conversion = self._start_conversion_execution(
            weights_s3_uri=PIPELINE_WEIGHTS_S3_URI,
            dataset_s3_uri=upload_info["s3_uri"],
            manifest_s3_uri=upload_info["manifest_s3_uri"],
            wanted_words=list(manifest["wanted_words"]),
            status_code="iotconnect-conversion-running",
            event_detail="Started IoTConnect conversion execution {execution_name}",
        )
        self._start_workflow_thread(
            self._monitor_conversion_execution,
            conversion["execution_arn"],
            conversion["execution_name"],
        )
        return conversion

    def start_sagemaker_training(self, upload_info: dict, manifest: dict) -> dict:
        if not SAGEMAKER_ROLE_ARN or not SAGEMAKER_IMAGE_URI:
            raise RuntimeError(
                "Set KWS_SAGEMAKER_ROLE_ARN and KWS_SAGEMAKER_IMAGE_URI to start a SageMaker training job."
            )
        if not SAGEMAKER_OUTPUT_BUCKET:
            raise RuntimeError("Set KWS_TRAINING_OUTPUT_BUCKET for SageMaker output artifacts.")
        if not standard_aws_credentials_available():
            raise RuntimeError(
                "This board does not have AWS credentials for SageMaker. "
                "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or /root/.aws/credentials."
            )
        session = create_boto3_session()
        sm = session.client("sagemaker")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        labels_slug = "-".join(manifest["wanted_words"][:4]) or "dataset"
        training_job_name = f"kws-{labels_slug[:28]}-{timestamp}".lower()
        output_uri = f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{'/'.join(part for part in [SAGEMAKER_OUTPUT_PREFIX, training_job_name] if part)}"
        weights_s3_uri = f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{'/'.join(part for part in [SAGEMAKER_WEIGHTS_PREFIX, training_job_name, 'model.pt'] if part)}"
        state_s3_uri = f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{'/'.join(part for part in [SAGEMAKER_WEIGHTS_PREFIX, training_job_name, 'model-state.pt'] if part)}"
        labels_s3_uri = f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{'/'.join(part for part in [SAGEMAKER_WEIGHTS_PREFIX, training_job_name, 'labels.txt'] if part)}"
        results_s3_uri = f"s3://{SAGEMAKER_OUTPUT_BUCKET}/{'/'.join(part for part in [SAGEMAKER_WEIGHTS_PREFIX, training_job_name, 'training-result.json'] if part)}"
        environment = {
            "KWS_DATASET_S3_URI": upload_info["s3_uri"],
            "KWS_WANTED_WORDS": ",".join(manifest["wanted_words"]),
            "KWS_RECOMMENDED_WANTED_WORDS": ",".join(DEFAULT_TRAINING_LABELS),
            "KWS_SAMPLE_RATE": str(SAMPLE_RATE),
            "KWS_CLIP_SECONDS": str(CLIP_SECONDS),
            "KWS_MANIFEST_S3_URI": upload_info["manifest_s3_uri"],
            "KWS_WEIGHTS_UPLOAD_S3_URI": weights_s3_uri,
            "KWS_STATE_UPLOAD_S3_URI": state_s3_uri,
            "KWS_LABELS_UPLOAD_S3_URI": labels_s3_uri,
            "KWS_RESULTS_UPLOAD_S3_URI": results_s3_uri,
            "KWS_TRAIN_EPOCHS": str(SAGEMAKER_TRAIN_EPOCHS),
            "KWS_TRAIN_BATCH_SIZE": str(SAGEMAKER_TRAIN_BATCH_SIZE),
            "KWS_TRAIN_LEARNING_RATE": str(SAGEMAKER_TRAIN_LEARNING_RATE),
            "KWS_TRAIN_PRETRAIN_ENABLED": TRAIN_PRETRAIN_ENABLED,
            "KWS_TRAIN_PRETRAIN_REQUIRED": TRAIN_PRETRAIN_REQUIRED,
            "KWS_TRAIN_PRETRAIN_SOURCE": TRAIN_PRETRAIN_SOURCE,
            "KWS_TRAIN_PRETRAIN_EPOCHS": TRAIN_PRETRAIN_EPOCHS,
            "KWS_TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL": TRAIN_PRETRAIN_MAX_SAMPLES_PER_LABEL,
            "KWS_TRAIN_PRETRAIN_VALIDATION_SPLIT": TRAIN_PRETRAIN_VALIDATION_SPLIT,
            "KWS_TRAIN_PRETRAIN_LEARNING_RATE": TRAIN_PRETRAIN_LEARNING_RATE,
            "KWS_TRAIN_PRETRAIN_WORDS": TRAIN_PRETRAIN_WORDS,
            "KWS_TRAIN_MUSAN_SOURCE": TRAIN_MUSAN_SOURCE,
            "KWS_TRAIN_MUSAN_MAX_CLIPS": TRAIN_MUSAN_MAX_CLIPS,
        }
        hyperparameters = {
            "dataset_s3_uri": upload_info["s3_uri"],
            "wanted_words": ",".join(manifest["wanted_words"]),
            "sample_rate": str(SAMPLE_RATE),
            "clip_seconds": str(CLIP_SECONDS),
            "epochs": str(SAGEMAKER_TRAIN_EPOCHS),
            "batch-size": str(SAGEMAKER_TRAIN_BATCH_SIZE),
            "learning-rate": str(SAGEMAKER_TRAIN_LEARNING_RATE),
            "pretrain-enabled": TRAIN_PRETRAIN_ENABLED or "1",
            "pretrain-source": TRAIN_PRETRAIN_SOURCE,
            "pretrain-epochs": TRAIN_PRETRAIN_EPOCHS or "6",
        }
        sm.create_training_job(
            TrainingJobName=training_job_name,
            RoleArn=SAGEMAKER_ROLE_ARN,
            AlgorithmSpecification={
                "TrainingImage": SAGEMAKER_IMAGE_URI,
                "TrainingInputMode": "File",
            },
            InputDataConfig=[
                {
                    "ChannelName": "training",
                    "DataSource": {
                        "S3DataSource": {
                            "S3DataType": "S3Prefix",
                            "S3Uri": upload_info["s3_uri"],
                            "S3DataDistributionType": "FullyReplicated",
                        }
                    },
                    "ContentType": "application/gzip",
                }
            ],
            OutputDataConfig={"S3OutputPath": output_uri},
            ResourceConfig={
                "InstanceType": SAGEMAKER_INSTANCE_TYPE,
                "InstanceCount": SAGEMAKER_INSTANCE_COUNT,
                "VolumeSizeInGB": 30,
            },
            StoppingCondition={"MaxRuntimeInSeconds": SAGEMAKER_MAX_RUNTIME_SECS},
            Environment=environment,
            HyperParameters=hyperparameters,
        )
        with self._lock:
            self._last_training_job = training_job_name
            self._last_training_output = state_s3_uri
            self._last_conversion_job = ""
            self._last_conversion_output = ""
            self._training_status = "direct-sagemaker-running"
            self._last_error = ""
        self._event("TRAIN", f"Started SageMaker job {training_job_name}")
        self._start_workflow_thread(
            self._monitor_training_job,
            training_job_name,
            dict(upload_info),
            json.loads(json.dumps(manifest)),
            state_s3_uri,
        )
        return {
            "mode": "direct-sagemaker",
            "training_job_name": training_job_name,
            "output_s3_uri": output_uri,
            "weights_s3_uri": weights_s3_uri,
            "state_s3_uri": state_s3_uri,
            "labels_s3_uri": labels_s3_uri,
            "results_s3_uri": results_s3_uri,
        }

    def start_training_workflow(self, upload_info: dict, manifest: dict) -> dict:
        summary = self.training_summary()
        if summary["mode"] == "iotconnect-conversion":
            return self.start_iotconnect_conversion_pipeline(upload_info, manifest)
        if summary["mode"] == "direct-sagemaker":
            return self.start_sagemaker_training(upload_info, manifest)
        raise RuntimeError(summary["status"])

    def perform_upload(self, labels: Optional[Iterable[str]] = None) -> dict:
        try:
            archive_path, manifest = self.build_archive(labels)
            upload_info = self.upload_archive(archive_path, manifest)
            self.clear_error()
            return {
                "archive_path": archive_path,
                "manifest": manifest,
                "upload": upload_info,
            }
        except Exception as exc:
            self.note_error(str(exc))
            raise

    def perform_training(self, labels: Optional[Iterable[str]] = None) -> dict:
        try:
            with self._lock:
                if self._workflow_in_progress_locked():
                    raise RuntimeError("A training or conversion workflow is already in progress. Wait for it to finish.")
            result = self.perform_upload(labels)
            training = self.start_training_workflow(result["upload"], result["manifest"])
            result["training"] = training
            self.clear_error()
            return result
        except Exception as exc:
            self.note_error(str(exc))
            raise

    def snapshot(self) -> dict:
        summaries = self.list_labels()
        collection_plan = self.collection_plan(summaries)
        with self._lock:
            recording = self._recording_snapshot_locked()
            last_capture_at = self._last_capture_at
            last_archive_name = self._last_archive_name
            last_archive_s3_uri = self._last_archive_s3_uri
            last_manifest_s3_uri = self._last_manifest_s3_uri
            last_training_job = self._last_training_job
            last_training_output = self._last_training_output
            last_conversion_job = self._last_conversion_job
            last_conversion_output = self._last_conversion_output
            last_installed_model_name = self._last_installed_model_name
            last_installed_model_s3_uri = self._last_installed_model_s3_uri
            last_install_at = self._last_install_at
            last_error = self._last_error
            iotconnect_connected = self._iotconnect_connected
        upload = self.upload_summary()
        native = self.native_upload_snapshot()
        training = self.training_summary()
        deployment = self.deployment_summary()
        return {
            "audio_device": self.audio_device,
            "dataset_root": str(DATASET_ROOT),
            "export_root": str(EXPORT_ROOT),
            "labels": [summary.__dict__ for summary in summaries],
            "collection_plan": collection_plan,
            "events": self.event_history(),
            "recording": recording,
            "upload": upload,
            "iotconnect": native,
            "training": training,
            "runtime": {
                "last_capture_at": last_capture_at,
                "last_archive_name": last_archive_name,
                "last_archive_s3_uri": last_archive_s3_uri,
                "last_manifest_s3_uri": last_manifest_s3_uri,
                "last_training_job": last_training_job,
                "last_training_output": last_training_output,
                "last_conversion_job": last_conversion_job,
                "last_conversion_output": last_conversion_output,
                "last_installed_model_name": last_installed_model_name,
                "last_installed_model_s3_uri": last_installed_model_s3_uri,
                "last_install_at": last_install_at,
                "last_error": last_error,
                "iotconnect_connected": iotconnect_connected,
            },
            "aws": {
                "region": AWS_REGION,
                "data_bucket": upload["bucket"],
                "data_prefix": S3_DATA_PREFIX,
                "output_bucket": SAGEMAKER_OUTPUT_BUCKET,
                "output_prefix": SAGEMAKER_OUTPUT_PREFIX,
                "converted_prefix": PIPELINE_OUTPUT_PREFIX,
                "sagemaker_ready": training["ready"],
                "image_configured": bool(SAGEMAKER_IMAGE_URI),
                "role_configured": bool(SAGEMAKER_ROLE_ARN),
                "upload_mode": upload["mode"],
                "training_mode": training["mode"],
            },
            "deployment": deployment,
            "capture": {
                "sample_rate": SAMPLE_RATE,
                "channels": CHANNELS,
                "clip_seconds": self._clip_seconds,
            },
        }

    def telemetry_payload(self, sdk_version: str, iotconnect_connected: bool) -> dict:
        snapshot = self.snapshot()
        label_count = len(snapshot["labels"])
        clip_count = sum(int(label["clip_count"]) for label in snapshot["labels"])
        recording_label = snapshot["recording"]["label"] or ""
        return {
            "sdk_version": sdk_version,
            "audio_device": snapshot["audio_device"],
            "upload_mode": snapshot["upload"]["mode"],
            "upload_ready": snapshot["upload"]["ready"],
            "upload_status": snapshot["upload"]["status"],
            "iotc_file_topic": snapshot["iotconnect"]["file_topic"],
            "iotc_bucket": snapshot["iotconnect"]["selected_bucket"],
            "label_count": label_count,
            "clip_count": clip_count,
            "recording": snapshot["recording"]["active"],
            "current_label": recording_label,
            "last_capture_at": snapshot["runtime"]["last_capture_at"],
            "capture_clip_seconds": snapshot["capture"]["clip_seconds"],
            "last_archive_name": snapshot["runtime"]["last_archive_name"],
            "last_archive_s3_uri": snapshot["runtime"]["last_archive_s3_uri"],
            "last_manifest_s3_uri": snapshot["runtime"]["last_manifest_s3_uri"],
            "last_training_job": snapshot["runtime"]["last_training_job"],
            "last_training_output": snapshot["runtime"]["last_training_output"],
            "last_conversion_job": snapshot["runtime"]["last_conversion_job"],
            "last_conversion_output": snapshot["runtime"]["last_conversion_output"],
            "sagemaker_ready": snapshot["training"]["ready"],
            "last_error": snapshot["runtime"]["last_error"],
        }


workspace = TrainingWorkspace()
iotconnect_bridge = IotConnectBridge(
    workspace=workspace,
    config_json_path=IOTC_CONFIG_JSON,
    cert_path=IOTC_DEVICE_CERT,
    key_path=IOTC_DEVICE_KEY,
    telemetry_secs=IOTC_TELEMETRY_SECS,
)
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return jsonify(workspace.snapshot())


@app.post("/api/capture/start")
def api_capture_start():
    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label", "")).strip()
    if not label:
        return jsonify({"ok": False, "error": "label is required"}), 400
    try:
        result = workspace.start_capture(label)
    except Exception as exc:
        workspace.note_error(str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400
    workspace.clear_error()
    return jsonify({"ok": True, "result": result, "state": workspace.snapshot()})


@app.post("/api/capture/stop")
def api_capture_stop():
    try:
        result = workspace.stop_capture()
    except Exception as exc:
        workspace.note_error(str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400
    workspace.clear_error()
    return jsonify({"ok": True, "result": result, "state": workspace.snapshot()})


@app.post("/api/labels/retire")
def api_labels_retire():
    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label", "")).strip()
    if not label:
        return jsonify({"ok": False, "error": "label is required", "state": workspace.snapshot()}), 400
    try:
        result = workspace.retire_label(label)
    except Exception as exc:
        workspace.note_error(str(exc))
        return jsonify({"ok": False, "error": str(exc), "state": workspace.snapshot()}), 400
    workspace.clear_error()
    return jsonify({"ok": True, "result": result, "state": workspace.snapshot()})


@app.post("/api/aws/upload")
def api_upload():
    payload = request.get_json(silent=True) or {}
    labels = payload.get("labels")
    try:
        result = workspace.perform_upload(labels)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify(
        {
            "ok": True,
            "archive_path": str(result["archive_path"]),
            "manifest": result["manifest"],
            "upload": result["upload"],
            "state": workspace.snapshot(),
        }
    )


@app.post("/api/aws/train")
def api_train():
    payload = request.get_json(silent=True) or {}
    labels = payload.get("labels")
    try:
        result = workspace.perform_training(labels)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify(
        {
            "ok": True,
            "archive_path": str(result["archive_path"]),
            "manifest": result["manifest"],
            "upload": result["upload"],
            "training": result["training"],
            "state": workspace.snapshot(),
        }
    )


@app.get("/api/models")
def api_models():
    try:
        models = workspace.list_model_packages()
    except Exception as exc:
        workspace.note_error(str(exc))
        return jsonify({"ok": False, "error": str(exc), "state": workspace.snapshot()}), 400
    workspace.clear_error()
    return jsonify({"ok": True, "models": models, "state": workspace.snapshot()})


@app.post("/api/models/install")
def api_models_install():
    payload = request.get_json(silent=True) or {}
    s3_uri = str(payload.get("s3_uri", "")).strip()
    try:
        result = workspace.install_model_package(s3_uri)
    except Exception as exc:
        workspace.note_error(str(exc))
        return jsonify({"ok": False, "error": str(exc), "state": workspace.snapshot()}), 400
    workspace.clear_error()
    return jsonify({"ok": True, "result": result, "state": workspace.snapshot()})


def _find_optimize_script() -> Optional[Path]:
    candidates = [
        BASE_DIR.parent / "scripts" / "optimize_dataset_clips.py",
        Path("/root/kws-training/scripts/optimize_dataset_clips.py"),
        Path(os.getenv("KWS_TRAINING_OPTIMIZE_SCRIPT", "")) if os.getenv("KWS_TRAINING_OPTIMIZE_SCRIPT") else None,
    ]
    for path in candidates:
        if path and path.is_file():
            return path
    return None


@app.post("/api/dataset/optimize")
def api_dataset_optimize():
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run"))
    include_bg = bool(payload.get("include_background_noise"))

    if workspace.snapshot()["recording"]["active"]:
        return jsonify({"ok": False, "error": "Stop the active recording before running Optimize Clips.", "state": workspace.snapshot()}), 409

    script_path = _find_optimize_script()
    if not script_path:
        msg = "optimize_dataset_clips.py not found. Set KWS_TRAINING_OPTIMIZE_SCRIPT or place the script under scripts/."
        workspace.note_error(msg)
        return jsonify({"ok": False, "error": msg, "state": workspace.snapshot()}), 500

    cmd = [sys.executable, str(script_path), "--dataset-root", str(DATASET_ROOT)]
    if dry_run:
        cmd.append("--dry-run")
    if include_bg:
        cmd.append("--include-background-noise")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        msg = "Optimize timed out after 600s."
        workspace.note_error(msg)
        return jsonify({"ok": False, "error": msg, "state": workspace.snapshot()}), 504

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "optimize failed").strip()
        workspace.note_error(err)
        return jsonify({"ok": False, "error": err, "stdout": proc.stdout, "stderr": proc.stderr, "state": workspace.snapshot()}), 500

    try:
        summary = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        summary = {"raw": proc.stdout}

    workspace._event(
        "DATASET",
        f"Optimized clips: {summary.get('optimized_files', 0)} changed, {summary.get('unchanged_files', 0)} unchanged, {summary.get('skipped_files', 0)} skipped" + (" (dry-run)" if dry_run else ""),
    )
    workspace.clear_error()
    return jsonify({"ok": True, "result": summary, "state": workspace.snapshot()})


def main():
    print(f"Starting KWS Training UI on http://{HOST}:{PORT}")
    print(f"Dataset root: {DATASET_ROOT}")
    print(f"Audio device: {workspace.audio_device}")
    print(f"Upload mode: {workspace.upload_summary()['mode']}")
    print(f"Upload status: {workspace.upload_summary()['status']}")
    print(f"Training mode: {workspace.training_summary()['mode']}")
    print(f"Training status: {workspace.training_summary()['status']}")
    iotconnect_bridge.start()
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
