# KR260 Inspection Cell Expansion Demo

Upgrades the /IOTCONNECT Starter Demo on the AMD Kria KR260 to a compact machine-vision inspection cell: a USB camera
watches a part or scene, the board compares each capture against a golden reference image, and pass/fail results,
counters, and cycle metrics stream to the cloud. An optional ROS 2 bridge maps ROS 2 topics into telemetry and cloud
commands onto ROS 2 services.

> [!IMPORTANT]
> Complete the [/IOTCONNECT quickstart guide for the KR260](../README.md) before proceeding.

## 1. Introduction

The demo captures a reference image of the inspection region (ROI), then scores every inspection as the normalized
mean absolute difference between the current camera view and that reference: 0.0 means identical, 1.0 means completely
different. A score at or below the threshold (default 0.15) is a pass. This simple golden-sample method needs no model
or training: aim the camera at the known-good part, capture the reference, and start inspecting. Any UVC USB webcam
works; USB 2.0 bandwidth is sufficient (validated with a Logitech C920 at 640x480).

## 2. Change Device Template

Before installing, change your device's template to `kr26IC` in the IOTCONNECT online platform:

1. Open your IOTCONNECT instance and navigate to your device's page.
2. Locate the **Template** field and click the edit icon.
3. Select the `kr26IC` template from the drop-down and save.

> [!TIP]
> If the `kr26IC` template is not yet present in your IOTCONNECT instance, import it from
> [kr26IC-template.json](kr26IC-template.json) via **Templates, Create Template, Import**.

## 3. Download and Install

Connect a USB webcam to one of the KR260 USB ports (U44/U46). The Kria Ubuntu image does not put the default user in
the `video` group, so grant camera access once, then log out and back in for it to take effect:

```bash
sudo usermod -aG video $USER
```

Then on the board run:

```bash
cd /opt/demo
wget -O package.tar.gz TODO-downloads.iotconnect.io-package-url
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

> [!NOTE]
> TODO: the package will be hosted on downloads.iotconnect.io; until then, build it yourself with the steps in
> section 7 and copy it to the board.

`install.sh` pip-installs the SDK and `opencv-python-headless` (prebuilt aarch64 wheel, no root required). The demo
runs fully unprivileged.

## 4. Using the Demo

```bash
cd /opt/demo
python3 app.py
```

To check the camera pipeline without connecting to IOTCONNECT, run `python3 app.py --dry-run`; it captures a
reference, runs one inspection against it (which should pass with a near-zero score), and prints a telemetry sample.

Typical cloud workflow once connected:

1. Aim the camera at the known-good part and send `capture-reference`.
2. Optionally restrict the inspection region first with `set-roi x,y,w,h` (pixels at 640x480), then recapture the
   reference. `set-roi full` returns to the full frame.
3. Send `start-inspection`. Each 5 second telemetry cycle runs one inspection; `trigger-inspection` runs one on
   demand and returns the result in the command ack.
4. Tune sensitivity with `set-threshold` (0.0 to 1.0; lower is stricter).

Telemetry streams to the **Live Data** tab every 5 seconds:

| Attribute | Type | Description |
|-----------|------|-------------|
| `sdk_version` | STRING | IOTCONNECT SDK version |
| `cpu_percent` | DECIMAL | CPU utilisation (%) |
| `memory_percent` | DECIMAL | RAM usage (%) |
| `som_temp_ps_c` | DECIMAL | SOM PS die temperature (C) |
| `camera_connected` | BOOLEAN | USB camera detected and streaming |
| `camera_kind` | STRING | `usb` or `none` |
| `inspection_active` | BOOLEAN | Continuous inspection running |
| `last_result` | STRING | `pass`, `fail`, `none`, `no_reference`, or `error` |
| `last_score` | DECIMAL | Difference score of the last inspection (0 to 1) |
| `pass_count` | INTEGER | Cumulative passes |
| `fail_count` | INTEGER | Cumulative fails |
| `yield_percent` | DECIMAL | pass / (pass + fail) * 100 |
| `cycle_time_ms` | DECIMAL | Time per inspection cycle (ms) |
| `fps` | DECIMAL | Inspections per second the pipeline can sustain |
| `ros2_bridge_active` | BOOLEAN | Optional ROS 2 bridge is feeding data |
| `ros2_data` | STRING | Latest ROS 2 topic values (JSON object) |
| `random` | INTEGER | Connectivity heartbeat |

### Commands

| Command | Parameter | Description |
|---------|-----------|-------------|
| `capture-reference` | none | Capture the current ROI as the golden reference |
| `start-inspection` | none | Start continuous inspection (requires a reference) |
| `stop-inspection` | none | Stop continuous inspection |
| `trigger-inspection` | none | Run one inspection; ack carries result and score |
| `reset-counters` | none | Zero the pass/fail counters |
| `set-roi` | `x,y,w,h` or `full` | Set the inspection region (invalidates the reference) |
| `set-threshold` | 0.0 to 1.0 | Pass/fail difference threshold (default 0.15) |
| `ros2-call` | `<name> [json]` | Forward a mapped service call to the ROS 2 bridge |
| `file-download` | URL | Download and apply an OTA update package |

## 5. Optional: ROS 2 Bridge

[src/ros2_bridge.py](src/ros2_bridge.py) is a separate rclpy node that subscribes to the topics listed in
[src/ros2_bridge.json](src/ros2_bridge.json) and forwards their values to the demo over a localhost UDP socket; they
appear in the `ros2_data` attribute and set `ros2_bridge_active`. The `ros2-call` command is forwarded to the bridge,
which calls the mapped `std_srvs/srv/Trigger` service (v1).

It requires ROS 2 Jazzy, the distribution matched to Ubuntu 24.04:
[installation instructions](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
(`ros-jazzy-ros-base` is sufficient). Start it in a second shell:

```bash
source /opt/ros/jazzy/setup.bash
python3 /opt/demo/ros2_bridge.py
```

> [!NOTE]
> The bridge code path in app.py (UDP ingest, `ros2_data`, `ros2_bridge_active`, `ros2-call` forwarding) is verified;
> the rclpy node itself has not yet been exercised against a live ROS 2 Jazzy install. TODO: validate on hardware
> with ROS 2 Jazzy installed.

## 6. How It Works

* Frames come from the first working `/dev/video*` device via OpenCV V4L2 at 640x480.
* The inspection score is `mean(|gray(ROI) - gray(reference)|) / 255`.
* `set-roi` invalidates the reference (the shapes must match), so recapture after changing it.
* Lighting changes move the score; keep the cell lighting stable, or raise the threshold.

## 7. Customize and Rebuild (Optional)

1. Clone the repository to your host machine:
   ```bash
   git clone https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos.git
   ```

2. Edit files in `amd-kria-kr260/inspection-demo/src/` as needed.

3. Rebuild the package:
   ```bash
   cd amd-kria-kr260/inspection-demo
   bash ./create-package.sh
   ```

4. Deliver the new package to the board:

   **Option A, direct copy (scp):**
   ```bash
   # On host:
   scp package.tar.gz ubuntu@<board-ip>:/opt/demo/
   # On board:
   cd /opt/demo && tar -xzf package.tar.gz --overwrite && bash ./install.sh
   ```

   **Option B, OTA via the /IOTCONNECT platform:**
   1. In the **Device** page, select **Firmware** on the bottom toolbar.
   2. Create a new firmware if needed: click **Create Firmware** (top-right), name it, select the `kr26IC` template,
      set version numbers (for example `0`, `0`), browse to `package.tar.gz`, and click **Save**.
   3. Back on the Firmware page, click the draft number under **Software Upgrades, Draft**.
   4. Click the publish icon under **Actions**.
   5. Select **OTA Updates** (top-right), choose your firmware's hardware and software versions, set **Target** to
      **Devices**, select your device, and click **Update**.
