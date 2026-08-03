# Upgrading and preparing workshop boards

How to get a FRDM i.MX 95 onto the current software stack, and how to prepare a fleet of them for a workshop.
Written to be repeatable: prepare **one** board fully, verify it, then clone.

> **Order matters.** Upgrade a board *without* an Ara240 first — it proves the whole flow with the risky
> variable absent. Only then touch an Ara board, and only with a restorable backup in hand.

## The stack

| Layer | Applies to | Notes |
|---|---|---|
| NXP i.MX Linux BSP | every board | **LF6.18.20_2.0.0** (25 June 2026) is current — [release notes RN00210](https://www.nxp.com/docs/en/release-note/RN00210.pdf) |
| NXP eIQ GenAI Flow | every board | the LLM/VLM/voice stack; check for a newer release at upgrade time |
| This demo package | every board | `frdm-imx95-genai-flow-demo-v1.0.2.tgz` (README section 5) |
| llama.cpp | every board | needed for GGUF models pushed from /IOTCONNECT |
| rt-sdk-ara240 | **Ara boards only** | 2.0.4 today; 2.1.1 (`imx-nxp-ara2-2.1.1-*.bin`) needs LF6.18.20_2.0.0 |
| eIQ AAF Connector | **Ara boards only** | must match the rt-sdk version |

### Known constraint before upgrading an Ara board

Every NXP-published Ara240 model (7B, Coder-1.5B, VL-7B) states runtime **r2.0.4** on its model card. It is
**not established** that those models load on rt-sdk 2.1.x. Upgrading the runtime may leave an Ara board with
no working models. Confirm with NXP which runtime their current models require *before* upgrading a board you
need for a demo — and take the backup below regardless.

Related open issue: `Qwen2.5-VL-7B-Instruct-Ara240` fails to load on 2.0.4 even on a freshly reset 16 GB
device — `[version] installed products minor versions are not compatible`, `model found to be dyn quant v2
model`, then a 15-minute session timeout and `wait for model load failed 402`. Capacity is ruled out.

## Step 0 — back up (Ara boards, or any board you cannot rebuild)

With a large SD card mounted at `/mnt/models`:

```bash
sync
dd if=/dev/mmcblk0 bs=4M status=none | gzip -1 > /mnt/models/emmc-backup-$(date +%Y%m%d).img.gz
sync
```

Restore (from a rescue boot or another machine with the card):

```bash
gunzip -c emmc-backup-YYYYMMDD.img.gz | dd of=/dev/mmcblk0 bs=4M conv=fsync
```

A 29 GB eMMC compresses to roughly 10–14 GB and takes 1–2 hours. Verify the file exists and is non-trivially
sized before proceeding.

## Step 1 — flash the BSP

Follow [FLASHING.md](../FLASHING.md) with the LF6.18.20_2.0.0 image for `imx95-19x19-verdin` / FRDM-IMX95.
Afterwards, expand the root filesystem — the stock image leaves most of the eMMC unallocated:

```bash
parted -s /dev/mmcblk0 resizepart 2 100%
resize2fs /dev/mmcblk0p2
df -h /            # expect ~28 GB
```

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
# runtime (matched to the BSP - 2.1.1 requires LF6.18.20_2.0.0)
chmod +x imx-nxp-ara2-2.1.1-*.bin && ./imx-nxp-ara2-2.1.1-*.bin
dpkg -i eiq-aaf-connector_*.deb
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
systemctl is-active genai-app genai-provision genai-camera genai-bench
curl -sk -o /dev/null -w "camera %{http_code}\n" https://127.0.0.1:8080/live
curl -s  -o /dev/null -w "shootout %{http_code}\n" http://127.0.0.1:8090/
curl -s  -o /dev/null -w "claim %{http_code}\n" http://127.0.0.1:8088/
```

## Step 5 — clone the fleet

Prepare and verify one **golden board**, then clone its eMMC to the rest rather than repeating the install:

```bash
# on the golden board (identity NOT installed)
dd if=/dev/mmcblk0 bs=4M status=none | gzip -1 > /mnt/models/golden.img.gz
```

Write that image to each board's eMMC, then on each one:

```bash
bash /opt/demo/workshop-install.sh    # re-derives the hostname from that board's MAC
```

Cloned boards get distinct `.local` names automatically because the hostname comes from the MAC. Confirm each
board's claim URL and write it on its card.

## Rollback

If an upgraded board misbehaves, restore its backup image (Step 0). Keep the golden image and at least one
known-good Ara backup until after the event.
