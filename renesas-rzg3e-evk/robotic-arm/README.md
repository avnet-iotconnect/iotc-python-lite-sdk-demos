# Renesas RZ/G3E EVK + /IOTCONNECT XArm Vision Demo

Port of the [TRIA Vision AI Kit 6490 robotic-arm demo](https://github.com/avnet-iotconnect/iotc-tria-vision-ai-kit-robotic-arm)
to the **Renesas RZ/G3E Evaluation Board Kit**. The demo controls a Hiwonder
XArm 1S over USB and streams telemetry / accepts commands from /IOTCONNECT.
Two interchangeable vision modes are available, selected at launch with `--mode`:

- **`ball`** (default, recommended on RZ/G3E) — autonomous eye-in-hand visual
  servoing. A wrist-mounted USB camera segments a colored ball by HSV; the
  arm pans / tilts / advances on its own to center, approach, and grab it.
  Only depends on OpenCV + NumPy + the xarm bus-servo library.
- **`asl`** — American Sign Language gesture control via MediaPipe + a small
  PointNet model. Heavy ML dependencies (`torch`, `mediapipe`) — **best-effort
  on the RZ/G3E**, see the [Mode availability](#mode-availability) section.

## TL;DR — fresh-board quick start

After completing the base [Renesas RZ/G3E EVK QuickStart](../README.md):

```bash
# 1. On the host PC (Git Bash / WSL / Linux):
ssh root@<BOARD-IP> python3 --version              # confirm: Python 3.12.x
wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/renesas-rzg3e-evk/robotic-arm/scripts/deps-download.sh \
  && bash ./deps-download.sh <BOARD-IP>

# 2. On the board:
bash ~/robotic-arm/scripts/deps-install.sh         # expect: cv2, numpy, xarm, hid, avnet... = OK

# 3. (Onboard the device in /IOTCONNECT, download the cert bundle, then
#     copy + rename the three files to ~/robotic-arm/ — see §4.)

# 4. Calibrate the ball color, then run:
cd ~/robotic-arm
./calibrate.sh                                     # browser at http://<BOARD-IP>:8000/
./start.sh --headless --web-port 8000              # demo + live browser view
```

Open `http://<BOARD-IP>:8000/` in any browser on the same LAN to watch the
camera feed with detection overlay during both calibration and the live demo.

## 1. Prerequisites

Complete the base [Renesas RZ/G3E EVK QuickStart](../README.md) first. That
guide covers flashing the SD-card image, bootloader setup, network bring-up,
and installing the /IOTCONNECT Lite SDK on the board. This demo additionally
assumes:

- The board boots, has a working ethernet connection, and you can SSH to it
  as `root` (the shipped image enables passwordless root SSH).
- The IoTConnect SDK is installed:
  `ssh root@<BOARD-IP> python3 -c "import avnet.iotconnect.sdk.lite"` succeeds.
- The board's Python is **3.12.x** (the shipped Yocto `rz-vlp 5.0.8` image
  uses 3.12.9). Confirm with `ssh root@<BOARD-IP> python3 --version`. The
  wheel-download script defaults to `cp312`; if your image differs, override
  with `PY_VER=cp311 bash deps-download.sh <ip>` or similar.

> [!NOTE]
> The Yocto image strips several Python stdlib modules (`resource`,
> `multiprocessing`, `statistics`). The demo source has been written to
> not depend on any of them — but if you adapt the code, be aware that
> packages like `psutil` and `py-cpuinfo` will not import here.

## 2. Additional Hardware

In addition to the items in the base QuickStart:

- **[Hiwonder XArm 1S](https://www.amazon.com/LewanSoul-Programmable-Feedback-Parameter-Programming/dp/B0CHY63V9P?th=1)** —
  USB-connected 6-DOF robotic arm with gripper. Powered separately from the
  RZ/G3E.
- **USB camera** — a UVC-class USB webcam (verified with the Logitech Brio
  100 and the eMeet C960). Mount on the wrist-roll servo with zip ties so it
  pitches with the gripper. A bare USB-camera PCB module behind the gripper
  jaws is best for `ball` mode (cleanest line of sight, removes parallax).
  The kernel exposes the camera as `/dev/video0` on this board.

You do **not** need an HDMI monitor. The RZ/G3E ships without a working
display server, and the demo is designed to be operated entirely from a
host PC (terminal over SSH, browser for video). If you have a USB hub
between the board and the camera + arm, prefer a **powered** hub — the
Brio 100 + arm together can exceed what a single bus-powered USB-C port
will deliver.

## 3. Install Demo Dependencies

The base RZ/G3E image does not ship pip repositories, so dependencies are
fetched on the host PC and transferred to the board (the same pattern the
base QuickStart uses for the IoTConnect SDK).

1. **Find the board's IP** — on the board's serial console:
   ```
   ip a
   ```
   Note the `inet` address under `end0`.

2. **On the host PC** (Git Bash / WSL / Linux), confirm the board's Python
   version (wheel ABI tags must match exactly):
   ```
   ssh root@<BOARD-IP> python3 --version
   ```
   The shipped image uses Python **3.12**, which is the script's default. If
   you're on a different image, prepend `PY_VER=cp311` (or the matching tag).

3. Run the download script. It fetches aarch64 wheels for the demo's Python
   deps, clones the demo source tree, and `scp`'s everything to the board:
   ```
   wget https://raw.githubusercontent.com/avnet-iotconnect/iotc-python-lite-sdk-demos/refs/heads/main/renesas-rzg3e-evk/robotic-arm/scripts/deps-download.sh \
     && bash ./deps-download.sh <BOARD-IP>
   ```
   > [!NOTE]
   > The script will skip `torch`, `torchvision`, and `mediapipe` if no
   > matching aarch64 wheel is available on PyPI. That's expected — those
   > packages drive the optional `asl` mode. The required wheels for `ball`
   > mode (`opencv-python-headless`, `numpy`, `xarm`, `hidapi`, `requests`)
   > all ship aarch64 wheels.

4. **On the board**, install the transferred wheels:
   ```
   bash ~/robotic-arm/scripts/deps-install.sh
   ```
   The script ends with a module availability check. On a healthy install
   you should see:
   ```
   Module availability check:
     OK    : cv2
     OK    : numpy
     OK    : xarm
     OK    : hid
     OK    : avnet.iotconnect.sdk.lite
     MISS  : torch                  <-- normal — only needed for `asl` mode
     MISS  : mediapipe              <-- normal — only needed for `asl` mode
   ```
   The `MISS` lines for `torch` / `mediapipe` are expected. If anything
   else shows `MISS`, see [Troubleshooting](#troubleshooting).

## 4. Onboard the Device to /IOTCONNECT

Follow [this guide](../../common/general-guides/UI-ONBOARD.md) to register
the RZ/G3E to /IOTCONNECT. You'll get back three files from the cloud
console — typically with names like:

- `iotcDeviceConfig (N).json`
- `cert_<deviceID>.crt`
- `pk_<deviceID>.pem`

The demo expects fixed names. From the host PC, copy them to the board with
the renames baked in:

```bash
DOWNLOAD=~/Downloads/<your-cert-folder>
scp "$DOWNLOAD/iotcDeviceConfig (N).json" root@<BOARD-IP>:~/robotic-arm/iotcDeviceConfig.json
scp "$DOWNLOAD/cert_<deviceID>.crt"       root@<BOARD-IP>:~/robotic-arm/device-cert.pem
scp "$DOWNLOAD/pk_<deviceID>.pem"         root@<BOARD-IP>:~/robotic-arm/device-pkey.pem
ssh root@<BOARD-IP> chmod 600 ~/robotic-arm/device-pkey.pem
```

Confirm with a quick smoke test on the board:

```
cd ~/robotic-arm && python3 -c "
from avnet.iotconnect.sdk.lite import DeviceConfig
DeviceConfig.from_iotc_device_config_json_file(
    device_config_json_path='iotcDeviceConfig.json',
    device_cert_path='device-cert.pem',
    device_pkey_path='device-pkey.pem',
); print('iotc config OK')"
```

The supplied [`robArm2_template.json`](robArm2_template.json) defines the
device-template attributes the demo publishes (gripper, wrist_roll,
wrist_flex, elbow_flex, shoulder_lift, shoulder_pan, the `state` label,
the `ballTrack` block, plus system telemetry). Import it as a custom
template in /IOTCONNECT before creating the device.

If you skip this section the demo still runs — it just prints `IoTConnect
is unavailable; running without cloud connectivity` and proceeds with
local-only operation.

## 5. Calibrate the Ball

> [!WARNING]
> Both calibration scripts release **all six servo torques** so you can
> free-pose the arm. **Always physically support the arm before pressing
> Enter** — on a wall- or ceiling-mounted arm the whole assembly will swing
> under gravity the instant torque drops.

### Step 1 — Ball color *(required)*

Captures HSV thresholds for ball segmentation. Writes `ball_color.json`.

```
cd ~/robotic-arm
./calibrate.sh
```

Because the RZ/G3E has no display server (and we install
`opencv-python-headless`), `calibrate.sh` defaults to the browser-based
calibrator [`browser_calibrate.py`](browser_calibrate.py). On startup it
prints a URL like:

```
[calib] HTTP listening on http://192.168.68.68:8000/
```

Open that URL from any laptop on the same LAN. The page shows a live
MJPEG video feed from the wrist camera; **click directly on the ball** in
the image to sample its HSV (each click samples a 7×7 patch). Hold the
ball under your demo lighting and click 5–10 times — you'll see a green
mask overlay grow to cover the ball as samples accumulate.

Page controls:

| Button             | What it does                                                                     |
|--------------------|----------------------------------------------------------------------------------|
| **Save & Quit**    | Writes `ball_color.json` and exits the script. Normal exit path. (green button) |
| **Save**           | Writes the file but keeps the page open so you can keep adding samples and re-save. |
| **Reset**          | Clears all samples (does not touch the on-disk file).                            |
| **Hold pose**      | Re-engages torque at the current arm pose so you can let go.                     |
| **Release torque** | Drops torque again so you can re-pose the camera.                                |
| **Quit**           | Exits without saving (warns if you have unsaved samples).                        |

`s` / `r` / `h` / `w` keystrokes work in the page as shortcuts.

If you have a working display attached and want the original cv2-window
calibrator instead, run `BROWSER=0 ./calibrate.sh` (uses
[`ball_calibrate.py`](ball_calibrate.py) — note: this won't render
because of `opencv-python-headless`).

### Step 2 — Scan poses *(required if your arm mount differs from the upstream demo)*

Captures the arm poses cycled through during `SCANNING`. Torque drops so
you can pose the arm by hand. This script prints to the console; no
browser needed.

```
./teach.sh
```

For each of `center` / `left edge` / `right edge`, pose the camera then
press `s` + Enter to snapshot. The script prints a `SCAN_POSE = [...]`
block ready to paste into [modes/ball_follow.py](modes/ball_follow.py).
`h` + Enter re-enables torque, `q` + Enter quits.

The poses pre-baked in [modes/ball_follow.py](modes/ball_follow.py:90)
were captured for a wall/VESA-mounted arm looking down at a table. If
your arm is on a benchtop base, recapture them.

### Step 3 — Camera-gripper offset + grab radius *(run when you change ball/gripper/camera)*

Reports three values you can paste into [modes/ball_follow.py](modes/ball_follow.py):

- `CAM_GRIPPER_OFFSET_X` / `_Y` — pixel shift between the camera optical
  axis and the gripper grab point. Leave at `0/0` for most builds.
- `TARGET_RADIUS_PX` — the ball's apparent radius (in pixels) at the
  height the gripper would normally grab from. **This is the value to
  update when you swap to a different-sized ball.**

```
./calibrate_offset.sh
```

Like the color calibrator, this defaults to a browser version
([`browser_calibrate_offset.py`](browser_calibrate_offset.py)) and prints
a URL like `http://192.168.68.68:8000/`. Open it, **physically pose the
gripper directly above the ball** at grab distance (use **Release torque**
to free-pose, **Hold pose** to lock), then click **Snapshot**. The page
displays a paste-ready block, e.g.:

```
CAM_GRIPPER_OFFSET_X = -3
CAM_GRIPPER_OFFSET_Y = +12
TARGET_RADIUS_PX     = 280
# leave RADIUS_TOLERANCE roughly +/-20 for a safe margin
```

`BROWSER=0 ./calibrate_offset.sh` falls back to the cv2-window version.

## 6. Run the Demo

The recommended invocation on the RZ/G3E:

```
cd ~/robotic-arm
./start.sh --headless --web-port 8000
```

`--mode ball` is the default. With the demo running, open
`http://<board-ip>:8000/` from any laptop on the same LAN to watch the
live camera feed with the ball-follow detection overlay (HSV mask, ball
circle, pan/tilt/radius errors) and the current state-machine label
(`SCANNING` → `TRACKING` → `GRABBING` → `HOLDING`).

Other useful invocations:

| Command                                              | When to use it                                          |
|------------------------------------------------------|---------------------------------------------------------|
| `./start.sh --headless --web-port 8000`              | **Recommended.** Live browser view, no display needed.  |
| `./start.sh --headless`                              | Pure-headless run. Watch progress via `tail -f run.log` and /IOTCONNECT telemetry. |
| `./start.sh --mode asl --headless --web-port 8000`   | Only if `torch` + `mediapipe` actually installed.       |
| `./start.sh`                                         | Tries the cv2 preview window. Won't render on this image (opencv is headless). |

All flags forwarded to `main.py`:

| Flag                    | Purpose                                                                         |
|-------------------------|---------------------------------------------------------------------------------|
| `--mode {ball,asl}`     | Vision mode. Default `ball` (the supported mode on RZ/G3E).                     |
| `--camera N`            | OpenCV camera index. Default `0` — the kernel exposes the USB UVC camera as `/dev/video0`. |
| `--headless`            | Skip the cv2 preview window (use over SSH or when no monitor is attached).      |
| `--web-port N`          | Serve the live annotated camera feed as MJPEG on port `N`. Pairs naturally with `--headless`. |
| `--perf-every N`        | Print per-frame timing every N frames (default `30`).                           |

> [!IMPORTANT]
> Always make sure you are in the `~/robotic-arm` directory before launching —
> the demo loads `iotcDeviceConfig.json`, `ball_color.json`, and (for `asl`
> mode) `model/point_net_1.pth` from the current directory.

A successful start looks like:

```
Connecting to XArm 1S...                              → Connected
Connecting to IoTConnect...                           → Connected to IoTConnect successfully!
Initializing to home position...                      → Home position reached!
Starting vision mode: ball
[INFO] Camera input: 0 (640, 480) — mode=ball headless=True
[INFO] Live web view: http://192.168.68.68:8000/
[ball] HSV range loaded: lower=[…] upper=[…]
[ball] moving to scan pose [center]...
[ball] SCAN[center]: no ball
…
```

Drop the ball anywhere within the scan envelope and the arm will find it,
approach, and grab. Open the gripper by hand (or via the `open_gripper`
/IOTCONNECT command) to release and re-arm the cycle.

## Mode availability

| Mode    | Required on RZ/G3E                                               | Status |
|---------|-------------------------------------------------------------------|--------|
| `ball`  | `opencv-python-headless`, `numpy`, `xarm`, `hidapi`               | Fully supported — all wheels are available as prebuilt aarch64 manylinux wheels. |
| `asl`   | `torch`, `torchvision`, `mediapipe` (in addition to `ball`'s deps) | Best-effort. These packages frequently lack `manylinux2014_aarch64` wheels for the CPython version shipped in the RZ/G3E image. If the install script reports `MISS: torch` or `MISS: mediapipe`, the `asl` mode will not start. |

If you need ASL mode and the install script couldn't fetch the wheels, you
have two options:

1. **Build from source on the board** — slow (`torch` is a multi-hour build
   on the RZ/G3E's Cortex-A55 cores) and may run out of memory; not
   recommended without careful planning.
2. **Use a custom Yocto image** that includes `meta-pytorch` /
   `meta-tensorflow-lite` recipes, then re-run `deps-install.sh` to pick up
   the remaining lighter deps. Out of scope for this guide.

## Supported /IOTCONNECT commands

These match the upstream TRIA demo and work in either mode (the arm responds
even while a vision mode is running):

- **Movement**: `move_forward`, `move_backward`, `move_left`, `move_right`,
  `move_up`, `move_down`, `move_to_home`, `move_to` (with a 6-position payload)
- **Wrist**: `wrist_roll_cw`, `wrist_roll_ccw`, `wrist_flex_up`, `wrist_flex_down`
- **Gripper**: `open_gripper`, `close_gripper`
- **Scripted demos**: `demo_wave`, `demo_bow`, `demo_stretch`, `demo_scan`,
  `demo_shake_no`, `demo_pickup`

## Telemetry

Every payload carries a top-level `state` field identifying the active mode
(`SCANNING`, `TRACKING`, `GRABBING`, `HOLDING`, etc. for ball mode;
`ASL-Gesture` for ASL mode), the six servo positions, and a `sysInfo_*` block
collected by [`systemdata.py`](systemdata.py). Ball mode additionally
publishes a `ballTrack` block with detection / controller state — see the
upstream demo's
[telemetry section](https://github.com/avnet-iotconnect/iotc-tria-vision-ai-kit-robotic-arm#iotconnect-telemetry)
for the full schema.

> [!NOTE]
> [`systemdata.py`](systemdata.py) was rewritten for this port to use only
> stdlib + `/proc` and `/sys` reads. The TRIA build relied on `psutil` and
> `py-cpuinfo`, but those packages import the `resource` and
> `multiprocessing` stdlib modules — both of which are stripped from the
> RZ/G3E's Yocto Python image. The RZ/G3E reports its CPU brand from
> `/proc/device-tree/model` ("Renesas SMARC EVK based on r9a09g047e57"),
> max CPU MHz from `/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq`,
> and CPU temperature from the `cpu-thermal` zone. `gpu_temp`, `memory_temp`,
> and `gpu_usage` are `0.0` on this board (no matching sysfs nodes).

## Troubleshooting

### Install / dependency errors

- **`deps-install.sh` reports `MISS: cv2` (or numpy / hid) even though the
  wheel installed.** Wheel ABI mismatch. The script downloaded `cp311`
  wheels but your board runs Python 3.12 (or vice versa). Check
  `python3 --version` on the board and re-run `deps-download.sh` with
  `PY_VER=cp312` (or `cp311`, etc.) prepended. Then on the board, remove
  the stale extracts before re-installing:
  ```
  SP=$(python3 -c "import sys; print([p for p in sys.path if 'site-packages' in p][0])")
  rm -rf "$SP/cv2" "$SP/numpy" "$SP/numpy.libs" "$SP"/hid*.so
  rm -f ~/*.whl
  ```
  Then re-run `deps-download.sh` from the host and `deps-install.sh` on
  the board.

- **`ModuleNotFoundError: No module named 'resource'` / `'multiprocessing'`
  / `'statistics'`.** The Yocto image strips these stdlib modules. The
  demo source has been written to avoid them, but if you see this from a
  Python package you've added (e.g. `psutil`, `py-cpuinfo`), that
  package won't work on this image.

- **`stdbuf: not found`.** The busybox image doesn't ship `stdbuf`. The
  bundled [`start.sh`](start.sh) does not use it — if you see this, you
  may have an outdated copy. Re-pull from the repo.

### Runtime errors

- **`xarm.Controller('USB')` fails to open.** Confirm the arm is powered
  and present:
  ```
  lsusb | grep 0483:5750
  ```
  (lsusb's database labels this VID:PID as "STMicroelectronics LED badge"
  — that's normal; the xArm shares the ST HID chip.)

- **Camera not opening / `[ERROR] Camera failed to open!`.**
  ```
  ls /dev/video*
  v4l2-ctl --list-devices
  ```
  The USB UVC camera is normally `/dev/video0`. The demo defaults to
  index `0`; pass `--camera 1` etc. if your kernel enumerated it
  differently.

- **`ball_color.json not found`.** Run `./calibrate.sh` first; both
  ball-follow and the offset calibrator depend on it.

- **`asl` mode raises `ModuleNotFoundError: No module named 'torch'`.**
  The ML wheels aren't installed (see [Mode availability](#mode-availability)).
  Use `--mode ball` instead.

- **Browser shows the page but the live MJPEG stays blank.** Camera
  thread couldn't open `/dev/video0`. Look at the calibrator's stdout
  on the board for `ERROR: could not open camera`. Common cause:
  another instance of the calibrator (or `main.py`) is still holding
  the device — `pgrep -af python` and `kill` it.

### USB / hardware

- **`xhci-renesas-hcd … reset high-speed USB device`** in dmesg, or
  `Event TRB for slot N ep N with no TDs queued` warnings. Cosmetic
  — these fire when V4L2 closes a capture handle while the XHCI
  controller still has buffers queued. The camera reattaches and the
  demo keeps running.

- **Camera or arm intermittently disappears from `lsusb`.** USB-power
  starvation. The Brio 100 + arm together can pull more than a single
  bus-powered USB-C port wants to deliver. Use a **powered** USB hub
  between the board and the camera.

- **Both HDMI ports show `disconnected` even with a monitor plugged
  in.** The shipped Yocto image doesn't bring up Weston, and the
  ADV7535 (carrier board HDMI) / IT6263 (LVDS-to-HDMI add-on) bridges
  may not assert HPD without a compositor. **You don't need a monitor
  for this demo** — operate everything via SSH + browser. If you
  really want a display, expect to install a Wayland compositor and
  swap `opencv-python-headless` for full `opencv-python` plus a Qt
  backend.

For everything mode-specific (ball-mode tuning constants, gripper stall
detection, scan-envelope tuning, etc.), the upstream demo's
[README](https://github.com/avnet-iotconnect/iotc-tria-vision-ai-kit-robotic-arm#readme)
remains the authoritative reference — the per-mode source code in
[`modes/`](modes/) is identical to the TRIA build.
