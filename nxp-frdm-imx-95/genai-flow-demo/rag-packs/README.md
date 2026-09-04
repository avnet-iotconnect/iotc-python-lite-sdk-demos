# RAG topic packs

One-click knowledge bases for the cockpit's **RAG** card (panel 5). Each pack is a
plain-text `.md` file of self-contained facts. The board fetches the raw file from
GitHub, chunks it (one paragraph = one retrieval chunk), embeds it on-device, and
answers grounded questions about that topic.

## How loading works

- A pack file is named `pack_<topic>.md`. The **`pack_` prefix is load-bearing**:
  when the board indexes a `pack_*` document it first **removes any other
  `pack_*`** already loaded, so exactly one topic pack is active at a time (a clean
  single-topic demo). Bring-your-own documents (the cockpit's *Advanced* section)
  do **not** use the prefix and simply add to whatever is loaded.
- The cockpit sends `rag-add <raw-url> pack_<topic>.md`, turns RAG on, and puts a
  sample question in panel 2.

## Writing a pack

- **One fact per paragraph**, separated by a blank line. Keep each paragraph under
  ~900 characters — it becomes a single chunk, and single-fact chunks retrieve best.
- **Make every paragraph self-contained** — repeat the subject rather than relying
  on "it"/"they", because a chunk is retrieved on its own with no surrounding
  context (e.g. "The Monaco Grand Prix…" not "This race…").
- Prefer timeless, verifiable facts; date anything that changes ("As of 2024, …").
- 15–20 paragraphs is a good size (~1 minute to embed on the board).

## Adding a pack to the cockpit

1. Drop `pack_<topic>.md` in this folder and push to `main` (the board fetches the
   raw file from GitHub, so it must be committed).
2. Add one entry to the `PACKS` array in
   [`portal/site/cockpit.html`](../portal/site/cockpit.html):
   `{id:"pack_<topic>.md", label:"🎯 My Topic", q:"A sample question?"}`
3. Redeploy the cockpit Lambda. The new button appears in panel 5.

## Current packs

Formula 1 · Hockey (NHL) · NFL Football · Baking & Desserts · /IOTCONNECT ·
Space & Astronomy · Coffee · Dinosaurs · National Parks · Classic Video Games
