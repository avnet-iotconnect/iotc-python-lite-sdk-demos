# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

from kws_engine import KeywordSpotter, KeywordSpotterError, KwsSettings, InferenceResult


client: Optional[Client] = None
spotter: Optional[KeywordSpotter] = None
listening_enabled = os.getenv("KWS_AUTOSTART", "1").strip().lower() not in ("0", "false", "no", "off")
last_error = ""
last_result: Optional[InferenceResult] = None
telemetry_period_secs = max(1.0, float(os.getenv("KWS_TELEMETRY_SECS", "2")))


def extract_and_run_tar_gz(targz_filename: str) -> bool:
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
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
    except subprocess.CalledProcessError:
        return False


def restart_process():
    print("")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def build_telemetry() -> dict:
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
        "kws_detected": bool(last_result.detected) if last_result is not None and listening_enabled else False,
        "inference_count": state["inference_count"],
        "detection_count": state["detection_count"],
        "last_detected_word": state["last_detected_word"],
        "last_detected_confidence": round(state["last_detected_confidence"], 6),
        "last_detected_at": state["last_detected_at"],
        "audio_device": state["audio_device"],
        "detection_threshold": round(state["threshold"], 4),
        "last_error": last_error,
    }


def safe_send_telemetry():
    if client is None or not client.is_connected():
        return
    client.send_telemetry(build_telemetry())


def on_command(msg: C2dCommand):
    global listening_enabled
    global last_error

    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "listen-start":
        listening_enabled = True
        last_error = ""
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening started")
        return

    if msg.command_name == "listen-stop":
        listening_enabled = False
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Keyword spotter listening stopped")
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
        except ValueError:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Threshold must be a decimal from 0.0 to 1.0")
        return

    if msg.command_name == "file-download":
        if len(msg.command_args) != 1:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            return

        package_url = msg.command_args[0]
        try:
            response = requests.get(package_url, stream=True, timeout=60)
            response.raise_for_status()
            with open("package.tar.gz", "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=8192):
                    file_handle.write(chunk)
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Downloading {package_url}")
            print("File downloaded successfully and saved to package.tar.gz")
            if extract_and_run_tar_gz("package.tar.gz"):
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

        if url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_tar_gz(url.file_name)
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
            model_path=model_dir / "ds_cnn_s_quantized.tflite",
            labels_path=model_dir / "labels.txt",
            threshold=float(os.getenv("KWS_DETECTION_THRESHOLD", "0.80")),
            cooldown_secs=float(os.getenv("KWS_COOLDOWN_SECS", "2.0")),
            arecord_device=os.getenv("KWS_ARECORD_DEVICE") or None,
        )
    )


def run_loop():
    global last_error
    global last_result

    next_idle_telemetry_at = 0.0

    while True:
        ensure_connected()

        if listening_enabled:
            try:
                result = spotter.run_once()
                last_result = result
                last_error = ""
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

            safe_send_telemetry()
            next_idle_telemetry_at = time.time() + telemetry_period_secs
            continue

        if time.time() >= next_idle_telemetry_at:
            safe_send_telemetry()
            next_idle_telemetry_at = time.time() + telemetry_period_secs

        time.sleep(0.25)


def main():
    global client
    global spotter
    global last_error

    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path="iotcDeviceConfig.json",
            device_cert_path="device-cert.pem",
            device_pkey_path="device-pkey.pem",
        )
    except DeviceConfigError as exc:
        print(exc)
        sys.exit(1)

    try:
        spotter = make_spotter()
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
    print("Model: ds_cnn_s_quantized.tflite")

    try:
        run_loop()
    except KeyboardInterrupt:
        print("Exiting.")
        if client is not None and client.is_connected():
            try:
                safe_send_telemetry()
                client.disconnect()
            except Exception:
                pass
        sys.exit(0)
    except Exception as exc:
        last_error = str(exc)
        print(last_error)
        safe_send_telemetry()
        sys.exit(1)


if __name__ == "__main__":
    main()
