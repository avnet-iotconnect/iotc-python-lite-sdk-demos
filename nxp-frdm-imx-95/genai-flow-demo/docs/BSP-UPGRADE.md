# Preparing FRDM i.MX 95 boards

How to get a FRDM i.MX 95 onto the working software stack. There are two audiences:

- **DIY / customer** — you prepare **your own** board from scratch. Do the full manual install once, per board.
  The demo [README](../README.md) is the primary guide; Steps 1–4 below are the same flow with the fleet
  details called out. Every board is flashed, **expanded**, and installed individually.
- **Workshop fleet** — a presenter prepares **one** golden board (Steps 1–4), verifies it, then clones it to
  the rest with UUU (Step 5). Cloned boards are already installed and already expanded; attendees only claim
  them. This is how ~30 boards get built without repeating the install 30 times.

> **Order matters.** Prepare a board *without* an Ara240 first — it proves the whole flow with the risky
> variable absent. Only then touch an Ara board, and only with a restorable backup in hand.

## Which BSP — read this first

Use **LF6.18.2-1.0.0 ("whinlatter", kernel 6.18.2, Python 3.13)**. That is what the working boards run and what
eIQ GenAI Flow is built for.

**Do _not_ use the newer LF6.18.20_2.0.0 ("wrynose") yet**, even though it is the latest release. It ships
**Python 3.14 only**, and NXP's GenAI Flow core is distributed as **`cpython-313` compiled binaries** (all
branches, including `main`). Python 3.14 cannot load a `cpython-313` module, so on LF6.18.20 the GenAI demo
stack **cannot run** — verified on hardware. Revisit only once NXP publishes `cpython-314` GenAI Flow builds.

## The stack

| Layer | Applies to | Notes |
|---|---|---|
| NXP i.MX Linux BSP | every board | **LF6.18.2-1.0.0** (whinlatter). See "Which BSP" above — not LF6.18.20. |
| NXP eIQ GenAI Flow | every board | the LLM/VLM/voice stack (v3.0); ships `cpython-313` binaries → needs Python 3.13 |
| This demo package | every board | `frdm-imx95-genai-flow-demo-v1.0.2.tgz` (README section 5) |
| llama.cpp | every board | needed for GGUF models pushed from /IOTCONNECT |
| rt-sdk-ara2 | **Ara boards only** | **2.0.4** on whinlatter (matches the r2.0.4 models). See the Ara note below. |
| eIQ AAF Connector | **Ara boards only** | **2.0**, matched to rt-sdk 2.0.4 |

### Ara240 runtime — stay on 2.0.4

Every NXP-published Ara240 model (7B, Coder-1.5B, VL-7B) states runtime **r2.0.4** on its model card, and
rt-sdk 2.0.4 is what whinlatter supports. The newer rt-sdk **2.1.1 requires LF6.18.20** — which breaks GenAI
Flow (above) — so there is no path today that gives you both the newer runtime and a working demo. Stay on
whinlatter + rt-sdk 2.0.4 + connector 2.0.

Related open issue: `Qwen2.5-VL-7B-Instruct-Ara240` fails to load on 2.0.4 even on a freshly reset 16 GB
device — `[version] installed products minor versions are not compatible`, `model found to be dyn quant v2
model`, then a 15-minute session timeout and `wait for model load failed 402`. Capacity is ruled out; the
suspect is the dyn-quant-v2 model format vs the 2.0.4 runtime. Raise with NXP before planning a VL demo.

## Step 0 — back up (Ara boards, or any board you cannot rebuild)

With a large SD card mounted (e.g. at `/mnt/models`):

```bash
sync
dd if=/dev/mmcblk0 bs=4M status=none | gzip -1 > /mnt/models/emmc-backup-$(date +%Y%m%d).img.gz
sync
```

Restore (from a rescue boot or another machine with the card):

```bash
gunzip -c emmc-backup-YYYYMMDD.img.gz | dd of=/dev/mmcblk0 bs=4M conv=fsync
```

A 29 GB eMMC compresses to roughly 10–17 GB and takes 1–2 hours. Verify the file exists and is non-trivially
sized before proceeding.

> A whole-device `dd` of `/dev/mmcblk0` captures the partitions but **not** the eMMC hardware boot partitions
> (`mmcblk0boot0/1`) where the bootloader lives. A raw `dd` restore onto a *different* board can therefore
> come up without a bootloader. Restore-in-place on the same board is fine (its boot0 is untouched); to move
> an image **between** boards, flash with UUU (Step 5), which writes the bootloader correctly.

## Step 1 — flash the BSP

Follow [FLASHING.md](../../FLASHING.md) with the **LF6.18.2-1.0.0** image. For the FRDM 15×15 board the files are
`imx-boot-imx95-15x15-lpddr4x-frdm-sd.bin-flash_all` (bootloader) and `imx-image-full-imx95evk.wic` (rootfs;
shared across i.MX95 variants — the board-specific part is the boot binary).

Afterwards, expand the root filesystem — the stock image leaves most of the eMMC unallocated:

```bash
parted -s /dev/mmcblk0 resizepart 2 100%
resize2fs /dev/mmcblk0p2
df -h /            # expect ~28 GB
```

> **Cloned fleet boards skip this** — the golden image (Step 5) is captured *after* expanding, so every clone
> comes up already at ~28 GB. Only a fresh BSP flash (DIY, or the first golden board) needs the resize.

## Step 2 — demo package and runtimes

```bash
mkdir -p /opt/demo && cd /opt/demo
wget -O package.tar.gz https://downloads.iotconnect.io/partners/nxp/packages/frdm-imx95-genai-flow-demo-v1.0.2.tgz
tar -xzf package.tar.gz --overwrite
bash ./install.sh
```

Then install **eIQ GenAI Flow** (demo README section 3) and run one prompt so the model blobs download
*before* the workshop:

```bash
cd /root/eiq_genai_flow && python3 eiq_genai_flow.py -i keyb -o text -m danube-500M-q8
```

**llama.cpp** (for GGUF pushes) — fastest for a fleet is to copy the built binaries from a prepared board:

```bash
scp -r root@<ready-board>:/opt/llama/src/build /opt/llama/src/
```

## Step 3 — Ara boards only

```bash
# runtime 2.0.4 (matches whinlatter and the r2.0.4 models)
dpkg -i rt-sdk-ara2_2.0.4.deb
dpkg -i eiq-aaf-connector_2.0.deb
systemctl enable --now rt-sdk-ara2 eiq-aaf-connector
```

Models live in `/usr/share/llm/<name>/`. On a board with a large SD card, keep them on the card and bind-mount
so the eMMC stays free:

```
/mnt/models/<name>  /usr/share/llm/<name>  none  bind,nofail  0 0
```

Verify: `curl -s http://127.0.0.1:8100/v1/models` should list each enabled model with `"ready": true`.

> The connector loads **all enabled models at startup** and the module has 16 GB: the text 7B needs 8.1 GB and
> the VL 7B needs 12 GB, so they cannot both be enabled. Changing the enabled set requires restarting
> `eiq-aaf-connector`, and swapping large models is safest after `systemctl restart rt-sdk-ara2` (a device
> reset). Neither is quick — do not plan to switch models live in front of an audience.

## Step 4 — workshop preparation

```bash
bash /opt/demo/workshop-install.sh
```

This gives the board a unique mDNS hostname from its MAC, installs and enables all four services
(`genai-app`, `genai-provision`, `genai-camera`, `genai-bench`), warns about anything missing, and prints the
board's URLs. Do **not** install a device identity — attendees claim boards with their own kit
(see [WORKSHOP.md](WORKSHOP.md)).

Verify before calling a board done:

```bash
systemctl is-active genai-provision genai-camera genai-bench   # genai-app is inactive until claimed
curl -sk -o /dev/null -w "camera %{http_code}\n"   https://127.0.0.1:8080/live
curl -s  -o /dev/null -w "shootout %{http_code}\n" http://127.0.0.1:8090/
curl -s  -o /dev/null -w "claim %{http_code}\n"    http://127.0.0.1:8088/
```

At this point a DIY board is done. For a workshop fleet, this verified board becomes the golden master.

## Step 5 — workshop fleet: golden image via UUU

Prepare and verify **one** golden board (Steps 1–4), then clone it to the rest. Because a raw `dd` image omits
the boot0 bootloader (Step 0 note), the fleet is deployed with **UUU** — the same USB tool used to flash the
BSP — which writes the bootloader *and* the image in one pass.

**a. Make the golden board pristine** (so clones don't all share one identity):

```bash
rm -f /opt/demo/iotcDeviceConfig.json /opt/demo/device-cert.pem /opt/demo/device-pkey.pem  # ship unclaimed
: > /etc/machine-id ; rm -f /var/lib/dbus/machine-id     # regenerated per clone on first boot
rm -f /root/.ssh/id_* /tmp/*.sh /tmp/*.result 2>/dev/null
```

> Do **not** delete `/etc/ssh/ssh_host_*` on a board you manage over SSH — a keyless sshd refuses the next
> connection and locks you out (recover with a power-cycle; the image regenerates keys at boot). Leaving the
> host keys means clones share them, which is harmless for the demo (we use `StrictHostKeyChecking=no`).

**b. Capture the image** to a large SD card, and verify it in the same job:

```bash
sync
dd if=/dev/mmcblk0 bs=4M status=none | gzip -1 > /mnt/golden/golden.img.gz && \
  gzip -t /mnt/golden/golden.img.gz && echo VERIFIED
```

Copy `golden.img.gz` to the flashing PC and keep it as the master (a ~29 GB eMMC compresses to ~4–5 GB when
mostly empty). **Always `gzip -t` before trusting it** — a silent write glitch produced a corrupt image once;
a clean re-clone fixed it.

**c. Flash each board.** Decompress the master once on the PC (UUU sparse-skips the empty part, so the ~29 GB
file flashes only its ~6 GB of real data):

```bash
gunzip -k golden.img.gz          # -> golden.img
```

Per board: power off, set SW1 to Serial Download (SDP), USB-C to **USB1**, power on, then:

```bash
uuu -b emmc_all imx-boot-imx95-15x15-lpddr4x-frdm-sd.bin-flash_all golden.img
```

Set SW1 back to eMMC boot, power on, and finally give the board its own hostname:

```bash
bash /opt/demo/workshop-install.sh    # re-derives imx95-XXXX.local from this board's MAC
```

Cloned boards get distinct `.local` names automatically (hostname comes from the MAC). Confirm each board's
claim URL and write it on its card.

> **Scaling to ~30 boards.** UUU flashes **every** matching board attached at once, so a couple of powered USB
> hubs let you flash 4–8 boards per batch and cut a ~3–4 hour serial job to under an hour. Each flash is ~6–8
> min (sparse). Do a batch, boot them, run `workshop-install.sh` on each, label the cards, repeat.

## Rollback

If an upgraded board misbehaves, restore its backup image (Step 0) **on the same board**. Keep the golden image
and at least one known-good Ara backup until after the event.
