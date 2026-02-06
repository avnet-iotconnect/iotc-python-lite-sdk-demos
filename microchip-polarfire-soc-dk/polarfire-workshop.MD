# PolarFire SoC Discovery Kit Workshop (Linux Bring-up + Fabric Accel)

This is an end-to-end workshop that boots Linux on the MPFS-DISCO-KIT and then runs a fabric acceleration demo that exercises MSS LSRAM from Linux and reports results to /IOTCONNECT.

## What you will do

1. Set jumpers and cables for Linux boot.
2. Program the FPGA with the AXI4 stream demo bitstream.
3. Flash Linux to microSD and boot to a shell.
4. Run the fabric accel demo and publish telemetry.

## Requirements

Hardware
- PolarFire SoC Discovery Kit (MPFS-DISCO-KIT)
- USB-C cable (power + UART)
- Ethernet cable (recommended for /IOTCONNECT)
- microSD card

Software
- FlashPro Express (for FPGA programming)
- Serial terminal (PuTTY, TeraTerm, etc.)
- SD card flashing tool (Balena Etcher, etc.)
- Libero SoC (only if you build the FPGA design from source)

Accounts
- /IOTCONNECT account and device onboarding credentials

## Repo assets used in this workshop

- FPGA programming job:
  - fpga-assets/AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07.job
- Demo app:
  - fabric-accel-demo/
- QuickStart (reference for Linux image and serial console):
  - README.md
- Deep-dive demo notes:
  - FPGA-ACCEL-WORKSHOP.md
  - fabric-accel-demo/mchp-polarfire-workshop.md

## Links

Linux image (prebuilt)
- Releases page: https://github.com/linux4microchip/meta-mchp/releases
  - Look for "Pre-built images for the Discovery Kit Reference Design" and download the pre-built image.
  - File name example (do not copy verbatim): mchp-base-image-mpfs-disco-kit.rootfs-YYYYMMDDHHMMSS.wic.gz

FPGA reference design releases (if you want to download instead of using this repo)
- https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design/releases

Reference design source (Libero Tcl)
- https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design

Board docs
- User guide (jumpers and connectors): https://mi-v-ecosystem.github.io/redirects/boards-mpfs-discovery-kit-user-guide
- Official update flow: https://mi-v-ecosystem.github.io/redirects/boards-mpfs-generic-updating-mpfs-kit

## Step 1: Hardware setup (jumpers + cables)

Set the Linux boot jumper positions:
- J45: 1-2
- J46: 1-2
- J47: Closed
- J49: 1-2

Connect cables:
- USB-C to the board (power + UART)
- Ethernet to RJ45 (recommended)

Do not insert the microSD card until after it is flashed in Step 3.

## Step 2: Program the FPGA

### Option A: Use the prebuilt job in this repo (recommended)

1. Open FlashPro Express.
2. Create a new project and import the .job file:
   fpga-assets/AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07/MPFS_DISCOVERY_KIT_AXI4_STREAM_DEMO_2025_07.job
3. Click RUN to program the device.
4. Power-cycle the board (unplug/replug USB-C).

### Option B: Build in Libero from source

1. Clone the reference design repo:
   https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design
2. Open Libero SoC.
3. Open the Execute Script dialog (Ctrl+U) and run:
   MPFS_DISCOVERY_KIT_REFERENCE_DESIGN.tcl
4. To match the AXI4 stream demo build, add the argument:
   AXI4_STREAM_DEMO
5. Run the Libero design flow and program the device.
   (Double-click "Run PROGRAM Action" in the flow.)

## Step 3: Flash the Linux image to microSD

1. Go to the Linux image releases page:
   https://github.com/linux4microchip/meta-mchp/releases
2. Download the pre-built Discovery Kit image from the release notes.
3. Extract the .wic.gz to a .wic file.
4. Flash the .wic to your microSD card using Balena Etcher (or a similar tool).
5. Insert the microSD card into the Discovery Kit.

## Step 4: Boot Linux and verify

1. Power the board via USB-C.
2. Open a serial terminal using the settings in README.md (115200 8N1, no flow control).
3. On Windows, connect to the middle-numbered COM port for the Linux console (per README.md).
4. Log in as root.
5. Verify:
   - uname -a
   - cat /etc/os-release

## Step 5: Install Python dependencies

On the board:

```
sudo opkg update
python3 -m pip install iotconnect-sdk-lite requests
```

## Step 6: Copy the demo app to the board

From your host PC (replace BOARD_IP):

```
ssh root@BOARD_IP "mkdir -p /home/weston/demo/fabric-accel"
scp -r microchip-polarfire-soc-dk/fabric-accel-demo/. root@BOARD_IP:/home/weston/demo/fabric-accel/
```

If scp fails with "Corrupted MAC on input":

```
ssh -o MACs=hmac-sha2-512-etm@openssh.com -o Ciphers=aes128-ctr root@BOARD_IP "mkdir -p /home/weston/demo/fabric-accel"
scp -r -o MACs=hmac-sha2-512-etm@openssh.com -o Ciphers=aes128-ctr microchip-polarfire-soc-dk/fabric-accel-demo/. root@BOARD_IP:/home/weston/demo/fabric-accel/
```

## Step 7: /IOTCONNECT onboarding files

Place these files in `/home/weston/demo/fabric-accel`:
- iotcDeviceConfig.json
- device-cert.pem
- device-pkey.pem

## Step 8: Run the demo

One-shot sanity check:

```
cd /home/weston/demo/fabric-accel
sudo python3 app.py --once
```

Expected output:
- Capture OK: True
- First: 1 Last: 256

Continuous loop (telemetry every 10 seconds):

```
sudo python3 app.py
```

## Optional: Device commands (/IOTCONNECT)

Create these device commands in your template:
- set-pattern <count>
- fpga-capture <count>
- set-led <mask> or set_leds <mask> (optional)

Examples:
- set-pattern 256
- fpga-capture 512
- set-led 0x1

## Memory map used by the demo

- MSS LSRAM: 0x6000_0000 (data buffer at 0x6000_0200)
- CoreAXI4DMAController registers: 0x6001_0000

## Troubleshooting

- If /dev/uio* is missing, the app will fall back to devmem2 if installed.
- If pattern_count too large:
  - When /dev/uio0 is 0x1000 bytes, max samples = 0xE00 / 8 = 448.
  - Use set-pattern 448 or lower, or force devmem2:
    FORCE_DEVMEM2=1 sudo python3 app.py
- If fpga_ok is 0, confirm the FPGA .job file includes AXI4_STREAM_DEMO.
- If set-led fails, CoreGPIO may not be exposed in your image; LED control is optional.

## Next steps

- Change the pattern count and observe telemetry impact.
- Extend the demo to stream into DDR instead of LSRAM.
- Add a device command to change pattern count at runtime.
