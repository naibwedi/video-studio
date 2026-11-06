"""`studio teaser`: cut a ~50 s teaser from a finished video (with its subtitles and sound), cross-faded.

Segments default to: the start of the first verse (with a short lead-in), two spots further in, and the closing end card.
Set your own in project.json:  "teaser": {"segments": [[17, 31], [70, 84], [110, 122.6]]}  or pass --segments 17-31,70-84
"""
import os, subprocess
from . import paths, render

X = 0.6   # cross-fade seconds


def auto_segments(p):
    lines = p["subtitles"]["lines"]
    dur = p["duration"]
    if not lines:
        return [[0, min(14, dur)], [dur * 0.45, dur * 0.45 + 12], [max(0, dur - 12), dur]]
    n = len(lines)
    segs = [[max(0.0, float(lines[0]["start"]) - 5), float(lines[0]["start"]) + 9]]
    for i in (n // 3, (2 * n) // 3):
        if i > 0:
            a = float(lines[i]["start"]) - 0.3
            segs.append([a, min(a + 12, dur)])
    segs.append([max(0.0, dur - 12), dur])
    return segs


def parse_segments(text):
    return [[float(x) for x in part.split("-")] for part in text.split(",")]


def build(p, size, segments=None, preview=False):
    segments = segments or (p.get("teaser") or {}).get("segments") or auto_segments(p)
    tag = "_preview" if preview else ""
    src = render.output_path(p, size, "full", preview)
    if not os.path.exists(src):
        src = render.build(p, size, "full", preview=preview)
    lens = [b - a for a, b in segments]
    n = len(segments)
    fx = []
    for i, (a, b) in enumerate(segments):
        fx.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,fps={p['fps']}[v{i}]")
        fx.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    cur_v, cur_a, acc = "v0", "a0", lens[0]
    for i in range(1, n):
        fx.append(f"[{cur_v}][v{i}]xfade=transition=fade:duration={X}:offset={acc - X:.3f}[xv{i}]")
        fx.append(f"[{cur_a}][a{i}]acrossfade=d={X}[xa{i}]")
        cur_v, cur_a = f"xv{i}", f"xa{i}"
        acc = acc + lens[i] - X
    fx.append(f"[{cur_v}]fade=t=in:st=0:d=0.6,fade=t=out:st={acc - 1.2:.2f}:d=1.2[vout]")
    fx.append(f"[{cur_a}]afade=t=in:st=0:d=0.4,afade=t=out:st={acc - 1.5:.2f}:d=1.5[aout]")
    out = os.path.join(paths.EXPORTS, p["_name"], f"{p['_name']}_teaser_{size}{tag}.mp4")
    bdir = os.path.join(p["_dir"], "build")
    os.makedirs(bdir, exist_ok=True)
    script = os.path.join(bdir, f"teaser_filter_{size}.txt")
    open(script, "w", encoding="utf-8").write(";\n".join(fx))
    render.run(["-i", paths.rel(src), "-/filter_complex", paths.rel(script), "-map", "[vout]", "-map", "[aout]"] +
               render.vcodec("preview" if preview else "final") +
               ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", paths.rel(out)])
    print(f"  wrote {paths.rel(out)}  ({acc:.1f}s, {n} segments: " + ", ".join(f"{a:.0f}-{b:.0f}" for a, b in segments) + ")")
    return out
