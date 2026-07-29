# Ara‑2 / NXP Ara240 stack: obtaining it, and compiling your own models

Reference notes for the `ara2` backend. The **run** path (install the runtime, run NXP's pre‑built models) is a
step‑by‑step in the README — [Enabling the Ara240 backend](../README.md#enabling-the-kinara-ara-2--nxp-ara240-backend).
This doc records how the software is obtained (no NDA needed) and how to build your *own* Ara240 models.

## Where the stack comes from — all account‑gated, not NDA

Everything for running models on the Ara240 is a normal **NXP‑account download** from the **Ara Software
Development Kit** page — <https://www.nxp.com/design/design-center/software/embedded-software/ara-software-development-kit:ARA-SDK> —
plus public GitHub and Hugging Face:

| Piece | Where | Access |
|---|---|---|
| **Ara2 Runtime SDK** (`rt-sdk-ara2`) | ARA‑SDK page; `github.com/nxp-imx/rt-sdk-ara2` | NXP account |
| **eIQ Connector** (`eiq-aaf-connector`) | ARA‑SDK page; open source on GitHub | NXP account / public |
| **Models** (`model.dvm`) | Hugging Face `huggingface.co/nxp/*-Ara240` | Public, Apache‑2.0 |

> ⚠️ **Runtime version must match the board BSP.** On BSP **LF6.18.2‑1.0.0** use **Runtime SDK `2.0.4` (`.deb`)**,
> which bundles a `uiodma.ko` matching the kernel. The `2.1.1` (`.bin`) targets **LF6.18.20_2.0.0**+, where the
> `uiodma` driver ships in the kernel image — so on the older BSP it brings up nothing (`modprobe uiodma` fails).
> Check the board with `uname -r`.

## Compiling your own models (only if the pre‑built ones aren't enough)

The `nxp/*-Ara240` models cover the demo. To put a **different** model on the Ara240 you compile it to a
`model.dvm` yourself:

- **Full Ara SDK** — `ara2-sdk-r<ver>.tar.gz` (~6.4 GB), which contains the host‑side **model‑converter Docker
  image** (separate from the runtime `.deb`).
- **A compile license key** — the converter's `.dvm` generation does a license checkout and fails without it.
- **An x86_64 Linux host** — Docker, ≥ 8 GB RAM (NXP's figure for generative‑AI compile), ~20 GB free disk.
- **The model in ONNX** (also PyTorch / TFLite / TF), plus quantization (Kinara quantizer or pre‑quantized;
  int8 typically needs a calibration set).
- Access via NXP's **DNPU Training Hub** / your FAE — expect NDA + license for the compiler (unlike the run path).

Once compiled, deploying it is the easy part: push the `model.dvm` bundle to the device straight from IOTCONNECT
— see [MODEL-PUSH.md](MODEL-PUSH.md).

## Board facts (this unit, for reference)

| Item | Value |
|---|---|
| Board / SoC | FRDM‑IMX95 (`imx95-15x15-lpddr4x-frdm`), i.MX 95 rev **2.0 (B0)** |
| Distro / kernel | NXP i.MX **6.18-whinlatter**, kernel `6.18.2-1.0.0-gf49f45233f7b` aarch64 |
| Ara‑2 module | PCIe `1e58:0002`, bound to `uiodma` after `rt-sdk-ara2` installs |
| Connector | eIQ AAF Connector on **:8100** (clear of the demo's MCP on :8000) |
