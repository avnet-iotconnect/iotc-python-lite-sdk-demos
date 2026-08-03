# Handoff prompt — NXP FRDM i.MX 95 GenAI Flow workshop prep

Paste this into the Claude Code session on the other PC to bring it up to speed on the work done
on this machine. It summarizes state, decisions, artifacts, and open items as of 2026-08-03.

---

## What this work is
Preparing a fleet of ~30 **NXP FRDM i.MX 95** boards running NXP's **eIQ GenAI Flow** demo, wired into
**Avnet /IOTCONNECT**, for a hands-on workshop. Repo:
`avnet-iotconnect/iotc-python-lite-sdk-demos`, path `nxp-frdm-imx-95/genai-flow-demo/`. Working branch for all
this work is **`workshop`** (not `main`). Standing rule: **no Claude co-author trailers on commits, no Claude
attribution in PR bodies.**

## Boards on the bench (IPs shift with DHCP — identify by role, not address)
- **Ara board** — `192.168.68.74` (was .76), hostname `imx95-15x15-lpddr4x-frdm`, claimed as `MCLiMX95b`.
  Has the Kinara Ara-2 / NXP Ara240 16 GB NPU. Runs the full working demo. **Left untouched.** Has a 64 GB SD
  card with a **17.2 GB full-eMMC backup** and the downloaded (but non-loading) VL-7B model.
- **Golden/workshop board** — `192.168.68.57` (has bounced through .70/.57), hostname `imx95-55ea`. No Ara.
  Reflashed to whinlatter, full stack rebuilt, **claimed as device `p95d122aa8a9`**. This is the golden master.
  Has a 64 GB SD card (label `golden`) holding the verified golden image.
- SSH: `root@<ip>`, no password. Always use
  `ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`.

## The big finding — which BSP to use
- **Use LF6.18.2-1.0.0 ("whinlatter", kernel 6.18.2, Python 3.13).** This is what runs the demo.
- **Do NOT use the newer LF6.18.20_2.0.0 ("wrynose").** It ships **Python 3.14 only**; NXP's GenAI Flow core is
  distributed as **`cpython-313` compiled binaries** (all branches of
  `nxp-appcodehub/dm-eiq-genai-flow-demonstrator`) that Python 3.14 cannot load. Verified on hardware: the demo
  stack does not run on LF6.18.20. Revisit only when NXP ships `cpython-314` builds.
- Decision: **stay on whinlatter (LF6.18.2-1.0.0)** and the docs were corrected to match.

## What was done this session
1. **Investigated running >7B on the Ara.** Downloaded NXP `Qwen2.5-VL-7B-Instruct-Ara240` (11.97 GB) to the
   Ara board's SD card, bind-mounted into `/usr/share/llm/`. It **fails to load** on rt-sdk 2.0.4 even alone on
   a freshly reset 16 GB device: `[version] installed products minor versions are not compatible`,
   `model found to be dyn quant v2 model`, then a 15-min timeout + `wait for model load failed 402`
   (`DV_MODEL_LOAD_FAILURE`). Capacity ruled out (tested after full `rt-sdk-ara2` device reset). Model card
   claims r2.0.4, so it's likely a dyn-quant-v2 vs runtime issue. **Open question for NXP.** Restored the
   working `Qwen2.5-7B-Instruct` + `Qwen25C15B` pair.
2. **Reflashed the golden board to whinlatter** via UUU (`emmc_all`, FRDM 15x15 boot binary +
   `imx-image-full-imx95evk.wic`), after first proving on the wrong BSP that LF6.18.20 breaks GenAI Flow.
3. **Rebuilt the full stack on the golden board:** rootfs expand, demo package v1.0.2, GenAI Flow + llama.cpp
   copied board-to-board from the Ara board (Python 3.13↔3.13), verified with a real `ask-llm` response.
4. **Fixed the stale CDN package.** The published `frdm-imx95-genai-flow-demo-v1.0.1.tgz` had an old
   `workshop-install.sh` that installed only 2 of 4 services (no camera, no shootout). Rebuilt as **v1.0.2**,
   uploaded to `downloads.iotconnect.io/partners/nxp/packages/frdm-imx95-genai-flow-demo-v1.0.2.tgz`, verified
   the live URL is byte-identical (sha256 `bd87a1e0…898a97`).
5. **Made a verified golden image.** `dd` of the golden board's eMMC → `golden.img.gz`, gzip-integrity
   verified (first pass corrupted by a transient write glitch; clean re-clone passed). **Master copy on this
   PC:** `C:\Users\micha\Downloads\golden-imx95-whinlatter-v1.0.2.img.gz` (4.52 GB). Also on the board's SD
   card at `/mnt/golden/golden.img.gz`.
6. **Fleet deploy method decided: UUU, not raw SD clone.** A whole-device `dd` of `/dev/mmcblk0` misses the
   eMMC boot partition (`mmcblk0boot0`) where the bootloader lives, so a raw restore to another board may not
   boot. UUU writes the bootloader correctly: `uuu -b emmc_all <frdm-boot-binary> golden.img`. UUU sparse-skips
   empty blocks (~6 GB real data) and flashes all attached boards at once — powered USB hubs let you batch.
7. **Claimed and tested the golden board** end-to-end (kit drop → MQTT connect in 633 ms → telemetry). Full
   attendee experience works.
8. **Corrected the documentation** (merged to `workshop`): BSP-UPGRADE.md rewritten around DIY-vs-workshop and
   the UUU clone; README corrected off LF6.18.20 → whinlatter and the fragile python3.13-on-3.14 workaround
   removed.

## PRs merged to `workshop` this session
- **#59** — republish demo package as v1.0.2 (all four workshop services)
- **#60** — BSP-UPGRADE.md: DIY vs workshop split, whinlatter correction, verified UUU fleet clone
- **#61** — README: whinlatter BSP correction + honest Neutron-on-FRDM caveat
(Branches deleted after merge. Repo has 4 branches: `main`, `workshop`, `rz3ge`, `wifi-module-exploration`.)

## Sites each prepared board serves
- Claim page: `http://<board>.local:8088` (or `:8088` by IP)
- LLM Shootout: `http://<board>.local:8090`
- Camera/live: `https://<board>.local:8080/live` (self-signed cert — accept once)
- Port 8100 (Ara AAF connector) exists only on the Ara board.

## Onboarding portal (AWS, for attendee self-service)
- Signup URL: `https://iynw30s3o6.execute-api.us-east-1.amazonaws.com/` (add `?new` to force a fresh form).
- **Event code: `EIQ2026`** (REQUIRE_CODE=1). Lambda `imx95-portal-api`, us-east-1, APPROVER `michael@lamptribe.com`.

## Open / pending items
- **Neutron NPU on FRDM whinlatter is UNCONFIRMED.** The whinlatter image ships only **EVK** Neutron DTBs
  (`imx95-15x15-evk-neutron.dtb`), **no `imx95-15x15-frdm-neutron.dtb`**; a booted FRDM shows the default
  ~960 MB CMA (needs >3 GB) though `/dev/neutron0` is present. README marks it Experimental. **Question:** the
  README benchmark table shows Neutron 13.7 tps "measured on FRDM LF6.18.2" — how was that measured? The other
  PC's session may know.
- **Ara VL-7B / larger-than-7B** — blocked on the r2.0.4 load failure above; needs NXP input on runtime vs
  dyn-quant-v2, or a BSP/runtime upgrade (which currently breaks GenAI Flow).
- **Fleet deploy (~30 boards)** — POSTPONED. Method ready (UUU + golden image). Before cloning, re-run the
  "pristine" step on the golden board (strip the `p95d122aa8a9` claim, blank machine-id) so clones ship
  unclaimed — the current golden SD image includes the claim.
- **Local branch note:** the working branch on THIS PC is `polarfire-load-saturation`, 82 commits behind
  `workshop`, with stale local copies of several genai-flow-demo files. All real work is on `workshop`.

## Gotcha learned (so the other session doesn't repeat it)
Do **not** delete `/etc/ssh/ssh_host_*` on a board you manage over SSH — a keyless sshd refuses the next
connection and locks you out (recovered by power-cycle; the image regenerates keys at boot). For golden images,
leave host keys (clones share them; harmless with StrictHostKeyChecking=no) and only blank `/etc/machine-id`.

---

### Suggested opening line for the other PC's session
"Continuing the NXP i.MX 95 GenAI Flow workshop prep. Read the state below. I need help with: <your ask —
e.g. the Neutron benchmark question, or finishing the 30-board fleet flash>." Then paste this file.
