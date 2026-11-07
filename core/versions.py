"""Version history of a project (snapshots of project.json) and reusable templates (the look of a video, without its song or shots)."""
import json, os, re, time
from . import paths, project

KEEP = 40
AUTO_EVERY = 300          # seconds between automatic snapshots


def _dir(name):
    d = os.path.join(project.project_dir(name), "versions")
    os.makedirs(d, exist_ok=True)
    return d


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def listing(name):
    out = []
    for f in sorted(os.listdir(_dir(name)), reverse=True):
        m = re.fullmatch(r"(\d{8}-\d{6})_([\w-]*)\.json", f)
        if not m:
            continue
        try:
            raw = _read(os.path.join(_dir(name), f))
        except (OSError, ValueError):
            continue
        out.append({"id": f[:-5], "time": time.mktime(time.strptime(m[1], "%Y%m%d-%H%M%S")), "label": m[2] or "saved",
                    "shots": len(raw.get("shots") or []), "lines": len((raw.get("subtitles") or {}).get("lines") or [])})
    return out


def snapshot(name, label="saved", force=False):
    """Copy project.json into versions/. Skipped when nothing changed since the newest snapshot, and (for 'auto') when one was made recently."""
    src = project.json_path(name)
    if not os.path.exists(src):
        return None
    text = _text(src)
    label = re.sub(r"[^\w-]", "-", label)[:24] or "saved"
    items = listing(name)
    if items:
        newest = os.path.join(_dir(name), items[0]["id"] + ".json")
        if _text(newest) == text:
            return None
        if label == "auto" and not force and time.time() - items[0]["time"] < AUTO_EVERY:
            return None
    vid = time.strftime("%Y%m%d-%H%M%S") + "_" + label
    with open(os.path.join(_dir(name), vid + ".json"), "w", encoding="utf-8") as f:
        f.write(text)
    for old in listing(name)[KEEP:]:
        try:
            os.remove(os.path.join(_dir(name), old["id"] + ".json"))
        except OSError:
            pass
    return vid


def restore(name, vid):
    if not re.fullmatch(r"\d{8}-\d{6}_[\w-]*", vid or ""):
        raise ValueError("bad version id")
    path = os.path.join(_dir(name), vid + ".json")
    if not os.path.exists(path):
        raise ValueError("no such version")
    snapshot(name, "before-restore", force=True)           # so a restore can itself be undone
    with open(project.json_path(name), "w", encoding="utf-8") as f:
        f.write(_text(path))


# ---------------------------------------------------------------- templates
TEMPLATES = os.path.join(paths.LIBRARY, "templates")
KEYS = ("channel", "theme", "fps", "crossfade", "fade_in", "fade_out", "audio_fade_in", "audio_fade_out", "grade", "sizes")


def template_names():
    return sorted(f[:-5] for f in os.listdir(TEMPLATES) if f.endswith(".json")) if os.path.isdir(TEMPLATES) else []


def save_template(name, from_project):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", name or ""):
        raise ValueError("Template names use letters, numbers, - or _")
    raw = _read(project.json_path(from_project))
    ov = raw.get("overlays") or {}
    data = {k: raw[k] for k in KEYS if k in raw}
    data["subtitles"] = {k: v for k, v in (raw.get("subtitles") or {}).items() if k in ("style", "font", "size", "margin_v", "pad")}
    tc, ec = ov.get("title_card"), ov.get("end_card")
    data["overlays"] = {"logo": ov.get("logo"), "title_card": ({k: tc[k] for k in ("subtitle", "in", "out") if k in tc} if tc else None),
                        "end_card": ({k: ec[k] for k in ("handle", "tagline") if k in ec} if ec else None),
                        "popups": [{"at": p["at"], "dur": p.get("dur", 5), "click": p.get("click", 2.6), "tagline": p.get("tagline", "Subscribe for more mezmur")}
                                   for p in ov.get("popups") or [] if isinstance(p, dict)],
                        "popup_style": ov.get("popup_style", "native")}
    os.makedirs(TEMPLATES, exist_ok=True)
    with open(os.path.join(TEMPLATES, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return name


def apply_template(raw, name, title):
    """Fill a brand new project's raw dict with the look from a template (card text uses the new title)."""
    path = os.path.join(TEMPLATES, name + ".json")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", name or "") or not os.path.exists(path):
        raise ValueError(f"No template '{name}'")
    t = _read(path)
    for k in KEYS:
        if k in t:
            raw[k] = t[k]
    raw.setdefault("subtitles", {}).update(t.get("subtitles") or {})
    ov, to = raw.setdefault("overlays", {}), t.get("overlays") or {}
    if to.get("logo"):
        ov["logo"] = to["logo"]
    if to.get("title_card"):
        ov["title_card"] = {"text": title, **to["title_card"]}
    if to.get("end_card"):
        ov["end_card"] = {"title": title, **to["end_card"], "in": 0.0}      # the editor places it near the end once the length is known
    ov["popups"] = to.get("popups", [])
    ov["popup_style"] = to.get("popup_style", "native")
    return raw
