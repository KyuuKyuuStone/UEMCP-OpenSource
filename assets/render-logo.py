#!/usr/bin/env python3
"""Render the UEMCP brand PNGs from the same vector geometry as the SVGs.

The mark is a U-shaped bridge: two port nodes at the top, one curved span, and
a diamond gateway node where the span bottoms out.  The wordmark is a monoline
"UEMCP" built from the same stroke weight family.

Everything is drawn at 4x and downsampled with LANCZOS, so the PNGs stay crisp
at every size.  Coordinates here mirror the numbers in logo.svg,
logo-mark.svg and logo-on-dark.svg (512 x 512 design grid).

Usage:
    python assets/render-logo.py
    python assets/render-logo.py --out-dir assets

Requires Pillow (only third-party dependency, and only for this script).
"""

import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Brand palette
# --------------------------------------------------------------------------
INK = "#0B1220"
PAPER = "#F7F9FC"
ACCENT = "#22D3EE"
ACCENT_DEEP = "#0891B2"
SLATE = "#7C8CA6"
NIGHT = "#0B1220"

DESIGN = 512
SUPERSAMPLE = 4

# --------------------------------------------------------------------------
# Geometry (512 x 512 design grid)
# --------------------------------------------------------------------------
MARK_STROKE = 40.0
PORT_RADIUS = 40.0
PORT_LEFT = (150.0, 94.0)
PORT_RIGHT = (362.0, 94.0)
SPAN_CENTER = (256.0, 214.0)
SPAN_RADIUS = 106.0
DIAMOND_CENTER = (256.0, 320.0)
DIAMOND_HALF = 36.0

WORD_STROKE = 22.0
WORD_TOP = 402.0
WORD_BOTTOM = 460.0
LETTER_W = 48.0
LETTER_X = [90.0, 164.0, 238.0, 312.0, 386.0]

DESIGN_TOP = PORT_LEFT[1] - PORT_RADIUS
DESIGN_BOTTOM = WORD_BOTTOM + WORD_STROKE / 2.0


def _arc(cx, cy, radius, start_deg, end_deg, steps=96):
    points = []
    for index in range(steps + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * index / steps)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def u_span():
    """Left port -> down -> bottom semicircle -> up -> right port."""
    points = [PORT_LEFT, (PORT_LEFT[0], SPAN_CENTER[1])]
    points += _arc(SPAN_CENTER[0], SPAN_CENTER[1], SPAN_RADIUS, 180.0, 0.0)
    points += [(PORT_RIGHT[0], SPAN_CENTER[1]), PORT_RIGHT]
    return points


def wordmark_paths():
    """Five monoline letters on the 512 grid, centred at x=256."""
    top, bottom = WORD_TOP, WORD_BOTTOM
    paths = []

    # U
    x = LETTER_X[0]
    radius = LETTER_W / 2.0
    paths.append([(x, top), (x, bottom - radius)])
    paths.append(_arc(x + radius, bottom - radius, radius, 180.0, 0.0, 48))
    paths.append([(x + LETTER_W, bottom - radius), (x + LETTER_W, top)])

    # E
    x = LETTER_X[1]
    paths.append([(x + LETTER_W, top), (x, top), (x, bottom), (x + LETTER_W, bottom)])
    paths.append([(x, (top + bottom) / 2.0), (x + LETTER_W - 6, (top + bottom) / 2.0)])

    # M
    x = LETTER_X[2]
    paths.append([
        (x, bottom), (x, top),
        (x + LETTER_W / 2.0, bottom - 24),
        (x + LETTER_W, top), (x + LETTER_W, bottom),
    ])

    # C (open to the right)
    x = LETTER_X[3]
    radius = (bottom - top) / 2.0
    center_y = (top + bottom) / 2.0
    paths.append(_arc(x + radius, center_y, radius, -49.2, -310.8, 96))

    # P (narrower bowl)
    x = LETTER_X[4]
    bowl_w = 40.0
    bowl_h = 34.0
    bowl_r = bowl_h / 2.0
    bowl_y = top + bowl_h / 2.0
    paths.append([(x, bottom), (x, top), (x + bowl_w - bowl_r, top)]
                 + _arc(x + bowl_w - bowl_r, bowl_y, bowl_r, -90.0, 90.0, 32)
                 + [(x, top + bowl_h)])
    return paths


def _stroke(draw, points, color, width):
    """Round-cap, round-join stroke drawn by stamping discs along the path.

    Pillow's wide-line joints leave spokes on long curves, so the path is
    resampled and stamped instead; this also matches SVG round joins exactly.
    """
    if len(points) < 2:
        return
    radius = width / 2.0
    step = max(0.6, width / 6.0)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        distance = math.hypot(x1 - x0, y1 - y0)
        count = max(1, int(distance / step))
        for index in range(count + 1):
            t = index / float(count)
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)


def _diamond(draw, center, half, color):
    cx, cy = center
    draw.polygon(
        [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)],
        fill=color,
    )


def draw_logo(image, offset, scale, palette, wordmark=True):
    draw = ImageDraw.Draw(image)
    ox, oy = offset
    stroke = MARK_STROKE * scale
    span = [(ox + x * scale, oy + y * scale) for x, y in u_span()]
    _stroke(draw, span, palette["mark"], stroke)
    for port in (PORT_LEFT, PORT_RIGHT):
        cx, cy = ox + port[0] * scale, oy + port[1] * scale
        r = PORT_RADIUS * scale
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=palette["mark"])
    _diamond(
        draw,
        (ox + DIAMOND_CENTER[0] * scale, oy + DIAMOND_CENTER[1] * scale),
        DIAMOND_HALF * scale,
        palette["accent"],
    )
    if wordmark:
        for path in wordmark_paths():
            scaled = [(ox + x * scale, oy + y * scale) for x, y in path]
            _stroke(draw, scaled, palette["word"], WORD_STROKE * scale)


def _canvas(size):
    return Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))


def _downsample(image, size):
    return image.resize((size, size), Image.LANCZOS)


def render_logo(size, palette, wordmark=True):
    big = _canvas(size)
    scale = (size * SUPERSAMPLE) / float(DESIGN)
    draw_logo(big, (0.0, 0.0), scale, palette, wordmark=wordmark)
    return _downsample(big, size)


# --------------------------------------------------------------------------
# Social preview (1280 x 640)
# --------------------------------------------------------------------------
SOCIAL_W, SOCIAL_H = 1280, 640


def _font(size, bold=False):
    candidates = []
    if bold:
        candidates += ["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
    else:
        candidates += ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _centered(draw, text, font, y, fill, width=SOCIAL_W):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (right - left)) / 2.0 - left, y - top), text, font=font, fill=fill)


def render_social(path):
    scale_factor = SUPERSAMPLE // 2  # 2x is enough for 1280 px
    width, height = SOCIAL_W * scale_factor, SOCIAL_H * scale_factor
    image = Image.new("RGBA", (width, height), NIGHT)
    draw = ImageDraw.Draw(image)

    # Gradient wash: a soft accent glow behind the logo.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.33)
    for step in range(10, 0, -1):
        radius = int(width * 0.055 * step)
        alpha = max(0, 10 - step) * 2
        glow_draw.ellipse(
            [cx - radius, cy - radius * 0.6, cx + radius, cy + radius * 0.6],
            fill=(34, 211, 238, alpha),
        )
    image = Image.alpha_composite(image, glow)
    draw = ImageDraw.Draw(image)

    # Logo lockup, vertically centred around 33% of the canvas height.
    scale = 0.58 * scale_factor
    ox = width / 2.0 - 256.0 * scale
    oy = height * 0.335 - ((DESIGN_TOP + DESIGN_BOTTOM) / 2.0) * scale
    draw_logo(image, (ox, oy), scale, {"mark": PAPER, "word": PAPER, "accent": ACCENT})

    rule_w = int(64 * scale_factor)
    rule_y = int(height * 0.635)
    draw.rounded_rectangle(
        [width // 2 - rule_w // 2, rule_y, width // 2 + rule_w // 2, rule_y + int(4 * scale_factor)],
        radius=int(2 * scale_factor),
        fill=ACCENT,
    )

    headline_font = _font(int(38 * scale_factor), bold=True)
    sub_font = _font(int(23 * scale_factor), bold=False)
    url_font = _font(int(19 * scale_factor), bold=False)
    _centered(draw, "Client-agnostic MCP gateway for editor automation",
              headline_font, int(height * 0.685), PAPER, width=width)
    _centered(draw, "Pure Python bridge  ·  no C++ build  ·  loopback only",
              sub_font, int(height * 0.785), SLATE, width=width)
    _centered(draw, "github.com/KyuuKyuuStone/UEMCP-OpenSource",
              url_font, int(height * 0.92), "#4B5B73", width=width)

    image = image.resize((SOCIAL_W, SOCIAL_H), Image.LANCZOS)
    image.convert("RGB").save(path, "PNG", optimize=True)


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Render UEMCP brand PNGs")
    parser.add_argument("--out-dir", default=os.path.dirname(os.path.abspath(__file__)))
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    light = {"mark": INK, "word": INK, "accent": ACCENT_DEEP}
    dark = {"mark": PAPER, "word": PAPER, "accent": ACCENT}

    render_logo(DESIGN, light).save(os.path.join(out_dir, "logo-512.png"), "PNG", optimize=True)
    render_logo(128, light).save(os.path.join(out_dir, "logo-128.png"), "PNG", optimize=True)
    render_social(os.path.join(out_dir, "social-preview.png"))

    for name in ("logo-512.png", "logo-128.png", "social-preview.png"):
        path = os.path.join(out_dir, name)
        with Image.open(path) as check:
            print("%s  %dx%d %s  %d bytes" % (name, check.width, check.height, check.format, os.path.getsize(path)))


if __name__ == "__main__":
    main()
