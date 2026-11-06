"""`studio thumb`: YouTube thumbnails (1280x720) from frames of the finished video + the title."""
import os, subprocess
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from . import overlays, paths

GOLD = (233, 190, 92)


def source_video(name, preview=False):
    d = os.path.join(paths.EXPORTS, name)
    order = ["16x9_VIDEO_only", "16x9_nosubs", "16x9"]
    for tag in order:
        f = os.path.join(d, f"{name}_{tag}" + ("_preview" if preview else "") + ".mp4")
        if os.path.exists(f):
            return f, tag == "16x9"      # last one has subtitles burned in
    return None, False


def frame(video, t, out):
    subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{t}", "-i", video, "-frames:v", "1",
                    "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720", out], check=True)


def make(p, t, text, sub, out, video):
    tmp = os.path.join(paths.CACHE, "_thumb_frame.png")
    os.makedirs(paths.CACHE, exist_ok=True)
    frame(video, t, tmp)
    im = Image.open(tmp).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = ImageEnhance.Color(im).enhance(1.1)
    # dark gradient from the bottom so the title is readable on any picture
    grad = Image.new("L", (1, 720))
    for y in range(720):
        grad.putpixel((0, y), int(215 * max(0.0, (y - 250) / 470) ** 1.4))
    shade = Image.new("RGB", (1280, 720), (0, 0, 0))
    im = Image.composite(shade, im, grad.resize((1280, 720)))
    d = ImageDraw.Draw(im, "RGBA")
    size = 170
    f = overlays.font(size)
    while d.textlength(text, font=f) > 1180 and size > 60:
        size -= 6
        f = overlays.font(size)
    d.text((60, 700 - size - (78 if sub else 30)), text, font=f, fill=GOLD + (255,), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    if sub:
        d.text((66, 700 - 62), sub, font=overlays.font(44), fill=(245, 235, 208, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    logo = overlays.round_logo(overlays.paths_file(p, p["overlays"]["logo"]["image"]), 130)
    im = im.convert("RGBA")
    im.alpha_composite(logo, (1280 - 130 - 36, 36))
    im.convert("RGB").save(out, quality=94)
    return out


def run(p, times=None, text=None, sub=None, preview=False):
    video, subs = source_video(p["_name"], preview)
    if not video:
        raise SystemExit("Build a video first:  studio build <project> --size 16x9 --variant video_only")
    if subs:
        print("note: the only 16:9 video has subtitles burned in; build --variant video_only for cleaner thumbnails")
    lines = p["subtitles"]["lines"]
    lo = float(lines[0]["start"]) if lines else 5.0
    hi = float(lines[-1]["end"]) if lines else p["duration"] - 5
    times = times or [round(lo + (hi - lo) * f, 1) for f in (0.15, 0.5, 0.85)]
    text = text if text is not None else (p.get("title") or p["_name"])
    sub = sub if sub is not None else p["channel"]["name"]
    outs = []
    for t in times:
        out = os.path.join(paths.EXPORTS, p["_name"], f"{p['_name']}_thumb_{t}s.png")
        outs.append(make(p, t, text, sub, out, video))
        print("  wrote", paths.rel(out))
    return outs
