# Ara-2 / Ara240 enablement + bring-up — FRDM-IMX95 GenAI Flow demo

Goal: run (and benchmark) LLMs on the **Kinara Ara-2 / NXP Ara240** M.2 module installed in our
**FRDM-IMX95**, then wire it into the /IOTCONNECT eIQ GenAI Flow demo as an `ara2` backend.

## TL;DR — two paths, very different cost

| | **Path A — Run NXP's pre-built models** *(recommended)* | **Path B — Compile our own models** |
|---|---|---|
| Needs | An **NXP account** (to pull `rt-sdk-ara2.deb`). Everything else is public. | Full **Ara SDK (~6.4 GB) + model converter + compile license key + an x86_64 Linux host**. |
| NDA? | **No** — account-gated download + public repos + Apache-2.0 models | Likely NDA + license (DNPU Training Hub / FAE) |
| When you need it | The demo's headline models (Qwen 1.5B + 7B) are already published for Ara240 | Only for models NXP hasn't published: Danube-500M, SmolVLM2, Llama-3.1-8B, custom fine-tunes |

**Bottom line:** for this demo we can almost certainly use **Path A** and skip the compiler entirely. Path B is
only needed if we insist on putting our *current* demo models (Danube/SmolVLM) or a bigger custom LLM on the Ara.

---

## Path A — Run the published Ara240 models (the fast path)

| Component | What it is | Where to get it | Access |
|---|---|---|---|
| **Ara2 Runtime SDK** (`rt-sdk-ara2`) | Proxy daemon, `libaraclient`, firmware, hw-metrics, Python bindings, `install.sh`; installs `rt-sdk-ara2.service` (starts at boot) | NXP **ARA-SDK** landing page (`ARA-SDK`); repo `github.com/nxp-imx/rt-sdk-ara2`; NXP Community *"How to install rt-sdk-ara2 on FRDM-IMX95"* + RN00459 | **NXP account** (EULA). **Version must match the board BSP — see note below** |

> ⚠️ **Version finding (verified on our board):** our board runs BSP **LF6.18.2-1.0.0**, whose kernel does **not**
> ship the `uiodma` PCIe driver. The runtime **2.1.1** `.bin` (what we first downloaded) targets **LF6.18.20_2.0.0**
> — it ships **no `uiodma.ko`** because that driver is baked into the newer kernel image, so its `hw_bringup.sh`
> fails here (`modprobe uiodma` → "module not found"). **Download the `2.0.4` `.deb` (`RT-SDK-ARA2-2.0.4`)**, which
> is the version paired with LF6.18.2-1.0.0 and carries the driver for our kernel. (Alternative: update the board
> to LF6.18.20_2.0.0 and use 2.1.1 — heavier, and not needed just to run the demo.)
| **`eiq-aaf-connector`** | REST server ("Optimum Ara") exposing an OpenAI-style `/v1/chat/completions` (SSE streaming) in front of the runtime | Public: `github.com/nxp-imx-support/eiq-aaf-connector` (+ deb) | Public |
| **Models (`model.dvm`)** | `nxp/Qwen2.5-Coder-1.5B-Ara240`, `nxp/Qwen2.5-7B-Instruct-Ara240` | Hugging Face `huggingface.co/nxp` (auto-fetched by launcher / a `fetch_models` wheel) | **Public, Apache-2.0** |
| **`llm-edge-studio`** *(optional GUI)* | Qt/QML launcher — model picker + prompt box, good for a booth screenshot | Public: `github.com/nxp-imx-support/llm-edge-studio`; `.deb` on NXP.com | Public / NXP.com |
| **BSP** | eIQ AAF Connector requires **LF6.18.2-1.0.0 (Q1 2026)** — **our board already runs `6.18.2-1.0.0`** ✅ | (already installed) | — |

**NXP-published Ara240 numbers (use as sanity anchors, we'll measure our own):**
Qwen2.5-Coder-1.5B ≈ **14.9 tok/s**, TTFT 0.26–9.5 s · Qwen2.5-7B-Instruct ≈ **6.0 tok/s**, TTFT 1.9–16.7 s.

**Demo integration note:** the `eiq-aaf-connector` speaks an **OpenAI-compatible REST API**, so the demo's `ara2`
backend can just POST to the local connector (`/v1/chat/completions`) instead of spawning a GenAI Flow
subprocess — cleaner than the Neutron path, and it streams tokens (SSE) for live tok/s telemetry.

## Path B — Compile our own models for Ara240 (only if Path A models aren't enough)

To turn an arbitrary model into a `model.dvm`:

1. **Full Ara SDK** — `ara2-sdk-r<ver>.tar.gz` (~6.4 GB), which contains the **host-side model-converter Docker
   image** (`dvdocker`, ~14 GB uncompressed). This is *separate from* the runtime `.deb` above.
2. **A compile license key** — the converter's `.dvm`-generation stage does a **license checkout** and fails
   without it. This is the specific thing to request; the runtime does not need it.
3. **An x86_64 Linux host** with **Docker**, **≥ 8 GB RAM** (NXP's figure for generative-AI compile; 2 GB for
   conventional CNNs), and ~20+ GB free disk for the image. *(We said we don't have this set up — so Path B
   means standing up an x86 box, or asking NXP/Kinara to compile the model for us.)*
4. **The model in ONNX** (converter also takes PyTorch / TorchScript / TFLite / TF / Caffe / Mxnet), plus
   **quantization** (integrated Kinara quantizer, or a pre-quantized model) — int8 quantization typically
   needs a **calibration dataset**.
5. **Access:** via NXP's **DNPU Training Hub** / your FAE — expect NDA + the compile license, unlike Path A.

## Questions to confirm with NXP

1. **Runtime access:** confirm `rt-sdk-ara2.deb` is downloadable with a standard **NXP account** (EULA), no NDA.
2. **BSP match:** `eiq-aaf-connector` targets **LF6.18.2-1.0.0** (our board) but `llm-edge-studio` v2.0.0's badge
   says LF6.18.20_2.0.0 — does `rt-sdk-ara2` run on our **LF6.18.2-1.0.0**, or do we need a BSP update?
3. **Python:** are the `rt-sdk-ara2` Python bindings built for **CPython 3.13** (our board's system Python 3.13.9)?
4. **Compile license (only if Path B):** how is the compile license key obtained, is it node-locked/floating,
   and is it separate from the runtime EULA?
5. **PCIe width:** our link trains to **Gen3 x1** though the endpoint is Gen4 x4 capable — expected for the
   FRDM-IMX95 M.2 slot? Throughput impact on model load / token latency?

---

## Board facts (verified on our unit)

| Item | Value |
|---|---|
| Board | NXP **FRDM-IMX95** (`imx95-15x15-lpddr4x-frdm`) |
| SoC | **i.MX 95**, revision **2.0 (B0)** |
| Distro / kernel | NXP i.MX Release Distro **6.18-whinlatter**, kernel **`6.18.2-1.0.0-gf49f45233f7b`** aarch64 |
| Python | **3.13.9** (system) |
| Ara-2 module | PCIe endpoint **`1e58:0002`** (rev 02), "Processing accelerators", IOMMU group 11 |
| Current module state | **`enable=0`, no driver bound** (BARs disabled); `Failed to enable PASID` in dmesg; link **Gen3 x1** (cap: Gen4 x4) |
| Software present | eIQ GenAI Flow 3.0.0, onnxruntime 1.23.2, torch 2.8.0; **no Ara runtime/driver yet** |
| Free rootfs | ~16 GB |

## References

- NXP **Ara SDK** page (`ARA-SDK`) · NXP **ARA240** module · Release Note **RN00459** (Ara2 Software Packages)
- NXP Community: *"How to install rt-sdk-ara2 on FRDM-IMX95"* (Solved) · *"Ara240 Run Time Environment (rt-sdk-ara2)"* (DNPU Training Hub)
- GitHub: `nxp-imx/rt-sdk-ara2` · `nxp-imx-support/eiq-aaf-connector` · `nxp-imx-support/llm-edge-studio` · `nxp-imx-support/vlm-edge-studio`
- Hugging Face: `huggingface.co/nxp/Qwen2.5-7B-Instruct-Ara240`, `huggingface.co/nxp/Qwen2.5-Coder-1.5B-Ara240`
