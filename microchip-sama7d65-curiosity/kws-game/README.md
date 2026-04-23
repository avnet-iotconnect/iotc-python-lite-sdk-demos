# Voice Blackjack (KWS Game)

Upgrades the /IOTCONNECT Starter Demo on the Microchip SAMA7D65-Curiosity Kit to a voice-controlled blackjack game served from the board's browser UI and connected to /IOTCONNECT for telemetry and cloud commands.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the Microchip SAMA7D65-Curiosity Kit](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/blob/main/microchip-sama7d65-curiosity/README.md) before proceeding.

> [!IMPORTANT]
> This demo uses the same USB microphone and keyword spotting pipeline as the [Keyword Spotting Demo](../kws-demo/README.md). The two demos cannot run at the same time — this game replaces the basic KWS demo on the device.

## 1. Introduction

Voice Blackjack runs a blackjack game locally on the board, exposes a browser UI over the board's local network, and uses a TensorFlow Lite keyword spotter to accept voice commands from a USB microphone. Game state, bankroll, and inference results are published as telemetry to /IOTCONNECT and can also be controlled via cloud commands.

The recognized voice commands are: `deal`, `hit`, `stand`, `double`, `reset`

Bet control uses on-screen buttons, arrow keys, or `F` for a safe default bet.

## 2. Visual Tour

<table>
  <tr>
    <td width="50%">
      <img src="../media/kws-blackjack-1.jpg" alt="Voice Blackjack main game board" />
      <br />
      <sub>Main game view with the active bankroll, bet, hand state, and current voice command list.</sub>
    </td>
    <td width="50%">
      <img src="../media/kws-blackjack-2.jpg" alt="Voice Blackjack controls and event log" />
      <br />
      <sub>Table controls and the event log make it easy to test voice actions against keyboard and button fallbacks.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="../media/kws-blackjack-iotc-latest_value.jpg" alt="IOTCONNECT latest value view for blackjack demo" />
      <br />
      <sub>The Latest Value view shows the current game state, active model package, detection threshold, and last command outcome.</sub>
    </td>
    <td width="50%">
      <img src="../media/kws-blackjack-iotc-commands.jpg" alt="IOTCONNECT commands view for blackjack demo" />
      <br />
      <sub>The Commands view lets operators trigger actions like <code>deal</code>, <code>hit</code>, and <code>reset</code> from the cloud.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="../media/kws-blackjack-iotc-live.jpg" alt="IOTCONNECT live data stream for blackjack demo" />
      <br />
      <sub>Live Data shows the raw telemetry stream exactly as the board publishes it during gameplay.</sub>
    </td>
    <td width="50%">
      <img src="../media/kws-blackjack-iotc-live_tabular.jpg" alt="IOTCONNECT tabular live data for blackjack demo" />
      <br />
      <sub>The tabular view is useful when you want to scan game-mode, totals, bankroll, and command history as structured fields.</sub>
    </td>
  </tr>
</table>

## 3. Import the Optional Dashboard

If you want the same /IOTCONNECT dashboard layout used during this demo, import the packaged dashboard export:

- [Microchip_Blackjack_Dash_dashboard_export.json](./dashboards/Microchip_Blackjack_Dash_dashboard_export.json)

Import flow:

1. Create the game template and device first (follow the steps in section 4 below).
2. In /IOTCONNECT, open **Dashboards**.
3. Choose the dashboard import option and upload `Microchip_Blackjack_Dash_dashboard_export.json`.
4. Open the imported dashboard and edit the embedded game widget URL so it points at your board:

```text
http://<board-ip>:8080
```

5. If your device unique ID is not `blackJack`, rebind the widgets to your actual device after import.

> [!NOTE]
> The export was captured from a working `blackJack` device, so some widget bindings may still reference that device identity when first imported.

## 4. Set Up Hardware and Template

1. Plug a USB microphone into one of the board's USB host ports.
2. Confirm the microphone is visible to ALSA:

```bash
arecord -l
```

3. Create your device in /IOTCONNECT with [kws-game-template.json](./kws-game-template.json).

> [!NOTE]
> The template code is `sama7d6Bj`. Template codes are limited to 10 characters on /IOTCONNECT.

The template exposes game state, bankroll, current command outcome, audio/model metadata, threshold, and telemetry interval. Template commands include both game actions (`deal`, `hit`, `stand`, `double`, `reset`, `bet-up`, `bet-down`, `safe-bet`) and runtime controls (`listen-start`, `listen-stop`, `set-threshold`, `set-interval`, `refresh-state`, `file-download`).

## 5. Deploy and Run

### Download and Install

On the board, run:

```bash
cd /opt/demo
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/main/microchip-sama7d65-curiosity/kws-game/packages/kws-game-package.zip
python3 -m zipfile -e kws-game-package.zip .
bash ./install.sh
```

### Run

```bash
cd /opt/demo
python3 game_app.py
```

Then open a browser on your local network to:

```
http://<board-ip>:8080
```

## 6. Telemetry

The game sends telemetry on startup, on a 60-second heartbeat, after an accepted voice detection, and after a cloud or local control action.

| Field | Description |
|---|---|
| `game_mode` | Current game state (`betting`, `player_turn`, `round_over`) |
| `bankroll` | Current chip total |
| `best_bankroll` | Highest bankroll reached this session |
| `bet` | Current bet amount |
| `hand_number` | Hands played this session |
| `player_total` / `dealer_total` | Current hand totals |
| `round_result` | Outcome of the last completed hand |
| `last_command` / `last_command_confidence` | Most recent voice or cloud command and its confidence |
| `audio_device` | ALSA capture device in use |
| `model_name` / `model_package` / `model_sha256` | Active model metadata |
| `detection_threshold` / `telemetry_interval` | Current runtime settings |

## 7. Commands

**Game actions:** `deal`, `hit`, `stand`, `double`, `reset`, `bet-up`, `bet-down`, `safe-bet`

**Runtime controls:** `listen-start`, `listen-stop`, `set-threshold`, `set-interval`, `refresh-state`, `file-download`

## 8. Keyboard Fallback

| Key | Action |
|---|---|
| `Enter` or `Space` | `deal` |
| `H` | `hit` |
| `S` | `stand` |
| `D` | `double` |
| `Arrow Up` / `Arrow Right` | `bet-up` |
| `Arrow Down` / `Arrow Left` | `bet-down` |
| `F` | `safe-bet` |
| `Esc` | `reset` |

## 9. Customize and Rebuild (Optional)

To modify the demo before deploying, edit files in `src/` and then rebuild:

```bash
bash ./create-package.sh
```

This regenerates `package.zip`, `packages/kws-game-package.zip`, and `../../common/package.zip`.

To deliver the updated package, use scp or OTA via /IOTCONNECT (see the [kws-demo Customize and Rebuild section](../kws-demo/README.md#7-customize-and-rebuild-optional) for the general OTA steps, substituting the `sama7d6Bj` template and the kws-game package file).

## 10. Environment Overrides

```bash
export KWS_AUTOSTART=1
export KWS_DETECTION_THRESHOLD=0.80
export KWS_COOLDOWN_SECS=1.2
export KWS_GAME_TELEMETRY_SECS=60
export KWS_ARECORD_DEVICE=plughw:0,0
export KWS_MODEL_DIR=/opt/demo/models
export KWS_CONFIG_DIR=/opt/demo
export KWS_GAME_PORT=8080
```

`KWS_CONFIG_DIR` points the app at the directory containing `iotcDeviceConfig.json`, `device-cert.pem`, and `device-pkey.pem`. Defaults to the current working directory. `KWS_GAME_PORT` sets the Flask server port (default `8080`).
