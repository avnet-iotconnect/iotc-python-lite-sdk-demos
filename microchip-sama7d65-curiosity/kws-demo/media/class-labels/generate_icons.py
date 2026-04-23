from __future__ import annotations

import math
import json
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


SIZE = 144
PADDING = 10
RADIUS = 24
ICON_TOP = 18
ICON_BOTTOM = 102
LABEL_TOP = 106

BG_TOP = (18, 30, 38, 255)
BG_BOTTOM = (40, 59, 69, 255)
BORDER = (230, 219, 191, 255)
TEXT = (245, 240, 227, 255)
TEXT_MUTED = (192, 204, 210, 255)
SHADOW = (0, 0, 0, 70)


Entry = dict[str, object]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/bahnschrift.ttf" if not bold else "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/segoeui.ttf" if not bold else "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/verdanab.ttf" if bold else "C:/Windows/Fonts/verdana.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_LABEL = load_font(18, bold=True)
FONT_META = load_font(13, bold=False)
FONT_QUESTION = load_font(44, bold=True)


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def gradient_tile() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        t = y / max(1, SIZE - 1)
        color = tuple(lerp(BG_TOP[i], BG_BOTTOM[i], t) for i in range(4))
        draw.line((0, y, SIZE, y), fill=color)

    vignette = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(56):
        alpha = int(65 * (i / 55))
        inset = i
        vdraw.rounded_rectangle(
            (inset, inset, SIZE - inset - 1, SIZE - inset - 1),
            radius=max(0, RADIUS - inset // 3),
            outline=(0, 0, 0, alpha),
            width=2,
        )
    image.alpha_composite(vignette)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (PADDING, PADDING, SIZE - PADDING, SIZE - PADDING),
        radius=RADIUS,
        fill=255,
    )
    image.putalpha(mask)
    return image


def with_shadow(base: Image.Image) -> Image.Image:
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        (PADDING + 3, PADDING + 5, SIZE - PADDING + 1, SIZE - PADDING + 3),
        radius=RADIUS,
        fill=SHADOW,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))

    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(base)
    return out


def create_canvas(accent: tuple[int, int, int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    tile = gradient_tile()
    draw = ImageDraw.Draw(tile)

    draw.rounded_rectangle(
        (PADDING, PADDING, SIZE - PADDING, SIZE - PADDING),
        radius=RADIUS,
        outline=BORDER,
        width=2,
    )
    draw.rounded_rectangle((PADDING + 8, PADDING + 8, PADDING + 24, PADDING + 24), radius=8, fill=accent)
    draw.line((PADDING + 30, PADDING + 16, SIZE - PADDING - 12, PADDING + 16), fill=(255, 255, 255, 22), width=2)
    draw.rounded_rectangle(
        (PADDING + 8, LABEL_TOP, SIZE - PADDING - 8, SIZE - PADDING - 8),
        radius=14,
        fill=(255, 255, 255, 20),
        outline=(255, 255, 255, 28),
        width=1,
    )
    return with_shadow(tile), ImageDraw.Draw(with_shadow(tile))


def add_label(image: Image.Image, label: str, accent: tuple[int, int, int, int]) -> Image.Image:
    draw = ImageDraw.Draw(image)
    display = label.strip("_").upper() if label.startswith("_") else label.upper()
    bbox = draw.textbbox((0, 0), display, font=FONT_LABEL)
    text_w = bbox[2] - bbox[0]
    draw.text(((SIZE - text_w) / 2, LABEL_TOP + 8 - bbox[1]), display, font=FONT_LABEL, fill=TEXT)

    meta = "VOICE"
    mb = draw.textbbox((0, 0), meta, font=FONT_META)
    mw = mb[2] - mb[0]
    draw.text(((SIZE - mw) / 2, LABEL_TOP - 6 - mb[1]), meta, font=FONT_META, fill=accent)
    return image


def icon_center() -> tuple[float, float]:
    return SIZE / 2.0, (ICON_TOP + ICON_BOTTOM) / 2.0


def draw_arrow(draw: ImageDraw.ImageDraw, direction: str, accent: tuple[int, int, int, int]) -> None:
    cx, cy = icon_center()
    shaft_len = 34
    head = 12
    if direction == "up":
        points = [(cx, cy - shaft_len), (cx + head, cy - shaft_len + head), (cx + 4, cy - shaft_len + head),
                  (cx + 4, cy + shaft_len / 2), (cx - 4, cy + shaft_len / 2), (cx - 4, cy - shaft_len + head),
                  (cx - head, cy - shaft_len + head)]
    elif direction == "down":
        points = [(cx, cy + shaft_len), (cx + head, cy + shaft_len - head), (cx + 4, cy + shaft_len - head),
                  (cx + 4, cy - shaft_len / 2), (cx - 4, cy - shaft_len / 2), (cx - 4, cy + shaft_len - head),
                  (cx - head, cy + shaft_len - head)]
    elif direction == "left":
        points = [(cx - shaft_len, cy), (cx - shaft_len + head, cy - head), (cx - shaft_len + head, cy - 4),
                  (cx + shaft_len / 2, cy - 4), (cx + shaft_len / 2, cy + 4), (cx - shaft_len + head, cy + 4),
                  (cx - shaft_len + head, cy + head)]
    else:
        points = [(cx + shaft_len, cy), (cx + shaft_len - head, cy - head), (cx + shaft_len - head, cy - 4),
                  (cx - shaft_len / 2, cy - 4), (cx - shaft_len / 2, cy + 4), (cx + shaft_len - head, cy + 4),
                  (cx + shaft_len - head, cy + head)]
    draw.polygon(points, fill=accent)


def draw_check(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int]) -> None:
    draw.line((42, 64, 60, 82), fill=accent, width=11, joint="curve")
    draw.line((60, 82, 97, 44), fill=accent, width=11, joint="curve")


def draw_cross(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int]) -> None:
    draw.line((45, 47, 99, 101), fill=accent, width=11)
    draw.line((99, 47, 45, 101), fill=accent, width=11)


def draw_speaker(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int], muted: bool = False) -> None:
    body = [(38, 64), (54, 64), (72, 48), (72, 96), (54, 80), (38, 80)]
    draw.polygon(body, fill=accent)
    if muted:
        draw.line((78, 54, 102, 90), fill=TEXT_MUTED, width=8)
        draw.line((102, 54, 78, 90), fill=TEXT_MUTED, width=8)
    else:
        draw.arc((72, 54, 102, 90), start=300, end=60, fill=TEXT, width=5)
        draw.arc((72, 44, 112, 100), start=300, end=60, fill=(255, 255, 255, 120), width=4)


def draw_question(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int]) -> None:
    bubble = [(36, 42), (108, 42), (108, 84), (78, 84), (64, 96), (62, 84), (36, 84)]
    draw.rounded_rectangle((36, 42, 108, 84), radius=16, outline=accent, width=6)
    draw.polygon([(70, 84), (84, 84), (66, 96)], fill=accent)
    draw.text((57, 34), "?", font=FONT_QUESTION, fill=TEXT)


def draw_power(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int], off: bool = False) -> None:
    draw.arc((43, 38, 101, 96), start=35, end=325, fill=accent, width=9)
    draw.line((72, 28, 72, 62), fill=accent, width=9)
    if off:
        draw.line((44, 96, 101, 39), fill=TEXT_MUTED, width=7)


def draw_stop(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int]) -> None:
    cx, cy = icon_center()
    r = 28
    points = []
    for i in range(8):
        ang = math.radians(22.5 + i * 45)
        points.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(points, fill=accent)
    draw.rectangle((62, 56, 82, 76), fill=BG_TOP)


def draw_go(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int, int]) -> None:
    draw.polygon([(52, 44), (96, 72), (52, 100)], fill=accent)
    draw.rounded_rectangle((44, 40, 104, 104), radius=24, outline=(255, 255, 255, 60), width=2)


def draw_icon(draw: ImageDraw.ImageDraw, label: str, accent: tuple[int, int, int, int]) -> None:
    if label == "_silence_":
        draw_speaker(draw, accent, muted=True)
    elif label == "_unknown_":
        draw_question(draw, accent)
    elif label == "yes":
        draw_check(draw, accent)
    elif label == "no":
        draw_cross(draw, accent)
    elif label in {"up", "down", "left", "right"}:
        draw_arrow(draw, label, accent)
    elif label == "on":
        draw_power(draw, accent, off=False)
    elif label == "off":
        draw_power(draw, accent, off=True)
    elif label == "stop":
        draw_stop(draw, accent)
    elif label == "go":
        draw_go(draw, accent)
    else:
        draw_speaker(draw, accent, muted=False)


ENTRIES: list[Entry] = [
    {"label": "_silence_", "filename": "silence.png", "accent": (148, 170, 178, 255)},
    {"label": "_unknown_", "filename": "unknown.png", "accent": (118, 186, 206, 255)},
    {"label": "yes", "filename": "yes.png", "accent": (102, 214, 152, 255)},
    {"label": "no", "filename": "no.png", "accent": (239, 116, 104, 255)},
    {"label": "up", "filename": "up.png", "accent": (108, 192, 255, 255)},
    {"label": "down", "filename": "down.png", "accent": (255, 176, 92, 255)},
    {"label": "left", "filename": "left.png", "accent": (103, 209, 196, 255)},
    {"label": "right", "filename": "right.png", "accent": (103, 209, 196, 255)},
    {"label": "on", "filename": "on.png", "accent": (112, 226, 145, 255)},
    {"label": "off", "filename": "off.png", "accent": (226, 120, 110, 255)},
    {"label": "stop", "filename": "stop.png", "accent": (247, 134, 76, 255)},
    {"label": "go", "filename": "go.png", "accent": (127, 224, 150, 255)},
]


def render_entry(output_dir: Path, label: str, filename: str, accent: tuple[int, int, int, int]) -> None:
    base = gradient_tile()
    canvas = with_shadow(base)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (PADDING, PADDING, SIZE - PADDING, SIZE - PADDING),
        radius=RADIUS,
        outline=BORDER,
        width=2,
    )
    draw.rounded_rectangle((PADDING + 8, PADDING + 8, PADDING + 24, PADDING + 24), radius=8, fill=accent)
    draw.line((PADDING + 30, PADDING + 16, SIZE - PADDING - 12, PADDING + 16), fill=(255, 255, 255, 22), width=2)
    draw.rounded_rectangle(
        (PADDING + 8, LABEL_TOP, SIZE - PADDING - 8, SIZE - PADDING - 8),
        radius=14,
        fill=(255, 255, 255, 20),
        outline=(255, 255, 255, 28),
        width=1,
    )
    draw_icon(draw, label, accent)
    add_label(canvas, label, accent)
    canvas.save(output_dir / filename)


def render_preview(output_dir: Path) -> None:
    cols = 4
    rows = math.ceil(len(ENTRIES) / cols)
    gap = 14
    width = cols * SIZE + (cols + 1) * gap
    height = rows * SIZE + (rows + 1) * gap + 52
    image = Image.new("RGBA", (width, height), (12, 20, 24, 255))
    draw = ImageDraw.Draw(image)
    title = "KWS LABEL ICONS"
    title_bbox = draw.textbbox((0, 0), title, font=FONT_LABEL)
    draw.text(((width - (title_bbox[2] - title_bbox[0])) / 2, 14), title, font=FONT_LABEL, fill=TEXT)

    for index, entry in enumerate(ENTRIES):
        col = index % cols
        row = index // cols
        tile = Image.open(output_dir / entry["filename"])
        x = gap + col * (SIZE + gap)
        y = 52 + gap + row * (SIZE + gap)
        image.alpha_composite(tile, (x, y))

    image.save(output_dir / "class-labels-preview.png")


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    for entry in ENTRIES:
        render_entry(output_dir, entry["label"], entry["filename"], entry["accent"])
    render_preview(output_dir)
    manifest = {
        "tile_size_px": SIZE,
        "theme": "signal-deck",
        "labels": [
            {"label": entry["label"], "filename": entry["filename"]}
            for entry in ENTRIES
        ],
        "preview": "class-labels-preview.png",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
