# RZ/G3E Vision Demo — Quick Start

Get from a booted RZ/G3E EVK to the live dashboard below in about 20 minutes.
The full reference is in [README.md](README.md); the presenter script is in [DEMO.md](DEMO.md).

<img src="media/rzg3e-vision-dashboard.jpg" alt="RZ/G3E Vision Demo dashboard" width="900" />

1. [What you need](#1-what-you-need)
2. [Prepare the board](#2-prepare-the-board)
3. [Import the template and dashboard](#3-import-the-template-and-dashboard)
4. [Install the demo](#4-install-the-demo)
5. [Run and verify](#5-run-and-verify)
6. [Try the cloud commands](#6-try-the-cloud-commands)

## 1. What you need

* RZ/G3E EVK flashed and reachable over SSH, with the /IOTCONNECT Lite SDK installed
  (sections 1–5 of [the board QuickStart](../README.md)).
* Two UVC USB cameras in the **USB 2.0 Type-A ports on the carrier's hub** (other ports may
  not enumerate). One camera also works; both pipelines then share it.
* Internet access from the board (one-time ~42 MB model download).
* A PC with Git Bash, WSL or Linux for `scp`.

## 2. Prepare the board

The stock SD image ends the root partition at 1.1 GB and it is nearly full. Grow it once
(root stays mounted; check the start sector with `fdisk -l /dev/mmcblk1` first):

```bash
printf "d\n2\nn\np\n2\n44880\n\nw\n" | fdisk /dev/mmcblk1
reboot
resize2fs /dev/mmcblk1p2
df -h /        # should now show the full card
```

## 3. Import the template and dashboard

### Device template

1. In /IOTCONNECT go to **Devices → Templates → Create Template → Import**.
2. Import [rzg3e-vision-template.json](rzg3e-vision-template.json) and save.
3. Create a device from the template (**Devices → Create Device**), download its
   `iotcDeviceConfig.json` and its certificate zip. See
   [the UI onboarding guide](../../common/general-guides/UI-ONBOARD.md) if needed.

### Dashboard

1. Go to **Create Dashboard → Import Dashboard**.
2. Upload [rzg3e-vision-dashboard.json](rzg3e-vision-dashboard.json).
3. Save, then map the widgets to your device when prompted (the export references the
   device it was built on).

## 4. Install the demo

On your PC, from this folder:

```bash
bash create-package.sh
scp package.tar.gz root@<board-ip>:/opt/demo/
```

On the board:

```bash
mkdir -p /opt/demo && cd /opt/demo
tar -xzf package.tar.gz && bash install.sh
```

Then copy the credentials from step 3 into `/opt/demo` under these exact names:

| File from /IOTCONNECT | Name on the board |
|---|---|
| `iotcDeviceConfig.json` | `/opt/demo/iotcDeviceConfig.json` |
| `cert_<device>.crt` (from the zip) | `/opt/demo/device-cert.pem` |
| `pk_<device>.pem` (from the zip) | `/opt/demo/device-pkey.pem` |

```bash
systemctl restart iotc-demo
```

The service is enabled, so the demo also starts by itself at every power-up.

## 5. Run and verify

* `tail -f /opt/demo/app.log` shows the connection sequence and one line per telemetry
  sample every 5 seconds.
* Open `http://<board-ip>:8080/` for both annotated feeds and a live stats strip.
* In /IOTCONNECT the device shows **Connected** and the dashboard tiles start moving:
  CPU, detector and face FPS gauges, zone entries/exits, identities in view.

Expected numbers with both cameras running: face pipeline ~60 ms per frame at 8 fps,
person detector ~350 ms per frame at ~2.7 fps, CPU around 75–85 %.

## 6. Try the cloud commands

From the dashboard's **Device Command** widget (or the device's Command tab):

| Try this | You should see |
|---|---|
| Stand in front of camera 1 | red box, `unknown`; **Identity Watch** shows an unknown person |
| `enroll <your name>` | yellow box counting to 5/5, ack *enrolled &lt;name&gt; (5 samples)*; box turns green with your name |
| `forget <your name>` | back to red / unknown |
| Walk through camera 2's zone | track ID and dwell timer; **Zone Entries / Exits** tick up |
| `set_zone 0,0,0.5,1` | zone moves to the left half of the frame |
| `set_mode faces` then `set_mode both` | detector gauge stops, CPU drops, face time falls to ~24 ms |
| `set_mirror off` | feeds stop being mirrored |
| `reset_counts` | entries and exits back to 0 |

The full command list is in [README.md](README.md#5-commands).
