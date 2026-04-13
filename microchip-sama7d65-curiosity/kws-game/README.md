# KWS Game

Hosts a local Flask game on the Microchip SAMA7D65-Curiosity Kit and uses the USB microphone keyword spotter as the controller.

## Concept

`Voice Blackjack` is a familiar, strategic table game that tolerates command latency much better than a reflex game.

Voice mapping:

- `go`: deal a new hand
- `yes`: hit
- `no`: stand
- `on`: double down
- `up` or `right`: increase bet by `25`
- `down` or `left`: decrease bet by `25`
- `off`: return to a safe default bet
- `stop`: reset the table

The game runs entirely on the board and is viewed from a browser connected to the board's IP address.

## Run On The Board

```bash
cd /root/kws-game
LD_LIBRARY_PATH=/root/kws-demo/libs:$LD_LIBRARY_PATH \
KWS_ARECORD_DEVICE=plughw:0,0 \
KWS_MODEL_DIR=/root/kws-game/models \
KWS_GAME_PORT=8081 \
/root/kws-venv/bin/python -u /root/kws-game/game_app.py
```

Then open:

```text
http://<board-ip>:8081
```

## Keyboard Fallback

- `Enter` or `Space`: deal
- `Y`: hit
- `N`: stand
- `O`: double down
- arrow keys: adjust bet
- `F`: safe bet
- `Esc`: reset

## Install Notes

- `Flask` must be installed in the Python environment used to launch the game.
- The game reuses the same TensorFlow Lite model and labels format as the KWS demo.
