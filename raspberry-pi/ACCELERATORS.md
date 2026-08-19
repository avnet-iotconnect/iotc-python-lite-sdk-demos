# M.2 AI Accelerators on Raspberry Pi 5 — Field Notes

Practical notes from building and measuring the vision demos in this
directory on two M.2 NPUs: the **DEEPX DX-M1** and the **Hailo-8**. Both are
~25 TOPS-class, both fit an M.2 slot on a Pi 5 (PCIe Gen 3 x1), and both run
real demos well — but they have distinctly different strengths, and the right
choice depends on the workload.

## DEEPX DX-M1

**Strengths**

- **Vision transformers (ViT) are a first-class workload.** CLIP's ViT-B
  image encoder measured **207 fps** on-device — enough to score every frame
  of a 30 fps camera with ~7× headroom, or run the vendor's 16-stream
  multi-channel demo.
- **Large model memory**: 4 GB of on-module LPDDR5 leaves room for multiple
  and larger models.
- **Straightforward Linux bring-up from public sources**: driver, runtime,
  firmware, and demo apps are all public GitHub repositories; the stack
  builds natively on Ubuntu and Raspberry Pi OS (aarch64).
- Runs a 270+ model zoo spanning CNNs and transformer families.

**Trade-offs**

- Higher power envelope (~3–5 W); wants an actively cooled installation.
- Younger ecosystem: expect some assembly during bring-up.

## Hailo-8

**Strengths**

- **CNN pipelines at remarkable efficiency.** YOLOv8m object detection, pose
  estimation, and instance segmentation each ran at the full **30 fps camera
  rate**, and CLIP inference drew only **0.8 W** measured at the module.
- **Polished, integrated tooling**: on Raspberry Pi OS the entire stack is
  one `apt install hailo-all`; TAPPAS/GStreamer pipelines, a rich apps suite
  (`hailo-apps`), and scheduler support for multi-model concurrency.
- **Mature ecosystem**: extensive documentation, an active community forum,
  and official Raspberry Pi partnership (the AI Kit family).

**Trade-offs**

- **Transformers are not its natural workload**: the dataflow architecture
  is optimized for CNNs, and ViT-class models pay a heavy context-switching
  penalty (see measurements below).
- Prebuilt runtime packages target Raspberry Pi OS; other distros require a
  Hailo Developer Zone account or source builds.
- No on-module DRAM (weights stream from host memory).

## Measured head-to-head (same Pi 5 platform, PCIe Gen 3 x1)

| Workload | DEEPX DX-M1 | Hailo-8 |
|---|---|---|
| CLIP ViT-B image encoder, NPU throughput | **207 fps** | 10.1 fps (85.7 ms latency) |
| CLIP text encoder | ~4.6 prompts/s (ran on host CPU) | **~11 prompts/s on-NPU** |
| YOLOv8m detect / pose / segment pipeline | not measured | **~30 fps (camera-limited), all three** |
| Power during CLIP inference (module) | not measured (3–5 W spec) | **0.81 W measured** |
| Live CLIP demo behavior | scores every frame, large headroom | scores update ~10 Hz under a 30 fps feed |

**Caveats**: single-sample measurements from working demo installations, not
controlled benchmarks. The CLIP models differ slightly per vendor toolchain
(quantization and fine-tune variants of the same ViT-B architecture), so
treat ratios as order-of-magnitude, not exact. Both modules negotiated PCIe
Gen 3 x1 — the Pi 5's single exposed lane, not the modules' maximum.

## Choosing

- **Transformer/VLM workloads** (CLIP, zero-shot search, vision-language):
  the DX-M1's architecture is built for this — it holds a ~20× throughput
  advantage on the ViT encoder in our measurements.
- **Classic CNN vision** (detection, pose, segmentation, tracking): the
  Hailo-8 delivers full camera rate at very low power with the smoothest
  install experience on Raspberry Pi OS.
- **Multi-stream or scoring-every-frame requirements**: DX-M1 headroom
  matters; a single Hailo-8 saturates on one transformer stream.
- **Battery/thermal-constrained CNN deployments**: Hailo-8's sub-1 W draw is
  hard to beat.

Both demos in this directory are steerable end-to-end from /IOTCONNECT — the
cloud surface (commands, telemetry, dashboards) is identical regardless of
which accelerator sits in the M.2 slot.
