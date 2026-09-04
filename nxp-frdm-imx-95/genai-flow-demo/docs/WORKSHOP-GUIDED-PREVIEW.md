# FRDM i.MX 95 GenAI — Guided Preview (presenter walkthrough)

A short, complete demo you drive from the /IOTCONNECT cockpit **before** turning attendees
loose on their own boards. It builds one idea at a time — *the model has to load → small models
are fast but guess → the NPU trades compile time for speed → the agent grounds what the LLM
invents → RAG grounds and refuses → the board can see*.

Every timing and quoted answer below was **measured on a real FRDM i.MX 95** (board `imx95-55ea`,
danube-500M-q8 unless noted) the night of 2026-09-03, driving the exact commands the cockpit sends.
Times are wall-clock from pressing a control to the answer appearing.

> **One-time pre-flight (do this before the audience arrives).** Every model pays a load on its
> first use. Warm the ones you'll show so the *demo* isn't the load bar:
> - `set-model danube-500M-q8`, `set-backend cpu`, ask one throwaway question (eats the ~44 s load).
> - `agent-start` (≈45 s to `ready`).
> - If you'll show vision: one `ask-vlm Describe what you see` (eats the ~43 s VLM load).
> - Confirm the cockpit header shows **build b22+** and the live pill is green.
>
> **Recommended board prep — remove the `garbage_model` demo corpus.** It is 959 filler chunks that
> (a) stretch every `rag-add` to ~85 s because the whole database re-embeds, and (b) pollute
> retrieval. Without it, `rag-add` drops to ~10 s. See *Insight 6*.

---

## 1 · The model has to load (warm vs cold)   ~1.5 min
**Settings:** model `danube-500M-q8`, backend `cpu`, RAG off.

| Do (frame 2 · Ask your board) | Measured | 
|---|---|
| `What is an NPU?` (first time) | **60 s** — 44 s of it is the one-time model load |
| `Why do edge devices need their own NPU?` | **17 s** — load 0 s, model stayed warm |
| `Explain model quantization in one paragraph.` | **17 s** |

**Say:** "The first answer took a minute; the next two took seventeen seconds. On a model this small
the *loading* is the cost, not the thinking — which is why the board keeps a model resident once it's up."

---

## 2 · Small and fast, but it guesses   ~1.5 min
**Settings:** frame 3 → Model → `qwen2.5-0.5b-instruct-q8_0` (a llama.cpp GGUF) → Set.

| Do | Measured | Answer |
|---|---|---|
| set-model | ~10 s | backend auto-labels `cpu-llama.cpp` |
| `What is an NPU?` | **22 s** (load **3.7 s**) | *"An NPU (NVIDIA Programming Unified Language) … developed by NVIDIA, a subsidiary of Alibaba Cloud."* ❌ |
| `Why do edge devices need their own NPU?` | 28 s | a solid, well-structured answer ✔ |

**Say:** "This model loads in under four seconds — twelve times faster than Danube — and it types
faster too. But look: it just invented that NPU stands for *NVIDIA Programming Unified Language* and
that NVIDIA is owned by Alibaba. **Fast is not the same as right.** These are half-billion-parameter
models running on a dev board, not GPT-4 — the whole point of the next few minutes is how we make a
small model *trustworthy*."

---

## 3 · CPU vs the Neutron NPU (same model)   ~3 min (mostly a wait)
**Settings:** model `danube-500M-q8`; frame 3 → Backend → **Neutron**.

| Do | Measured |
|---|---|
| set-backend neutron | ~10 s |
| `What is an NPU?` on Neutron | **141 s** — 129 s is a one-time NPU model **compile**, then **12.8 tok/s** vs CPU's 9.8 (+31%) |

**Say:** "The NPU has to compile the model the first time — that's the two-minute wait, and it happens
once. After that it generates about a third faster than the CPU for the same model and the same answer.
For a booth you pre-warm this; the wait itself is worth narrating — 'this is the NPU building an
optimized version of the model.'" Then **set-backend cpu** to move on quickly.

---

## 4 · The hallucination, and the Agent that fixes it   ~3.5 min — *the key beat*
**Settings:** model `danube-500M-q8`, backend `cpu`, RAG off.

First, ask the plain LLM things it cannot know:

| Do (frame 2, LLM tab) | Answer |
|---|---|
| `What time is it right now?` | *"The current time is 12:00:00 PM."* ❌ (it was 03:29) |
| `What is today's date?` | *"Today's date is the day of the week in the Gregorian calendar…"* ❌ nonsense |

Now **Warm agent** (frame 2) — or it's already warm from pre-flight — and switch to the **Agent** tab:

| Do (Agent tab) | Measured | Tool | Answer |
|---|---|---|---|
| `What time is it right now?` | 12 s | `get_time` | *"Friday, September 04, 2026 at 03:29 UTC"* ✔ |
| `What is plugged into my USB ports?` | 11 s | `get_usb` | *"Logitech, Inc. Brio 101"* ✔ |
| `How much memory am I using?` | 12 s | `get_memory` | *"2171 MB of 7690 MB of RAM, CPU load 14.6%"* ✔ |

**Say:** "Same board, same tiny model. On its own it *invented* the time. As an agent, it doesn't guess
— it picks a real tool, the board runs it, and the answer is grounded in fact. That is the difference
between a chatbot and something you can put in a product." (Note the agent card also shows *which* tool
it chose and how it routed — `llm` when the model picked the tool itself, `keyword-override` when the
safety net corrected it.)

---

## 5 · RAG: ground it in the manual, and watch it refuse   ~4 min
**Settings:** model `danube-500M-q8`; frame 2 → **RAG: on**.

| Do | Measured | Answer |
|---|---|---|
| `What kind of processor is inside the NXP i.MX 95?` | 55 s (cold) / ~11 s warm | *"…the i.MX 95 applications processor, a high-performance Arm Cortex-A55."* ✔ grounded |
| `How many eggs are in a dozen?` | **6 s** | *"I'm unable to assist you with this topic."* ✔ refuses off-topic by design |

**Add your own document (live):** frame 3 area → drop a **small `.txt`/`.md`** on the RAG upload, or paste a URL.
- Measured: a 7-chunk text doc indexed in **~85 s**, then answered from it (e.g. asking about starting the
  demo services returned the procedure from the uploaded note). Removing it takes about the same (full re-embed).

**Say:** "RAG turns the board into 'ask the manual.' It answered the processor question from real docs —
and when I asked something off-topic, it *declined* instead of making something up. Refusing is a feature.
And you can drop in your own document and it'll answer from that too."

> **Presenter cautions for §5:**
> - Use **danube-500M-q8**, not q4 — q4 reproducibly fails RAG (refuses instead of quoting).
> - The ~85 s add time is almost entirely the 959-chunk `garbage_model` corpus re-embedding. On a
>   board prepped per *Insight 6* this is ~10 s and safe to do live; otherwise kick it off and talk
>   while it runs, or pre-stage it.

---

## 6 · The board can see   ~2 min
**Settings:** frame 3 → Vision model. `smolvlm-500M` is more accurate; `smolvlm-256M` is faster.

| Do (frame 2, VLM tab) | Measured | Answer |
|---|---|---|
| `Describe what you see in this image.` | 43 s first (load) / ~60 s | *"a collage of various electronic components — circuit boards, resistors, capacitors, integrated circuits — in a grid-like pattern"* ✔ (camera was on a wall of demo boards) |
| `What color are the boards and posters on the wall?` | 12 s | *"white"* ✔ |
| `How many people are in view?` (no people in frame) | — | *"10 people"* ❌ |

**Say:** "It genuinely describes the scene. But notice the last one — with nobody in front of the camera
it confidently counted ten people. Ask a vision model an **open** question ('describe what you see') or
one that matches what the camera actually sees; a leading question about things that aren't there invites
a guess. Point the camera at the room and ask again — it'll get *you* right."

---

## Timing budget

| Segment | Board time | With narration |
|---|---|---|
| 1 · warm vs cold | ~1.5 min | ~3 min |
| 2 · small & fast | ~1.5 min | ~3 min |
| 3 · CPU vs NPU | ~3 min (compile) | ~4 min |
| 4 · agent | ~1.5 min (pre-warmed) | ~4 min |
| 5 · RAG | ~2 min (+85 s if adding a doc live) | ~5 min |
| 6 · vision | ~1.5 min | ~3 min |
| **Total** | **~11 min pure** | **~20–25 min guided** |

Pre-warming (pre-flight) removes ~3–4 minutes of load bars from the audience's view.

## Insights to use out loud

1. **Loading dominates on small models.** Danube ~44 s, qwen-GGUF ~4 s, Neutron ~129 s compile. Pre-warm.
2. **Fast ≠ correct.** Both small LLMs invented facts (Danube: "quantization" → quantum mechanics;
   qwen-0.5b: "NPU = NVIDIA Programming Unified Language, owned by Alibaba"). This is the honest, memorable
   framing for on-device AI — set the expectation, then show the fixes.
3. **Neutron = +31% throughput for a 129 s one-time compile.** Great for sustained use; narrate the compile.
4. **The agent is the money shot.** Invented time/date from the LLM → real time, real USB device, real
   memory from the agent. This is the clearest "why does this matter" moment in the whole demo.
5. **RAG both grounds and refuses.** A correct grounded answer *and* a polite off-topic refusal are both
   selling points — small models made trustworthy by retrieval.
6. **Remove `garbage_model` on workshop boards.** It's 959 filler chunks that make `rag-add` ~85 s and
   muddy retrieval; without it, adds are ~10 s. Strong candidate to bake into the golden image.
7. **VLM: ask open or scene-true questions.** "Describe what you see" was accurate; "how many people" at a
   board-wall hallucinated ten. Point the camera at the audience for people questions.
8. **Use q8 for anything grounded.** q4 is faster but fails RAG.

## Exact prompt list (copy/paste)

```
# Segment 1 (danube-500M-q8, cpu, RAG off)
What is an NPU?
Why do edge devices need their own NPU?
Explain model quantization in one paragraph.
# Segment 2 (set-model qwen2.5-0.5b-instruct-q8_0)
What is an NPU?
Why do edge devices need their own NPU?
# Segment 3 (set-model danube-500M-q8, set-backend neutron, then back to cpu)
What is an NPU?
# Segment 4 (RAG off; plain LLM, then Warm agent + Agent tab)
What time is it right now?
What is today's date?
What time is it right now?          (agent)
What is plugged into my USB ports?  (agent)
How much memory am I using?         (agent)
# Segment 5 (RAG on, danube-500M-q8)
What kind of processor is inside the NXP i.MX 95?
How many eggs are in a dozen?
# Segment 6 (VLM tab)
Describe what you see in this image.
What color are the boards and posters on the wall?
```
