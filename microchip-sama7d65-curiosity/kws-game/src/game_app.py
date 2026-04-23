from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from typing import Deque, Optional
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

try:
    from avnet.iotconnect.sdk.lite import Callbacks, Client, DeviceConfig, DeviceConfigError, C2dCommand, C2dOta
    from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
    from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

    SDK_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - import depends on target image
    DeviceConfigError = Exception
    Callbacks = Client = DeviceConfig = DeviceConfigError = C2dCommand = C2dOta = C2dAck = None  # type: ignore[assignment]
    SDK_VERSION = "unavailable"
    SDK_IMPORT_ERROR = str(exc)

from kws_engine import KeywordSpotter, KwsSettings


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = Path("/opt/demo/models") if Path("/opt/demo/models").is_dir() else BASE_DIR / "models"
MODEL_DIR = Path(os.getenv("KWS_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
DEFAULT_CONFIG_DIR = Path(os.getcwd())
CONFIG_DIR = Path(os.getenv("KWS_CONFIG_DIR", str(DEFAULT_CONFIG_DIR)))
HOST = os.getenv("KWS_GAME_HOST", "0.0.0.0")
PORT = int(os.getenv("KWS_GAME_PORT", "8080"))
DEBUG = os.getenv("KWS_GAME_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
TELEMETRY_INTERVAL_SECS = max(1.0, float(os.getenv("KWS_GAME_TELEMETRY_SECS", os.getenv("KWS_TELEMETRY_SECS", "60"))))

COMMAND_ALIASES = {
    "go": "deal",
    "yes": "hit",
    "no": "stand",
    "on": "double",
    "stop": "reset",
    "up": "bet-up",
    "right": "bet-up",
    "down": "bet-down",
    "left": "bet-down",
    "off": "safe-bet",
}
GAME_ACTIONS = {"deal", "hit", "stand", "double", "reset", "bet-up", "bet-down", "safe-bet"}

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

cloud_bridge: Optional["IotConnectGameBridge"] = None


def restart_process():
    print("")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def local_package_name(package_url: str) -> str:
    candidate = Path(urlparse(package_url).path).name
    if candidate.endswith(".zip") or candidate.endswith(".tar.gz"):
        return candidate
    return "package.zip"


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

        script_file_path = Path(os.getcwd()) / "install.sh"
        if not script_file_path.is_file():
            print("install.sh not found in the current directory.")
            return True

        try:
            subprocess.run(["bash", str(script_file_path)], check=True)
            script_file_path.unlink(missing_ok=True)
            print("Successfully executed install.sh")
            return True
        except Exception as exc:
            script_file_path.unlink(missing_ok=True)
            print(f"Error executing install.sh: {exc}")
            return False
    except (subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile):
        return False


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


def resolve_config_file(config_dir: Path, env_var: str, candidate_names: tuple[str, ...], glob_patterns: tuple[str, ...]) -> Path:
    explicit_value = os.getenv(env_var, "").strip()
    if explicit_value:
        explicit_path = Path(explicit_value)
        return explicit_path if explicit_path.is_absolute() else config_dir / explicit_path

    for name in candidate_names:
        candidate = config_dir / name
        if candidate.is_file():
            return candidate

    for pattern in glob_patterns:
        matches = sorted(path for path in config_dir.glob(pattern) if path.is_file())
        if matches:
            return matches[0]

    return config_dir / candidate_names[0]


def make_card(rng: random.Random) -> dict:
    rank = rng.choice(RANKS)
    suit = rng.choice(SUITS)
    value = 11 if rank == "A" else 10 if rank in {"10", "J", "Q", "K"} else int(rank)
    return {"rank": rank, "suit": suit, "value": value}


def hand_total(cards: list[dict]) -> int:
    total = sum(card["value"] for card in cards)
    aces = sum(1 for card in cards if card["rank"] == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


class VoiceBlackjack:
    def __init__(self):
        self._lock = threading.Lock()
        self._rng = random.Random()
        self._spotter = self._make_spotter()
        self._running = True
        self._command_history: Deque[dict] = deque(maxlen=18)
        self._event_history: Deque[dict] = deque(maxlen=12)
        self.listening_enabled = os.getenv("KWS_AUTOSTART", "1").strip().lower() not in {"0", "false", "no", "off"}
        self.cloud_connected = False
        self.cloud_status = "disabled"
        self.model_name = self._spotter.settings.model_path.name
        self.model_sha256 = sha256_file(self._spotter.settings.model_path)
        self.model_package = read_package_info(self._spotter.settings.model_path.parent).get("package_name", "")
        self._reset_table()
        self._kws_thread = threading.Thread(target=self._kws_loop, daemon=True, name="kws-loop")
        self._kws_thread.start()

    @staticmethod
    def _normalize_command(label: str) -> str:
        normalized = str(label or "").strip().lower()
        return COMMAND_ALIASES.get(normalized, normalized)

    def _make_spotter(self) -> KeywordSpotter:
        model_path = MODEL_DIR / "model.tflite"
        if not model_path.is_file():
            model_path = MODEL_DIR / "ds_cnn_s_quantized.tflite"
        return KeywordSpotter(
            KwsSettings(
                model_path=model_path,
                labels_path=MODEL_DIR / "labels.txt",
                threshold=float(os.getenv("KWS_DETECTION_THRESHOLD", "0.80")),
                cooldown_secs=float(os.getenv("KWS_COOLDOWN_SECS", "1.2")),
                arecord_device=os.getenv("KWS_ARECORD_DEVICE") or None,
            )
        )

    def _reset_table(self):
        self.mode = "betting"
        self.bankroll = getattr(self, "bankroll", 500)
        self.best_bankroll = max(getattr(self, "best_bankroll", self.bankroll), self.bankroll)
        self.bet = min(max(getattr(self, "bet", 25), 5), max(5, self.bankroll))
        self.player_cards: list[dict] = []
        self.dealer_cards: list[dict] = []
        self.last_result = {"label": "", "confidence": 0.0, "detected": False}
        self.last_error = ""
        self.round_result = "Set your bet, then say DEAL"
        self.flash_text = "Voice Blackjack"
        self.flash_until = time.monotonic() + 60.0
        self.double_available = False
        self.hand_number = getattr(self, "hand_number", 0)
        self._append_event("READY", "Casino table is open")

    def _append_event(self, title: str, detail: str):
        self._event_history.appendleft({"title": title, "detail": detail, "at": time.strftime("%H:%M:%S")})

    def _append_command(self, label: str, confidence: float, detected: bool):
        self._command_history.appendleft(
            {"label": label, "confidence": round(confidence, 3), "detected": detected, "at": time.strftime("%H:%M:%S")}
        )

    def _set_flash(self, text: str, duration: float = 1.6):
        self.flash_text = text
        self.flash_until = time.monotonic() + duration

    def set_listening_enabled(self, enabled: bool):
        with self._lock:
            self.listening_enabled = bool(enabled)

    def set_cloud_status(self, connected: bool, status: str):
        with self._lock:
            self.cloud_connected = bool(connected)
            self.cloud_status = status

    def set_last_error(self, message: str):
        with self._lock:
            self.last_error = message
            if message:
                self._append_event("ERROR", message)

    def set_threshold(self, threshold: float):
        self._spotter.set_threshold(threshold)

    def _start_hand(self, source: str):
        if self.bankroll <= 0:
            self.bankroll = 500
            self.bet = 25
            self._append_event("RESET", "Bankroll restored to 500")

        self.hand_number += 1
        self.mode = "player_turn"
        self.player_cards = [make_card(self._rng), make_card(self._rng)]
        self.dealer_cards = [make_card(self._rng), make_card(self._rng)]
        self.double_available = self.bankroll >= self.bet * 2
        self.round_result = "Choose HIT, STAND, or DOUBLE"
        self._set_flash(f"Hand {self.hand_number} dealt", 1.8)
        self._append_event("DEAL", f"{source} started hand {self.hand_number} with bet {self.bet}")

        if hand_total(self.player_cards) == 21:
            self._stand(source, natural=True)

    def _dealer_play(self):
        while hand_total(self.dealer_cards) < 17:
            self.dealer_cards.append(make_card(self._rng))

    def _finish_hand(self, source: str, result: str):
        player = hand_total(self.player_cards)
        dealer = hand_total(self.dealer_cards)

        if result == "blackjack":
            winnings = int(self.bet * 1.5)
            self.bankroll += winnings
            self.round_result = f"Blackjack pays {winnings}"
            self._append_event("BLACKJACK", f"{source} hit blackjack for +{winnings}")
        elif result == "win":
            self.bankroll += self.bet
            self.round_result = f"You win {self.bet}"
            self._append_event("WIN", f"{source} beat dealer {dealer} to {player}")
        elif result == "push":
            self.round_result = "Push"
            self._append_event("PUSH", f"{source} tied dealer at {player}")
        else:
            self.bankroll -= self.bet
            self.round_result = f"You lose {self.bet}"
            self._append_event("LOSE", f"{source} lost hand with {player} against {dealer}")

        self.best_bankroll = max(self.best_bankroll, self.bankroll)
        self.bet = min(max(5, self.bet), max(5, self.bankroll if self.bankroll > 0 else 5))
        self.mode = "round_over"
        self.double_available = False
        self._set_flash(self.round_result, 2.5)

    def _hit(self, source: str):
        self.player_cards.append(make_card(self._rng))
        self.double_available = False
        total = hand_total(self.player_cards)
        self._append_event("HIT", f"{source} took a card to {total}")
        if total > 21:
            self._finish_hand(source, "lose")

    def _stand(self, source: str, natural: bool = False):
        self._dealer_play()
        player = hand_total(self.player_cards)
        dealer = hand_total(self.dealer_cards)

        if natural and player == 21 and dealer != 21:
            self._finish_hand(source, "blackjack")
            return
        if dealer > 21 or player > dealer:
            self._finish_hand(source, "win")
        elif dealer == player:
            self._finish_hand(source, "push")
        else:
            self._finish_hand(source, "lose")

    def _double_down(self, source: str):
        if not self.double_available or self.bankroll < self.bet * 2:
            return
        self.bet *= 2
        self.player_cards.append(make_card(self._rng))
        self.double_available = False
        total = hand_total(self.player_cards)
        self._append_event("DOUBLE", f"{source} doubled to {self.bet} and drew to {total}")
        if total > 21:
            self._finish_hand(source, "lose")
        else:
            self._stand(source)

    def handle_command(self, label: str, confidence: float, detected: bool, source_name: str = "voice"):
        with self._lock:
            command = self._normalize_command(label)
            self.last_result = {"label": command, "confidence": confidence, "detected": detected}
            self._append_command(command, confidence, detected)
            if not detected:
                return

            source = source_name

            if command == "deal":
                if self.mode in {"betting", "round_over"}:
                    self._start_hand(source)
                elif self.mode == "player_turn":
                    self._set_flash("Hand already active", 0.9)
                return

            if command == "reset":
                self._reset_table()
                self._append_event("RESET", f"{source} reset the table")
                return

            if self.mode == "betting":
                if command == "bet-up":
                    self.bet = min(self.bankroll, self.bet + 25) if self.bankroll > 0 else self.bet
                    self._set_flash(f"Bet set to {self.bet}", 1.0)
                elif command == "bet-down":
                    self.bet = max(5, self.bet - 25)
                    self._set_flash(f"Bet set to {self.bet}", 1.0)
                elif command == "safe-bet":
                    self.bet = 25 if self.bankroll >= 25 else max(5, self.bankroll)
                    self._set_flash(f"Safe bet {self.bet}", 1.0)
                elif command in {"hit", "stand", "double"}:
                    self._set_flash("Adjust bet or say DEAL", 0.9)
                return

            if self.mode != "player_turn":
                return

            if command == "hit":
                self._hit(source)
            elif command == "stand":
                self._stand(source)
            elif command == "double":
                self._double_down(source)
            elif command in {"bet-up", "bet-down", "safe-bet"}:
                self._set_flash("Wait for next hand to change bet", 0.9)

    def _kws_loop(self):
        while self._running:
            with self._lock:
                listening_enabled = self.listening_enabled

            if not listening_enabled:
                time.sleep(0.25)
                continue

            try:
                result = self._spotter.run_once()
                self.handle_command(result.label, result.confidence, result.detected, source_name="voice")
                if result.detected and cloud_bridge is not None:
                    cloud_bridge.send_telemetry(reason="event", detection_event=True)
            except Exception as exc:
                with self._lock:
                    self.last_error = str(exc)
                    self._append_event("AUDIO", self.last_error)
                time.sleep(1.0)

    def snapshot(self) -> dict:
        with self._lock:
            now = time.monotonic()
            return {
                "mode": self.mode,
                "bankroll": self.bankroll,
                "best_bankroll": self.best_bankroll,
                "bet": self.bet,
                "hand_number": self.hand_number,
                "player_cards": self.player_cards,
                "dealer_cards": self.dealer_cards,
                "player_total": hand_total(self.player_cards) if self.player_cards else 0,
                "dealer_total": hand_total(self.dealer_cards) if self.dealer_cards else 0,
                "dealer_bust": hand_total(self.dealer_cards) > 21 if self.dealer_cards else False,
                "double_available": self.double_available,
                "round_result": self.round_result,
                "flash_text": self.flash_text if now <= self.flash_until else "",
                "last_result": self.last_result,
                "last_error": self.last_error,
                "audio_device": self._spotter.audio_device_name(),
                "model_name": self.model_name,
                "model_package": self.model_package,
                "model_sha256": self.model_sha256,
                "detection_threshold": round(self._spotter.threshold, 4),
                "listening": self.listening_enabled,
                "cloud_connected": self.cloud_connected,
                "cloud_status": self.cloud_status,
                "command_history": list(self._command_history),
                "events": list(self._event_history),
            }


class IotConnectGameBridge:
    def __init__(self, table: VoiceBlackjack):
        self.table = table
        self.telemetry_secs = TELEMETRY_INTERVAL_SECS
        self.client: Optional[Client] = None  # type: ignore[type-arg]
        self.device_config = None
        self.enabled = False
        self.started = False
        self._next_periodic_at = 0.0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if Client is None or DeviceConfig is None:
            self.table.set_cloud_status(False, f"sdk unavailable: {SDK_IMPORT_ERROR}")
            return

        config_json = resolve_config_file(
            CONFIG_DIR,
            "KWS_DEVICE_CONFIG_FILE",
            ("iotcDeviceConfig.json",),
            ("*iotcDeviceConfig*.json",),
        )
        cert_path = resolve_config_file(
            CONFIG_DIR,
            "KWS_DEVICE_CERT_FILE",
            ("device-cert.pem", "cert_blackJack.crt"),
            ("cert_*.crt", "*device-cert*.pem", "*.crt"),
        )
        key_path = resolve_config_file(
            CONFIG_DIR,
            "KWS_DEVICE_PKEY_FILE",
            ("device-pkey.pem", "pk_blackJack.pem"),
            ("pk_*.pem", "*device-pkey*.pem", "*pkey*.pem"),
        )
        if not config_json.is_file() or not cert_path.is_file() or not key_path.is_file():
            self.table.set_cloud_status(False, "config files not found")
            return

        try:
            print(f"Using /IOTCONNECT config files: {config_json.name}, {cert_path.name}, {key_path.name}")
            self.device_config = DeviceConfig.from_iotc_device_config_json_file(
                device_config_json_path=str(config_json),
                device_cert_path=str(cert_path),
                device_pkey_path=str(key_path),
            )
        except DeviceConfigError as exc:
            self.table.set_cloud_status(False, str(exc))
            return

        self.client = Client(
            config=self.device_config,
            callbacks=Callbacks(  # type: ignore[operator]
                ota_cb=self.on_ota,
                command_cb=self.on_command,
                disconnected_cb=self.on_disconnect,
            ),
        )
        self.enabled = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="iotconnect-loop")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self.client is not None and self.client.is_connected():
            try:
                self.send_telemetry(reason="shutdown")
                self.client.disconnect()
            except Exception as exc:
                print(f"IotConnectGameBridge.stop: ignoring shutdown exception: {exc}")

    def ensure_connected(self):
        if self.client is None:
            raise RuntimeError("Client is not initialized")
        if self.client.is_connected():
            self.table.set_cloud_status(True, "connected")
            return
        print("(re)connecting to /IOTCONNECT...")
        self.client.connect()
        if not self.client.is_connected():
            self.table.set_cloud_status(False, "connect failed")
            raise RuntimeError("Unable to connect to /IOTCONNECT")
        self.table.set_cloud_status(True, "connected")

    def build_telemetry(self, detection_event: bool = False) -> dict:
        snapshot = self.table.snapshot()
        last_result = snapshot.get("last_result", {}) or {}
        return {
            "sdk_version": SDK_VERSION,
            "listening": snapshot["listening"],
            "game_mode": snapshot["mode"],
            "bankroll": snapshot["bankroll"],
            "best_bankroll": snapshot["best_bankroll"],
            "bet": snapshot["bet"],
            "hand_number": snapshot["hand_number"],
            "player_total": snapshot["player_total"],
            "dealer_total": snapshot["dealer_total"],
            "dealer_bust": snapshot["dealer_bust"],
            "double_available": snapshot["double_available"],
            "round_result": snapshot["round_result"],
            "last_command": last_result.get("label", ""),
            "last_command_confidence": round(float(last_result.get("confidence", 0.0)), 6),
            "last_command_detected": bool(detection_event and last_result.get("detected", False)),
            "audio_device": snapshot["audio_device"],
            "model_name": snapshot["model_name"],
            "model_package": snapshot["model_package"],
            "model_sha256": snapshot["model_sha256"],
            "detection_threshold": snapshot["detection_threshold"],
            "telemetry_interval": round(self.telemetry_secs, 3),
            "last_error": snapshot["last_error"],
        }

    def send_telemetry(self, reason: str = "periodic", detection_event: bool = False):
        if self.client is None or not self.client.is_connected():
            return
        telemetry = self.build_telemetry(detection_event=detection_event)
        self.client.send_telemetry(telemetry)
        print(f"Sent {reason} telemetry:", telemetry)

    def on_command(self, msg: C2dCommand):  # type: ignore[valid-type]
        print("Received command", msg.command_name, msg.command_args, msg.ack_id)
        command_name = VoiceBlackjack._normalize_command(msg.command_name)

        if command_name in GAME_ACTIONS:
            self.table.handle_command(command_name, 1.0, True, source_name="cloud")
            if msg.ack_id is not None:
                self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Executed {command_name}")  # type: ignore[union-attr]
            self.send_telemetry(reason="command")
            return

        if msg.command_name == "listen-start":
            self.table.set_listening_enabled(True)
            if msg.ack_id is not None:
                self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Voice control listening started")  # type: ignore[union-attr]
            self.send_telemetry(reason="command")
            return

        if msg.command_name == "listen-stop":
            self.table.set_listening_enabled(False)
            if msg.ack_id is not None:
                self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Voice control listening stopped")  # type: ignore[union-attr]
            self.send_telemetry(reason="command")
            return

        if msg.command_name == "set-threshold":
            if len(msg.command_args) != 1:
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")  # type: ignore[union-attr]
                return
            try:
                new_threshold = float(msg.command_args[0])
                if new_threshold < 0.0 or new_threshold > 1.0:
                    raise ValueError()
                self.table.set_threshold(new_threshold)
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Threshold set to {new_threshold:.3f}")  # type: ignore[union-attr]
                self.send_telemetry(reason="command")
            except ValueError:
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Threshold must be a decimal from 0.0 to 1.0")  # type: ignore[union-attr]
            return

        if msg.command_name == "set-interval":
            if len(msg.command_args) != 1:
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")  # type: ignore[union-attr]
                return
            try:
                new_interval = float(msg.command_args[0])
                if new_interval <= 0.0:
                    raise ValueError()
                self.telemetry_secs = max(1.0, new_interval)
                self._next_periodic_at = 0.0
                if msg.ack_id is not None:
                    self.client.send_command_ack(  # type: ignore[union-attr]
                        msg,
                        C2dAck.CMD_SUCCESS_WITH_ACK,
                        f"Telemetry interval set to {self.telemetry_secs:g} seconds",
                    )
                self.send_telemetry(reason="command")
            except ValueError:
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Interval must be a positive number of seconds")  # type: ignore[union-attr]
            return

        if msg.command_name == "refresh-state":
            if msg.ack_id is not None:
                self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Sending current state telemetry")  # type: ignore[union-attr]
            self.send_telemetry(reason="refresh")
            return

        if msg.command_name == "file-download":
            if len(msg.command_args) != 1:
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")  # type: ignore[union-attr]
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
                    self.client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Downloading {package_url}")  # type: ignore[union-attr]
                print(f"File downloaded successfully and saved to {package_name}")
                if extract_and_run_package(package_name):
                    print("Download command successful. Restarting the application...")
                    restart_process()
            except Exception as exc:
                error_message = f"Failed to download package: {exc}"
                print(error_message)
                if msg.ack_id is not None:
                    self.client.send_command_ack(msg, C2dAck.CMD_FAILED, error_message)  # type: ignore[union-attr]
            return

        print(f"Command {msg.command_name} not implemented")
        if msg.ack_id is not None:
            self.client.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")  # type: ignore[union-attr]

    def on_ota(self, msg: C2dOta):  # type: ignore[valid-type]
        print(f"Starting OTA downloads for version {msg.version}")
        self.client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)  # type: ignore[union-attr]
        extraction_success = False
        for url in msg.urls:
            print(f"Downloading OTA file {url.file_name} from {url.url}")
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
                print(f"ERROR: Unhandled file format for file {url.file_name}")

        if extraction_success is True:
            print("OTA successful. Restarting the application...")
            self.client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)  # type: ignore[union-attr]
            restart_process()
        else:
            print("Encountered a download processing error. Not restarting.")

    def on_disconnect(self, reason: str, disconnected_from_server: bool):
        print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))
        self.table.set_cloud_status(False, reason)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.ensure_connected()
                now_monotonic = time.monotonic()
                if not self.started or now_monotonic >= self._next_periodic_at:
                    self.send_telemetry(reason="startup" if not self.started else "periodic")
                    self.started = True
                    self._next_periodic_at = now_monotonic + self.telemetry_secs
            except Exception as exc:
                self.table.set_cloud_status(False, str(exc))
                print(exc)
            self._stop_event.wait(1.0)


table = VoiceBlackjack()
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return jsonify(table.snapshot())


@app.post("/api/action")
def api_action():
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command", "")).strip().lower()
    if not command:
        return jsonify({"ok": False, "error": "command is required"}), 400
    table.handle_command(command, 1.0, True, source_name="keyboard")
    if cloud_bridge is not None:
        cloud_bridge.send_telemetry(reason="local-action")
    return jsonify({"ok": True, "state": table.snapshot()})


def main():
    global cloud_bridge

    cloud_bridge = IotConnectGameBridge(table)
    cloud_bridge.start()

    print(f"Starting Voice Blackjack on http://{HOST}:{PORT}")
    print(f"Audio device: {table.snapshot()['audio_device']}")
    print(f"Model: {table.snapshot()['model_name']}")
    print(f"Model package: {table.snapshot()['model_package']}")
    print(f"IOTCONNECT config directory: {CONFIG_DIR}")
    print(f"Cloud status: {table.snapshot()['cloud_status']}")

    try:
        app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False, threaded=True)
    finally:
        if cloud_bridge is not None:
            cloud_bridge.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting.")
        sys.exit(0)
