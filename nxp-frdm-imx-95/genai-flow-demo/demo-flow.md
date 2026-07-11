# FRDM i.MX 95 GenAI Demo Flow

A complete walk-through for demonstrating every feature, with expected results, time-to-result, and the telemetry
to point at. All timings were measured on real hardware (FRDM-IMX95, BSP LF6.18.2). Assumes the device is powered,
on the network, and onboarded. Full specs for every AI model in the demo are in [MODELS.md](MODELS.md).

**The one rule:** the board runs **one AI operation at a time**. `ask-llm`, `ask-vlm`, `ask-agent`, and
`run-benchmark` will answer "busy" while another is running — and a **voice session holds the engine for its entire
duration**. If commands start failing with "busy", send `voice-stop` and check `genai_status`/`voice_status`.

---

## 0. Cold boot → demo-ready (~10 minutes)

The full sequence from plugging in the board to every model verified. Model weights live on the eMMC, so
nothing re-downloads at boot — this is about starting services, setting state, and warming/verifying each
engine. Times are measured.

### T+0:00 — Power on
Plug in the board; Linux boots in ~1 minute. Find the IP (router, serial console, or wait for `board_ip`
telemetry). A static DHCP lease avoids every downstream IP problem.

### T+1:00 — Start the demo services
SSH or serial in as `root`, then:

```bash
cat readme.txt   # section 1 is the paste-to-start block
```

Paste the block: cloud app, camera server, and MCP server start with a status printout (`RUNNING` ×3 + board
IP, ~15 s). The MCP auth token persists across boots — no re-login needed.

### T+2:00 — Browser checks
1. Device shows online in /IOTCONNECT; telemetry timestamps current (10 s cadence).
2. Open `https://<board-ip>:8080` once and accept the self-signed cert (new browsers/IPs only) — unlocks the
   embedded **AI Responses** and **Live Camera** panels.
3. If the IP changed since the dashboard was built: edit the two Embedded widget links.

### T+2:30 — Set the demo state (settings persist, so make them deliberate)

| Send | Value | Why |
|---|---|---|
| `set-model` | `danube-500M-q8` | beats 4–6 need the GenAI Flow path — and q8 specifically: the faster q4 reproducibly fails RAG (returns refusals instead of quoting docs; see [MODELS.md](MODELS.md)) |
| `set-backend` | `neutron` | the NPU headline on the gauges |
| `set-rag` | `off` | beat 3 (hallucination) requires it |
| `set-stt` | `moonshine-base` | the balanced transcriber |

### T+3:00 — Warm and verify every model (watch each ready-signal)

Order matters: **`agent-start` before any `voice-start`** (voice holds the engine lock).

| Step | Send | Ready signal | Wait |
|---|---|---|---|
| 1 | `agent-start` | `agent_status: ready` | ~1 min |
| 2 | `ask-vlm` (no argument) | Vision card fills; `vlm_tps` ≈ 9.5 — also proves the camera | ~45 s |
| 3 | `ask-llm hello` | LLM card fills; `llm_tps` ≈ 13.7, gauges move — proves the NPU path | ~2.5 min |
| 4 | `ask-agent what time is it` | correct time in the Agent card, ~15 s (session is warm) — proves the agent end-to-end | ~15 s |

Note: `ask-llm` reloads its model on every call by design — step 3 *verifies* the NPU path and populates the
dashboard; it doesn't make later asks faster. The agent session is the only persistently-warm LLM.

### T+7:00 — Voice smoke test (do this even if voice is only the encore)

1. If the venue is new: run the **mic check** (failure playbook, below) — 30 seconds that prevent an hour of
   mystery. Speech seconds must hit **2000+ RMS**.
2. `voice-start` → wait for `voice_status: listening` (~2–3 min) → *"Hey NXP"* … beep … *"what is the wake
   word?"* → spoken answer lands.
3. Optional but glorious: *"Hey NXP … turn on the lights"* — verifies agent bridge + MCP + the LED device in
   one utterance.
4. **`voice-stop`** — leave the engine free for the demo loop.

### T+10:00 — Demo-ready state

| Telemetry | Should read |
|---|---|
| `genai_status` | `idle` |
| `agent_status` | `ready` |
| `voice_status` | `off` (start it live per visitor, or leave running if voice-first) |
| `llm_model` / `llm_backend` / `llm_rag` | `danube-500M-q8` / `neutron` / `off` |
| `board_ip` | matches the Embedded widget links |
| Gauges | populated from the warm-up answers, needles in green |

---

## 1. Dashboard tour (30 seconds)

No commands — just orient the visitor:

* **Gauges**: LLM tokens/sec (green = fast), SoC temperature (idle ≈ 44–46 °C), CPU load.
* **AI Engine Status**: current model (`danube-500M-q8`), backend (`neutron` = the on-chip NPU), RAG state, voice
  and agent session states.
* **AI Responses panel**: four cards — LLM, Vision, Voice, Agent — every answer appears here within ~2 s of
  completing, served by the board itself.
* **Live Camera**: the board's own HTTPS video stream.

**Talking point**: *"Everything you'll see — language model, vision model, speech, video — runs on this one chip.
The cloud only carries the telemetry."*

## 2. Vision: the board describes what it sees (~45 s)

**Do**: press the **"Ask VLM: Describe Scene"** button (or `ask-vlm What do you see?` — with no argument it
defaults to "Describe what you see in this image").

**Expect**: command acks in ~2 s; **30–45 s later** the orange Vision card fills with a scene description —
reliably identifies people, clothing colors, glasses, held objects, and room features.

**Point at**: `vlm_response` (the description), `vlm_vision_time` (**~3.6–4.5 s** vision encode),
`vlm_tps` (**~10 tok/s** decode).

**Crowd move**: have the visitor hold an object up to the camera and ask again — it names what they're holding.

## 3. The hallucination A/B: why agents matter (~2 min)

This is the smartest beat in the demo. **Requires RAG Off** for part one (the RAG classifier otherwise politely
declines off-topic questions — itself worth showing, see beat 5).

1. Flip **RAG Grounding → Off**, `set-model qwen2.5-0.5b-instruct-q8_0`, then `ask-llm what time is it`.
   **Expect ~15 s** (llama.cpp loads in 5.6 s — this used to be the slowest moment of the flow; on Danube it costs
   1–2.5 min): a confidently **invented** time. No LLM has a clock; the fancier model just invents more fluently.
   Let the visitor laugh.
2. Press **"Agent: What Time Is It?"** (`ask-agent what time is it`).
   **Expect**: first-ever run ~90 s (session load); **pre-warmed: 10–20 s** — the **correct** date and time.

**Point at** the green Agent card / telemetry chain:
* `agent_tool: get_time` — the LLM *chose* an action instead of answering
* `agent_tool_result` — the real data the board fetched
* `agent_response` — the grounded answer
* `agent_router` — `llm` (model picked the tool itself) or `keyword-override` (the safety net caught a bad pick)

**Follow-ups** (each 10–20 s, session stays warm): `ask-agent how warm is the chip` (compare with the temperature
gauge live!), `ask-agent how much memory is in use`, `ask-agent what usb devices are plugged in` (plug something
in and ask again), and — via the on-board MCP server — `ask-agent how many devices are in my iotconnect deployment`
(the device querying its own cloud fleet).

## 4. RAG: "ask the manual" (~1 min per question)

RAG runs through the Danube/GenAI Flow path only, so switch back first: `set-model danube-500M-q8` — and for
crowd pacing, `set-backend cpu` (a 44 s load per question instead of the NPU's 129 s compile; save the NPU for
the ladder beat where the wait *is* the story).

**Do**: flip **RAG Grounding → On**, then `ask-llm How do I expand the root filesystem?`

**Expect**: the answer quotes the board's documentation **verbatim**, including the exact `parted` and `resize2fs`
commands. Other good questions: *"What baud rate does the serial console use?"* (115200), *"What tokens per second
does the Neutron NPU achieve?"* (13.7).

**Point at**: `llm_rag: on`, and the contrast with beat 3's invention — same model, now grounded.

**Talking point**: *"The knowledge base is just a JSON file of facts — swap in your service manual and your field
techs get this on every machine, fully offline."*

## 5. Performance ladder: CPU → NPU → bigger models (~5 min)

Ask the same question at each rung and watch the **tokens/sec gauge** and answer quality:

| Do | `llm_backend` shows | Expect `llm_tps` | Time to answer | Quality |
|---|---|---|---|---|
| `set-backend cpu` → `ask-llm What is an NPU?` | `cpu` | **10.1** | ~1 min | fluent, shaky facts |
| `set-backend neutron` → same question | `neutron` | **13.7** | ~2.5 min (NPU compile dominates) | same words, +35% speed |
| `set-model danube-500M-q4` → same (still neutron) | `neutron` | **15.9** | ~2.5–3 min | fastest measured — but quantization broke its RAG ability (refusals instead of quotes), which is why it isn't the default |
| `set-model qwen2.5-0.5b-instruct-q8_0` → same | `cpu-llama.cpp` | **12.9** | **~15 s** | correct definition, 5.6 s load |
| `set-model qwen2.5-1.5b-instruct-q4_k_m` → same | `cpu-llama.cpp` | **5.7** | ~30 s | best reasoning |
| `set-model danube-500M-q8` | back to GenAI Flow | | | |

For short crowd loops run just three rungs — **q8-CPU → qwen-0.5B → qwen-1.5B** (all ≤1 min) — and quote the NPU
numbers from the gauge history; the full six-rung walk with the compile waits is for engaged engineers.

**Point at**: `llm_tps`, `llm_ttft` (0.13–0.83 s, model-dependent), `llm_backend` changing, and the answers.

**The close**: *"Notice the trade — the smarter model runs at half the speed on CPU. The Kinara Ara-2 module drops
into this same demo and moves the smart models up the speed column. That's the roadmap, running live."*

## 6. Voice finale: "Hey NXP" (~3 min setup, then continuous)

Best with the USB headset (show floors are loud); a powered speaker on the 3.5 mm jack works in quieter settings.

1. Send `voice-start`. **Expect**: `voice_status` goes `starting` → **`listening` after ~2–3 min** (models +
   NPU compile). Don't speak before `listening`.
2. Say **"Hey NXP"** … *pause for the beep* … then one clear question. Running them together puts the wake word
   into the transcript.
3. **Expect**: answer speaks aloud **10–20 s** after you finish; the purple Voice card and `voice_question` /
   `voice_response` / `voice_exchanges` update per round. It re-arms for the next wake word automatically.
4. **RAG applies to voice too**: with RAG On it answers board questions from the docs and politely rejects
   off-topic or garbled audio ("I can't help with that request" — show this, it's a feature). For open chat,
   set RAG Off before `voice-start`.
5. **The showstopper — voice-controlled action**: with the agent pre-warmed (§0), say
   *"Hey NXP … turn on the lights."* The spoken request routes through the agent, which finds the target device
   in the IoTConnect fleet by name fragment ("lights" → `e84AIvaLights`) and sends the allowlisted LED command
   through the on-board MCP server — **a physical LED across the room switches on**. The green Agent card shows
   the chain: `send_device_command` → *"Sent command board-user-led on to device e84AIvaLights"*. Then:
   *"Hey NXP … turn **off** the lights."* Requires the MCP server running and authenticated (§0 start block +
   README §10).
6. **Transcription accuracy is selectable**: `set-stt whisper-small.en` before `voice-start` for the accuracy-
   critical version (0.00 % clean-speech WER, +1.2 s per utterance) — `moonshine-base` is the balanced default.
7. **`voice-stop` when done** — this is the step people forget, and it blocks every other AI command until sent.

## 7. Optional: the official benchmark (10–30 min — run between crowds)

`run-benchmark` executes NXP's own eIQ GenAI Flow benchmark suite and publishes `bench_tps` (**12.92** on
NPU+RAG), `bench_ttft` (**0.28 s**), `bench_cpu_avg` (**23.6 %** — the NPU doing the work), `bench_mem_avg`.
`run-benchmark report` re-publishes the last results instantly — useful to refresh the dashboard without rerunning.

---

## Timing quick reference

| Action | First time | Warmed |
|---|---|---|
| `ask-vlm` | ~45 s | ~30–45 s |
| `ask-agent` | ~90 s | **10–20 s** |
| `ask-llm` (danube, CPU) | ~1 min | ~1 min (reloads each call) |
| `ask-llm` (danube, NPU) | ~2.5 min | ~2.5 min (NPU compile each call) |
| `ask-llm` (danube q4, NPU) | ~2.5–3 min | ~2.5–3 min (fastest tok/s once running: 15.9) |
| `ask-llm` (qwen 0.5B, llama.cpp) | **~15 s** | ~15 s |
| `ask-llm` (qwen 1.5B, llama.cpp) | ~30 s | ~30 s |
| voice LED action ("turn on the lights") | — | 10–20 s to the physical LED |
| `voice-start` → `listening` | ~2–3 min | — |
| voice exchange | — | 10–20 s |
| Dashboard telemetry refresh | every 10 s | AI Responses panel: ~2 s |

## Telemetry cheat sheet

| Attribute | What it tells the visitor | Healthy value |
|---|---|---|
| `genai_status` | what the AI engine is doing | `idle` / `generating` / `agent` / `voice` |
| `llm_tps` | generation speed | 10.1 CPU · 13.7 NPU · 12.9 qwen-0.5B · 5.7 qwen-1.5B ([MODELS.md](MODELS.md)) |
| `llm_ttft` | responsiveness | 0.13–0.83 s (model-dependent; see [MODELS.md](MODELS.md)) |
| `llm_backend` | where inference runs | `cpu` / `neutron` / `cpu-llama.cpp` |
| `llm_rag` | grounded or free-wheeling | `on` for doc questions |
| `agent_router` | did the LLM route correctly | `llm` (itself) / `keyword-override` (safety net) |
| `vlm_vision_time` | image understanding speed | 3.6–4.5 s |
| `cpu_temp` | thermal story | ~45 °C idle, ~63 °C under sustained load |
| `voice_status` | voice session state | `listening` = ready for "Hey NXP" |
| `voice_stt` | active transcriber | `moonshine-base` (balanced) / `whisper-small.en` (0 % WER) |
| `board_ip` | where the embedded widgets point | must match Embedded widget links |

## Failure playbook

| Symptom | Cause | Fix |
|---|---|---|
| Commands ack "busy" | a voice session or long operation owns the engine | `voice-stop`, or wait for `genai_status: idle` |
| Command shows "Failed" in history | template missing that command | import the updated template |
| Camera/Responses panel shows a browser warning | self-signed cert not yet trusted | open `https://<board-ip>:8080` in a tab, accept, reload |
| Panels blank after network change | board got a new IP | update the two Embedded links to `board_ip`'s value |
| Device offline in /IOTCONNECT | network blip / IP move | app self-restarts its session within ~60 s |
| Voice cuts questions to one word | VAD silence window reset by a reinstall | see the VAD tuning note in the README (800 ms) |
| Wake word ignored AND no beep after a reboot or venue move | ALSA card order reshuffles on boot; GStreamer playback lands on a device with no output, and auto-detection can misroute audio | pin devices by name in `/opt/demo/genai-config.json`: `"capture_device": "sysdefault:CARD=C920"`, `"playback_device": "sysdefault:CARD=mqsaudio"`, then `voice-stop` / `voice-start` |
| Wake word ignored at a new venue | speaking too far from the mic (works at ≥4000 RMS, fails near the ~450 noise floor) | run the mic check below; move the mic to arm's length of the speaker |
| Status badges show `error` but everything works | last-known value from a past failure (statuses don't auto-clear) | run any successful operation of that engine (e.g. `voice-start`/`voice-stop`) and it resets |
| Nothing responds at all | app died | on the board: `cd /opt/demo && nohup python3 -u app.py > app.log 2>&1 &` |

### Venue mic check (run after any board move, before doors open)

With the voice session stopped, this beeps, records 12 s, and prints a level bar per second — say
"Hey NXP, what time is it" after the beep. You want the speech seconds at **2000+ RMS**; the noise floor is ~450.

```bash
aplay -D sysdefault:CARD=mqsaudio /root/eiq_genai_flow/assets/ww_earcon.wav
arecord -D sysdefault:CARD=C920 -f S16_LE -r 16000 -c 1 -d 12 /tmp/mictest.wav
python3 -c "
import wave, struct, math
w = wave.open('/tmp/mictest.wav'); n = w.getnframes()
d = struct.unpack('%dh' % n, w.readframes(n))
[print('sec %2d: rms %5.0f %s' % (s, r, '#'*int(r/150))) for s in range(n//16000)
 for r in [math.sqrt(sum(x*x for x in d[s*16000:(s+1)*16000])/16000)]]"
```

## Suggested 4-minute loop per visitor

**Vision hook** (they're in the picture, 45 s) → **hallucination A/B** (Qwen invents in 15 s, the agent answers
truly in 15 more) → **ask the manual** (RAG On, verbatim procedure, ~1 min) → **the ladder close** (gauge + Ara-2
roadmap). Voice is the encore for engaged visitors — and *"Hey NXP, turn on the lights"* is the exit-wow. Budget
3 extra minutes for voice and always `voice-stop` afterward.
