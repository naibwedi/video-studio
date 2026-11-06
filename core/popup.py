"""Animated subscribe pop-up made with Pillow + an ffmpeg overlay expression (no Remotion needed).

The card slides in from the left, waits, the button 'clicks' (turns into SUBSCRIBED), then it slides out.
Text comes from project.json, so it works for any channel, title or language.
"""
import os
from PIL import Image, ImageDraw
from . import overlays

IN, OUT = 0.55, 0.45   # slide-in / slide-out seconds


def _bell(d, cx, cy, s, fill):
    d.polygon([(cx - s, cy + s * 0.55), (cx - s * 0.7, cy + s * 0.55), (cx - s * 0.7, cy - s * 0.1), (cx - s * 0.35, cy - s * 0.75),
               (cx + s * 0.35, cy - s * 0.75), (cx + s * 0.7, cy - s * 0.1), (cx + s * 0.7, cy + s * 0.55), (cx + s, cy + s * 0.55),
               (cx + s, cy + s * 0.75), (cx - s, cy + s * 0.75)], fill=fill)
    d.ellipse((cx - s * 0.25, cy + s * 0.8, cx + s * 0.25, cy + s * 1.2), fill=fill)


def card(p, cfg, vertical, subscribed):
    """RGBA image of the card, in one of its two states."""
    sc = 1.15 if vertical else 1.0
    cw, ch = int(820 * sc), int(290 * sc)
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(28 * sc), fill=(8, 14, 36, 215), outline=overlays.GOLD[:3] + (150,), width=3)
    ls = int(104 * sc)
    logo = overlays.round_logo(overlays.paths_file(p, p["overlays"]["logo"]["image"]), ls)
    img.alpha_composite(logo, (int(26 * sc), int(24 * sc)))
    x = int(26 * sc) + ls + int(22 * sc)
    d.text((x, int(28 * sc)), cfg["handle"], font=overlays.font(int(38 * sc)), fill=overlays.GOLD)
    d.text((x, int(82 * sc)), cfg["tagline"], font=overlays.font(int(27 * sc), bold=False), fill=overlays.CREAM)
    # button + bell
    bx, by, bh = int(26 * sc), int(158 * sc), int(92 * sc)
    label = "SUBSCRIBED" if subscribed else "SUBSCRIBE"
    bf = overlays.font(int(36 * sc), serif=False)
    bw = int(d.textlength(label, font=bf)) + int(110 * sc)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=bh // 2, fill=(130, 100, 100, 255) if subscribed else (204, 0, 0, 255))
    tx = bx + int(34 * sc)
    if subscribed:
        cx, cy = bx + int(52 * sc), by + bh // 2
        d.line([(cx - 14 * sc, cy), (cx - 4 * sc, cy + 11 * sc), (cx + 15 * sc, cy - 12 * sc)], fill="white", width=int(7 * sc), joint="curve")
        tx = bx + int(82 * sc)
    d.text((tx, by + bh // 2), label, font=bf, fill="white", anchor="lm")
    gx = bx + bw + int(18 * sc)
    d.ellipse((gx, by, gx + bh, by + bh), fill=(204, 0, 0, 255) if subscribed else (255, 255, 255, 50))
    _bell(d, gx + bh // 2, by + bh // 2 - int(4 * sc), int(17 * sc), "white")
    return img


def normalize(p, popups):
    """Config entries may be plain seconds or objects; return full dicts."""
    base = {"handle": p["channel"]["handle"], "tagline": "Subscribe for more mezmur", "dur": 5.0, "click": 2.6}
    out = []
    for e in popups:
        d = dict(base)
        d.update({"at": float(e)} if isinstance(e, (int, float)) else e)
        out.append(d)
    return out


def make(p, cfg, bdir, tag, vertical, W0, H0, scale):
    """Write the two card PNGs. Returns (path_a, path_b, card_w, card_h, x, y) at output size."""
    paths_out = []
    for sub in (False, True):
        im = card(p, cfg, vertical, sub)
        if scale != 1:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
        path = os.path.join(bdir, f"popup_{tag}_{'b' if sub else 'a'}.png")
        im.save(path)
        paths_out.append(path)
    cw, ch = im.size
    x1 = int((40 if vertical else 60) * scale)
    y = int(950 * scale) if vertical else int((H0 - 250) * scale) - ch
    return paths_out[0], paths_out[1], cw, ch, x1, y


def x_expr(t0, t1, cw, x1):
    """ffmpeg expression for the card's x: eased slide in, hold, eased slide out."""
    return (f"{x1}-({x1}+{cw})*pow(1-clip((t-{t0})/{IN},0,1),3)"
            f"-({x1}+{cw})*pow(clip((t-({t1}-{OUT}))/{OUT},0,1),3)")
