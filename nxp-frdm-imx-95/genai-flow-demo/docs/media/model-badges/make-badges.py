#!/usr/bin/env python3
"""
Render one badge PNG per model-name value, for /IOTCONNECT transformation widgets.

Adds/edits: put a new row in BADGES and re-run. A row is
    (telemetry value, file stem, display name, spec line, accent colour[, muted])
The telemetry value is documentation only - the widget mapping lives in README.md.
`muted` (optional, default False) greys the name too - used for the empty/unknown
states in the "fallback" set, so they read as an absence rather than a model.

Needs Pillow and Chrome (Chrome does the text layout; each size is rendered
natively rather than upscaled, which is what keeps the 256px set sharp).
    python make-badges.py
"""
import os, shutil, subprocess, sys, tempfile
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME_PATH") or next(
    (p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                 "/usr/bin/google-chrome", "/usr/bin/chromium",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
     if os.path.exists(p)), None)

GREEN, BLUE, ARA, ORANGE, PURPLE, TEAL = "#1F9D55", "#2B6CB0", "#6B46C1", "#DD6B20", "#805AD5", "#2C7A7B"
SLATE, MUTED = "#4A5568", "#94A3B8"

# Backend accents deliberately mirror the model accents: a Danube badge (green)
# pairs with neutron (green), a llama.cpp model (blue) with cpu-llama.cpp (blue),
# an Ara model (violet) with ara2 (violet) - the two tiles colour-match on screen.

# Spec lines are sourced from MODELS.md - keep them verifiable, and keep live
# measurements (tokens/sec) off the artwork; the dashboard gauge shows those.
BADGES = {
    "llm": [
        ("danube-500M-q8",               "danube-500M-q8",               "danube-500M-q8",               "500M params \u00b7 8-bit \u00b7 eIQ GenAI Flow",       GREEN),
        ("danube-500M-q4",               "danube-500M-q4",               "danube-500M-q4",               "500M params \u00b7 4-bit \u00b7 eIQ GenAI Flow",       GREEN),
        ("qwen2.5-0.5b-instruct-q8_0",   "qwen2.5-0.5b-instruct-q8_0",   "qwen2.5-0.5b-instruct-q8_0",   "0.5B params \u00b7 8-bit \u00b7 llama.cpp on CPU",      BLUE),
        ("qwen2.5-1.5b-instruct-q4_k_m", "qwen2.5-1.5b-instruct-q4_k_m", "qwen2.5-1.5b-instruct-q4_k_m", "1.5B params \u00b7 4-bit K_M \u00b7 llama.cpp on CPU",  BLUE),
        ("Qwen2.5-7B-Instruct",          "Qwen2.5-7B-Instruct",          "Qwen2.5-7B-Instruct",          "7B params \u00b7 Kinara Ara-2 module",              ARA),
        ("Qwen2.5-Coder-1.5B",           "Qwen2.5-Coder-1.5B",           "Qwen2.5-Coder-1.5B",           "1.5B params \u00b7 Kinara Ara-2 module",            ARA),
        ("Qwen25C15B",                   "Qwen25C15B",                   "Qwen25C15B",                   "1.5B params \u00b7 Ara-2 \u00b7 pushed from IOTCONNECT", ARA),
    ],
    "vlm": [
        ("smolvlm-256M (q8)",   "smolvlm-256M-q8",   "SmolVLM2-256M", "256M params \u00b7 INT8 \u00b7 vision + language", ORANGE),
        ("smolvlm-500M (q8)",   "smolvlm-500M-q8",   "SmolVLM2-500M", "500M params \u00b7 INT8 \u00b7 vision + language", ORANGE),
        ("smolvlm-256M (fp32)", "smolvlm-256M-fp32", "SmolVLM2-256M", "256M params \u00b7 fp32 \u00b7 vision + language", ORANGE),
        ("smolvlm-500M (fp32)", "smolvlm-500M-fp32", "SmolVLM2-500M", "500M params \u00b7 fp32 \u00b7 vision + language", ORANGE),
    ],
    "stt": [
        ("moonshine-tiny",   "moonshine-tiny",   "moonshine-tiny",   "40 MB \u00b7 3.9 s avg \u00b7 fastest",          PURPLE),
        ("moonshine-base",   "moonshine-base",   "moonshine-base",   "84 MB \u00b7 4.2 s avg \u00b7 balanced default", PURPLE),
        ("whisper-small.en", "whisper-small.en", "whisper-small.en", "275 MB \u00b7 5.4 s avg \u00b7 0.00 % WER",      TEAL),
    ],
    "backend": [
        ("cpu",            "cpu",            "CPU",              "6\u00d7 Arm Cortex-A55 \u00b7 eIQ GenAI Flow",       SLATE),
        ("cpu-llama.cpp",  "cpu-llama-cpp",  "CPU \u00b7 llama.cpp",  "6\u00d7 Arm Cortex-A55 \u00b7 GGUF runtime",         BLUE),
        ("neutron",        "neutron",        "eIQ Neutron NPU",  "on-chip NPU \u00b7 i.MX 95",                    GREEN),
        ("ara2",           "ara2",           "Kinara Ara-2",     "Ara240 M.2 module \u00b7 discrete NPU",         ARA),
    ],
    # Shared empty/unknown states - use for any of the four attributes above.
    "fallback": [
        ("(empty)",  "not-loaded",  "No model loaded", "engine idle",                  MUTED, True),
        ("(other)",  "other-model", "Custom model",    "value not in the badge set",   MUTED, True),
    ],
}

SIZES = [512, 256]                                     # width; height is width/4
VARIANTS = {"": ("#243247", "#6B7A8C"),                # light tiles
            "-white": ("#FFFFFF", "#A9B6C4")}          # dark tiles

CARD = """
<div class="badge"><div class="bar" style="background:{accent}"></div>
<div class="txt"><div class="name{dim}">{name}</div><div class="spec">{spec}</div></div></div>"""

PAGE = """<html><head><meta charset="utf-8"><style>
  html,body{{margin:0;padding:0;background:transparent}}
  .badge{{width:{w}px;height:{h}px;display:flex;align-items:center;box-sizing:border-box;
         padding:0 {pad}px;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}}
  .bar{{width:{bar}px;height:{barh}px;border-radius:{barr}px;flex:0 0 auto;margin-right:{gap}px}}
  .txt{{min-width:0}}
  .name{{font-size:{fname}px;font-weight:600;color:{c1};letter-spacing:-0.01em;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.15}}
  .name.dim{{color:{c2};font-weight:500}}
  .spec{{font-size:{fspec}px;font-weight:400;color:{c2};margin-top:{sgap}px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2}}
</style></head><body>{cards}</body></html>"""


def render(kind, rows, width, variant, tmp):
    h, s = width // 4, width / 512.0
    c1, c2 = VARIANTS[variant]
    html = PAGE.format(
        w=width, h=h, pad=int(18 * s), bar=max(3, int(8 * s)), barh=int(66 * s),
        barr=max(2, int(4 * s)), gap=int(16 * s), fname=round(30 * s, 1),
        fspec=round(16.5 * s, 1), sgap=int(5 * s), c1=c1, c2=c2,
        cards="".join(CARD.format(accent=r[4], name=r[2], spec=r[3],
                                  dim=" dim" if len(r) > 5 and r[5] else "")
                      for r in rows))
    hp = os.path.join(tmp, "%s-%d%s.html" % (kind, width, variant))
    pp = os.path.join(tmp, "%s-%d%s.png" % (kind, width, variant))
    with open(hp, "w", encoding="utf-8") as f:
        f.write(html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--default-background-color=00000000", "--screenshot=" + pp,
                    "--window-size=%d,%d" % (width, h * len(rows)),
                    "file:///" + hp.replace("\\", "/")],
                   check=True, capture_output=True, timeout=120)
    sheet = Image.open(pp).convert("RGBA")
    outdir = os.path.join(OUT, kind)
    os.makedirs(outdir, exist_ok=True)
    for i, r in enumerate(rows):
        sheet.crop((0, i * h, width, (i + 1) * h)).save(
            os.path.join(outdir, "%s%s-%d.png" % (r[1], variant, width)))


def main():
    if not CHROME:
        sys.exit("Chrome not found - set CHROME_PATH")
    tmp = tempfile.mkdtemp(prefix="badges-")
    try:
        for kind, rows in BADGES.items():
            for width in SIZES:
                for variant in VARIANTS:
                    render(kind, rows, width, variant, tmp)
            print("ok: %s (%d values)" % (kind, len(rows)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
