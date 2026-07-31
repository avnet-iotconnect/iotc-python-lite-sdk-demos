# FRDM i.MX 95 GenAI Workshop Guide

How to run a hands-on workshop where every attendee leaves with a FRDM i.MX 95 connected to **their own
private /IOTCONNECT space**, running the eIQ GenAI demo (LLM, agent, vision, benchmarks).

The model: **boards are prepared "up to a point" by the host** (flashed, demo + models installed, on the room
network). Attendees sign up on the onboarding portal, download their personal **board kit**, and drop it on
their board's **claim page** — no SSH, no terminals, no file copying.

```
attendee's laptop                        their board (from its card)
────────────────                         ───────────────────────────
portal signup (event code)
   └─> board-kit .zip  ── drag & drop ─> http://imx95-XXXX.local:8088
                                            └─> board restarts the demo
                                                └─> live in THEIR dashboard
```

---

## Part 1 — Host preparation (per board, ~before the workshop)

Do this once per board. Steps 1–4 are identical for every board, so prepare one and clone the eMMC/SD if
your logistics allow.

1. **Flash / check the BSP** — 6.18-whinlatter or later (see [../FLASHING.md](../FLASHING.md)); expand the
   root partition:
   ```bash
   parted -s /dev/mmcblk0 resizepart 2 100% && resize2fs /dev/mmcblk0p2
   ```
2. **Install the demo package** (README §5) into `/opt/demo` and run `bash install.sh`.
3. **Install NXP eIQ GenAI Flow** (README §3) and run one prompt so the model blobs are downloaded — the
   room network should not be doing multi-GB downloads mid-workshop:
   ```bash
   cd /root/eiq_genai_flow && python3 eiq_genai_flow.py -i keyb -o text -m danube-500M-q8
   ```
4. **Do NOT install any device identity** — boards ship unclaimed; attendees bring their own.
5. **Run the workshop installer**:
   ```bash
   bash /opt/demo/workshop-install.sh
   ```
   This gives the board a **unique hostname from its MAC** (e.g. `imx95-4f2c`), enables the demo +
   claim-page services on boot, and prints the board's claim URL:
   ```
   Claim page:  http://imx95-4f2c.local:8088
   ```
6. **Write the URL on the board's card** (sticker or tent card next to each board). This is how attendees
   find *their* board among many — every board in the room has a different name.
7. **Room network**: boards and attendee laptops must share one LAN (the venue Wi-Fi or a workshop router).
   mDNS (`.local`) must be allowed — on locked-down venue networks, bring your own access point.
8. **Portal event code**: set/rotate the `EVENT_CODE` env var on the `imx95-portal-api` Lambda so signups
   onboard instantly (no approval clicks mid-workshop). Tell attendees the code at the start.

## Part 2 — Attendee experience (~10 minutes to a live board)

> Hand attendees **[ATTENDEE-GUIDE.md](ATTENDEE-GUIDE.md)** — their own manual with every link, what
> they can do, the full list of /IOTCONNECT platform capabilities the workshop exercises, what happens
> if they keep (or hand back) the board, and troubleshooting.


Give attendees these steps (slide or handout):

1. **Sign up**: open the portal (host shares the URL), enter your name, email, company, and the **event
   code**. Your private space is created instantly.
2. **Check your email**: /IOTCONNECT sends an invite — set your password. That's your login at
   [awspoc.iotconnect.io](https://awspoc.iotconnect.io); you'll only see *your* space.
3. **Download your board kit** (.zip) from the signup page.
4. **Find your board's URL** on the card next to it (e.g. `http://imx95-4f2c.local:8088`) and open it.
5. **Drop the kit .zip on the page.** The board installs your identity and the page reports
   **"✓ Connected as p95…"** within a minute.
6. **Open [your dashboard](https://awspoc.iotconnect.io)** — your board is live. Try the Command panel:
   - `ask-llm` *what is an NPU?* — on-device LLM
   - `ask-agent` *how warm is the board?* — agent with real board tools
   - `ask-vlm` — describe what the camera sees (if a camera is fitted)
   - `run-benchmark` — measured tokens/sec on the dashboard
   The LLM shootout UI also runs on the board: `http://imx95-XXXX.local:8090`.

## Part 3 — Multi-board rooms: how collisions are prevented

- **Unique names**: each board's hostname (and thus its `.local` URL) is derived from its MAC — no two
  boards in the room share an address. The card on the board is the source of truth.
- **Claim guard**: a board that already holds an identity says **"This board is already claimed"** (showing
  the device id) and requires an explicit confirmation to replace it — a mistyped URL can't silently steal a
  neighbor's board. Re-claiming backs up the previous identity to `/opt/demo/identity-backup-*`.
- **Wrong-board recovery**: claimed the wrong one? Just claim the right board with the same zip — a kit can
  be installed on any single board (last claim wins for that device id), and the neighbor re-claims theirs.

## Troubleshooting (host cheat-sheet)

| Symptom | Fix |
|---|---|
| `imx95-XXXX.local` doesn't resolve | Venue blocks mDNS — use the board's IP (check the router), or your own AP |
| Page says connected but dashboard empty | Attendee is logged into the wrong account — the invite email is per-signup |
| "Identity installed, but no connection" | Board has no internet route — check the room uplink |
| Claim page down | `systemctl restart genai-provision` on the board |
| Demo down after claim | `systemctl status genai-app`; logs: `journalctl -u genai-app -f` |
| Attendee lost their kit | The portal signup page re-offers the download on the same browser (localStorage), or look up the request in DynamoDB `imx95-portal-requests` |

## Related docs

- [Onboarding portal](../portal/README.md) — the signup/approval backend
- [Demo README](../README.md) — full command reference and GenAI Flow install
- [BENCHMARKS.md](BENCHMARKS.md) — measured numbers + the on-board shootout UI
- [demo-flow.md](../demo-flow.md) — scripted booth/demo narratives
