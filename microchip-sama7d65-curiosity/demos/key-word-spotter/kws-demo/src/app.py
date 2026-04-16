# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import os
import sys
import time
import subprocess
import tarfile
import urllib.request
import zipfile
import hashlib
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

from kws_engine import KeywordSpotter, KeywordSpotterError, KwsSettings, InferenceResult


client: Optional[Client] = None
spotter: Optional[KeywordSpotter] = None
CONFIG_DIR = Path(os.getenv("KWS_CONFIG_DIR", os.getcwd()))
listening_enabled = os.getenv("KWS_AUTOSTART", "1").strip().lower() not in ("0", "false", "no", "off")
last_error = ""
last_result: Optional[InferenceResult] = None
telemetry_interval_secs = max(1.0, float(os.getenv("KWS_TELEMETRY_SECS", "60")))
next_periodic_telemetry_at = 0.0
active_model_name = ""
active_model_package = ""
active_model_sha256 = ""


def extract_and_run_package(archive_filename: str) -> bool:
    try:
        archive_path = Path(archive_filename)
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(os.getcwd())
        elif archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(os.getcwd())
        else:
            print(f"Unsupported package format: {archive_path.name}")
            return False

        script_file_path = os.path.join(os.getcwd(), "install.sh")
        if not os.path.isfile(script_file_path):
            print("install.sh not found in the current directory.")
            return True

        try:
            subprocess.run(["bash", script_file_path], check=True)
            os.remove(script_file_path)
            print("Successfully executed install.sh")
            return True
        except subprocess.CalledProcessError as exc:
            os.remove(script_file_path)
            print(f"Error executing install.sh: {exc}")
            return False
        except Exception as exc:
            os.remove(script_file_path)
            print(f"An error occurred: {exc}")
            return False
    except (subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile):
        return False


def restart_process():
    print("")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def local_package_name(package_url: str) -> str:
    candidate = Path(urlparse(package_url).path).name
    if candidate.endswith(".zip") or candidate.endswith(".tar.gz"):
        return candidate
    return "package.zip"


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


def build_telemetry(detection_event: bool = False) -> dict:
    state = spotter.state_snapshot() if spotter is not None else {
        "audio_device": "",
        "detection_count": 0,
        "inference_count": 0,
        "last_detected_at": "",
        "last_detected_confidence": 0.0,
        "last_detected_word": "",
        "threshold": 0.0,
    }

    return {
        "sdk_version": SDK_VERSION,
        "listening": listening_enabled,
        "kws_label": last_result.label if last_result is not None else "",
        "kws_confidence": round(last_result.confidence, 6) if last_result is not None else 0.0,
        "kws_class_id": last_result.class_id if last_result is not None else -1,
        "kws_detected": bool(detection_event and last_result is not None and last_result.detected and listening_enabled),
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
        "telemetry_interval": round(telemetry_interval_secs, 3),
        "last_error": last_error,
    }


def safe_send_telemetry(reason: str = "periodic", detection_event: bool = False):
    if client is None or not client.is_connected():
        return
    telemetry = build_telemetry(detection_event=detection_event)
    client.send_telemetry(telemetry)
    print(f"Sent {reason} telemetry:", telemetry)


def schedule_next_periodic(now_monotonic: Optional[float] = None):
    global next_periodic_telemetry_at
    if now_monotonic is None:
        now_monotonic = time.monotonic()
    next_periodic_telemetry_at = now_monotonic + telemetry_interval_secs


def on_command(msg: C2dCommand):
    global listening_enabled
    global last_error
    global telemetry_interval_secs
    global next_periodic_telemetry_at

    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "listen-start":
        listening_enabled = True
        last_error = ""
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening started")
        safe_send_telemetry(reason="command")
        return

    if msg.command_name == "listen-stop":
        listening_enabled = False
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening stopped")
        safe_send_telemetry(reason="command")
        return

    if msg.command_name == "set-threshold":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return

        try:
            new_threshold = float(msg.command_args[0])
            if new_threshold < 0.0 or new_threshold > 1.0:
                raise ValueError()
            spotter.set_threshold(new_threshold)
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Threshold set to {new_threshold:.3f}")
            safe_send_telemetry(reason="command")
        except ValueError:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Threshold must be a decimal from 0.0 to 1.0")
        return

    if msg.command_name == "set-interval":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return

        try:
            new_interval = float(msg.command_args[0])
            if new_interval <= 0.0:
                raise ValueError()
            telemetry_interval_secs = max(1.0, new_interval)
            next_periodic_telemetry_at = 0.0
            if msg.ack_id is not None:
                client.send_command_ack(
                    msg,
                    C2dAck.CMD_SUCCESS_WITH_ACK,
                    f"Telemetry interval set to {telemetry_interval_secs:g} seconds",
                )
            safe_send_telemetry(reason="command")
            schedule_next_periodic()
        except ValueError:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Interval must be a positive number of seconds")
        return

    if msg.command_name == "file-download":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return

        package_url = msg.command_args[0]
        try:
            package_name = local_package_name(package_url)
            response = requests.get(package_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(package_name, "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=8192):
                    file_handle.write(chunk)
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Downloading {package_url}")
            print(f"File downloaded successfully and saved to {package_name}")
            if extract_and_run_package(package_name):
                print("Download command successful. Restarting the application...")
                restart_process()
        except Exception as exc:
            error_message = f"Failed to download package: {exc}"
            print(error_message)
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, error_message)
        return

    print("Command %s not implemented!" % msg.command_name)
    if msg.ack_id is not None:
        client.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


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


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


def ensure_connected():
    if client.is_connected():
        return

    print("(re)connecting...")
    client.connect()
    if not client.is_connected():
        raise RuntimeError("Unable to connect to /IOTCONNECT")


def make_spotter() -> KeywordSpotter:
    model_dir = Path(os.getenv("KWS_MODEL_DIR", "/opt/demo/models"))
    return KeywordSpotter(
        KwsSettings(
            model_path=resolve_model_path(model_dir),
            labels_path=resolve_labels_path(model_dir),
            threshold=float(os.getenv("KWS_DETECTION_THRESHOLD", "0.80")),
            cooldown_secs=float(os.getenv("KWS_COOLDOWN_SECS", "2.0")),
            min_signal_rms=float(os.getenv("KWS_MIN_SIGNAL_RMS", "0.012")),
            arecord_device=os.getenv("KWS_ARECORD_DEVICE") or None,
        )
    )


def run_loop():
    global last_error
    global last_result

    while True:
        ensure_connected()

        if listening_enabled:
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
            except KeywordSpotterError as exc:
                last_error = str(exc)
                print(last_error)
                time.sleep(2)
            except Exception as exc:
                last_error = f"Unexpected inference error: {exc}"
                print(last_error)
                time.sleep(2)

            if detection_event:
                safe_send_telemetry(reason="event", detection_event=True)

            now_monotonic = time.monotonic()
            if now_monotonic >= next_periodic_telemetry_at:
                safe_send_telemetry(reason="periodic")
                schedule_next_periodic(now_monotonic)
            continue

        now_monotonic = time.monotonic()
        if now_monotonic >= next_periodic_telemetry_at:
            safe_send_telemetry(reason="periodic")
            schedule_next_periodic(now_monotonic)

        time.sleep(0.25)


def main():
    global client
    global spotter
    global last_error
    global active_model_name
    global active_model_package
    global active_model_sha256

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
        spotter = make_spotter()
        active_model_name = spotter.settings.model_path.name
        active_model_sha256 = sha256_file(spotter.settings.model_path)
        active_model_package = read_package_info(spotter.settings.model_path.parent).get("package_name", "")
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
    print("Keyword spotter is %s" % ("listening" if listening_enabled else "idle"))
    print("Audio device:", spotter.audio_device_name())
    print("Model:", active_model_name)

    safe_send_telemetry(reason="startup")
    schedule_next_periodic()

    try:
        run_loop()
    except KeyboardInterrupt:
        print("Exiting.")
        if client is not None and client.is_connected():
            try:
                safe_send_telemetry(reason="shutdown")
                client.disconnect()
            except Exception:
                pass
        sys.exit(0)
    except Exception as exc:
        last_error = str(exc)
        print(last_error)
        safe_send_telemetry(reason="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
