from __future__ import annotations

import os
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

SDK_IMPORT_ERROR = ""

try:
    from avnet.iotconnect.sdk.lite import Callbacks, Client, DeviceConfig, DeviceConfigError, C2dCommand, C2dOta
    from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
    from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck
except Exception as exc:  # pragma: no cover
    SDK_IMPORT_ERROR = str(exc)
    Callbacks = Client = DeviceConfig = DeviceConfigError = C2dCommand = C2dOta = C2dAck = None
    SDK_VERSION = "unavailable"


class IotConnectBridge:
    def __init__(self, workspace, config_json_path: Path, cert_path: Path, key_path: Path, telemetry_secs: float = 60.0):
        self.workspace = workspace
        self.config_json_path = Path(config_json_path)
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.telemetry_secs = max(5.0, float(telemetry_secs))
        self.client = None
        self.device_config = None
        self.last_error = ""
        self.connected = False
        self.started = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def snapshot(self) -> dict:
        return {
            "available": not bool(SDK_IMPORT_ERROR),
            "started": self.started,
            "connected": self.connected,
            "config_path": str(self.config_json_path),
            "cert_path": str(self.cert_path),
            "key_path": str(self.key_path),
            "telemetry_secs": self.telemetry_secs,
            "sdk_version": SDK_VERSION,
            "last_error": self.last_error or SDK_IMPORT_ERROR,
        }

    def _set_error(self, message: str):
        self.last_error = message
        self.workspace.note_error(message)

    def _clear_error(self):
        self.last_error = ""

    def _ack(self, msg: C2dCommand, status, text: str):
        try:
            if self.client is not None and msg.ack_id is not None:
                self.client.send_command_ack(msg, status, text)
        except Exception as exc:  # pragma: no cover
            self._set_error(f"Command ack failed: {exc}")

    def _extract_and_run_package(self, archive_filename: str) -> bool:
        archive_path = Path(archive_filename)
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(os.getcwd())
        elif archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(os.getcwd())
        else:
            raise RuntimeError(f"Unsupported package format: {archive_path.name}")

        install_path = Path(os.getcwd()) / "install.sh"
        if install_path.is_file():
            os.chmod(install_path, 0o755)
            rc = os.system(f"bash {install_path}")
            if rc != 0:
                raise RuntimeError("install.sh failed")
            install_path.unlink(missing_ok=True)
        return True

    def _restart_process(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _package_name_from_url(self, package_url: str) -> str:
        name = Path(urlparse(package_url).path).name
        if name.endswith(".zip") or name.endswith(".tar.gz"):
            return name
        return "package.zip"

    def _run_upload_command(self, msg: C2dCommand):
        try:
            result = self.workspace.perform_upload()
            self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Dataset uploaded: {result['upload']['s3_uri']}")
            self.send_telemetry("command-upload")
        except Exception as exc:
            self._ack(msg, C2dAck.CMD_FAILED, str(exc))

    def _run_training_command(self, msg: C2dCommand):
        try:
            result = self.workspace.perform_training()
            training = result["training"]
            summary = training.get("execution_arn") or training.get("training_job_name") or "started"
            self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Training workflow started: {summary}")
            self.send_telemetry("command-train")
        except Exception as exc:
            self._ack(msg, C2dAck.CMD_FAILED, str(exc))

    def _run_file_download(self, msg: C2dCommand, package_url: str):
        try:
            package_name = self._package_name_from_url(package_url)
            response = requests.get(package_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(package_name, "wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        handle.write(chunk)
            self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Downloaded {package_name}")
            self._extract_and_run_package(package_name)
            self.send_telemetry("command-file-download")
            time.sleep(1)
            self._restart_process()
        except Exception as exc:
            self._ack(msg, C2dAck.CMD_FAILED, f"file-download failed: {exc}")

    def _run_restart(self, msg: C2dCommand):
        self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Restarting application")
        time.sleep(1)
        self._restart_process()

    def on_command(self, msg: C2dCommand):
        name = msg.command_name
        args = list(msg.command_args or [])
        self.workspace.note_event("IOTCONNECT", f"Command received: {name}")

        if name == "refresh-state":
            self.send_telemetry("refresh-state")
            self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "State telemetry sent")
            return

        if name == "set-upload-mode":
            if len(args) != 1:
                self._ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument: auto, iotconnect, or direct")
                return
            try:
                self.workspace.set_upload_mode(str(args[0]))
                self.send_telemetry("set-upload-mode")
                self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Upload mode set to {self.workspace.upload_summary()['mode']}")
            except Exception as exc:
                self._ack(msg, C2dAck.CMD_FAILED, str(exc))
            return

        if name == "set-audio-device":
            if len(args) != 1:
                self._ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
                return
            try:
                self.workspace.set_audio_device(str(args[0]))
                self.send_telemetry("set-audio-device")
                self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Audio device set to {self.workspace.audio_device}")
            except Exception as exc:
                self._ack(msg, C2dAck.CMD_FAILED, str(exc))
            return

        if name == "set-clip-seconds":
            if len(args) != 1:
                self._ack(msg, C2dAck.CMD_FAILED, "Expected 1 numeric argument")
                return
            try:
                seconds = int(float(args[0]))
                self.workspace.set_clip_seconds(seconds)
                self.send_telemetry("set-clip-seconds")
                self._ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Clip seconds set to {seconds}")
            except Exception as exc:
                self._ack(msg, C2dAck.CMD_FAILED, str(exc))
            return

        if name == "upload-dataset":
            threading.Thread(target=self._run_upload_command, args=(msg,), daemon=True).start()
            return

        if name == "start-training":
            threading.Thread(target=self._run_training_command, args=(msg,), daemon=True).start()
            return

        if name == "restart-app":
            threading.Thread(target=self._run_restart, args=(msg,), daemon=True).start()
            return

        if name == "file-download":
            if len(args) != 1:
                self._ack(msg, C2dAck.CMD_FAILED, "Expected 1 URL argument")
                return
            threading.Thread(target=self._run_file_download, args=(msg, str(args[0])), daemon=True).start()
            return

        self._ack(msg, C2dAck.CMD_FAILED, "Not Implemented")

    def on_ota(self, msg: C2dOta):
        try:
            if self.client is not None:
                self.client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
            extraction_success = False
            for url in msg.urls:
                urllib.request.urlretrieve(url.url, url.file_name)
                extraction_success = self._extract_and_run_package(url.file_name)
                if not extraction_success:
                    break
            if extraction_success and self.client is not None:
                self.client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
                self.send_telemetry("ota")
                time.sleep(1)
                self._restart_process()
        except Exception as exc:
            self._set_error(f"OTA failed: {exc}")

    def on_disconnect(self, reason: str, disconnected_from_server: bool):
        self.connected = False
        self.workspace.set_iotconnect_connected(False)
        self.workspace.note_event(
            "IOTCONNECT",
            f"Disconnected{' from server' if disconnected_from_server else ''}: {reason}",
        )

    def _make_client(self):
        if SDK_IMPORT_ERROR:
            raise RuntimeError(f"iotconnect-sdk-lite is unavailable: {SDK_IMPORT_ERROR}")
        if not self.config_json_path.is_file():
            raise RuntimeError(f"Device config not found: {self.config_json_path}")
        if not self.cert_path.is_file():
            raise RuntimeError(f"Device certificate not found: {self.cert_path}")
        if not self.key_path.is_file():
            raise RuntimeError(f"Device private key not found: {self.key_path}")

        self.device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path=str(self.config_json_path),
            device_cert_path=str(self.cert_path),
            device_pkey_path=str(self.key_path),
        )
        self.client = Client(
            config=self.device_config,
            callbacks=Callbacks(
                ota_cb=self.on_ota,
                command_cb=self.on_command,
                disconnected_cb=self.on_disconnect,
            ),
        )

    def ensure_connected(self):
        with self._lock:
            if self.client is None:
                self._make_client()
        if self.client.is_connected():
            self.connected = True
            self.workspace.set_iotconnect_connected(True)
            return
        self.client.connect()
        self.connected = self.client.is_connected()
        self.workspace.set_iotconnect_connected(self.connected)
        if not self.connected:
            raise RuntimeError("Unable to connect to /IOTCONNECT")

    def send_telemetry(self, reason: str = "periodic"):
        self.ensure_connected()
        self.workspace.set_iotconnect_connected(True)
        payload = self.workspace.telemetry_payload(SDK_VERSION, self.connected)
        self.client.send_telemetry(payload)
        self.workspace.note_event("IOTCONNECT", f"Sent {reason} telemetry")

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self.send_telemetry("periodic" if self.started else "startup")
                self.started = True
                self._clear_error()
            except Exception as exc:
                self.connected = False
                self.workspace.set_iotconnect_connected(False)
                self._set_error(str(exc))
            self._stop_event.wait(self.telemetry_secs)

    def start(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self.client is not None and self.client.is_connected():
            try:
                self.client.disconnect()
            except Exception:
                pass
