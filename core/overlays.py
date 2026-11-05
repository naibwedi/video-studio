"""Subtitles (.srt/.ass) and the picture overlays: corner logo, title card, end card."""
import os
from PIL import Image, ImageDraw, ImageFont
from . import paths

GOLD = (233, 190, 92, 255)
CREAM = (245, 235, 208, 255)


def ts(sec, srt=True):
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",") if srt else f"{h}:{m:02d}:{s:05.2f}"


def write_srt(p, path):
    lines, pad = p["subtitles"]["lines"], p["subtitles"]["pad"]
    open(path, "w", encoding="utf-8").write("\n".join(
        f"{i}\n{ts(l['start'] + pad)} --> {ts(l['end'] - pad)}\n{l['text']}\n" for i, l in enumerate(lines, 1)))


def write_ass(p, size_name, W, H, path):
    sub = p["subtitles"]
    fs, mv, pad = sub["size"][size_name], sub["margin_v"][size_name], sub["pad"]
    ass = ["[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\n" % (W, H),
           "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
           "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
           f"Style: Lyric,{sub['font']},{fs},&H00F5F5F5,&H00F5F5F5,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,60,60,{mv},1\n",
           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
    ass += [f"Dialogue: 0,{ts(l['start'] + pad, False)},{ts(l['end'] - pad, False)},Lyric,,0,0,0,,{{\\fad(250,250)}}{l['text']}"
            for l in sub["lines"]]
    open(path, "w", encoding="utf-8").write("\n".join(ass))


def font(size, bold=True, serif=False):
    name = "georgia.ttf" if serif else ("ebrimabd.ttf" if bold else "ebrima.ttf")
    try:
        return ImageFont.truetype(os.path.join(paths.FONTS_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def round_logo(path, size):
    logo = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    logo.putalpha(mask.resize((size, size), Image.LANCZOS))
    return logo


def centered(d, W, y, text, f, fill):
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x + 3, y + 3), text, font=f, fill=(0, 0, 0, 200))
    d.text((x, y), text, font=f, fill=fill)


def make_logo(p, W, H, vertical, path):
    cfg = p["overlays"]["logo"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    size = 150 if vertical else 130
    lg = round_logo(paths_file(p, cfg["image"]), size)
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * 0.78)))
    img.alpha_composite(lg, (45, 140) if vertical else (W - size - 45, 38))
    img.save(path)


def make_title(p, W, H, vertical, path):
    cfg = p["overlays"]["title_card"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle((0, H * 0.36, W, H * 0.64), fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, band)
    d = ImageDraw.Draw(img)
    ty = H * (0.43 if vertical else 0.42)
    centered(d, W, ty, cfg["text"], font(130 if vertical else 150), GOLD)
    if cfg.get("subtitle"):
        centered(d, W, ty + (170 if vertical else 190), cfg["subtitle"], font(42 if vertical else 46), CREAM)
    img.save(path)


def make_end(p, W, H, vertical, path):
    cfg = p["overlays"]["end_card"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    d = ImageDraw.Draw(img)
    ls = 300 if vertical else 240
    top = int(H * (0.25 if vertical else 0.16))
    img.alpha_composite(round_logo(paths_file(p, cfg.get("logo", p["overlays"]["logo"]["image"])), ls), ((W - ls) // 2, top))
    y0 = top + ls + 40
    centered(d, W, y0, cfg["title"], font(96 if vertical else 90), GOLD)
    centered(d, W, y0 + 130, cfg["handle"], font(54 if vertical else 50), GOLD)
    if cfg.get("tagline"):
        centered(d, W, y0 + 210, cfg["tagline"], font(36 if vertical else 34, serif=True), (245, 232, 200, 255))
    img.save(path)


def paths_file(p, ref):
    for base in (p["_dir"], paths.ROOT):
        cand = os.path.join(base, ref)
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(ref)
