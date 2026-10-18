# Plan: AMD Kria Expansion Demos for /IOTCONNECT

Status: plan only, nothing implemented yet. Phase 1 (quickstarts for `amd-kria-kv260`, `amd-kria-kr260`,
`amd-kria-kd240`) is complete. This document specifies the Phase 2 expansion demos, their IOTCONNECT templates,
dependencies, and the items that must be verified on hardware before or during implementation.

All facts below were researched against official AMD/Canonical sources in October 2026, and the platform facts were
verified live on a KR260 (rev B, boot firmware K26-BootFW-01.02) running Ubuntu 24.04.2 LTS (kernel 6.8.0-1015-xilinx,
Python 3.12.3).

## 1. Platform Facts That Shape the Design

* The Ubuntu 24.04 Kria image preinstalls `xmutil` (1.2.1) and `dfx-mgr` (2024.2.0, daemon `dfx-mgr.service` active by
  default). `xmutil` is the supported front end; it talks to the dfx-mgr daemon over `/var/run/dfx-mgrd.socket`, and
  `dfx-mgr-client` is the lower-level equivalent. Both exist on Ubuntu 24.04; there is no need to choose one at
  install time. `xmutil` requires sudo for every subcommand.
* Accelerator firmware lives under `/lib/firmware/xilinx/<app>/` (bitstream + dtbo + json). The stock image ships only
  the `k26-starter-kits` and `k24-starter-kits` flat shells (`xlnx-default-bitstreams` package); verified on the
  KR260, where `sudo xmutil listapps` shows `k26-starter-kits` loaded in slot 0.
* Additional accelerator apps come from `ppa:xilinx-apps` as `xlnx-firmware-<kit>-<app>` debs plus (usually) a Docker
  container for the userspace side. App availability on Ubuntu 24.04 is much narrower than on 22.04:
  * KV260 on 24.04: BIST only. Smart Camera, AI Box ReID, Defect Detect, and NLP SmartVision are released for
    Ubuntu 22.04 only.
  * KR260 on 24.04: BIST and ROS 2 TSN only. The 10GigE Vision Camera and ROS 2 Perception Node apps are 22.04 only.
  * KD240 on 24.04: BIST, ROS 2 TSN, and FOC Motor Control 0.5. The FOC app is the one accelerated app with a real
    Ubuntu 24.04 release.
* `xmutil getpkgs` is documented as unsupported on Kria Ubuntu and returns an empty list on the stock 24.04 image
  (verified). App discovery for our demos should list `/lib/firmware/xilinx` or parse `xmutil listapps` instead.
* Telemetry sources on the stock image (verified on the KR260, hwmon names expected to match on the K26 kits):
  * `hwmon` device `ams` (Zynq UltraScale+ AMS/SYSMON): `temp1_input`, `temp2_input`, `temp3_input` in millidegrees
    (PS, remote, and PL sensors). Note: no `/sys/class/thermal` zones exist on this kernel, so code must read hwmon.
  * `hwmon` device `ina260_u14`: `in1_input` (mV), `curr1_input` (mA), `power1_input` (uW) for the SOM 5V rail.
  * `hwmon` device `pwmfan` (fan).
  * `/proc/stat` and `/proc/meminfo` for CPU and memory, same approach as the RZ/V2H system monitor demo.
  * `xlnx_platformstats` (package `xlnx-platformstats`) is preinstalled and wraps the same sources if we prefer
    parsing a tool over sysfs.
* Python 3.12 with PEP 668: all pip installs need `--break-system-packages` (or a venv).
* Docker is not preinstalled on the 24.04 image.
* The demo app runs as the `ubuntu` user, but `xmutil` needs root. Decision needed at implementation time: either run
  `app.py` with sudo (like some existing demos run as root), or ship a sudoers drop-in in `install.sh` allowing
  `ubuntu` to run `/usr/bin/xmutil` without a password. The sudoers drop-in is the cleaner option and keeps the
  OTA/file-download flow running as `ubuntu`.

## 2. Repository Layout

Each demo follows the `renesas-rzv2h-evk/system-monitor-demo` expansion demo convention:

```
amd-kria-<board>/<demo-dir>/
  README.md                  (template import, download and install, usage, telemetry and command tables)
  create-package.sh          (tar -czf package.tar.gz -C ./src .)
  <code>-template.json       (IOTCONNECT device template)
  src/app.py                 (demo application)
  src/install.sh             (on-device dependency install, runs after OTA extraction)
```

`package.tar.gz` is never committed (`.gitignore` already covers it). Download URLs in the READMEs will point at
downloads.iotconnect.io. TODO: exact hosting path on downloads.iotconnect.io to be assigned when packages are built.

The shared system monitor demo (section 3) is identical on all three boards. Decision (implemented): the demo is
duplicated into each board directory, matching the repo's self-contained board directory convention; the three `src/`
trees and the `kriaSM` template are kept byte-identical, with only the README board references differing.

## 3. Demo A: Kria System and Accelerator Monitor (all three boards)

Status: IMPLEMENTED in `amd-kria-<board>/system-monitor-demo/` for all three boards.

Upgrades the starter demo to stream system telemetry and manage PL accelerator apps from the cloud. One template
serves all three kits.

Implementation sketch: `app.py` reads `/proc/stat`, `/proc/meminfo`, and the `ams` + `ina260` hwmon nodes directly (no
extra Python packages); accelerator state comes from `sudo xmutil listapps` (parse the `Accelerator`/`Active_slot`
columns) and `/lib/firmware/xilinx` directory listing; app switching shells out to `sudo xmutil unloadapp` and
`sudo xmutil loadapp <name>`.

Template code: `kriaSM` (name `kria-system-monitor`, authType 2, dataFrequency 10, fileSupport true).

Attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `board` | STRING | Board id (kv260, kr260, kd240) from the FRU EEPROM via `xmutil boardid` |
| `cpu_percent` | DECIMAL | Overall CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `som_temp_ps_c` | DECIMAL | AMS temp1, PS die temperature (C) |
| `som_temp_rem_c` | DECIMAL | AMS temp2, remote die temperature (C) |
| `som_temp_pl_c` | DECIMAL | AMS temp3, PL die temperature (C) |
| `som_voltage_v` | DECIMAL | SOM 5V rail voltage (INA260) |
| `som_current_a` | DECIMAL | SOM 5V rail current (INA260) |
| `som_power_w` | DECIMAL | SOM power draw (INA260) |
| `loaded_app` | STRING | Currently loaded PL accelerator app, or "none" |
| `apps_installed` | STRING | JSON array of installed accelerator app names |
| `random` | INTEGER | Connectivity heartbeat |

Commands:

| Command | Param | Description |
|---------|-------|-------------|
| `list-apps` | no | Refresh and ack with the `xmutil listapps` output |
| `load-app` | yes | `sudo xmutil unloadapp` then `sudo xmutil loadapp <param>`; ack with result |
| `unload-app` | no | `sudo xmutil unloadapp`; ack with result |
| `file-download` | yes | OTA update package (standard) |

Dependencies: none beyond the Lite SDK (`iotconnect-sdk-lite`, `requests`). `install.sh` optionally writes the xmutil
sudoers drop-in.

Hardware verification status (KR260 rev B, Ubuntu 24.04.2, 2026-10-18):

* VERIFIED on KR260: `install.sh` end to end (pip install, sudoers rule); `python3 app.py --dry-run` returns full
  telemetry (board autodetect `kr260` from `/proc/device-tree/model`, AMS temps 34.0/32.5/31.3 C, INA260
  5.05 V / 0.637 A / 3.22 W, loaded app `k26-starter-kits`); `listapps` parsing for both loaded and none states; a
  full `unloadapp`/`loadapp k26-starter-kits` round trip as user `ubuntu` through the scoped sudoers rule (xmutil
  wrapped in a root-owned `timeout`) with a cold sudo timestamp; `install.sh` in both interactive and simulated OTA
  (`IOTC_OTA=1`, stdin detached) contexts. The code also passed an adversarial multi-agent review; confirmed findings
  (install.sh exit code, OTA failure acks, unkillable root sudo child on xmutil hang, sudoers scope, interactive sudo
  prompt during OTA) were fixed before commit.
* VERIFIED on KD240 (rev A/B/1, factory boot firmware XilinxSOM_BootFW_20230507, 2026-10-18): the 24.04 image boots
  on factory firmware; board autodetects as `kd240` from `/proc/device-tree/model` ("ZynqMP KD240 revA/B/1"); hwmon
  names are `ams`, `pwmfan`, and `ina260_u3` (the INA260 label indeed differs from the KR260's `ina260_u14`; the
  prefix match handles it); dry-run telemetry reads 5.01 V / 0.365 A / 1.82 W and three AMS temps; both starter-kit
  shells ship with `k24-starter-kits` auto-loaded, and the `k24-starter-kits` unload/load round trip works through
  the scoped sudoers rule. The KD240's PS Ethernet appears as `eth0` (plus `can0`).
* Remaining: pip/SDK install on the KD240 (blocked until its Ethernet is connected to J24), KV260 on the bench, and
  end-to-end telemetry in the IOTCONNECT Live Data tab after onboarding (needs a device created with the `kriaSM`
  template).
* AMS temp channel-to-sensor mapping (temp1/2/3 vs PS/remote/PL) is taken from the AMS driver channel order; worth a
  cross-check against `xlnx_platformstats` output on each kit.

## 4. Demo B: KV260 Vision AI Demo (DPU)

Goal: DPU-accelerated object detection on the KV260 reporting detections, class counts, FPS, and latency, with OTA
model swap.

Key constraint found in research: there is no Vitis AI / DPU path on Ubuntu 24.04 today. The smartcam accelerated app
and the whole Vitis AI 2022.1-2.5 stack are released for Ubuntu 22.04 only; Kria-PYNQ documents Ubuntu 22.04 only;
DPU-PYNQ (Vitis AI 2.5 overlays for KV260/KR260) was archived read-only in August 2025; VART 3.5 needs Python 3.10.
Decision (recommended): the vision demo targets the Ubuntu Desktop 22.04 LTS Kria image with Kria-PYNQ, while the
board quickstart stays on 24.04. The demo README must say plainly that the vision demo requires reflashing to 22.04.
Alternative rejected for now: CPU-only inference on 24.04 (does not demonstrate the DPU, which is the point of the
kit). Revisit if AMD ships a 24.04 Vitis AI release.

Implementation sketch: Kria-PYNQ install (`sudo bash install.sh -b KV260`, about 25 minutes) provides `pynq_dpu`.
`app.py` loads `DpuOverlay("dpu.bit")`, then `overlay.load_model("<model>.xmodel")`, captures frames from a USB webcam
via OpenCV, runs YOLO-class detection, and publishes results. OTA model swap: a `set-model` command downloads a new
`.xmodel` (plus labels and metadata JSON) through the standard `file-download` package flow and calls `load_model`
again; models must be compiled with Vitis AI 2.5 `vai_c` for the DPU-PYNQ B4096 architecture fingerprint, or
`load_model` fails its subgraph assertion.

Template code: `kv26VAI` (name `kv260-vision-ai`, dataFrequency 5 or 10, fileSupport true).

Attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `som_temp_ps_c` | DECIMAL | PS die temperature (C) |
| `model_name` | STRING | Currently loaded xmodel name |
| `detection_active` | BOOLEAN | Inference loop running |
| `total_detections` | INTEGER | Objects detected in current frame |
| `person_count` | INTEGER | Persons detected in current frame |
| `class_counts` | STRING | Per-class counts (JSON object) |
| `primary_class` | STRING | Top-1 class in current frame |
| `primary_confidence` | DECIMAL | Top-1 confidence (%) |
| `fps` | DECIMAL | End-to-end frames per second |
| `inference_time_ms` | DECIMAL | DPU inference time per frame (ms) |
| `latency_ms` | DECIMAL | Capture-to-publish latency per frame (ms) |
| `random` | INTEGER | Connectivity heartbeat |

Commands:

| Command | Param | Description |
|---------|-------|-------------|
| `start-detection` | no | Start the camera + DPU inference loop |
| `stop-detection` | no | Stop the inference loop |
| `set-model` | yes | Name of an installed model package to activate (triggers `load_model`) |
| `set-threshold` | yes | Detection confidence threshold, 0.0 to 1.0 |
| `file-download` | yes | OTA update package; also used to deliver model packages |

Dependencies: Ubuntu Desktop 22.04 LTS Kria image, boot firmware 01.02+ (2022.1 era or later), Kria-PYNQ
(pynq, pynq-dpu, Vitis AI 2.5 runtime), OpenCV (`python3-opencv` or pip), USB webcam (or AR1335 IAS module from the
Basic Accessory Pack; USB is simpler and matches other demos in this repo). Model zoo source: Vitis AI 2.5 model zoo
xmodels compiled for B4096 (e.g. yolov3/yolox variants).

Verify on hardware:

* Kria-PYNQ install succeeds on the current Ubuntu 22.04 Kria image (the repo is still maintained but pin a known-good
  commit); confirm `pynq_dpu` imports and the B4096 overlay loads.
* Python version on the 22.04 image vs Kria-PYNQ wheels (Kria-PYNQ targets 22.04's Python 3.10).
* xmodel inference end to end with a USB camera; measure FPS and latency to size `dataFrequency`.
* `load_model` re-invocation at runtime for the OTA swap (works per DPU-PYNQ notebooks; confirm no memory leak over
  repeated swaps).
* Whether the Lite SDK and PYNQ coexist (PYNQ installs its own venv/jupyter stack; the demo may need to run inside
  PYNQ's environment with the SDK pip-installed there).
* TODO: confirm whether the KV260 on hand has boot firmware new enough for the 22.04 image (check with
  `sudo xmutil bootfw_status`; update first if it shows 2021.1).

## 5. Demo C: KR260 Inspection Cell Demo

Status: IMPLEMENTED in `amd-kria-kr260/inspection-demo/` (template `kr26IC`). The implementation uses golden-sample
reference comparison (normalized mean absolute difference on the grayscale ROI) and adds a `capture-reference`
command plus `last_score` and `ros2_data` attributes relative to the tables below. Camera path uses pip
`opencv-python-headless` (aarch64 wheel), so the demo needs no root at all. The ROS 2 bridge ships as a separate
rclpy node (`src/ros2_bridge.py` + `ros2_bridge.json`) talking to the app over localhost UDP (5577 data in, 5578
command forward).

Hardware verification status (KR260 rev B, Logitech C920 on USB, 2026-10-18): reference capture at 640x480, pass and
fail threshold paths, counters and yield, ROI set/recapture/inspect (200x150), malformed-input rejection, and the
bridge UDP ingest path all verified live; inspection cycle measured at about 68 ms (about 15 FPS capability). One
image-wide fact worth knowing: the Kria Ubuntu image does not put the default user in the `video` group, so camera
demos need a one-time `sudo usermod -aG video $USER` plus re-login (documented in the demo README). The code passed an
adversarial multi-agent review; confirmed findings (camera fd leak through the OTA execv, metadata-node adoption,
stale camera_connected after unplug, UDP bind failures, success acks lost to execv before the MQTT flush, bridge
heartbeat and config validation) were fixed before commit, and the ack-flush fix was back-ported to the system
monitor demo. The ROS 2 bridge was subsequently verified end to end on the KR260 against a live ROS 2 Jazzy install
(ros-jazzy-ros-base via the ros2-apt-source deb): heartbeat drives ros2_bridge_active, Float64 and String topics
land in ros2_data, and a forwarded ros2-call invokes the mapped Trigger service. One live-only find: rclpy's Node
class owns a read-only `services` property, so the bridge stores its clients as `trigger_clients`.

Goal: a compact machine-vision inspection station: a camera watches parts, the app classifies pass/fail (presence,
color, or simple defect check via OpenCV), and IOTCONNECT shows live results, counters, and cycle metrics. Optional
ROS 2 bridge for robotics integration.

Camera decision: USB3 UVC camera as the primary path (uvcvideo/v4l2 ships in the generic Ubuntu arm64 kernel; not
officially validated by AMD on KR260, so verify early). GigE Vision as a documented option via Aravis
(`aravis-tools` 0.8.30 is in the noble arm64 archive; the KR260's extra Ethernet ports make a dedicated camera subnet
natural once a PL design enables them, but the PS port works for a single GigE camera too). AMD's official 10GigE
Vision app is 22.04-only and needs an IMX547 camera, so it is out of scope.

Runs on the standard Ubuntu 24.04 quickstart image (no reflash needed).

Implementation sketch: `app.py` captures frames with OpenCV, runs a configurable inspection function (ROI + threshold
based), and publishes results. The optional ROS 2 bridge is a separate `ros2_bridge.py` node (rclpy) that subscribes
to configurable topics and republishes them as telemetry, and exposes IOTCONNECT commands as ROS 2 service calls;
installed only when the user opts in.

Template code: `kr26IC` (name `kr260-inspection-cell`, dataFrequency 5 or 10, fileSupport true).

Attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `som_temp_ps_c` | DECIMAL | PS die temperature (C) |
| `camera_connected` | BOOLEAN | Camera detected and streaming |
| `camera_kind` | STRING | usb or gige |
| `inspection_active` | BOOLEAN | Inspection loop running |
| `last_result` | STRING | pass or fail for the most recent inspection |
| `pass_count` | INTEGER | Cumulative pass count |
| `fail_count` | INTEGER | Cumulative fail count |
| `yield_percent` | DECIMAL | pass / (pass + fail) * 100 |
| `cycle_time_ms` | DECIMAL | Time per inspection cycle (ms) |
| `fps` | DECIMAL | Camera frames per second |
| `ros2_bridge_active` | BOOLEAN | ROS 2 bridge node connected (false when not installed) |
| `random` | INTEGER | Connectivity heartbeat |

Commands:

| Command | Param | Description |
|---------|-------|-------------|
| `start-inspection` | no | Start the continuous inspection loop |
| `stop-inspection` | no | Stop the loop |
| `trigger-inspection` | no | Run a single inspection cycle and ack with the result |
| `reset-counters` | no | Zero pass/fail counters |
| `set-roi` | yes | Inspection region as "x,y,w,h" |
| `set-threshold` | yes | Inspection sensitivity, 0.0 to 1.0 |
| `ros2-call` | yes | Forward "service_name json_args" to a ROS 2 service via the bridge |
| `file-download` | yes | OTA update package (standard) |

Dependencies: `python3-opencv` (apt) or `opencv-python-headless` (pip), optional `aravis-tools` + `python3-gi` for
GigE, optional ROS 2 Jazzy via packages.ros.org apt repo (Jazzy is the Tier 1 match for Ubuntu 24.04 arm64; KRS is
frozen at 22.04/Humble and is not used).

Verify on hardware:

* UVC camera enumeration and capture on the KR260 USB3 ports under Ubuntu 24.04 (expected but not officially
  validated; no `/dev/video*` existed on the bare board, so test with the camera attached).
* Sustained OpenCV capture + JPEG encode CPU load on the 4x Cortex-A53 (sizes `dataFrequency` and resolution choice).
* ROS 2 Jazzy apt install footprint on the 4GB RAM / SD card (ros-jazzy-ros-base, not desktop) and rclpy coexistence
  with the PEP 668 pip environment.
* If demonstrating GigE: aravis against an actual GigE Vision camera on the PS port. TODO: confirm which GigE camera
  is available in the lab.

## 6. Demo D: KD240 Motor Control Demo

Goal: cloud-controlled field-oriented control (FOC) of the Motor Accessory Pack BLDC motor, with speed, current,
position, and fault telemetry.

Stack decision: AMD's official FOC Motor Control app 0.5 explicitly targets Ubuntu 24.04 and the 2024.1 toolchain, so
this demo runs on the standard quickstart image (no reflash). The "Vitis Motor Control Library" itself is HLS IP used
inside the PL firmware; the runtime Python interface comes from the `foc-motor-ctrl` application library
(github.com/Xilinx/foc-motor-ctrl), which ships C++ and Python (pybind11) interfaces built on libiio.

Install flow (from the official deployment guide): add `ppa:xilinx-apps`, `ppa:ubuntu-xilinx/default`, and
`ppa:lely/ppa`; `sudo apt install xlnx-firmware-kd240-motor-ctrl-qei xlnx-app-kd240-foc-motor-ctrl`; load the PL
firmware with `sudo xmutil unloadapp` + `sudo xmutil loadapp kd240-motor-ctrl-qei`. Motor parameters come from
`/etc/motor-control/config` (defaults to `anaheim.config` for the accessory pack motor). The app package also provides
a Bokeh dashboard (`start_motor_dashboard`, port 3006); our demo uses the Python library directly instead, and the
README should warn that the dashboard and the demo cannot both own the motor at once.

Implementation sketch: `app.py` imports the foc-motor-ctrl Python module, polls speed/position/current/voltage and
fault status on a timer, and maps commands onto the library's mode and setpoint calls (modes per the official app:
Off, Speed (-10000 to 10000 rpm), Torque (-2.5 to 2.5 A), Open Loop).

Template code: `kd24MC` (name `kd240-motor-control`, dataFrequency 5, fileSupport true).

Attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `som_temp_ps_c` | DECIMAL | PS die temperature (C) |
| `motor_mode` | STRING | off, speed, torque, or open_loop |
| `speed_setpoint_rpm` | DECIMAL | Commanded speed (rpm) |
| `speed_rpm` | DECIMAL | Measured mechanical speed (rpm) |
| `position_deg` | DECIMAL | Rotor mechanical position (degrees) |
| `current_ia_a` | DECIMAL | Phase A current (A) |
| `current_ib_a` | DECIMAL | Phase B current (A) |
| `current_ic_a` | DECIMAL | Phase C current (A) |
| `dc_link_v` | DECIMAL | DC link voltage (V) |
| `fault_active` | BOOLEAN | Any critical fault latched |
| `fault_status` | STRING | Fault flags (JSON object) |
| `random` | INTEGER | Connectivity heartbeat |

Commands:

| Command | Param | Description |
|---------|-------|-------------|
| `set-speed` | yes | Speed setpoint in rpm, -10000 to 10000 (implies speed mode) |
| `set-torque` | yes | Torque setpoint in A, -2.5 to 2.5 (implies torque mode) |
| `set-mode` | yes | off, speed, torque, or open_loop |
| `stop` | no | Immediate stop (mode off, setpoint 0) |
| `clear-faults` | no | Clear latched faults if the library exposes it |
| `file-download` | yes | OTA update package (standard) |

Dependencies: Motor Accessory Pack HW-MACCP01-SK-G (24V BLDC motor + encoder + 24V motor supply), the three PPAs
above, `xlnx-firmware-kd240-motor-ctrl-qei`, `xlnx-app-kd240-foc-motor-ctrl` (pulls pybind11, libiio, bokeh),
`lm-sensors` (used by the official guide for the 1-Wire temperature sensor path).

Verify on hardware:

* The exact Python module name and API surface of the foc-motor-ctrl pybind11 bindings (not documented; inspect
  `/opt/xilinx/xlnx-app-kd240-foc-motor-ctrl` after install). TODO.
* DC link connector silkscreen: UG1093 says J39, the FOC guide says J29. Check the board. TODO.
* Package availability for 24.04 CONFIRMED (2026-10-18): the noble view of `ppa:xilinx-apps` lists
  `xlnx-app-kd240-foc-motor-ctrl` 0.5.2-0xlnx1 and `xlnx-firmware-kd240-motor-ctrl-qei` 1.0-0xlnx2. A clean install
  on the board still needs to be exercised once the KD240 is on the bench. The kit alone is not enough to run the
  demo: the Motor Accessory Pack HW-MACCP01-SK-G (24V BLDC motor, encoder, cables, 24V motor supply) is required and
  must be purchased separately.
* Fault telemetry fields actually exposed by the library (dashboard shows critical/warning indicators; map to
  `fault_status`).
* Encoder wiring (J42 vs J43 and the J44 jumper position) with the accessory pack cable.
* Safe-stop behavior: confirm `set-mode off` ramps or cuts PWM, and decide whether `stop` should also disengage the
  DC link.

## 7. Open Items Summary

* downloads.iotconnect.io hosting paths for all packages. TODO.
* Decide shared-source vs duplicated layout for Demo A. TODO.
* KV260 vision demo is blocked on the Ubuntu 22.04 reflash decision (recommended) or a future AMD Vitis AI release
  for 24.04.
* KD240 foc-motor-ctrl Python API must be inspected on hardware before the template is finalized.
* Confirm hwmon device names on KV260 and KD240 (verified on KR260 only).
* Templates in this plan use codes kriaSM, kv26VAI, kr26IC, kd24MC; confirm they are unused in the target IOTCONNECT
  instance before import.
