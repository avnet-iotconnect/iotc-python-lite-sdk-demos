# /IOTCONNECT Drone Simulator (EC2 / any Linux host)

A Python simulator for the `tykho_drone` device template. It behaves like a quadcopter flight controller and feeds
the **Witekio and Indeema Drone Platform** dashboard without any hardware. It is designed to run unattended on an
EC2 instance (or any Linux machine with Python 3.9+) as a systemd service.

## What it does

* Reports every attribute in the `tykho_drone` template: `Attitude`, `Battery`, `Motor`, `Gyroscope`,
  `Accelerometer`, `Altitude`, `ControllerInfo` and `DemoOn`.
* **Normal mode:** sends one telemetry message every **90 seconds**.
* **Demo mode:** sends one telemetry message every **3 seconds** and flies a scripted mission
  (take off, cruise with turns, hover, land, repeat) so every gauge and chart on the dashboard moves.
* Demo mode is triggered by the dashboard's **Demo** button. The button sends the `demo 5 60 1010` command; the
  first argument is treated as the demo length in minutes, so the default demo lasts 5 minutes and then the
  simulator lands the drone and drops back to the 90 second cadence. Pressing the button again restarts the timer.

### Cloud-to-device commands

All commands are already defined in the `tykho_drone` template.

| Command | Sent by | Effect |
|---|---|---|
| `demo [minutes]` | Demo button (`demo 5 60 1010`) | Demo mode for N minutes (default 5). `demo 0` or `demo off` stops it. |
| `on` | manual | Demo mode with no time limit. |
| `off` | manual | Stop demo mode. |
| `pwm <1000-2000>` | Throttle and Motor switches | Sets the commanded motor PWM. Values of 1100 and above spin up and hover outside demo mode. |
| `SetInterval <secs> [demo_secs]` | manual | Changes the normal (and optionally demo) reporting interval at runtime. |

## Files

| Path | Purpose |
|---|---|
| `src/app.py` | The simulator. |
| `setup-ec2.sh` | One-shot installer: installs Python, the SDK, your credentials and a systemd service. |
| `drone-simulator.service` | systemd unit template used by the installer. |
| `reference/tykho_drone_template.json` | The device template export. Import this if the template is missing from your account. |
| `reference/drone_platform_dashboard_export.json` | The dashboard export. Import this if you need to recreate the dashboard. |

Credentials are intentionally **not** in this repository. Ignore rules in this directory prevent `*.pem`, `*.crt`
and `iotcDeviceConfig*.json` from being committed.

## 1. Prerequisites in /IOTCONNECT

You need a device created from the `tykho_drone` template with X.509 (self-signed or CA) authentication, and the
three files that /IOTCONNECT gives you for it:

* `iotcDeviceConfig.json` (download it with the paper-and-cog icon on the device's info panel)
* the device certificate (for example `cert_drone1.crt`)
* the device private key (for example `pk_drone1.pem`)

The exported dashboard is bound to the device unique ID `drone1`. If you use a different device ID, edit the
dashboard widgets to point at your device.

## 2. Install on EC2

1. Launch an EC2 instance with Amazon Linux 2023 or Ubuntu 22.04+. It only needs **outbound** HTTPS (443) and
   MQTT over TLS (8883); no inbound ports are required.
2. Copy the three credential files to the instance, for example:

   ```bash
   scp -i my-key.pem iotcDeviceConfig.json cert_drone1.crt pk_drone1.pem ec2-user@<EC2_PUBLIC_IP>:~/
   ```

3. On the instance, clone this repository and run the installer:

   ```bash
   sudo dnf install -y git          # apt-get install -y git on Ubuntu
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   cd iotc-python-lite-sdk-demos/drone-simulator
   bash ./setup-ec2.sh ~/iotcDeviceConfig.json ~/cert_drone1.crt ~/pk_drone1.pem
   ```

   The installer puts everything in `/opt/drone-simulator`, creates a virtual environment with the
   [/IOTCONNECT Python Lite SDK](https://github.com/avnet-iotconnect/iotc-python-lite-sdk), and starts the
   `drone-simulator` service so it survives reboots.

4. Watch it connect and report:

   ```bash
   sudo journalctl -u drone-simulator -f
   ```

   You should see `MQTT connected` followed by a line like `[normal] alt=0cm hdg=213 pwm=1000 batt=25.08V 0.2A`
   every 90 seconds. Open the dashboard and press **Demo**: the log switches to `[DEMO (299s left)]` lines every
   3 seconds and the gauges start moving.

### Changing the intervals

Edit `/opt/drone-simulator/simulator.env` and restart the service:

```bash
sudo nano /opt/drone-simulator/simulator.env     # NORMAL_INTERVAL_SECS, DEMO_INTERVAL_SECS, DEMO_DURATION_MINUTES
sudo systemctl restart drone-simulator
```

## 3. Running manually (without systemd)

```bash
pip3 install iotconnect-sdk-lite
cd drone-simulator/src
python3 app.py --config ~/iotcDeviceConfig.json --cert ~/cert_drone1.crt --key ~/pk_drone1.pem
```

Useful options:

```
--normal-interval 90     seconds between messages outside demo mode
--demo-interval 3        seconds between messages in demo mode
--demo-duration 5        default demo length in minutes
--quiet                  less SDK logging
--dry-run                print telemetry locally without connecting (add --dry-run-demo to start in demo mode)
```

Environment variables `IOTC_DEVICE_CONFIG`, `IOTC_DEVICE_CERT`, `IOTC_DEVICE_KEY`, `NORMAL_INTERVAL_SECS`,
`DEMO_INTERVAL_SECS` and `DEMO_DURATION_MINUTES` can be used instead of the flags.

## 4. Dashboard notes

The dashboard widgets map to the telemetry as follows:

* **Motor 1..4 RPM gauges** show `Motor.PWM1..PWM4`.
* **Drone Altitude (cm)** shows `Altitude`.
* **HEADING / ROLL / PITCH** and **Drone Orientation** show `Attitude.heading`, `Attitude.angX`, `Attitude.angY`.
* **Battery Consumption / Battery Stats** show the `Battery` object. The simulated pack is a 6S 5200 mAh battery
  that drains under load and is "swapped" automatically when it gets low while landed.
* **Flight Controller Information** shows the static `ControllerInfo` fields.
* **Demo** button sends `demo 5 60 1010`, **Throttle** and **Motor** switches send `pwm <value>`.
