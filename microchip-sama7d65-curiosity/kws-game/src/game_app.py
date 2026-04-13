from __future__ import annotations

import random
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque

from flask import Flask, jsonify, render_template, request

from kws_engine import KeywordSpotter, KwsSettings


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(__import__("os").getenv("KWS_MODEL_DIR", BASE_DIR / "models"))
HOST = __import__("os").getenv("KWS_GAME_HOST", "0.0.0.0")
PORT = int(__import__("os").getenv("KWS_GAME_PORT", "8080"))
DEBUG = __import__("os").getenv("KWS_GAME_DEBUG", "0").strip() in {"1", "true", "yes"}

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


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
        self._reset_table()
        self._kws_thread = threading.Thread(target=self._kws_loop, daemon=True, name="kws-loop")
        self._kws_thread.start()

    def _make_spotter(self):
        model_path = MODEL_DIR / "model.tflite"
        if not model_path.is_file():
            model_path = MODEL_DIR / "ds_cnn_s_quantized.tflite"
        return KeywordSpotter(
            KwsSettings(
                model_path=model_path,
                labels_path=MODEL_DIR / "labels.txt",
                threshold=float(__import__("os").getenv("KWS_DETECTION_THRESHOLD", "0.80")),
                cooldown_secs=float(__import__("os").getenv("KWS_COOLDOWN_SECS", "1.2")),
                arecord_device=__import__("os").getenv("KWS_ARECORD_DEVICE") or None,
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
        self.round_result = "Set your bet, then say GO"
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

    def handle_command(self, label: str, confidence: float, detected: bool, manual: bool = False):
        with self._lock:
            self.last_result = {"label": label, "confidence": confidence, "detected": detected}
            self._append_command(label, confidence, detected)
            if not detected:
                return

            source = "keyboard" if manual else "voice"

            if label == "go":
                if self.mode in {"betting", "round_over"}:
                    self._start_hand(source)
                return

            if label == "stop":
                self._reset_table()
                self._append_event("STOP", f"{source} reset the table")
                return

            if self.mode == "betting":
                if label in {"up", "right"}:
                    self.bet = min(self.bankroll, self.bet + 25) if self.bankroll > 0 else self.bet
                    self._set_flash(f"Bet set to {self.bet}", 1.0)
                elif label in {"down", "left"}:
                    self.bet = max(5, self.bet - 25)
                    self._set_flash(f"Bet set to {self.bet}", 1.0)
                elif label == "on":
                    self.bet = min(self.bankroll, max(50, self.bankroll // 2)) if self.bankroll > 0 else self.bet
                    self._set_flash(f"Power bet {self.bet}", 1.0)
                elif label == "off":
                    self.bet = 25 if self.bankroll >= 25 else max(5, self.bankroll)
                    self._set_flash(f"Safe bet {self.bet}", 1.0)
                return

            if self.mode != "player_turn":
                return

            if label == "yes":
                self._hit(source)
            elif label == "no":
                self._stand(source)
            elif label == "on":
                self._double_down(source)
            elif label in {"up", "right"}:
                self._set_flash("YES = Hit", 0.9)
            elif label in {"down", "left"}:
                self._set_flash("NO = Stand", 0.9)
            elif label == "off":
                self._set_flash("ON = Double Down", 0.9)

    def _kws_loop(self):
        while self._running:
            try:
                result = self._spotter.run_once()
                self.handle_command(result.label, result.confidence, result.detected)
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
                "model_name": self._spotter.settings.model_path.name,
                "command_history": list(self._command_history),
                "events": list(self._event_history),
            }


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
    table.handle_command(command, 1.0, True, manual=True)
    return jsonify({"ok": True, "state": table.snapshot()})


def main():
    print(f"Starting Voice Blackjack on http://{HOST}:{PORT}")
    print(f"Audio device: {table.snapshot()['audio_device']}")
    print(f"Model: {table.snapshot()['model_name']}")
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
