# Generative AI at the Edge — 60-Minute Workshop

**Abstract, agenda, and slide-by-slide deck** for the hands-on FRDM i.MX 95 GenAI workshop.
Presenter-facing companion to [ATTENDEE-GUIDE.md](ATTENDEE-GUIDE.md) (the attendee handout) and
[WORKSHOP.md](WORKSHOP.md) (board prep and room logistics). A presentable HTML version of these
slides is at [workshop-slides.html](workshop-slides.html) — open it in a browser, arrow keys to
navigate.

---

## Abstract

Generative AI is leaving the data center. In this hands-on hour, you'll run a language model, a
vision-language model, a tool-calling agent, a retrieval database, and a complete offline voice
assistant — all on an embedded board on the bench in front of you, and all managed from the cloud.

Each attendee gets an **NXP FRDM i.MX 95** (6× Cortex-A55, eIQ Neutron NPU, 8 GB LPDDR4X) running
NXP's **eIQ GenAI Flow** pipeline, connected to a **private space in Avnet /IOTCONNECT**. You'll
claim your board with a drag-and-drop, prompt its on-device LLM from your own dashboard, catch it
hallucinating, fix that with an agent and with RAG, and measure exactly what tokens/sec,
time-to-first-token, quantization, and an NPU are worth — including a live look at the **Kinara
Ara-2 (NXP Ara240)** discrete NPU running a 7-billion-parameter model on the presenter's board:
five times the parameters at the same speed, on the same board.

Along the way you'll learn the model lifecycle that production fleets need: pushing a new model
from the /IOTCONNECT console to a device in under a minute, and how that differs from an OTA
application update and from a plain file update (like refreshing the RAG knowledge base); how
field-captured images, clips, and telemetry metadata become **ground truth** in S3 for retraining
in **Amazon SageMaker**; and how **Kinesis Video Streams** and services like Rekognition extend
the same pipeline to live video.

No ML background required — if you can bring up a board, you can leave with a working mental model
of edge GenAI, real measured numbers, and a platform account that keeps working after the workshop.

**Audience:** hardware design engineers with some firmware experience; no ML background assumed.
**Duration:** 60 minutes. **Format:** presentation + guided hands-on (each attendee has a prepared
board; boards are returned at the end, accounts remain live).

---

## Agenda

| Time | Segment | What happens |
|---|---|---|
| 0:00–0:04 | **Welcome** | What's on your bench, what you'll leave knowing |
| 0:04–0:16 | **GenAI in hardware terms** | LLMs & quantization, VLMs, agents, RAG, voice + STT — each concept mapped to what's on the board |
| 0:16–0:22 | **The stage** | i.MX 95 + Neutron NPU, Ara240 discrete NPU, eIQ GenAI Flow, /IOTCONNECT (attendees start portal signup here) |
| 0:22–0:34 | **Lab: claim your board** | Portal → board kit → claim page → your private dashboard → first prompts |
| 0:34–0:42 | **Measuring GenAI** | The metrics that matter, the measured model ladder, live LLM shootout, the Ara240 before/after |
| 0:42–0:52 | **The model lifecycle** | Live model push from the console; OTA vs. model update vs. file update; SageMaker retraining; ground truth in S3; KVS video |
| 0:52–0:56 | **Voice finale** | "Hey NXP" — the fully offline voice pipeline, ending with a spoken command that flips a real LED across the room |
| 0:56–1:00 | **Wrap-up + Q&A** | What stays live after today, where everything is documented |

**Pacing notes for the presenter**

- At **0:16**, tell attendees to start the portal signup on their laptops (name, email, company,
  event code) while you present the platform section — invites and kits are ready by lab time.
- Send `agent-start` to your presenter board at **0:22** (~1 min to warm). Idle agent sessions
  auto-stop after `agent_idle_timeout_s` (60 min default), so one warm-up covers the talk — but a dead
  agent kills the LED beat, so re-send it if `agent_status` ever leaves `ready`.
- Send `voice-start` at **~0:49**, but only **after** slide 22's verification `ask-llm` (and any
  `rag-add` fallback question) has completed — the voice session needs 2–3 minutes to reach
  `listening`, and once it starts, `ask-llm` reports **busy** until `voice-stop`.
- The board runs **one AI operation at a time** — a second command sent while one is running
  fails immediately with a **"busy"** ack (nothing queues). Tell attendees to wait for
  `genai_status: idle` between commands, and don't fire dashboard buttons at your presenter board
  while the shootout or a voice session is running.

---

## The deck

Format: **slide title** → bullets as they appear on the slide → *speaker notes* (with source
files so future edits stay honest). ~28 slides for 60 minutes; the lab and demo slides hold the
screen for several minutes each.

---

### 1 · Title

**Generative AI at the Edge**
A hands-on hour with the NXP FRDM i.MX 95, the Ara240 NPU, and Avnet /IOTCONNECT

- Presenter name · event · date

*Notes: Boards should already be powered and claimed-page-ready (see WORKSHOP.md host prep). The
card next to each board carries its personal claim URL — mention that now so nobody unplugs or
swaps boards.*

---

### 2 · What's on your bench

- **Your board**: NXP FRDM i.MX 95 — prepared, powered, on the room network
- **The card next to it**: your board's personal URL (`http://imx95-XXXX.local:8088`) — this is how you'll claim it
- **My board**: the same FRDM i.MX 95 **plus a Kinara Ara-2 / NXP Ara240** M.2 NPU module
- Every model you'll use today runs **on the board** — the cloud is how we reach it, measure it, and manage it

*Notes: Set the frame early: this is not an API demo — the LLM, VLM, STT, TTS, and vector DB all
execute on the 6 Cortex-A55s (and NPUs) in front of them. The only cloud round-trips are commands
in and telemetry out. Boards go back at the end; their /IOTCONNECT accounts stay live
(ATTENDEE-GUIDE §5–6).*

---

### 3 · What you'll leave knowing

- What LLMs, VLMs, agents, RAG, and a voice pipeline actually are — in hardware terms
- How GenAI performance is measured: load time, TTFT, tokens/sec — and what quantization and NPUs buy
- How to run all of it on an i.MX 95, and what changes when you add an Ara240
- How a fleet manages models from /IOTCONNECT: **OTA vs. model push vs. file update**
- How field data becomes **ground truth** in S3, retrains in **SageMaker**, and comes back as a model push
- Where live video fits: **KVS streaming** and cloud analysis services

*Notes: This list mirrors the agenda — return to it in the wrap-up as "we did all of this."*

---

### 4 · Agenda

- The agenda table from above, as a timeline.

*Notes: Flag the two audience-participation moments: the lab at 0:22 and the shootout at ~0:38.*

---

### 5 · What is an LLM, in hardware terms

- A next-token predictor: text in → probability of the next token out, looped
- A **token** ≈ 4 characters; every generated token reads essentially **all the weights** once
- The weights are a big constant array: Danube-500M at 8-bit ≈ **496 MB**; Qwen2.5-7B ≈ 15 GB at FP16
- So generation speed is **memory-bandwidth-bound** — a very familiar problem
- Parameter count buys capability; it also costs bandwidth, RAM, and storage

*Notes: This audience thinks in buses and footprints — meet them there. "500 million parameters"
lands as "a 496 MB lookup structure you stream through per token" (sizes: MODELS.md language-model
table). That's why tok/s, not FLOPs, is the number everyone quotes, and why the rest of the hour
is about fitting the best model into the bandwidth you have.*

---

### 6 · Quantization: the first lever you pull

- Shrink weights from FP16 → INT8 → INT4: smaller, faster, *usually* fine
- On this board: Danube-500M **q8 = 496 MB**, **q4 = 345 MB** — q4 is faster everywhere
- The catch: naive uniform 4-bit **broke RAG** on Danube (canned refusals instead of quoting docs)
- GGUF **Q4_K_M** mixed-precision keeps damage-sensitive layers at 6-bit — Qwen-1.5B kept its reasoning
- Lesson: *4-bit is survivable with mixed precision, brutal without it* — always re-validate after quantizing

*Notes: The demo carries a real cautionary tale (MODELS.md quantization section + QoR table):
Danube-q4 scores F on RAG synthesis while chatting fluently — quantization broke exactly the
fragile skill. Analogy that lands: it's precision loss in a control loop — fine until it isn't,
and you find out in validation, not in the datasheet.*

---

### 7 · VLM: a camera the board can talk about

- Vision-language model = **vision encoder + LLM decoder**
- On this board: **SmolVLM2-256M**, INT8, ~250 MB — answers questions about a live USB-camera frame
- Measured: vision encode ~4.4 s · first token ~4.9 s · decode ~9.5 tok/s
- The image **never leaves the board**
- Two costs to watch: the *encode* (per image) and the *decode* (per token)

*Notes: `ask-vlm` captures a fresh frame via GStreamer and answers "Describe what you see"
(numbers: MODELS.md VLM table — README §7 carries older figures). The privacy point — inference
where the sensor is — is a real product argument for this audience. Mention the warm-worker
trick: the first VLM question pays a ~40 s model load, then a resident worker answers in ~5 s
(src/vlm_worker.py).*

---

### 8 · Agents: stop the model from guessing

- Ask a small LLM *"what time is it?"* — it will confidently invent one
- An **agent** fixes that: the LLM only **chooses a tool** → the board **executes it** → the answer is grounded in the tool's real output
- This board's tools: time, SoC temperature, memory, disk, uptime, IP, USB devices — plus **cloud tools** (its own /IOTCONNECT fleet) via an on-board MCP server
- Telemetry shows the whole chain: `agent_tool` → `agent_tool_result` → `agent_response`

*Notes: The hallucination A/B is the demo's smartest beat (demo-flow.md): `ask-llm what time is
it` (wrong, fast, confident) vs. `ask-agent what time is it` (right, with the tool chain in
telemetry). Be honest about small-model agents: a keyword fallback rescues unparseable tool picks
(`agent_router` says `llm` or `keyword`), and a grounding check replaces divergent answers with
the raw tool result (src/app.py). That's what production agents on 500M-parameter models look
like.*

---

### 9 · RAG: teach the board its own manual

- Small models hallucinate **facts**; RAG retrieves real passages and injects them into the prompt
- Ingredients: an **embedding model** (all-MiniLM-L6-v2 — 22 M params, 384-dim vectors, 88 MB) + a chunked knowledge base + similarity search
- This board's knowledge base is literally **24 hand-written passages in a JSON file** — about itself
- With RAG on: *"How do I expand the root filesystem?"* → the actual `parted`/`resize2fs` commands, verbatim
- Measured lesson: **grounding beats parameters** — tiny Danube + RAG outscores every bigger ungrounded model on documentation questions

*Notes: Show rag-db/FRDM95_hand_made_chunks.json on screen — a RAG DB demystified to "a JSON file
of facts" is a genuine aha for this audience. Swap in your service manual and every field unit
answers from it, offline. QoR table (MODELS.md): Danube-q8 grades D on ungrounded general facts
but A- on RAG synthesis with RAG on (overall C unassisted → B+ grounded). Embedding runs on the
board at ~30 chunks/s. Keep the stale-chunk observation in your pocket — it pays off on slide
22.*

---

### 10 · The voice pipeline: four models in a row

- **"Hey NXP"** wake word (VIT, always-on, ~5% CPU) → **STT** → **LLM** → **TTS** (VITS, streaming, 22 MB) — fully offline
- STT is a classic embedded trade-off — pick per product:

| STT model | Size | Transcribe | Word error rate |
|---|---|---|---|
| moonshine-tiny | 40 MB | 3.85 s | 1.06 % |
| moonshine-base | 84 MB | 4.21 s | 1.59 %* |
| whisper-small.en | 275 MB | 5.40 s | 0.00 % |

- *\*base wins in real room acoustics — clean-set WER flatters tiny*

*Notes: Numbers from MODELS.md STT table (NXP's official benchmark, WER vs. known transcript).
`set-stt` switches transcribers from the cloud; it applies at the next `voice-start`. Wake-word
physics worth sharing: reliable detection needs ~4000 RMS at the mic — arm's length — which is
why show-floor voice demos fail. We close the workshop with this pipeline live.*

---

### 11 · The board: NXP FRDM i.MX 95

- **i.MX 95**: 6× Cortex-A55 + Cortex-M7 + Cortex-M33, **eIQ Neutron NPU** (2 TOPS)
- FRDM board: **8 GB LPDDR4X**, 32 GB eMMC, Wi-Fi 6 / BT 5.4 (IW612)
- What the full GenAI kit costs in resources (measured):
  - Disk: GenAI Flow 1.6 GB · Python AI stack 1.6 GB · llama.cpp + Qwen models 2.0 GB · SmolVLM 0.7 GB → **~16 GB still free**
  - RAM: full demo state (voice session + warm agent) ≈ 5.3–6.8 GB of 8 GB
- **eIQ GenAI Flow** = NXP's pipeline tying it together: wake word, STT, RAG, LLM, TTS

*Notes: Budgets from MODELS.md "what fits" tables — engineers love a resource budget. One honest
caveat: the Neutron path is experimental — it needs B0 silicon and a device-tree overlay
reserving a 4 GB CMA pool, and it recompiles the model on every launch (~2 min). That's why the
demo's default backend is CPU.*

---

### 12 · The accelerator: Kinara Ara-2 / NXP Ara240

- Discrete edge NPU: **~40 eTOPS**, M.2 M-key card, PCIe — purpose-built for generative AI
- Software: **eIQ AAF Connector** — an **OpenAI-compatible REST server** (`/v1/chat/completions`) on the board, in front of the Ara runtime
- So `ask-llm` doesn't change — `set-backend ara2` just reroutes it
- Models stay **resident** on the module: zero load time per prompt; during 7B generation, ~12% host CPU and host RAM flat
- Pre-compiled models are public (Apache-2.0): Qwen2.5-7B-Instruct and Qwen2.5-Coder-1.5B on Hugging Face

*Notes: Specs and stack from MODELS.md Ara240 section. The OpenAI-compatible API is a deliberate
teaching point: the industry-standard LLM interface, served by an M.2 card on PCIe. Runtime and
connector are NXP-account-gated (not NDA); compiling *custom* models needs the full Ara SDK on an
x86_64 host plus a compile license. Numbers land on slide 19 — this slide is what it is, that one
is what it's worth.*

---

### 13 · The management plane: /IOTCONNECT

- Every board here is a normal /IOTCONNECT device — nothing workshop-specific
- The **device template** is the contract: this one defines **54 telemetry attributes** and **18 commands**
- **D2C**: the board publishes ~50 attributes every 10 s over MQTT (perf metrics, AI responses, health)
- **C2D**: every dashboard button is a real cloud-to-device command with an acknowledgement
- Plus: x.509 device identity, OTA delivery, **AI model management**, file storage, fleet queries — all on a public REST API
- Isolation is enforced by the **platform**, not the workshop UI: you'll only ever see your own board

*Notes: The capability-to-API mapping table in ATTENDEE-GUIDE §4 is the reference — everything
today (signup, cockpit, dashboards) runs on the same REST API customers use. The "your private
entity" model is the multi-tenant mechanism a production deployment uses to separate customers.
**Cue the room now**: open the portal URL, sign up with the event code — kits will be ready when
the lab starts.*

---

### 14 · Lab: claim your board (~5–10 minutes)

1. **Sign up** on the portal — name, email, company, **event code**, and **choose a password** → your private space is created instantly
2. **Log in** at [awspoc.iotconnect.io](https://awspoc.iotconnect.io) with the password you just chose — no email check needed
3. **Download your board kit** (.zip) — your device's identity: config + x.509 cert + private key
4. **Open your board's URL** from the card (`http://imx95-XXXX.local:8088`)
5. **Drag the kit onto the page** → board installs the identity, restarts the demo → **"✓ Connected as p95…"**

*Notes: Follow ATTENDEE-GUIDE §2 — that's the attendees' own copy of these steps plus
troubleshooting. The password-at-signup path needs the event code (it uses instant onboarding);
anyone who leaves it blank falls back to the emailed invite with a temporary password. What the
kit is: `iotcDeviceConfig.json`, `device-cert.pem`, `device-pkey.pem` — a real x.509 device
identity, the same mechanism a production fleet uses, not a workshop toy.
Claim-page safety: a claimed board demands an explicit confirmation before being re-claimed, so a
mistyped URL can't steal a neighbor's board (WORKSHOP.md part 3). Failure cheat-sheet is in
WORKSHOP.md troubleshooting: mDNS blocked → use the board IP; connected-but-empty-dashboard →
wrong account.*

---

### 15 · Lab: first prompts

From your device's **Command panel** (or the cockpit):

- `ask-llm` *what is an NPU?* — on-device LLM; the answer arrives as **telemetry**
- `ask-agent` *how warm is the board?* — watch `agent_tool` → `agent_tool_result` → grounded answer
- The response cards fill on your dashboard; `llm_tps` and `llm_ttft` land next to them
- First `ask-llm` takes ~1 minute and the first `ask-agent` ~90 s — that's the **model load**, and it's a metric (`llm_load_time`)

*Notes: The command is acked immediately; the response comes back as telemetry ~10 s later — make
that explicit or attendees will think it hung. The first-load pause is a teaching moment, not an
apology: load time is one of the metrics on the next section's table (attendee boards get no
pre-warm, so their first agent answer takes ~90 s; afterwards 10–20 s). While the room waits out
their first load, run the hallucination A/B on your own board: `ask-llm what time is it` (invents
one) vs. `ask-agent what time is it` (tool chain in telemetry). Full command palette: README §6.*

---

### 16 · What just happened

- Your laptop → /IOTCONNECT REST API → **C2D command** over MQTT → the board runs the model → **D2C telemetry** → your dashboard
- Every hop is the same one a production fleet of thousands uses
- The board found its broker and credentials itself at boot (discovery + provisioning)
- Commands are acknowledged; telemetry is stored (latest value + history)

*Notes: One architecture diagram slide — laptop, cloud, board, with the C2D/D2C arrows labeled.
The punchline for this audience: you just operated a secure, multi-tenant device-management
pipeline, and none of it was mocked. ATTENDEE-GUIDE §4 maps each hop to its API area.*

---

### 17 · How GenAI performance is measured

| Metric | What it is | Why you care |
|---|---|---|
| **Load** | Model/pipeline init, paid before the first token | Cold-start latency; hidden in most datasheets |
| **TTFT** | Prompt → first token (after load) | Perceived responsiveness |
| **tok/s** | Completion tokens ÷ generation time | Sustained throughput — *the* headline number |
| **Wall** | End-to-end, as a user experiences it cold | The honest number |
| **CPU % / peak RAM** | Sampled at 1 Hz during the run | What's left for the rest of your product |

- Report load **separately** — never buried in tok/s
- Know your tokenizer: some paths count real tokens, others estimate ~4 chars/token
- The official benchmark's JSON report is the authoritative source (`run-benchmark`)

*Notes: Definitions and methodology from BENCHMARKS.md and MODELS.md (all figures measured via
the demo's real code paths, /proc sampled at 1 Hz, load always a separate column). The
estimated-vs-exact token distinction matters when comparing engines — GenAI Flow counts real
tokens, the llama.cpp and Ara paths estimate. This rigor is the difference between benchmarketing
and measurement, and this audience appreciates that.*

---

### 18 · The measured ladder (same prompt, same board)

| Model | Runtime / backend | Load (s) | TTFT (s) | tok/s | Quality* |
|---|---|---|---|---|---|
| Danube-500M q8 | GenAI Flow · CPU | 44 | 0.74 | 10.1 | C (B+ w/ RAG) |
| Danube-500M q8 | GenAI Flow · **Neutron NPU** | 129 | 0.48 | **13.7** | same model, +35% |
| Danube-500M q4 | GenAI Flow · Neutron NPU | 147 | 0.31 | **15.9** | D+ (RAG broken) |
| Qwen2.5-0.5B Q8_0 | llama.cpp · CPU | **5.6** | 0.13 | 12.9 | B |
| Qwen2.5-1.5B Q4_K_M | llama.cpp · CPU | 7.1 | 0.83 | 5.7 | **B+** — best reasoning |

- *\*QoR grades from the same question set — small-sample, honest rubric*
- The trade in one row: the best-reasoning model is the **slowest**
- Parameter count buys reasoning; today it costs tok/s

*Notes: MODELS.md language-model + QoR tables. Three stories in one table: (1) the NPU adds ~35%
to whichever Danube it runs, but pays a 2-min compile per launch; (2) llama.cpp's mmap load is
23× faster than GenAI Flow's pipeline spin-up — runtime architecture matters as much as silicon;
(3) the q4 row is the quantization cautionary tale from slide 6, now with numbers. Leave this
table up while introducing the next slide — the Ara240 exists to break this trade-off.*

---

### 19 · Add the Ara240: the trade-off breaks

- Same 1.5B-class model: **5.7 tok/s on the CPU → 18.7 tok/s on the Ara240** (~3.3×)
- **Qwen2.5-7B** — five times the parameters — runs at **5.1 tok/s**: the speed the CPU managed on a 1.5B
- Load per prompt: **zero** (models stay resident on the module)
- Host CPU during 7B generation: **~12%** — the A55s are free for your actual product
- *"Five times the parameters at the same speed. Same board — we just added the card."*

*Notes: MODELS.md Ara240 tables. Be honest with the gauge: the 7B's 5.1 tok/s is not a big
number — the win is quality-at-speed, not raw speed (the demo's own video script forbids
rescaling the tok/s gauge to flatter it). Answer-quality exhibit if asked: on "What color is an
apple?", only the 7B covers red/green/yellow, mixes, and ripeness; the 0.5B invents black apples;
the 1.5B leads with "green" (BENCHMARKS.md, verbatim outputs).*

---

### 20 · Live: the LLM shootout

- On **your** board: open `http://imx95-XXXX.local:8090` (or the cockpit's Model Shootout)
- One prompt → every engine you tick → **load / TTFT / gen / tok/s / CPU / RAM** + each model's verbatim answer
- On **my** board: the same shootout with the Ara240 rows lit
- Watch the answers, not just the numbers — quality tracks parameter count

*Notes: bench_server.py serves the shootout UI on :8090 (installed as the genai-bench service on
workshop boards). Attendee boards show CPU/Neutron/llama.cpp rows; Ara240 rows are greyed out
without the module — say that before someone asks. Budget honestly: a full multi-engine shootout
takes minutes (Neutron rows pay their 2-min compile); pre-select 2–3 quick engines for the room
and let your Ara240 run in parallel on the projector. This is the section's hands-on payoff —
give it 4 full minutes.*

---

### 21 · Three kinds of update (this demo implements all three)

| | **OTA update** | **Model push** | **File update** |
|---|---|---|---|
| Payload | Application package (`package.tar.gz`) | AI model (Ara240 `.dvm` bundle or GGUF) | A document / data file (e.g. RAG DB) |
| Mechanism | Firmware → OTA campaign | **AI Models → Push Model** (module command + presigned S3 URL) | `rag-add` command + presigned URL |
| Device does | Untars, runs `install.sh`, restarts app | Downloads → deploys → loads on NPU → serves | Downloads → chunks → re-embeds → ready |
| Progress | OTA acks | `model_deploy_status`: idle → downloading → deploying → loading → **ready** | `rag_status`: downloading → indexing → **ready** |
| Scale | Fleet campaigns, versioned | One device or a fleet, versioned models | Per-device or scripted |

- Three different risk profiles, three different cadences — a fleet needs all three

*Notes: This distinction is implemented in src/app.py, not just described: `on_ota` (package),
`on_module_command` ct:2 (model), `rag-add` (file). Frame by cadence and blast radius: app code
changes rarely and needs QA and rollback; models change on retrain cycles and need ~2× model size
in free disk; knowledge files can change weekly and touch nothing else. Updating the RAG DB
without touching model or app is exactly why the file lane exists — next two slides demo lanes
two and three.*

---

### 22 · Live: push a model from the console

- **AI Models → My Model → Create Model**: name, a clean **Code** (3–10 alphanumeric — it becomes the model's install path), version, the model `.tar`
- **AI Models → Push Model**: pick model + version → template → device → **Push**
- Watch `model_deploy_status` on the dashboard: *idle → downloading → deploying → loading → ready*
- Measured on this board: **~54 seconds** from click to serving
- Then: `ask-llm` — answered by the model that didn't exist on the board a minute ago

*Notes: Full walkthrough with screenshots: docs/MODEL-PUSH.md. Under the hood for the curious:
the push arrives as a module command (`ct:2`) carrying a presigned S3 URL; the device downloads,
untars into `/usr/share/llm/<Code>/`, restarts the AAF connector, and acks OTA_DOWNLOAD_DONE.
Leave "Convert through sagemaker?" unchecked here — this tar is already Ara-compiled; that
checkbox is the hook into the next slide's story. If the live push is risky on venue Wi-Fi, the
RAG file update is the fallback demo: `rag-add` a URL, watch `rag_status` walk to ready, then ask
a question only the new document answers — and note the shipped KB still says "Ara-2 will be
supported in a future version," which is why file updates matter.*

---

### 23 · Retraining in the cloud (the loop closes)

- The fleet doesn't just *consume* models — it *produces* the data that improves them
- The loop: **capture on device → upload via /IOTCONNECT file support → S3 → SageMaker training → conversion pipeline → deploy back to the fleet (OTA or Model Push)**
- Shipping example in this repo — **KWS Training Studio** (Microchip SAMA7D65):
  - capture voice-command clips on the board → dataset to S3 through /IOTCONNECT
  - **SageMaker** trains a PyTorch keyword model; **Step Functions** converts it to a board-ready TFLite package
  - the new model deploys back to the device runtime (via OTA / `file-download`)
- The `Create Model` dialog's "Convert through sagemaker?" option is the hook into the **conversion half** of this machinery

*Notes: Source: microchip-sama7d65-curiosity/kws-training (README + docs/ARCHITECTURE.md) — a
complete, working retrain loop built on the same /IOTCONNECT primitives the attendees used today.
Be precise about scope: today's Qwen LLMs are *deployed*, not retrained — the retrain loop is
demonstrated on a keyword-spotting model, where edge retraining genuinely pays off, and the KWS
example closes its loop via OTA / `file-download` (Model Push is the equivalent lane shown live
on slide 22). Also be precise about ownership: file upload, S3 storage, and model delivery are
/IOTCONNECT platform features they've touched; the SageMaker training job itself runs in the
customer's AWS account (the board needs AWS credentials to submit it), and the platform's
provisioned `conv-*` Step Functions pipeline is a conversion workflow, not raw training.*

---

### 24 · Ground truth: what your fleet knows that you don't

- **Ground truth** = real field data with verified labels — the raw material of every retrain
- /IOTCONNECT file support gives each device an **S3-backed bucket**: captured images and clips upload from the device and land under **Telemetry Files**
- Working example in this repo — the **file-upload demo** (NXP FRDM-IMX93):
  - `capture-picture` → JPEG · `record-start/stop` → 30 s MP4 clips (zip-wrapped) → uploaded to S3
  - telemetry carries the **metadata**: `recording`, `pending_uploads`, `uploaded_clips`, `upload_failures`, `last_clip`
- Media + telemetry context (what, when, device state) = the raw material of a labeled dataset — add labels and it becomes ground truth

*Notes: Source: nxp-frdm-imx-93/file-upload-demo/README.md. Connect it backwards: slide 23's
SageMaker loop starts from exactly this kind of captured, contextualized data — and the labeling
step matters: the file-upload demo's telemetry is upload bookkeeping, while the KWS demo captures
clips *into per-command label folders*, which is what makes them ground truth. Today's demo used
the same S3 upload path for something small: `rag-show` publishes RAG chunk files to Telemetry
Files. The telemetry metadata is what makes captured media *usable* — a clip with device state
and timestamps attached is a dataset row; a bare clip is just a file.*

---

### 25 · Live video: KVS, and what the cloud adds

- For streams, not clips: **AWS Kinesis Video Streams**, provisioned per device by /IOTCONNECT at creation
- Two modes (both are working demos in this repo):
  - **KVS PutMedia** — ingest to the cloud: durable, recorded, replayable
  - **KVS WebRTC** — peer-to-peer live view: sub-second latency, board is the WebRTC master
- Start/stop from the device's **Video Streaming** tab; view live in the console
- Once media is in S3/KVS, cloud analysis is a service call away — e.g. **Amazon Rekognition** for labels, faces, objects → results can feed telemetry, alerts, and the retraining loop

*Notes: Sources: tria-vision-ai-kit-6490/kvs-webrtc and kvs-putmedia READMEs (same demos exist
for STM32MP257). The stream resource (PutMedia vs. WebRTC) is chosen at device creation with the
plitekvs template. Be accurate about today's board: the workshop dashboard's camera view is a
local MJPEG server on the board, not KVS — KVS is the productization path for off-LAN and
recorded video (the genai README §12 points there). Rekognition framing: the demos ship the
capture-and-stream half; wiring Rekognition onto that S3/KVS media is standard AWS integration —
present it as the architecture, not as a button in this repo.*

---

### 26 · Finale: "Hey NXP"

- Wake word → Moonshine STT → LLM → VITS TTS — **no cloud in the loop**
- Ask it something. Then ask it to *do* something:
- *"Hey NXP … turn on the lights"* → voice → agent → /IOTCONNECT → **a real LED on another device switches on**
- Four models, a tool-calling agent, and a cloud command — from one spoken sentence, on one embedded board

*Notes: You sent `voice-start` at ~0:49; `voice_status` should read `listening` now. Speak the
wake word, pause for the earcon, then ask — running them together puts "Hey NXP" into the
transcript. Speak at arm's length (~4000 RMS). The LED beat needs the companion LED device online
and the agent warm — idle agent sessions auto-stop, so re-warm with `agent-start` at ~0:45 and
verify both before `voice-start`; have the fallback ready: a plain voice Q&A plus the
`voice_question`/`voice_response` telemetry on screen is still a strong close. Send `voice-stop`
afterward — a voice session holds the AI engine until stopped.*

---

### 27 · What you leave with

- A mental model: **tokens/sec is a bandwidth story · quantize but re-validate · ground or agent your small models · measure load separately**
- A live **/IOTCONNECT account** — your entity, dashboard, and RAG documents stay yours after today
- The full demo — code, docs, every measured number — is public:
  - Attendee guide · benchmarks · model catalog · model-push walkthrough — all in the repo
  - NXP eIQ GenAI Flow · Ara240 models on Hugging Face
- The board goes back; everything you built today doesn't

*Notes: ATTENDEE-GUIDE §5–6 covers keep-vs-return details; the repo link is on their handout.
Point at the guide's platform-capabilities table one last time — it doubles as an evaluation
checklist for their own products.*

---

### 28 · Q&A / Thank you

- Repo: `github.com/avnet-iotconnect/iotc-python-lite-sdk-demos` → `nxp-frdm-imx-95/genai-flow-demo`
- Your manual for today: **ATTENDEE-GUIDE.md**
- Contact / next steps

*Notes: Good seed questions if the room is quiet: "What would it take to run OUR model on this?"
(answer: GGUF → drop-in via set-model; Ara240 → pre-compiled or the Ara SDK with a compile
license) and "What does the Neutron NPU do while the Ara runs the LLM?" (answer: today
one-AI-at-a-time; the roadmap is LLM on Ara + vision on Neutron + speech on CPU concurrently —
MODELS.md 'what becomes possible').*

---

## Source map (for maintaining this deck)

| Slides | Source of truth |
|---|---|
| 5–10 (concepts, model specs) | [MODELS.md](../MODELS.md), [README.md](../README.md) §7–11 |
| 11–12 (board, Ara240) | [MODELS.md](../MODELS.md) budgets + Ara240 section, [ARA2-ENABLEMENT-REQUEST.md](ARA2-ENABLEMENT-REQUEST.md) |
| 13–16 (platform, lab) | [ATTENDEE-GUIDE.md](ATTENDEE-GUIDE.md), [WORKSHOP.md](WORKSHOP.md), portal/README.md |
| 17–20 (performance) | [BENCHMARKS.md](BENCHMARKS.md), [MODELS.md](../MODELS.md), src/bench_server.py |
| 21–22 (updates, model push) | [MODEL-PUSH.md](MODEL-PUSH.md), src/app.py (`on_ota`, `on_module_command`, `rag-add`) |
| 23 (SageMaker retraining) | `microchip-sama7d65-curiosity/kws-training/` README + docs |
| 24 (ground truth / S3) | `nxp-frdm-imx-93/file-upload-demo/README.md` |
| 25 (KVS / Rekognition) | `tria-vision-ai-kit-6490/kvs-webrtc/` + `kvs-putmedia/` READMEs, [README.md](../README.md) §12 |
| 26 (voice) | [README.md](../README.md) §8, [demo-flow.md](../demo-flow.md), [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md) |
