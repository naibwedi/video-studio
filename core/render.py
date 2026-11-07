"""Render a project to video.

Two stages, so small edits re-render fast:
  1. every shot is rendered once into its own graded segment and cached in .cache/segments (keyed by what is in it)
  2. a final pass joins the segments with cross-fades, adds logo / title / pop-ups / subtitles and the audio.
Change one shot -> only that segment is rendered again.
"""
import hashlib, json, os, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from . import overlays, paths, popup as popmod
from .project import SIZES

STILL = (".png", ".jpg", ".jpeg", ".webp")
SEG_VERSION = "1"
VARIANTS = ("full", "nosubs", "video_only")


_GPU = None


def gpu_ok():
    """True if this PC can encode H.264 on the NVIDIA GPU (tested once with a tiny clip). STUDIO_ENCODER=cpu|gpu overrides."""
    global _GPU
    forced = os.environ.get("STUDIO_ENCODER", "").lower()
    if forced in ("cpu", "gpu"):
        return forced == "gpu"
    if _GPU is None:
        r = subprocess.run([paths.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                            "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, text=True)
        _GPU = r.returncode == 0
    return _GPU


def vcodec(kind):
    """Encoder arguments. kind: 'segment' (near lossless, cached), 'final', 'preview'."""
    if gpu_ok():
        cq = {"segment": 14, "final": 19, "preview": 30}[kind]
        return ["-c:v", "h264_nvenc", "-preset", "p5" if kind != "preview" else "p1", "-rc", "vbr", "-cq", str(cq),
                "-b:v", "0", "-spatial-aq", "1"]
    cpu = {"segment": ["-preset", "veryfast", "-crf", "14"], "final": ["-preset", os.environ.get("STUDIO_PRESET", "faster"), "-crf", "19"],
           "preview": ["-preset", "ultrafast", "-crf", "28"]}[kind]
    return ["-c:v", "libx264"] + cpu


def run(args):
    subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error"] + args, check=True, cwd=paths.ROOT)


def grade_filter(g):
    parts = [f"eq=contrast={g['contrast']}:saturation={g['saturation']}:brightness={g['brightness']}"]
    if g.get("colorbalance"):
        parts.append("colorbalance=" + g["colorbalance"])
    if g.get("vignette"):
        parts.append("vignette=PI/5")
    if g.get("grain"):
        parts.append(f"noise=alls={g['grain']}:allf=t")
    return ",".join(parts)


def segment(p, shot, L, W, H, vertical):
    """Render (or fetch from cache) one graded shot of length L seconds at W x H."""
    fps, g = p["fps"], p["grade"]
    src = shot["file"]
    st = os.stat(src)
    key = hashlib.sha1(json.dumps([SEG_VERSION, paths.rel(src), st.st_size, int(st.st_mtime), shot["start"], round(L, 3), shot["pan"],
                                   shot["motion"], shot.get("zoom"), W, H, fps, g], sort_keys=True).encode()).hexdigest()[:16]
    out = os.path.join(paths.CACHE, "segments", key + ".mp4")
    if os.path.exists(out):
        return out, True
    os.makedirs(os.path.dirname(out), exist_ok=True)
    still = src.lower().endswith(STILL)
    if still:
        inp = ["-loop", "1", "-t", f"{L:.3f}", "-i", paths.rel(src)]
        pre = f"[0:v]fps={fps},"
    else:
        inp = ["-ss", f"{shot['start']}", "-t", f"{L + 1:.3f}", "-i", paths.rel(src)]
        pre = f"[0:v]fps={fps},trim=duration={L:.3f},setpts=PTS-STARTPTS,"
    pan, motion = shot["pan"], shot["motion"]
    if vertical:
        d = 0.0 if motion == "static" else 0.06
        x = f"(iw-ow)*({pan - d / 2:.3f}+{d}*t/{L:.3f})"
        mv = f"scale=-2:{H}:flags=lanczos,setsar=1,crop={W}:{H}:x='{x}':y=0"
    elif still and motion != "static":
        z0, z1 = shot.get("zoom") or [1.04, 1.14]
        frames = int(L * fps) + 1
        mv = (f"scale=3840:2160:flags=lanczos,setsar=1,zoompan=z='{z0}+({z1}-{z0})*on/{frames}':"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}")
    elif motion == "static":
        mv = f"scale={W}:{H}:flags=lanczos,setsar=1"
    else:   # slow push-in drift
        sx, sy = int(W * 1.06) // 2 * 2, int(H * 1.06) // 2 * 2
        mv = (f"scale={sx}:{sy}:flags=lanczos,setsar=1,crop={W}:{H}:x='(iw-ow)*(0.2+0.6*t/{L:.3f})':"
              f"y='(ih-oh)*(0.3+0.4*t/{L:.3f})'")
    tmp = out + ".tmp.mp4"
    run(inp + ["-filter_complex", f"{pre}{mv},{grade_filter(g)},format=yuv420p[v]", "-map", "[v]", "-an",
               ] + vcodec("segment") + ["-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{L:.3f}", paths.rel(tmp)])
    os.replace(tmp, out)
    return out, False


def output_path(p, size_name, variant, preview):
    tag = {"full": "", "nosubs": "_nosubs", "video_only": "_VIDEO_only"}[variant] + ("_preview" if preview else "")
    d = os.path.join(paths.EXPORTS, p["_name"])
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{p['_name']}_{size_name}{tag}.mp4")


def build(p, size_name, variant="full", preview=False):
    t0 = time.time()
    W0, H0 = SIZES[size_name]
    W, H = (W0 // 2, H0 // 2) if preview else (W0, H0)
    vertical = H0 > W0
    sfx = "v" if vertical else "h"
    fps, X, dur = p["fps"], p["crossfade"], p["duration"]
    shots = p["_shots"]
    if not shots:
        raise SystemExit("This project has no shots yet.")
    bdir = os.path.join(p["_dir"], "build")
    os.makedirs(bdir, exist_ok=True)

    cuts = [s["at"] for s in shots] + [dur]
    cuts[0] = 0.0
    n = len(shots)
    seg_len = [cuts[i + 1] - cuts[i] + (X / 2 if i in (0, n - 1) else X) for i in range(n)] if n > 1 else [dur]
    print(f"{p['_name']} {size_name} {variant}{' (preview)' if preview else ''}: {n} shots, {dur:.1f}s")

    # shots are independent, so render several at once (each goes to its own cache file)
    workers = max(1, min(int(os.environ.get("STUDIO_WORKERS", 3)), os.cpu_count() or 1))
    segs = [None] * n

    def one(i):
        f, cached = segment(p, shots[i], seg_len[i], W, H, vertical)
        segs[i] = f
        print(f"  shot {i + 1:2d}/{n}  {shots[i]['clip']:>10}  {'cached' if cached else 'rendered'}", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, range(n)))

    inputs = []
    for f in segs:
        inputs += ["-i", paths.rel(f)]
    nxt = n
    ov = p["overlays"]
    steps, idx = [], {}

    def add_input(args, name):
        nonlocal nxt
        inputs.extend(args)
        idx[name] = nxt
        nxt += 1

    def png(name, maker):
        path = os.path.join(bdir, f"{name}_{size_name}.png")
        maker(p, W0, H0, vertical, path)
        if preview:
            Image.open(path).resize((W, H), Image.LANCZOS).save(path)
        return paths.rel(path)

    loop = ["-loop", "1", "-t", f"{dur:.3f}", "-i"]
    if ov.get("logo"):
        add_input(loop + [png("logo", overlays.make_logo)], "logo")
    if ov.get("title_card"):
        add_input(loop + [png("title", overlays.make_title)], "title")
    if ov.get("end_card"):
        add_input(loop + [png("end", overlays.make_end)], "end")
    popups = ov.get("popups") or []
    native = ov.get("popup_style", "native") == "native"
    popup_file = os.path.join(paths.LIBRARY, "overlays", f"popup_{sfx}.mov")
    if popups and not native and not os.path.exists(popup_file):
        print(f"  note: {paths.rel(popup_file)} is missing, so the subscribe pop-ups are skipped")
        popups = []
    ov = {**ov, "popups": popups}
    pop_cards = []
    if native:
        scale = W / W0
        for k, cfg in enumerate(popmod.normalize(p, popups)):
            a, b, cw, ch, x1, y = popmod.make(p, cfg, bdir, f"{size_name}{k}", vertical, W0, H0, scale)
            ia, ib = nxt, nxt + 1
            add_input(["-loop", "1", "-t", f"{dur:.3f}", "-i", paths.rel(a)], f"pa{k}")
            add_input(["-loop", "1", "-t", f"{dur:.3f}", "-i", paths.rel(b)], f"pb{k}")
            pop_cards.append((k, cfg, cw, x1, y))
    else:
        for k in range(len(popups)):
            add_input(["-i", paths.rel(popup_file)], f"popup{k}")
    with_audio = variant != "video_only"
    if with_audio:
        add_input(["-i", paths.rel(p["_audio"])], "audio")

    fx = []
    prev = "[0:v]"
    for k in range(1, n):
        fx.append(f"{prev}[{k}:v]xfade=transition={shots[k].get('transition', 'fade')}:duration={X}:offset={cuts[k] - X / 2:.3f}[x{k}]")
        prev = f"[x{k}]"

    layers = []
    if "logo" in idx:
        c = ov["logo"]
        f = f"format=rgba,fade=t=in:st={c['in']}:d=1.0:alpha=1"
        if c.get("out"):
            f += f",fade=t=out:st={c['out']}:d={c.get('fade_out', 0.8)}:alpha=1"
        fx.append(f"[{idx['logo']}:v]{f}[lg]")
        layers.append("lg")
    if "title" in idx:
        c = ov["title_card"]
        fx.append(f"[{idx['title']}:v]format=rgba,fade=t=in:st={c['in']}:d=1.2:alpha=1,"
                  f"fade=t=out:st={c['out'] - 1.5}:d=1.5:alpha=1[tt]")
        layers.append("tt")
    if "end" in idx:
        c = ov["end_card"]
        fx.append(f"[{idx['end']}:v]format=rgba,fade=t=in:st={c['in']}:d=1.8:alpha=1[en]")
        layers.append("en")
    for k, start in enumerate([] if native else popups):
        fx.append(f"[{idx[f'popup{k}']}:v]format=rgba{',scale=%d:%d' % (W, H) if preview else ''},setpts=PTS+{start}/TB[pp{k}]")
        layers.append(f"pp{k}")
    native_layers = []
    for k, cfg, cw, x1, y in pop_cards:
        pa0, pa1 = cfg["at"], cfg["at"] + cfg["dur"]
        xe = popmod.x_expr(pa0, pa1, cw, x1)
        native_layers.append((f"[{idx[f'pa{k}']}:v]", xe, y, f"between(t,{pa0},{pa0 + cfg['click']})"))
        native_layers.append((f"[{idx[f'pb{k}']}:v]", xe, y, f"between(t,{pa0 + cfg['click']},{pa1})"))
    cur = prev
    for j, lay in enumerate(layers):
        nm = f"[o{j}]"
        extra = ":eof_action=pass" if lay.startswith("pp") else ""
        fx.append(f"{cur}[{lay}]overlay=0:0:format=auto{extra}{nm}")
        cur = nm

    for src, xe, y, en in native_layers:
        nm = f"[o{len(layers) + native_layers.index((src, xe, y, en))}]"
        fx.append(f"{cur}{src}overlay=x='{xe}':y={y}:enable='{en}':eval=frame:format=auto{nm}")
        cur = nm

    subs_on = variant == "full" and p["subtitles"]["enabled"] and p["subtitles"]["lines"]
    tail = ""
    if subs_on:
        ass = os.path.join(bdir, f"subs_{size_name}.ass")
        overlays.write_ass(p, size_name, W0, H0, ass)
        tail = f"ass={paths.rel(ass)}:fontsdir='C\\:/Windows/Fonts',"
    fx.append(f"{cur}{tail}fade=t=in:st=0:d={p['fade_in']},fade=t=out:st={dur - p['fade_out']:.2f}:d={p['fade_out']}[vout]")
    if with_audio:
        fx.append(f"[{idx['audio']}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={p['audio_fade_in']},"
                  f"afade=t=out:st={dur - p['audio_fade_out']:.2f}:d={p['audio_fade_out']}[aout]")
    overlays.write_srt(p, os.path.join(bdir, "lyrics.srt"))

    script = os.path.join(bdir, f"filter_{size_name}_{variant}.txt")
    open(script, "w", encoding="utf-8").write(";\n".join(fx))
    out = output_path(p, size_name, variant, preview)
    enc = vcodec("preview" if preview else "final")
    audio = ["-map", "[aout]", "-c:a", "aac", "-b:a", "256k"] if with_audio else []
    run(inputs + ["-/filter_complex", paths.rel(script), "-map", "[vout]"] + audio +
        ["-t", f"{dur:.3f}"] + enc + ["-pix_fmt", "yuv420p", "-r", str(fps),
                                                       "-movflags", "+faststart", paths.rel(out)])
    print(f"  wrote {paths.rel(out)}  ({time.time() - t0:.0f}s)")
    return out
