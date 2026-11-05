"""Load a project.json, fill in defaults, and resolve things like "L3" (= start of lyric line 3) into seconds."""
import copy, json, os, re, sys
from . import paths

DEFAULTS = {
    "title": "",
    "fps": 24,
    "crossfade": 0.6,
    "sizes": ["16x9", "9x16"],
    "fade_in": 1.0,
    "fade_out": 2.5,
    "audio_fade_in": 0.4,
    "audio_fade_out": 3.5,
    "grade": {"contrast": 1.05, "saturation": 0.92, "brightness": -0.015,
              "colorbalance": "rs=-0.02:bs=0.04:rh=0.04:bh=-0.03", "vignette": True, "grain": 2},
    "subtitles": {"enabled": True, "font": "Ebrima", "size": {"16x9": 54, "9x16": 64},
                  "margin_v": {"16x9": 70, "9x16": 400}, "pad": 0.05, "lines": []},
    "overlays": {
        "logo": {"image": "library/brand/logo.jpg", "in": 9.5, "out": 104.0, "fade_out": 0.8},
        "title_card": None,
        "end_card": None,
        "popups": [],
    },
    "shots": [],
}
SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def project_dir(name):
    return os.path.join(paths.PROJECTS, name)


def json_path(name):
    return os.path.join(project_dir(name), "project.json")


def load(name):
    path = json_path(name)
    if not os.path.exists(path):
        sys.exit(f"No project '{name}'. Expected {path}  (try: python studio.py list)")
    p = merge(DEFAULTS, json.load(open(path, encoding="utf-8")))
    p["_name"], p["_dir"] = name, project_dir(name)
    if "audio" not in p:
        sys.exit("project.json needs an \"audio\" file")
    p["_audio"] = resolve_file(p, p["audio"])
    p["duration"] = float(p.get("duration") or audio_seconds(p["_audio"]))
    lines = p["subtitles"]["lines"]
    p["_shots"] = [resolve_shot(p, s, lines) for s in p["shots"]]
    p["_shots"].sort(key=lambda s: s["at"])
    return p


def save_raw(name, mutate):
    """Read project.json as written, let `mutate` edit it, write it back (keeps a .bak)."""
    path = json_path(name)
    raw = json.load(open(path, encoding="utf-8"))
    open(path + ".bak", "w", encoding="utf-8").write(json.dumps(raw, ensure_ascii=False, indent=1))
    mutate(raw)
    open(path, "w", encoding="utf-8").write(json.dumps(raw, ensure_ascii=False, indent=1))


def resolve_file(p, ref):
    """A project file can be given relative to the project folder, relative to the studio root, or absolute."""
    for base in (p["_dir"], paths.ROOT, ""):
        cand = os.path.join(base, ref) if base else ref
        if os.path.exists(cand):
            return os.path.abspath(cand)
    sys.exit(f"File not found: {ref}")


def resolve_clip(p, clip):
    """'6988904' -> library/stock/p6988904.mp4, otherwise treat it as a path (video or still image)."""
    if re.fullmatch(r"\d+", str(clip)):
        f = paths.stock_path(clip)
        if not os.path.exists(f):
            sys.exit(f"Stock clip {clip} is not downloaded. Run: python studio.py fetch-ids {clip}:<fps>   (or fetch with a search)")
        return f
    return resolve_file(p, str(clip))


def at_time(value, lines):
    """number of seconds, 'L3' = start of lyric line 3, 'L3m' = middle of line 3, 'L3e' = its end."""
    if isinstance(value, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(value)):
        return float(value)
    m = re.fullmatch(r"L(\d+)([mse]?)", str(value))
    if not m:
        sys.exit(f"Bad time '{value}' (use seconds or L<number>, L<number>m, L<number>e)")
    ln = lines[int(m[1]) - 1]
    a, b = float(ln["start"]), float(ln["end"])
    return {"": a, "s": a, "m": (a + b) / 2, "e": b}[m[2]]


def resolve_shot(p, s, lines):
    return {"at": at_time(s["at"], lines), "file": resolve_clip(p, s["clip"]), "clip": str(s["clip"]),
            "start": float(s.get("start", 0)), "pan": float(s.get("pan", 0.5)),
            "motion": s.get("motion", "drift")}


def audio_seconds(path):
    import re as _re, subprocess
    r = subprocess.run([paths.ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True)
    m = _re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
