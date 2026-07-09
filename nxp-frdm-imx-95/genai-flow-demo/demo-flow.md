# FRDM i.MX 95 GenAI Demo Flow

A complete walk-through for demonstrating every feature, with expected results, time-to-result, and the telemetry
to point at. All timings were measured on real hardware (FRDM-IMX95, BSP LF6.18.2). Assumes the device is powered,
on the network, and onboarded.

**The one rule:** the board runs **one AI operation at a time**. `ask-llm`, `ask-vlm`, `ask-agent`, and
`run-benchmark` will answer "busy" while another is running — and a **voice session holds the engine for its entire
duration**. If commands start failing with "busy", send `voice-stop` and check `genai_status`/`voice_status`.

---

## 0. Pre-demo checklist (10 minutes before)

On the board (SSH or serial console, login `root`):

```bash
pgrep -f "python3 -u app.py"        || (cd /opt/demo && nohup python3 -u app.py > app.log 2>&1 &)
pgrep -f camera-server              || (cd /opt/demo && nohup python3 camera-server.py > camera.log 2>&1 &)
```

In the browser:

1. Open the /IOTCONNECT dashboard.
2. Open `https://<board-ip>:8080` in its own tab once and accept the self-signed certificate — this unlocks the
   embedded **AI Responses** panel and **Live Camera** view.
3. Confirm the status block shows `genai_status: idle` and telemetry timestamps are current (updates every 10 s).

**Pre-warm the models** so no visitor waits through a first-load:

| Send | Why | Wait |
|---|---|---|
| `ask-agent what time is it` | loads the agent's persistent LLM session | ~90 s |
| `ask-vlm` (no argument) | exercises camera + SmolVLM | ~45 s |
| `ask-llm hello` | warms the GenAI Flow path on the current backend | ~1 min (CPU) / ~2.5 min (NPU) |

> [!IMPORTANT]
> If the venue moved the board to a new IP: the app self-heals its cloud connection (~60 s), but the two
> **Embedded** widget links (`/responses`, `/live`) must be edited to the new address. Pin a static DHCP lease to
> avoid this entirely. The `board_ip` telemetry attribute always shows the current address.

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

1. Flip **RAG Grounding → Off**, then send `ask-llm what time is it`.
   **Expect** (~1 min on CPU / ~2.5 min on NPU — each `ask-llm` reloads the model, see timing table): a confidently
   **invented** time, e.g. *"The time is 12:00 PM."* Let the visitor laugh.
2. Press **"Agent: What Time Is It?"** (`ask-agent what time is it`).
   **Expect**: first-ever run ~90 s (session load); **pre-warmed: 10–20 s** — the **correct** date and time.

**Point at** the green Agent card / telemetry chain:
* `agent_tool: get_time` — the LLM *chose* an action instead of answering
* `agent_tool_result` — the real data the board fetched
* `agent_response` — the grounded answer
* `agent_router` — `llm` (model picked the tool itself) or `keyword-override` (the safety net caught a bad pick)

**Follow-ups** (each 10–20 s, session stays warm): `ask-agent how warm is the chip` (compare with the temperature
gauge live!), `ask-agent how much memory is in use`, `ask-agent how long has the board been running`.

## 4. RAG: "ask the manual" (~1–2.5 min per question)

**Do**: flip **RAG Grounding → On**, then `ask-llm How do I expand the root filesystem?`

**Expect**: the answer quotes the board's documentation **verbatim**, including the exact `parted` and `resize2fs`
commands. Other good questions: *"What baud rate does the serial console use?"* (115200), *"What tokens per second
does the Neutron NPU achieve?"* (13.9).

**Point at**: `llm_rag: on`, and the contrast with beat 3's invention — same model, now grounded.

**Talking point**: *"The knowledge base is just a JSON file of facts — swap in your service manual and your field
techs get this on every machine, fully offline."*

## 5. Performance ladder: CPU → NPU → bigger models (~5 min)

Ask the same question at each rung and watch the **tokens/sec gauge** and answer quality:

| Do | `llm_backend` shows | Expect `llm_tps` | Time to answer | Quality |
|---|---|---|---|---|
| `set-backend cpu` → `ask-llm What is an NPU?` | `cpu` | **~10.9** | ~1 min | fluent, shaky facts |
| `set-backend neutron` → same question | `neutron` | **~13.9** | ~2.5 min (NPU compile dominates) | same words, +27% speed |
| `set-model qwen2.5-0.5b-instruct-q8_0` → same | `cpu-llama.cpp` | **~14** | **~15–20 s** | correct definition |
| `set-model qwen2.5-1.5b-instruct-q4_k_m` → same | `cpu-llama.cpp` | **~6.5** | ~30–60 s | best reasoning |
| `set-model danube-500M-q8` | back to GenAI Flow | | | |

**Point at**: `llm_tps`, `llm_ttft` (0.3–0.7 s), `llm_backend` changing, and the answers themselves.

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
5. **`voice-stop` when done** — this is the step people forget, and it blocks every other AI command until sent.

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
| `ask-llm` (qwen 0.5B, llama.cpp) | ~15–20 s | ~15–20 s |
| `ask-llm` (qwen 1.5B, llama.cpp) | ~30–60 s | ~30–60 s |
| `voice-start` → `listening` | ~2–3 min | — |
| voice exchange | — | 10–20 s |
| Dashboard telemetry refresh | every 10 s | AI Responses panel: ~2 s |

## Telemetry cheat sheet

| Attribute | What it tells the visitor | Healthy value |
|---|---|---|
| `genai_status` | what the AI engine is doing | `idle` / `generating` / `agent` / `voice` |
| `llm_tps` | generation speed | 10.9 CPU · 13.9 NPU · 14 qwen-0.5B · 6.5 qwen-1.5B |
| `llm_ttft` | responsiveness | 0.3–0.7 s |
| `llm_backend` | where inference runs | `cpu` / `neutron` / `cpu-llama.cpp` |
| `llm_rag` | grounded or free-wheeling | `on` for doc questions |
| `agent_router` | did the LLM route correctly | `llm` (itself) / `keyword-override` (safety net) |
| `vlm_vision_time` | image understanding speed | 3.6–4.5 s |
| `cpu_temp` | thermal story | ~45 °C idle, ~63 °C under sustained load |
| `voice_status` | voice session state | `listening` = ready for "Hey NXP" |
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

**Vision hook** (they're in the picture, 45 s) → **hallucination A/B** (laugh, then the agent's real answer, 60 s)
→ **ask the manual** (RAG On, verbatim procedure, 60 s) → **the ladder close** (gauge + Ara-2 roadmap, 60 s).
Voice is the encore for engaged visitors — budget 3 extra minutes and always `voice-stop` afterward.
