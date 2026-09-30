# RZ/G3E EVK — Vision Demo Walkthrough

What runs on the board, what the audience sees, and a suggested script.

## 1. The experience at a glance

Two USB cameras feed two vision pipelines on the four Cortex-A55 cores of the Renesas
RZ/G3E. Every identity, count and metric flows through **/IOTCONNECT** over MQTT, and every
knob is a cloud command. Everything is watchable live in a browser at
`http://<board-ip>:8080/` — no HDMI monitor.

| Pipeline | Camera 1: face identity | Camera 2: occupancy |
|---|---|---|
| Models | YuNet face detector + SFace face recogniser | NanoDet-Plus-m person detector + centroid tracker |
| Runtime | OpenCV DNN, CPU | OpenCV DNN, CPU |
| Model size | 0.2 MB + 37 MB | 3.6 MB |
| Measured on this board, both pipelines running | ~55–70 ms per frame incl. recognition, capped at 8 fps | ~350 ms per frame, ~2.7 fps |
| Measured with only that pipeline running | ~24 ms per frame | ~260 ms per frame, ~3.8 fps |
| Cloud story | enrol from the cloud, unknown-person rule | live occupancy, entries/exits, dwell |

The punchline: **the same edge-to-cloud framework as the RZ/V2H AI demo, on the CPU-only
RZ/G3E — practical analytics with zero accelerator and zero extra runtime**, plus the honest
inference-time numbers that show where an accelerator would take you.

## 2. Suggested script (10 minutes)

1. **Open the page.** Browser on `http://<board-ip>:8080/`. Two live feeds, status strip
   on top: cloud connected, cameras detected, CPU load and temperature.

2. **Walk in front of camera 1.** Red box, `unknown`. On the /IOTCONNECT dashboard
   `identities` reads *unknown* and `unknown_present` goes true. If a rule is set up, the
   notification arrives now. *"The board has never seen me."*

3. **Enrol from the cloud.** Send `enroll <your name>` from the device's Command tab. The
   box turns yellow with a `enrolling 3/5` counter, the ack comes back with
   *enrolled &lt;name&gt; (5 samples)*. Step out and back in: green box with your name and
   the match score; the dashboard shows `identities = <name>`, `unknown_present` false.
   *"No model was retrained, nothing left the board — the cloud just told the device who
   I am."* Show `/gallery` for the stored thumbnail.

4. **Bring in a second person** (or hold up a phone photo): one green, one red, dashboard
   shows *&lt;name&gt;, unknown*. `forget <name>` puts you back to red.

5. **Camera 2: occupancy.** Walk through the highlighted zone. Boxes with track IDs, a
   dwell timer while inside, `in`/`out` counters in the header. On the dashboard
   `zone_count`, `entries_total`, `exits_total`, `dwell_max_s` move within one 5-second
   sample. Send `set_zone 0,0,0.5,1` to move the zone to the left half of the frame live.

6. **The CPU story.** Point at `det_infer_ms` (~350 ms) next to `face_infer_ms` (~60 ms)
   and `cpu_percent` (~80% with both running). Send `set_mode occupancy` — the detector
   speeds up to ~260 ms; `set_mode faces` drops face time to ~24 ms. `set_mode both`
   to restore. *"This is the CPU tier. The RZ/V2H demo runs a 188 MB YOLOv3 at camera
   rate on its DRP-AI with the CPUs idle — same framework, same dashboard, different
   silicon."*

7. **Close on the plumbing.** Cameras hot-plug (unplug one: both pipelines share the other;
   plug it back: they split again). Settings persist across reboots. `file-download <url>`
   updates the whole demo over the air.

## 3. Dashboard suggestions

* Text tile: `identities` (large font). Boolean indicator: `unknown_present`.
* Gauges: `zone_count`, `dwell_max_s`. Counters: `entries_total`, `exits_total`.
* Line chart: `face_infer_ms` and `det_infer_ms` on one axis, `cpu_percent` on another.
* Rule: `unknown_present == true` → email/SMS. Rule: `zone_count > 2` → "queue forming".

## 4. Things that go wrong in a live demo

* **Lighting.** Enrol in the room you present in; backlighting kills recognition. Enrol a
  second time (samples accumulate) if the first match score sits near the 0.36 threshold.
* **Camera order.** First camera by USB port is faces. `swap_cameras` if they are reversed.
* **Occupancy needs bodies, not heads.** Give camera 2 a wide, slightly elevated view.
  A webcam on a laptop lid pointed at a doorway works well.
* **Both pipelines on one camera** is fine for a table-top demo — plug in one camera and
  both feeds show the same view with different annotations.
