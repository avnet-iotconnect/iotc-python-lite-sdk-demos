# FRDM i.MX 95 GenAI Workshop — Attendee Guide

Welcome. In this workshop you get a **NXP FRDM i.MX 95** board running NXP's **eIQ GenAI Flow** stack,
connected to **your own private space** in Avnet **/IOTCONNECT**. Everything runs *on the board* — the
language model, the vision model, the speech recognizer, the retrieval database. /IOTCONNECT is how you
reach it, measure it, and manage it from anywhere.

---

## 1. Your links

| What | Where |
|---|---|
| **Sign-up portal** (start here) | *(host provides — enter the attendee code you were given)* |
| **Your cockpit** | `<portal-url>/cockpit` — the workshop UI for your board |
| **/IOTCONNECT console** | https://awspoc.iotconnect.io — the full platform (dashboards, models, files) |
| **Your board's claim page** | `http://imx95-XXXX.local:8088` — printed on the card next to your board |
| **Your board's LLM shootout** (local) | `http://imx95-XXXX.local:8090` |
| **Your board's camera stream** (local) | `https://imx95-XXXX.local:8080/live` |
| Demo source + docs | https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/tree/main/nxp-frdm-imx-95/genai-flow-demo |
| /IOTCONNECT REST API reference | https://docs.iotconnect.io/iotconnect/rest-api/ |
| NXP eIQ GenAI Flow | https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator |

## 2. Getting started (about 5 minutes)

1. **Sign up** on the portal with your name, email, company and the **attendee code**. Your private
   /IOTCONNECT space is created instantly.
2. **Check your email** — /IOTCONNECT sends a welcome message with a **temporary password**. Sign in at the
   console and set a real one.
3. **Download your board kit** (.zip) from the portal page. It contains your device identity:
   `iotcDeviceConfig.json`, `device-cert.pem`, `device-pkey.pem`.
4. **Claim your board**: open the URL on your board's card and **drag the kit zip onto the page**. The board
   installs the identity, restarts the demo and reports **✓ Connected** within a minute.
5. **Open your cockpit** and start asking your board questions.

## 3. What you can do

**Ask the board** — three different on-device models:
- **LLM** — a language model running on the CPU, the Neutron NPU, or the Ara240 NPU if your board has one.
- **Agent** — the LLM plus real tools: it answers from *actual board data* (time, temperature, memory,
  storage, uptime, USB devices) instead of guessing.
- **VLM** — a vision-language model that describes what the camera sees.

**Model shootout** — the centrepiece. Pick several engines, give them one prompt, and the cockpit runs it
across all of them on your board, reporting **load time, time-to-first-token, generation time, tokens/sec and
token count**, with each model's verbatim answer. This is the honest way to see what quantization, an NPU, or
a bigger model actually buys you.

**RAG (retrieval-augmented generation)** — teach your board about *your* documents:
- Drop a **PDF, .txt, .md, .csv, .json or .log** on the cockpit, or paste a **web page URL**.
- The document is converted to text in the cloud, then **chunked and embedded on your board**.
- Turn **RAG on** and the board answers from your documents instead of its general knowledge.
- **View** any document's chunks to see exactly what was indexed, and **remove** documents you no longer want.
- Indexing takes ~2 minutes: the whole database is re-embedded each time, and GenAI Flow ships a large
  built-in corpus (~959 chunks) that dominates that time.

**Voice assistant** — start it from the cockpit, then say **"Hey NXP"** and ask a question out loud. Wake word,
speech recognition, the language model and speech synthesis all run on the board.

**Deploy a model** — in the /IOTCONNECT console under **My Models**, upload a model and **push** it to your
device. The board downloads, installs and serves it automatically. (This is deliberately done in the console
so you see the real platform workflow.)

**Benchmark** — run GenAI Flow's own benchmark and watch the numbers land as telemetry.

## 4. What /IOTCONNECT is doing behind the scenes

Everything in this workshop is built on the **/IOTCONNECT REST API**. Here is the full list of platform
capabilities in play — useful if you are evaluating the platform for your own product.

| Platform capability | Where you see it | API area |
|---|---|---|
| **Authentication** — solution key → basic token → bearer token, per user | Signing into the cockpit | `Auth/basic-token`, `Auth/login` |
| **Entity (tenant) creation** — every attendee gets an isolated sub-entity | Your private space | `Entity` |
| **User creation & invitation** — account provisioned with role, timezone, and a welcome email | Your welcome email | `User` (+ `sendInvitationEmail`) |
| **Role-based access** — you are an Admin *of your entity only* | You only ever see your own board | `Role/lookup` |
| **Device templates** — the attribute + command contract for the device type | Every telemetry field and button | `device-template`, `template-attribute`, `template-command` |
| **Device creation with x509 identity** — self-signed certificate registered per board | Your board kit | `Device`, `certificateText` |
| **Device provisioning / discovery** — the board finds its broker and identity at boot | Your board connecting | discovery + `device-identity` |
| **Telemetry ingestion (D2C)** — the board publishes ~50 attributes every 10 s over MQTT | Gauges, model stats, RAG status | `Telemetry/device/{guid}` |
| **Latest-value + historical telemetry** | Cockpit gauges; console charts | `Telemetry`, `attribute-history` |
| **Commands (C2D)** — every button sends a real cloud-to-device command | Ask, set-model, voice, RAG | `template-command/device/{guid}/send` |
| **Command acknowledgements** — the board reports success/failure back | Activity log entries | ACK on each command |
| **File storage & model deployment (OTA)** — upload a model, push it to devices | My Models → Push | `Module`, `Module/push`, `File` |
| **Module commands** — the model push arrives as a typed message with a presigned download URL | `model_deploy_status` on the board | C2D module command (`ct:2`) |
| **Device lookup / fleet queries** — enumerate devices in an entity | Cockpit finding your board | `Device/lookup` |

Two things worth calling out:

- **Isolation is enforced by the platform, not by the workshop UI.** The cockpit signs in *as you* and uses
  *your* token for every call. A user in one entity cannot see or command another entity's devices — the same
  mechanism that separates customers in a production deployment.
- **The board is a normal /IOTCONNECT device.** Nothing about it is workshop-specific: the same template,
  telemetry, commands and OTA mechanisms are what you would use for a fleet of thousands.

## 5. If you keep the board

Your entity, user account and device stay live after the workshop, so the board keeps working —
plug it into any network with internet access and it reconnects on its own. Useful next steps:

- The demo, its install script and all documentation are in the
  [public repository](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/tree/main/nxp-frdm-imx-95/genai-flow-demo)
  — including the [benchmarks](BENCHMARKS.md) and the [model catalog](../MODELS.md).
- The board's identity lives in `/opt/demo/` (`iotcDeviceConfig.json` + the two `.pem` files). Keep your kit
  zip if you ever reflash.
- To point the board at your **own** /IOTCONNECT account later, create a device there and swap those three
  files.
- The board is a standard NXP FRDM i.MX 95 — you can wipe it and use it for anything else.

## 6. If you hand the board back

Nothing to do — the host will re-claim it for the next attendee, which replaces the device identity. Your
account, your entity and your RAG documents remain yours in /IOTCONNECT; only the hardware moves on. If you
want a clean slate, remove your documents from the RAG database first (each row has a **remove** button).

## 7. Troubleshooting

| Symptom | What to do |
|---|---|
| Board URL doesn't resolve | The venue may block mDNS — ask the host for the board's IP address |
| Claim page says "already claimed" | You are at the wrong board, or re-claiming your own — check the card, then tick the confirmation box |
| First LLM answer is slow (~1 min) | Normal: the model loads on first use, then stays warm |
| "I'm unable to assist you with this topic" | RAG is on and the question is outside the indexed documents — turn RAG off, or ask about your documents |
| Ara240 buttons are greyed out | Your board has no Ara240 module fitted — CPU and Neutron still work |
| Cockpit shows "stale" | The board lost its network or power — check the board, then reload |

Questions during the workshop: ask your host. Afterwards: open an issue on the
[demo repository](https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/issues).
