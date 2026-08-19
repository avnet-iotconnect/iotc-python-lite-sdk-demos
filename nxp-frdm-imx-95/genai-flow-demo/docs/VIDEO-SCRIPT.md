# Video script: FRDM i.MX 95 GenAI demo (Ara240 board)

Production script for a screen-recorded walkthrough of [demo-flow.md](../demo-flow.md) on a board fitted with the
**Kinara Ara-2 / NXP Ara240** module.

**Method:** silent capture, voice-over in post. You do **not** talk while operating — record clean screen and
board footage, let the long waits run, then read the VO over the edit and cut the dead time out.

**Deliverables from one session:**

| Cut | Length | Audience |
|---|---|---|
| **Master** | ~11 min, chaptered | engineers, docs repo, NXP/Avnet field |
| **Short cut** | ~3:20 | booth loop, social, exec summary — edited from the same takes ([EDL in §6](#6-short-cut-edl)) |

Capture time is **~35–40 minutes** of real board time. Budget 90 minutes with pre-flight and retakes.

---

## 1. Pre-flight

### 1.1 Board state — verified 2026-07-25

Checked on `192.168.68.71` before this script was written:

| Item | State |
|---|---|
| `genai-app`, `genai-camera`, `genai-mcp` | active |
| `rt-sdk-ara2`, `eiq-aaf-connector` | active |
| Ara module | bound, `Kernel driver in use: uiodma` (`1e58:0002`) |
| Connector `/v1/models` | `Qwen2.5-7B-Instruct` **ready**, `Qwen25C15B` **ready** |
| Backend / RAG | `ara2` / off |
| Camera | Logitech **Brio 101**, `/snapshot` 200 (51 KB) |
| Board clock | correct (no NTP drift) |
| `genai_status` | idle |

### 1.2 Audio capture — fixed, verify before the voice segment

`capture_device` was pinned to `sysdefault:CARD=C920`, but the board's webcam is now a **Brio 101**. `arecord` on
the C920 name failed with *"cannot find card"* — the wake word would never have been heard. It is now
`sysdefault:CARD=B101` and `genai-app` has been restarted. Ambient noise floor measures ~380 RMS (healthy).
Original config saved at `/opt/demo/genai-config.json.bak-prevideo`.

**Run the venue mic check anyway** — speech seconds must hit **2000+ RMS**:

```bash
aplay -D sysdefault:CARD=mqsaudio /root/eiq_genai_flow/assets/ww_earcon.wav
arecord -D sysdefault:CARD=B101 -f S16_LE -r 16000 -c 1 -d 12 /tmp/mictest.wav
python3 -c "
import wave, struct, math
w = wave.open('/tmp/mictest.wav'); n = w.getnframes()
d = struct.unpack('%dh' % n, w.readframes(n))
[print('sec %2d: rms %5.0f %s' % (s, r, '#'*int(r/150))) for s in range(n//16000)
 for r in [math.sqrt(sum(x*x for x in d[s*16000:(s+1)*16000])/16000)]]"
```

If your speech lands under 2000, move the mic to arm's length. A retake because the wake word was ignored costs
5 minutes (the `voice-start` reload); this check costs 30 seconds.

### 1.3 Disk space — read this before the model-push segment

The board is at **92% full (2.3 GB free)**. The push downloads the package to `/usr/share/llm/.push-download.tar`
and extracts it alongside — peak usage is roughly **2× the model size**, and `Qwen25C15B` is **1.8 GB**.

Deleting the already-pushed copy is required anyway (otherwise the "device doesn't have this model" beat is a
lie) and frees the headroom the push needs:

```bash
# Stage the model-push segment: remove the previously pushed model so the push is genuine
systemctl stop eiq-aaf-connector
rm -rf /usr/share/llm/Qwen25C15B
python3 - <<'EOF'
import json
p = '/usr/share/eiq/aaf-connector/server_config.json'
d = json.load(open(p))
for m in d['available_models']:
    if m['name'] == 'Qwen25C15B':
        m['enabled'] = False
json.dump(d, open(p, 'w'), indent=4)
EOF
systemctl start eiq-aaf-connector
df -h /                       # expect ~4.1 GB free
sleep 150                     # the 7B reloads onto the Ara (~2 min)
curl -s http://127.0.0.1:8100/v1/models   # Qwen2.5-7B-Instruct "ready":true, no Qwen25C15B
```

Do this **at least 5 minutes before Take 1**, not between takes. If free space is under ~4 GB after the delete,
clear other cruft first (`rm -f /root/eiq_genai_flow/Benchmark_*.log`, old `/opt/demo/*.log`).

You will need the model `.tar` in IOTCONNECT already (**AI Models → My Model**, code `Qwen25C15B`). If it isn't
there, create it per [MODEL-PUSH.md](MODEL-PUSH.md) before recording — the upload is not screen-worthy at 1.8 GB.

### 1.4 Benchmark report — pick the right one

`run-benchmark report` re-publishes the **most recent** `Benchmark_*.json` in `/root/eiq_genai_flow`. Today that's
a **July 9 STT run** with no LLM metrics — it would publish `bench_tps: 0`. The real NPU LLM benchmark
(`llm_avg_tps 12.92`, `llm_avg_ttft 0.28`, `cpu_avg 23.59`) is the July 3 neutron report.

Move the STT reports aside so the LLM report is the newest — this selects which **real** measurement gets
republished, it does not invent numbers:

```bash
mkdir -p /root/eiq_genai_flow/stt-bench-archive
mv /root/eiq_genai_flow/Benchmark_*kasr_*.json /root/eiq_genai_flow/stt-bench-archive/
ls -t /root/eiq_genai_flow/Benchmark_*.json | head -1   # must be the ..._neutron_..._keyb_... one
```

The alternative is running the real thing live (`run-benchmark`, 10–30 min) before the session and filming the
fresh result. Better numbers on screen, worse use of an hour.

### 1.5 Dashboard prep

1. **Embedded widget links** — both must point at `https://192.168.68.71:8080`. Fix them if the IP moved.
2. **Accept the self-signed cert**: open `https://192.168.68.71:8080` in the recording browser once, accept, and
   confirm the **Camera Feed** and AI Responses panels render inside the dashboard. A cert interstitial on camera
   is a retake.
3. Zoom the browser to **100%**, hide the bookmarks bar, close every other tab.
4. Work through the widget audit below — a pre-Ara dashboard needs changes.

### 1.6 Dashboard widget audit (an Ara240 video needs these)

**The embedded Responses panel is the backbone of this video and needs no changes.** It is served by the board,
not driven by the template, so it is always truthful: its badge row shows live `genai_status`, `llm_model`,
`llm_backend` (including `ara2`), `llm_rag`, `voice_status`, `voice_stt`, `vlm_model`, `agent_status`; the LLM
card footer shows `tok/s | TTFT | tokens`; and the agent card footer shows the whole chain,
`tool <name> -> <result> (router: <router>)` ([camera-server.py:158](../src/camera-server.py#L158)). Keep it in
frame for every segment.

**Toggle widgets lie on an Ara board.** `Backend` and `Model` are two-state controls. With the board on `ara2`
serving `Qwen2.5-7B-Instruct`, they still read **NPU** and **Danube** — contradicting the Responses badges in the
same frame. They are fine as *controls*; they are unusable as *state display*.

Artwork for the engine-state tiles is in this repo:

- [media/icons/](media/icons/) — one glyph per attribute (`llm_backend`, `llm_model`, `vlm_model`, `voice_stt`),
  transparent PNG at 64/128/256 px in slate and white, plus editable SVGs.
- [media/model-badges/](media/model-badges/) — one badge **per model-name value**, for transformation widgets
  that swap an image in for a text box. 14 values across `llm_model` / `vlm_model` / `voice_stt`, 4:1 at
  512×128 and 256×64. The exact value→file mapping is in that folder's README; re-run `make-badges.py` after
  pushing a new model, since its `Code` becomes a new `llm_model` value with no badge.

| Fix | What | Why |
|---|---|---|
| **Add** | **AI Engine Status** — text widget bound to `llm_model` + `llm_backend` (it exists in [the repo export](../FRDM_i.MX_95_GenAI_dashboard.json); import or rebuild it) | §3.6–3.8 are *about* the backend changing. Without it, the only truthful backend readout is the small Responses badge |
| **Add** | **CPU Load (%)** gauge on `cpu_percent` (0–100), and a **SoC Temperature** gauge on `cpu_temp` (0–100 °C, green to ~55, red from ~70) | §3.2 tour and the §3.4 *"how warm is the chip"* follow-up, which compares the agent's answer against a live gauge |
| **Add** | **Benchmark Telemetry** widget on `bench_tps`, `bench_ttft`, `bench_cpu_avg`, `bench_mem_avg` | §3.10 has nothing to show without it |
| **Change** | **VLM Time to First Token** gauge max `3` → **`6`** | Real `vlm_ttft` is ~4.9 s. At max 3 the needle **pegs at full red on every vision call** |
| **Change** | **LLM Time to First Token** gauge max `3` → **`5`** | Ara 7B TTFT is 2.06 s — at max 3 it sits ~70% of scale in the red band, during the headline shot |
| **Leave** | **LLM Tokens / Second** at 0–20 | Do **not** rescale to flatter the Ara — see §3.7. The honest ladder needs green at 10+ |
| **Optional** | **`model_deploy_status` / `_name` / `_detail`** added to the `genaiflow` template, plus a text widget | §3.8. If you skip it, use the fallback in that segment |
| **Clear** | The red **"Failed"** under the `Voice Asst.` toggle — residue from `voice-start` failing on the old C920 capture device | It's in every wide shot. One successful `voice-start` / `voice-stop` clears it |

Some of these may already exist off-screen — the dashboard scrolls horizontally. **Scroll right and check before
rebuilding anything.** After any widget edit, re-export the dashboard so the layout is saved.

**Minimum viable change** if you're short on time: add **AI Engine Status**, fix the two gauge maxes, and clear
the Voice "Failed" badge. Everything else has a documented fallback in the shot list.

### 1.7 Warm-up sequence — the 12 minutes before Take 1

Order matters. `agent-start` must precede any `voice-start`, and voice holds the engine for its whole session.

| # | Send | Wait for | Why |
|---|---|---|---|
| 1 | `set-backend ara2` · `set-model Qwen2.5-7B-Instruct` | ack | known start state |
| 2 | `set-rag off` · `set-stt moonshine-base` | ack | beat 4 needs RAG off |
| 3 | `agent-start` | `agent_status: ready` (~1 min) | makes every `ask-agent` 10–20 s on camera |
| 4 | `ask-vlm` | Vision card fills (~45 s) | proves camera + VLM, populates gauges |
| 5 | `ask-llm hello` | LLM card fills | proves the Ara path end-to-end |
| 6 | `ask-agent what time is it` | correct time | proves agent + board clock |

Then **clear the decks**: the cards you just filled will be on screen when you start recording. Either accept
that (they're plausible demo state) or send a throwaway `ask-llm hi` so the visible card is neutral.

> Do **not** pre-warm the voice session. Segment 3.9 films `voice-start` going `starting → listening`.

### 1.8 Reset between takes

```bash
# From your host, if a take goes wrong:
ssh root@192.168.68.71 "systemctl restart genai-app"   # ~15 s to reconnect; clears a stuck busy-lock
```

From the dashboard, the cheaper reset: `voice-stop`, then wait for `genai_status: idle`. Most "failed" takes are
just the busy-lock — check `genai_status` before assuming something is broken.

---

## 2. Capture setup

### 2.1 Sources

| Source | What | Notes |
|---|---|---|
| **A — Screen** | 1920×1080 @ 30 fps, browser full-screen on the dashboard | Primary. ~80% of runtime |
| **B — Board** | Phone/DSLR on a tripod, framing the FRDM-IMX95 + Ara240 M.2 + camera + the LED device | Cold open, the "turn on the lights" payoff, cutaways over waits |
| **C — Responses page** | Second browser window on `https://192.168.68.71:8080/responses` | Optional. Big, legible answer cards — better than the dashboard's small cards for long answers. It polls every 2 s |

Record A continuously for the whole session. Shoot B as separate b-roll clips before and after — you'll cut it
in over the waits. Don't try to switch scenes live.

### 2.2 Redact before you record

Anything on screen that you would not put in a public repo:

- IOTCONNECT account name / email in the top-right nav → crop the frame or blur in post
- Solution key, environment, CPID, device serials on the device detail page
- The MCP `iotconnect-cli configure` line (credentials) — never on camera
- Presigned S3 URLs in `model_deploy_detail` or logs
- Your LAN topology if it identifies a customer site

Also: OS notifications **off**, clock/battery hidden if possible, desktop clean.

### 2.3 Answer cards fill, they don't stream

Neither the dashboard nor `/responses` streams tokens — the answer appears complete, ~2 s after generation ends.
Frame the **LLM Tokens / Second** gauge in shot so the speed story has something to land on, and write VO that
says "*lands at 5 tokens a second*", not "*watch it stream*".

---

## 3. Shot list and script

Each segment: what you send, how long it really takes, what to capture, where to cut, and the verbatim VO.
Timings are measured ([MODELS.md](../MODELS.md)). VO word counts assume ~140 wpm.

Send every command from the dashboard's **Device Command** panel unless a Control widget is named — the one-click
widgets (`VLM: Scene?`, `Agent: Time?`, `RAG`, `Backend`, `Model`) film better than typing.

---

### 3.1 Cold open — the hardware (0:25 finished)

**Capture:** Source B only. Slow pan across the board: SoC, the Ara240 M.2 module, the webcam, the LED device
across the desk. 3 takes, 30 s each. No screen.

**VO:**

> This is an NXP FRDM i.MX 95 development board. On it: a six-core Arm CPU, NXP's on-chip eIQ Neutron NPU, and —
> in the M.2 slot — a Kinara Ara-2 discrete AI accelerator. No GPU, no cloud inference, no internet dependency
> for any of the AI you're about to see. A language model, a vision model, speech recognition, text to speech,
> and a tool-calling agent all run on this one board. The cloud carries telemetry, and nothing else.

---

### 3.2 Dashboard tour (0:40 finished)

**Do:** nothing. Mouse moves only — hover each region as the VO names it.

**Capture:** Source A, full dashboard. Move the cursor deliberately: gauges → status tiles → the Responses
panel's badge row → the four response cards → Camera Feed.

**Real time:** 40 s. No cut.

**VO** — this read matches the **four-gauge** dashboard (LLM tok/s, LLM TTFT, VLM tok/s, VLM TTFT):

> Everything the board does reports to IOTCONNECT. Tokens per second and time to first token — for the language
> model and the vision model both — live, every ten seconds. These tiles are the AI engine's state: idle or
> generating, whether the agent and voice sessions are alive, whether retrieval grounding is on. This strip
> tells you exactly what's loaded right now — the model, and which piece of silicon it's running on. These four
> cards are the answers themselves — language, vision, voice, and agent — served by the board's own web server.
> And that's the board's camera, streaming from the board. Watch the tokens-per-second gauge and that backend
> badge through the rest of this video. Between them, they're the whole story.

> **If you added the CPU Load and SoC Temperature gauges** (§1.6), use this line instead of the first sentence:
> *"Tokens per second, time to first token, CPU load, SoC temperature — live, every ten seconds."*

---

### 3.3 Vision: what the board sees (0:50 finished)

**Do:** hold an object in front of the camera → click **VLM: Scene?** (or `ask-vlm What do you see?`).

**Real time:** ack ~2 s, card fills **30–45 s** later.

**Capture:** A on the dashboard. When the card fills, zoom in post on `vlm_response`, `vlm_vision_time`,
`vlm_tps`. Cut in B-roll of you holding the object during the wait.

**Cut:** trim the wait to ~4 s of b-roll.

**Expect:** a scene description that names people, clothing colours, glasses, held objects.
`vlm_vision_time` **3.6–4.5 s**, `vlm_tps` **≈10**.

**VO:**

> One command, sent from the cloud. The board grabs a frame from its own camera and runs SmolVLM on it locally.
> Three and a half seconds to encode the image, ten tokens a second to describe it — and it gets the details:
> the person, what they're wearing, what they're holding. The image never left the board. For a factory line or
> a medical device, that's not a nice-to-have, it's the requirement.

---

### 3.4 The hallucination A/B (1:40 finished) — the smartest beat

**Do, in order:**

| # | Send | Expect |
|---|---|---|
| 1 | `set-backend cpu` | ack |
| 2 | `set-model qwen2.5-0.5b-instruct-q8_0` | ack |
| 3 | `ask-llm what time is it` | **~15 s** → a confidently **invented** time |
| 4 | Click **Agent: Time?** (`ask-agent what time is it`) | **10–20 s** (session pre-warmed) → the **correct** time |

**Capture:** A. On step 3, zoom the LLM card. On step 4, zoom the green **Agent: Real Board Data** card in the
Responses panel — its footer line carries the whole chain in one string:
`tool get_time -> <the real clock value> (router: llm)`. That footer is the money shot of this segment.

**Then the follow-ups** (each 10–20 s, session stays warm — pick two):

- `ask-agent how warm is the chip` — **only if you added the SoC Temperature gauge** (§1.6), so you can cut
  between the agent's spoken number and the live gauge. Without that gauge, use a USB or memory question instead
  — an unverifiable number on screen is a weaker beat than a visibly verifiable one
- `ask-agent what usb devices are plugged in` — plug something in first, on camera
- `ask-agent how many devices are in my iotconnect deployment` — the board querying its own cloud fleet via the
  on-board MCP server

**Cut:** keep both waits — 15 s and 15 s is watchable, and the pause before a wrong answer is comedy.

**VO:**

> Let's ask a small language model what time it is. Fifteen seconds, and it answers with total confidence — and
> it's wrong. It has to be. No language model has a clock. The fancier the model, the more fluently it invents.
> Now the same question through the agent. The model doesn't answer — it *chooses a tool*. `get_time`. The board
> executes that tool, reads its own hardware clock, and the model writes the answer around the real value.
> Correct date, correct time, and the whole reasoning chain is right there in the telemetry: which tool it
> picked, what that tool returned, and what it said. That's the difference between a chatbot and something you'd
> let touch a machine. And it works on live board state — the chip temperature, the USB devices plugged in this
> second — and through the on-board MCP server, on the fleet in the cloud.

---

### 3.5 RAG: ask the manual (1:00 finished)

**Do:**

| # | Send | Expect |
|---|---|---|
| 1 | `set-model danube-500M-q8` (backend stays `cpu`) | ack |
| 2 | **RAG → On** (`set-rag on`) | `llm_rag: on` |
| 3 | `ask-llm How do I expand the root filesystem?` | **~1 min** → the answer quotes the docs **verbatim**, including `parted` and `resize2fs` |

**Capture:** A, zoomed on the LLM card when it fills — the exact commands are the payoff. Optionally switch to
Source C for this one; the long answer is far more legible on `/responses`.

**Cut:** cover the ~44 s load with B-roll.

**Other good questions if you want a second take:** *"What baud rate does the serial console use?"* (115200),
*"What tokens per second does the Neutron NPU achieve?"* (13.7).

**VO:**

> Same class of small model that just invented a timestamp. But now grounding is on, and there's a vector
> database of this board's documentation sitting on the eMMC. The question retrieves the relevant passages, they
> go into the prompt, and the answer comes back quoting the manual verbatim — the actual `parted` and `resize2fs`
> commands, not a plausible-looking guess. The knowledge base is a JSON file of facts. Swap in your service
> manual, and every field tech gets this on every machine, fully offline.

---

### 3.6 The performance ladder (1:40 finished, ~13 min real)

**One question, every rung** — use the long form so the answers are substantial and the A/B in §3.7 is
apples-to-apples:

> `Explain what an NPU is and why edge devices use one.`

**Do, in order** (send `set-rag off` first so the rungs are comparable):

| # | Send | `llm_backend` | Expect `llm_tps` | Real wait |
|---|---|---|---|---|
| 1 | `set-backend cpu` + `set-model danube-500M-q8` → ask | `cpu` | **10.1** | ~1 min |
| 2 | `set-backend neutron` → ask | `neutron` | **13.7** | ~2.5 min |
| 3 | `set-model danube-500M-q4` → ask | `neutron` | **15.9** | ~2.5–3 min |
| 4 | `set-backend cpu` + `set-model qwen2.5-0.5b-instruct-q8_0` → ask | `cpu-llama.cpp` | **12.9** | **~15 s** |
| 5 | `set-model qwen2.5-1.5b-instruct-q4_k_m` → ask | `cpu-llama.cpp` | **5.7** | ~30 s |

> **Critical:** `set-backend ara2` short-circuits every other path ([app.py:547](../src/app.py#L547)). To leave
> the Ara you must send `set-backend cpu` or `neutron` — changing the model alone is not enough. Conversely,
> `set-model Qwen2.5-7B-Instruct` forces the backend *back* to `ara2`. Rung 4 therefore needs **both** commands.

**Capture:** A, wide enough to hold the tokens/sec gauge and the `llm_backend` field together. After each answer,
hold 3 s on the gauge — you need a clean frame per rung for the post-production comparison table.

**Cut:** this is 13 minutes that becomes 100 seconds. Cut every load. Build a **side-by-side or stacked
comparison graphic** in post from the five gauge frames; the VO rides over that, not over the raw footage.
**Leave rung 5 running into §3.7** — do not reset state.

**VO:**

> Same question, five different ways to run it. On the six A55 cores: ten tokens a second. Move the same model
> to the on-chip Neutron NPU: thirteen point seven — thirty-five percent faster for free, just by changing where
> it runs. Quantize it further, still on the NPU: nearly sixteen. That's the fastest number in this demo — and
> it's also the model whose answers got worse, which is exactly the trade you have to make at the edge. Now
> switch families. A half-billion-parameter Qwen through llama.cpp: twelve point nine tokens a second, and it
> loads in five seconds instead of two minutes. And the one-and-a-half-billion model — the best answers of the
> whole set, real reasoning — crawls at five point seven. There's the problem in one line: the quality you want
> lives in the big models, and today the big models are slow.

---

### 3.7 The Ara240 headline (1:20 finished) — the wow

**Do** — you are already on rung 5 (`cpu` + `qwen2.5-1.5b-instruct-q4_k_m`) with that answer on screen:

| # | Send | Expect |
|---|---|---|
| 1 | *(reuse rung 5's answer)* | `llm_tps` **5.7**, a 1.5B model |
| 2 | `set-backend ara2` | ack: *"ask-llm now runs on the Ara240 via the AAF connector"* |
| 3 | **Same question** | `llm_ttft` **≈2 s**, `llm_tps` **≈5.1–6.3**, and a visibly **richer, longer** answer — from a **7B** |

**Capture — read this before you shoot it.** The tokens/sec gauge **cannot** tell this story, and if you lean on
it, it tells the opposite one. The claim is *"a 7B runs at the speed of a 1.5B"* — so both needles land in the
same place, around 5–6 on a 0–20 scale whose green band starts at 10. Two orange needles read as "both slow" to
a viewer who isn't listening carefully. Do **not** rescale the gauge to make 5 tok/s green: you just spent 100
seconds establishing that scale in §3.6, and moving it mid-video is both obvious and dishonest.

Carry the segment on three things instead:

1. **The two answers side by side.** Capture both the 1.5B and the 7B answer full-frame and clean — the 7B's is
   visibly longer and better reasoned. This is the primary evidence. Use the `/responses` page (Source C) if the
   dashboard card truncates.
2. **The model name changing** in the Responses badge row: `qwen2.5-1.5b-instruct-q4_k_m` → `Qwen2.5-7B-Instruct`,
   and `backend` → `ara2`. Zoom it in post. (The `Model` and `Backend` **toggles** will still read "Danube" and
   "NPU" — keep them out of frame or crop them out, they're controls, not state. See §1.6.)
3. **The gauge held steady** — used deliberately, as proof the *speed didn't change* while the model got 5× bigger.
   That's the correct use of two matching needles.

Cut to Source B on the Ara240 module in the M.2 slot as the VO says "we just added the card."

**Real time:** ~30 s + ~45 s. No cut needed — this segment plays close to real time.

**Expect no reload:** `llm_load_time` reads **0**. The Ara model stays resident in the connector.

**VO:**

> Remember that one-and-a-half-billion model crawling at five point seven tokens a second. Same board, same
> question — but now it's running on the Ara-2 module in the M.2 slot. This answer is coming from a
> **seven**-billion-parameter model. Five times the parameters. Two seconds to first token, and it's generating
> at the same speed the CPU managed with a model a fifth the size. Look at the difference in the answers. That's
> not a benchmark improvement, that's a different class of product — and the board didn't change. We just added
> the card. Same-size comparison, if you want it stark: that 1.5B model runs at eighteen point seven tokens a
> second on the module. Three and a third times the CPU.

---

### 3.8 Cloud → edge model push (1:10 finished)

**Do:**

| # | Where | Action | Expect |
|---|---|---|---|
| 1 | Board | *(pre-flight §1.3 already removed `Qwen25C15B`)* | connector serves only the 7B |
| 2 | IOTCONNECT | **AI Models → Push Model**, model `Qwen25C15B` v1.0.0.0, template `genaiflow`, **Selected devices → MCLiMX95b**, **Push Model** | — |
| 3 | Dashboard | watch `model_deploy_status` | `idle → downloading → deploying → loading → ready`, **~54 s** |
| 4 | Dashboard | `ask-llm In one sentence, what is edge AI?` | answered by `Qwen25C15B` on the Ara240 |
| 5 | Dashboard | `set-model Qwen2.5-7B-Instruct` | instant — both stay resident |

**Capture:** A on the IOTCONNECT AI Models page for the push click, then cut to the dashboard for the status
chain. If your template lacks `model_deploy_*` (§1.5), open a terminal on `journalctl -fu genai-app` beside the
dashboard and film that instead — the same states print there.

**Cut:** the ~54 s compresses to ~20 s; keep every state transition visible for at least a beat.

**VO:**

> The model on that module doesn't have to be the one you shipped. This is IOTCONNECT's model management:
> upload once to the cloud, then push to one device or a whole fleet. This board does not currently have this
> model. Push. And the device does the rest by itself — downloads the package, unpacks it, loads it onto the
> Ara-2, and starts serving it. Fifty-four seconds, cloud to edge, no SSH, no truck roll. Ask it a question and
> the answer comes back from the model that arrived a minute ago.

---

### 3.9 Voice finale + the LED (1:30 finished, ~7 min real)

**Set state first** — voice and the agent run the CPU/Danube path in this build, **not** the Ara:

| # | Send | Why |
|---|---|---|
| 1 | `set-backend neutron` | the voice path's NPU headline |
| 2 | `set-model danube-500M-q8` | GenAI Flow voice pipeline |
| 3 | `set-rag off` | open conversation; set `on` if you want the "politely refuses off-topic" behaviour |
| 4 | confirm `agent_status: ready` | required for the LED action; re-send `agent-start` if it idled out (60 min default — `agent_idle_timeout_s`) |
| 5 | `voice-start` | **wait for `voice_status: listening` — 2–3 min. Do not speak before it.** |

**Then, on camera** (pause after the wake word every time — running them together puts "Hey NXP" in the
transcript):

1. *"Hey NXP"* … **beep** … *"what is the wake word?"* → spoken answer in **10–20 s**
2. *"Hey NXP"* … **beep** … *"turn on the lights"* → **the LED across the room switches on**
3. *"Hey NXP"* … **beep** … *"turn off the lights"*
4. `voice-stop` ← **do not forget this**

**Capture:** this needs both sources. A on the dashboard (`voice_status`, the purple Voice card,
`voice_question` / `voice_response`, then the green Agent card showing `send_device_command` →
*"Sent command board-user-led on to device e84AIvaLights"*). B framed on the LED device. In post, cut to B on
the word "lights" and hold through the switch-on.

**Audio:** the board speaks aloud through the 3.5 mm MQS jack. Your screen capture will **not** record it. Either
mic the speaker with a separate recorder for that segment, or subtitle the spoken reply in post. Decide before
you record — this is the one place silent capture costs you something.

**Cut:** the 2–3 min `voice-start` load compresses to a 3 s status-field time-lapse.

**VO:**

> Wake word, speech to text, language model, text to speech — the entire voice pipeline, on the board, offline.
> No cloud round trip, no account, no microphone data leaving the room. Say the wake word, wait for the beep,
> ask your question, and it answers out loud in about fifteen seconds. And because that voice request routes
> through the same agent you saw earlier, it isn't limited to talking. "Turn on the lights." The agent finds the
> target device in the IoTConnect fleet by name, sends an allowlisted LED command through the board's own MCP
> server — and a physical device across the room switches on. Voice, to agent, to cloud, to hardware. Running on
> a development board with no internet dependency in the loop.

---

### 3.10 Benchmark and close (0:45 finished)

**Do:** `run-benchmark report` → publishes instantly.

**Expect** (from the July 3 neutron report, after §1.4): `bench_tps` **12.92**, `bench_ttft` **0.28 s**,
`bench_cpu_avg` **23.6%**, `bench_mem_avg` ~3874 MB.

**Capture:** A on the **Benchmark Telemetry** widget — add it first if it isn't on your dashboard (§1.6), there
is no board-served fallback for these four values. Then a final wide of the whole dashboard, then Source B: a
slow push in on the board, everything running.

**VO:**

> These are NXP's own eIQ GenAI Flow benchmark numbers, measured on this board and published straight to the
> dashboard. Twelve point nine tokens a second on the Neutron NPU, first token in under three tenths of a
> second — and the CPU sitting at twenty-three percent, because the NPU is doing the work. Everything in this
> video ran on one development board: a language model, a vision model, speech in and speech out, an agent with
> real tools, retrieval grounding on local documentation, and a seven-billion-parameter model on a discrete NPU
> module. All of it managed, monitored and updated from IOTCONNECT — including the model itself.

**End card:** board + Ara240 still, with links to the repo and `demo-flow.md`.

---

## 4. Timing budget

| Segment | Finished | Real capture |
|---|---|---|
| 3.1 Cold open | 0:25 | 2 min b-roll |
| 3.2 Dashboard tour | 0:40 | 0:40 |
| 3.3 Vision | 0:50 | ~1 min |
| 3.4 Hallucination A/B | 1:40 | ~3 min |
| 3.5 RAG | 1:00 | ~1.5 min |
| 3.6 Ladder | 1:40 | **~13 min** |
| 3.7 Ara240 headline | 1:20 | ~2 min |
| 3.8 Model push | 1:10 | ~2 min |
| 3.9 Voice + LED | 1:30 | **~7 min** |
| 3.10 Benchmark + close | 0:45 | ~1 min |
| **Total** | **~11:00** | **~33 min** + pre-flight |

---

## 5. Post-production

**Cuts.** Every model load, NPU compile, and `voice-start` gets cut. Two techniques, used consistently:

- **Speed ramp with a timer burn-in** for anything you want the viewer to *feel* (the NPU compile, the model
  push) — keep the elapsed clock visible so the compression is honest.
- **Hard cut with a B-roll cover** for anything that's just waiting (danube loads, the qwen ladder).

Never cut so that a wait *looks* instant when it isn't — the timings are a selling point, and an engineer who
buys a board expecting 15-second NPU answers is a support ticket.

**Callouts.** Zoom or highlight-box each of these as the VO names them:

| Segment | Highlight |
|---|---|
| 3.3 | `vlm_vision_time`, `vlm_tps`. **Avoid the VLM TTFT gauge unless you raised its max to 6** — at 3 it pegs |
| 3.4 | the Agent card footer: `tool get_time -> <value> (router: llm)` |
| 3.5 | the `parted` / `resize2fs` commands in the answer |
| 3.6 | `llm_tps` + the backend badge per rung → build the comparison graphic |
| 3.7 | the two answers **side by side** (primary), the model badge changing to `Qwen2.5-7B-Instruct` / `ara2`, and the gauge held steady as proof the speed didn't change. Crop out the Backend/Model toggles |
| 3.8 | the `model_deploy_status` state chain |
| 3.9 | `voice_status: listening`, `send_device_command`, then cut to the LED |

**Lower thirds** (one per chapter, 3 s): `On-device vision — SmolVLM` · `Grounded vs. invented — the agent` ·
`Ask the manual — RAG` · `CPU → NPU → bigger models` · `Kinara Ara-2: a 7B at the edge` ·
`Cloud-to-edge model deployment` · `"Hey NXP" — offline voice + real actions`

**Chapter markers** at each §3.x boundary — required for YouTube on an 11-minute technical video.

**Captions.** Burn in the numbers at minimum (tok/s, TTFT, seconds). Booth loops play muted.

---

## 6. Short cut EDL

~3:20, assembled from the master's takes. No new capture.

| # | Source | Length | Content |
|---|---|---|---|
| 1 | 3.1 | 0:15 | Board pan, tight. Open on the Ara240 module |
| 2 | 3.3 | 0:30 | Vision — object in frame, card fills, `vlm_tps` callout |
| 3 | 3.4 | 0:50 | Full A/B: invented time → agent's correct time + tool chain |
| 4 | 3.6→3.7 | 0:50 | Ladder comparison graphic (3 s) straight into the 1.5B-CPU vs 7B-Ara A/B |
| 5 | 3.9 | 0:40 | "Hey NXP … turn on the lights" → LED switches on |
| 6 | 3.10 | 0:15 | Wide dashboard + end card |

Re-record a **tighter VO** for this cut — don't try to trim the master's read; the sentences won't land. Keep the
lines *"we just added the card"* and *"voice, to agent, to cloud, to hardware."*

Skipped in the short cut: RAG, the model push, the benchmark. If the audience is IOTCONNECT-focused rather than
silicon-focused, swap item 4 for the §3.8 model push instead.

---

## 7. If it breaks mid-record

| Symptom | Do this |
|---|---|
| Command acks **"busy"** | `voice-stop`, wait for `genai_status: idle`. Nothing is broken — this is the one-operation-at-a-time rule |
| Card never fills | Check `genai_status`. If `generating` for over 3 min on a CPU/danube rung, that's normal; over 5 min, restart `genai-app` |
| Wake word ignored, no beep | Mic level (§1.2). Confirm `capture_device` is `sysdefault:CARD=B101` and `voice_status: listening` |
| `ask-llm` on `ara2` fails | `systemctl status eiq-aaf-connector`; `curl http://127.0.0.1:8100/v1/models` must show `"ready":true` |
| Push stalls on `downloading` | Disk (§1.3). `df -h /` — you need ~2× the model size free |
| Camera panel shows a cert warning | Open `https://192.168.68.71:8080`, accept, reload the dashboard. Retake the segment |
| Agent gives a wrong time | Board clock drifted: `date -u -s 'YYYY-MM-DD HH:MM:SS'; hwclock --systohc`. **Retake §3.4** — a wrong time in the agent beat destroys that segment's point |
| Status badge stuck on `error` | Last-known value, doesn't auto-clear. Run any successful op on that engine to reset it before recording |
| Nothing responds | `systemctl restart genai-app genai-camera genai-mcp`, wait 20 s |

**The one rule, on set:** the board runs one AI operation at a time, and a voice session holds the engine for its
entire duration. Ninety percent of on-set confusion is that rule. Check `genai_status` first, always.
