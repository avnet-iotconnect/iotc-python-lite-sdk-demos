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
> **What resets the warm model (read this — it explains every surprise wait).** The board keeps ONE
> warm LLM session, identified by *(model, backend, RAG)*. It restarts — paying the full load again — on:
> - **any** Model / Backend / RAG change in frame 3, *even re-selecting the value already set*;
> - warming the **Agent** (one session at a time: the agent releases the chat model, and the next plain
>   LLM ask releases the agent — each flip costs a reload);
> - ~60 minutes idle (the session reaper), or a voice session.
>
> On CPU a restart costs ~44 s. **On Neutron it costs the full ~2 min compile — the compile is per
> session start, not per board.** So on Neutron: get it warm, then *touch nothing* between asks.
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

## 2 · Small and fast, but it guesses   ~2 min
**Settings:** frame 3 → Model → `qwen2.5-0.5b-instruct-q8_0` (a llama.cpp GGUF) → Set.

| Do | Measured | Point |
|---|---|---|
| set-model | ~10 s | backend auto-labels `cpu-llama.cpp` |
| `What is an NPU?` | **22 s** (load **3.7 s**) | **speed** — loads 12× faster than Danube (3.7 s vs 44 s) and types faster (~12.5 vs 9.8 tok/s) |
| `What year was the NXP i.MX 95 released?` | ~15 s | **facts** — answers a confident **wrong** year (measured: "2018" one run, "2009" the next) |
| (ask the year question **again**) | ~15 s | it gives a **different wrong** year — proof it's guessing, not recalling |

**Say:** "This model loads in under four seconds — twelve times faster than Danube — and types faster too.
Now watch the facts: I'll ask what year this very board's processor came out... it says 2018. Ask again...
now it says 2009. Both wrong, and *different* — it isn't remembering a fact, it's generating a plausible-looking
one. **Fast is not the same as right.** These are half-billion-parameter models on a dev board, not GPT-4 — the
next few minutes are about making a small model *trustworthy*."

> **Why the answers won't match this script exactly.** These models sample with randomness (temperature), so
> every run's wording — and every hallucination — differs. That's the point of running the year question twice.
> Reliable-to-hallucinate prompts (tested on qwen-0.5b): *"What year was the NXP i.MX 95 released?"* and
> *"How many CPU cores does the i.MX 95 have?"* (it says 4 with hyperthreading; it's actually 6 Cortex-A55).
> Avoid *"Who is the CEO of NXP?"* — it sensibly declines rather than inventing. And note "What is an NPU?"
> is usually answered *correctly* — use it for the **speed** point, the year question for the **guessing** point.


## 3 · CPU vs the Neutron NPU (same model)   ~3 min (mostly a wait)
**Settings:** model `danube-500M-q8`; frame 3 → Backend → **Neutron**.

| Do | Measured |
|---|---|
| set-backend neutron | ~10 s |
| `What is an NPU?` on Neutron | **141 s** — 129 s is the NPU model **compile**, then **12.8 tok/s** vs CPU's 9.8 (+31%) |
| a second Neutron ask (touch nothing in between) | fast — the session is warm |

**Say:** "The NPU compiles the model when the session starts — that's the two-minute wait. After that it
generates about a third faster than the CPU for the same model and the same answer. The wait itself is worth
narrating — 'this is the NPU building an optimized version of the model.'" Then **set-backend cpu** to move on.

> ⚠️ The compile is **not** cached: ANY frame-3 click (even re-selecting the same model), a RAG toggle, or
> warming the agent restarts the session — and on Neutron a restart is another ~2 min compile. Measured live:
> a presenter clicked set-model (to the model already selected) while on Neutron and the next ask recompiled.

---

## 4 · The hallucination, and the Agent that fixes it   ~3.5 min — *the key beat*
**Settings:** model `danube-500M-q8`, backend `cpu`, RAG off.

First, ask the plain LLM things it cannot know:

| Do (frame 2, LLM tab) | Answer |
|---|---|
| `What time is it right now?` | *"The current time is 12:00:00 PM."* ❌ (it was 03:29) |
| `What is today's date?` | *"Today's date is the day of the week in the Gregorian calendar…"* ❌ nonsense |

Now **Warm agent** (frame 2) — or it's already warm from pre-flight — and switch to the **Agent** tab.
(Note: the agent takes over the board's single LLM session, so your next *plain* LLM ask after this segment
will pay the ~44 s reload — that's why §5's first RAG ask shows "cold".)

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
**Settings:** model `danube-500M-q8`, **backend `cpu`** (set it if you were on Neutron), frame 2 → **RAG: on**.
**Ask in the LLM tab, not the Agent tab** — RAG grounds the plain LLM; the Agent answers board questions (time,
USB, memory) and would just answer a knowledge question from the model, ungrounded.

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
2. **Fast ≠ correct, and non-deterministic.** Small models invent facts and word them differently every
   run (qwen-0.5b gave the i.MX 95 release year as 2018, then 2009; Danube drifts "quantization" into
   quantum mechanics). Don’t rely on a specific funny quote landing — rely on the *pattern*: ask a
   niche fact twice and it contradicts itself. That inconsistency is the honest, memorable framing.
3. **Neutron = +31% throughput for a ~129 s compile per session start.** Not cached — any model/backend/RAG
   click or agent warm-up recompiles. Warm it, then don’t touch frame 3; narrate the compile when it happens.
4. **The agent is the money shot.** Invented time/date from the LLM → real time, real USB device, real
   memory from the agent. This is the clearest "why does this matter" moment in the whole demo.
5. **RAG both grounds and refuses.** A correct grounded answer *and* a polite off-topic refusal are both
   selling points — small models made trustworthy by retrieval.
6. **Remove `garbage_model` on workshop boards.** It's 959 filler chunks that make `rag-add` ~85 s and
   muddy retrieval; without it, adds are ~10 s. Strong candidate to bake into the golden image.
7. **VLM: ask open or scene-true questions.** "Describe what you see" was accurate; "how many people" at a
   board-wall hallucinated ten. Point the camera at the audience for people questions.
8. **Use q8 for anything grounded.** q4 is faster but fails RAG.
9. **Tabs matter.** RAG/knowledge questions go in the **LLM** tab; the **Agent** tab is for board facts
   (time, USB, memory). Asking a knowledge question in the Agent tab now just answers it from the model
   (ungrounded) instead of erroring — but for a grounded answer, use the LLM tab with RAG on.

## Exact prompt list (copy/paste)

```
# Segment 1 (danube-500M-q8, cpu, RAG off)
What is an NPU?
Why do edge devices need their own NPU?
Explain model quantization in one paragraph.
# Segment 2 (set-model qwen2.5-0.5b-instruct-q8_0)
What is an NPU?
What year was the NXP i.MX 95 released?
What year was the NXP i.MX 95 released?    (ask again - different wrong answer)
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
