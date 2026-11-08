"""Edits to a project as plain data: save/validate (used by the editor and the dashboard) and the editing operations Claude uses.

A 'doc' is the same shape the editor works with: numeric times in seconds, shots contiguous (a shot runs until the next one starts).
Indices in the operations are 1-based ("shot 5", "line 3"), as they appear in the editor.
"""
import json, os, re
from . import draft, fx, paths, project, textstyle

MIN_SHOT = 0.5


# ---------------------------------------------------------------- saving (shared with the editor / dashboard)
def save_project(name, data):
    def mutate(raw):
        if "shots" in data:
            shots = []
            for s in data["shots"]:
                at = s["at"]
                if not (isinstance(at, (int, float)) or re.fullmatch(r"L\d+[mse]?", str(at)) or re.fullmatch(r"\d+(\.\d+)?", str(at))):
                    raise ValueError(f"bad shot time {at!r}")
                clip = str(s["clip"])
                known = re.fullmatch(r"(pb)?\d+", clip) or any(os.path.exists(os.path.join(base, clip)) for base in (project.project_dir(name), paths.ROOT, ""))
                if not known:
                    raise ValueError(f"bad clip {clip!r}: not a library number and no such file")
                item = {"at": float(at) if re.fullmatch(r"\d+(\.\d+)?", str(at)) else at, "clip": str(s["clip"]),
                        "start": float(s.get("start", 0)), "pan": float(s.get("pan", 0.5))}
                if s.get("transition") in project.TRANSITIONS and s["transition"] != "fade":
                    item["transition"] = s["transition"]
                if s.get("look") in fx.LOOKS:
                    item["look"] = s["look"]
                if s.get("move") in fx.MOVES:
                    item["move"] = s["move"]
                shots.append(item)
            raw["shots"] = shots
        if "fx" in data:
            raw["fx"] = fx.clean(data["fx"])
        if "subs" in data:
            raw.setdefault("subtitles", {})["style"] = textstyle.clean(data["subs"])
        if "lines" in data:
            lines = []
            for ln in data["lines"]:
                item = {"text": str(ln["text"]), "start": round(float(ln["start"]), 2), "end": round(float(ln["end"]), 2)}
                if ln.get("keywords"):
                    item["keywords"] = [str(k) for k in ln["keywords"]]
                lines.append(item)
            raw.setdefault("subtitles", {})["lines"] = lines
        if "title" in data:
            raw["title"] = str(data["title"])
        if "channel" in data:
            raw["channel"] = {"name": str(data["channel"].get("name", "")), "handle": str(data["channel"].get("handle", ""))}
        if "overlays" in data:
            ov, new = raw.setdefault("overlays", {}), data["overlays"]
            num = lambda x: None if x in (None, "") else float(x)
            if "logo" in new:
                ov["logo"] = {**ov.get("logo", {"image": "library/brand/logo.jpg"}), "in": num(new["logo"].get("in")), "out": num(new["logo"].get("out"))}
            for key, fields in (("title_card", ("text", "subtitle")), ("end_card", ("title", "handle", "tagline"))):
                if key in new:
                    c = new[key]
                    if not c:
                        ov[key] = None
                    else:
                        ov[key] = {f: str(c.get(f, "")) for f in fields}
                        ov[key]["in"] = num(c.get("in")) or 0.0
                        if key == "title_card":
                            ov[key]["out"] = num(c.get("out")) or 6.0
            if "popups" in new:
                pops = []
                for e in new["popups"]:
                    pops.append({"at": float(e["at"]), "dur": float(e.get("dur", 5)), "click": float(e.get("click", 2.6)),
                                 "tagline": str(e.get("tagline", "Subscribe for more mezmur"))})
                ov["popups"] = pops
        if "theme" in data:
            raw["theme"] = [w for w in re.split(r"[\s,]+", str(data["theme"])) if w] if isinstance(data["theme"], str) else list(data["theme"])
    project.save_raw(name, mutate)


# ---------------------------------------------------------------- doc <-> project
def load_doc(name):
    p = project.load(name)
    shots = [{"at": round(float(s["at"]), 2), "clip": str(s["clip"]), "start": round(float(s["start"]), 2), "pan": round(float(s["pan"]), 2),
              "transition": s["transition"], "look": s.get("look") or "", "move": s.get("move") or ""} for s in p["_shots"]]
    if shots:
        shots[0]["at"] = 0.0
    lines = []
    for ln in p["subtitles"]["lines"]:
        item = {"text": ln["text"], "start": round(float(ln["start"]), 2), "end": round(float(ln["end"]), 2)}
        if ln.get("keywords"):
            item["keywords"] = list(ln["keywords"])
        lines.append(item)
    ov = p["overlays"]
    popups = [{"at": float(e), "dur": 5.0, "click": 2.6, "tagline": "Subscribe for more mezmur"} if isinstance(e, (int, float))
              else {"at": float(e["at"]), "dur": float(e.get("dur", 5)), "click": float(e.get("click", 2.6)), "tagline": e.get("tagline", "Subscribe for more mezmur")}
              for e in (ov.get("popups") or [])]
    return {"title": p["title"], "theme": " ".join(p.get("theme") or []), "duration": float(p["duration"]), "shots": shots, "lines": lines,
            "channel": dict(p["channel"]), "subs": textstyle.clean(p["subtitles"].get("style")), "fx": fx.clean(p.get("fx")),
            "overlays": {"logo": {"in": (ov.get("logo") or {}).get("in"), "out": (ov.get("logo") or {}).get("out")},
                         "title_card": dict(ov["title_card"]) if ov.get("title_card") else None,
                         "end_card": dict(ov["end_card"]) if ov.get("end_card") else None, "popups": popups}}


def save_doc(name, doc):
    save_project(name, {"title": doc["title"], "theme": doc["theme"], "shots": doc["shots"], "lines": doc["lines"], "channel": doc["channel"],
                        "overlays": doc["overlays"], "subs": doc.get("subs") or textstyle.DEFAULT, "fx": doc.get("fx") or fx.DEFAULT_FX})


def edit(name, fn):
    """Load, apply `fn(doc) -> message`, save. Returns the message. Nothing is written if fn raises."""
    doc = load_doc(name)
    msg = fn(doc)
    save_doc(name, doc)
    return msg


# ---------------------------------------------------------------- helpers
def shot_end(doc, i):
    return doc["shots"][i + 1]["at"] if i + 1 < len(doc["shots"]) else doc["duration"]


def index_at(doc, t):
    k = 0
    for i, s in enumerate(doc["shots"]):
        if s["at"] <= t:
            k = i
    return k


def _item(doc, kind, n):
    seq = doc[kind]
    if not isinstance(n, int) or n < 1 or n > len(seq):
        raise ValueError(f"There is no {kind[:-1]} {n}: this video has {len(seq)} {kind}.")
    return seq[n - 1]


def _t(x, what="time"):
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number of seconds, got {x!r}")
    if v < 0:
        raise ValueError(f"{what} cannot be negative")
    return round(v, 2)


def fmt(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def describe_shot(doc, i):
    s = doc["shots"][i]
    tags = draft.load().get(s["clip"], {}).get("tags", [])
    return f"shot {i + 1}: #{s['clip']} {fmt(s['at'])}-{fmt(shot_end(doc, i))} ({shot_end(doc, i) - s['at']:.1f}s) from {s['start']}s into the clip, pan {s['pan']}" + (f", enters with '{s['transition']}'" if i and s.get("transition", "fade") != "fade" else "") + (f", look {s['look']}" if s.get("look") else "") + (f", move {s['move']}" if s.get("move") else "") + (f" [{' '.join(tags[:5])}]" if tags else "")


def describe_line(doc, i):
    ln = doc["lines"][i]
    return f"line {i + 1}: {fmt(ln['start'])}-{fmt(ln['end'])} \"{ln['text']}\"" + (f" keywords: {' '.join(ln['keywords'])}" if ln.get("keywords") else "")


# ---------------------------------------------------------------- operations (each returns a short message)
def split_shot(doc, time):
    t = _t(time)
    i = index_at(doc, t)
    s = doc["shots"][i]
    if t - s["at"] < MIN_SHOT or shot_end(doc, i) - t < MIN_SHOT:
        raise ValueError(f"{fmt(t)} is within {MIN_SHOT}s of a cut (shot {i + 1} runs {fmt(s['at'])}-{fmt(shot_end(doc, i))}); pick a time further inside the shot.")
    doc["shots"].insert(i + 1, {"at": t, "clip": s["clip"], "start": round(s["start"] + (t - s["at"]), 2), "pan": s["pan"], "transition": "fade"})
    return f"Split shot {i + 1} at {fmt(t)}. There are now {len(doc['shots'])} shots."


def delete_shot(doc, shot):
    s = _item(doc, "shots", shot)
    if len(doc["shots"]) < 2:
        raise ValueError("Cannot delete the only shot.")
    msg = f"Deleted shot {shot} (#{s['clip']}); the {'next' if shot == 1 else 'previous'} shot now covers its time."
    doc["shots"].remove(s)
    doc["shots"][0]["at"] = 0.0
    return msg


def move_cut(doc, shot, time):
    """Move the cut at the START of shot `shot` (2 or higher) to `time`."""
    _item(doc, "shots", shot)
    if shot < 2:
        raise ValueError("Shot 1 starts at 0 and cannot be moved. To change shot 1's length, move the cut of shot 2.")
    i, t = shot - 1, _t(time)
    lo, hi = doc["shots"][i - 1]["at"] + MIN_SHOT, shot_end(doc, i) - MIN_SHOT
    if hi < lo:
        raise ValueError("The neighbouring shots are too short to move this cut.")
    at = round(min(max(t, lo), hi), 2)
    doc["shots"][i]["at"] = at
    return f"Cut before shot {shot} is now at {fmt(at)}" + ("" if at == t else f" (limited from {fmt(t)} to keep shots at least {MIN_SHOT}s)") + "."


def set_clip(doc, shot, clip, start=None):
    s = _item(doc, "shots", shot)
    clip = str(clip)
    if not re.fullmatch(r"(pb)?\d+", clip) or not os.path.exists(paths.stock_path(clip)):
        raise ValueError(f"Clip {clip} is not in the library. Use search_clips to find valid clip numbers.")
    s["clip"] = clip
    s["start"] = _t(start) if start is not None else 1.0
    return f"Shot {shot} now uses clip #{clip} starting {s['start']}s into it."


def set_shot(doc, shot, start=None, pan=None):
    s = _item(doc, "shots", shot)
    if start is not None:
        s["start"] = _t(start, "start")
    if pan is not None:
        p = float(pan)
        if not 0 <= p <= 1:
            raise ValueError("pan must be between 0 (left) and 1 (right)")
        s["pan"] = round(p, 2)
    return describe_shot(doc, shot - 1)


def set_line(doc, line, text=None, start=None, end=None, keywords=None):
    ln = _item(doc, "lines", line)
    if text is not None:
        ln["text"] = str(text)
    if start is not None:
        ln["start"] = _t(start, "start")
    if end is not None:
        ln["end"] = _t(end, "end")
    if keywords is not None:
        ln["keywords"] = [str(k) for k in (keywords.split() if isinstance(keywords, str) else keywords)]
    if ln["end"] <= ln["start"]:
        raise ValueError(f"The line would end ({fmt(ln['end'])}) before it starts ({fmt(ln['start'])}).")
    return describe_line(doc, line - 1)


def add_line(doc, text, start, end):
    a, b = _t(start, "start"), _t(end, "end")
    if b <= a:
        raise ValueError("end must be after start")
    doc["lines"].append({"text": str(text), "start": a, "end": b})
    doc["lines"].sort(key=lambda l: l["start"])
    return f"Added a lyric line at {fmt(a)}-{fmt(b)}. There are now {len(doc['lines'])} lines."


def delete_line(doc, line):
    ln = _item(doc, "lines", line)
    doc["lines"].remove(ln)
    return f"Deleted line {line} \"{ln['text']}\"."


def shift_lines(doc, seconds, first=1, last=None):
    d = float(seconds)
    last = last or len(doc["lines"])
    if not 1 <= first <= last <= len(doc["lines"]):
        raise ValueError(f"line range must be within 1-{len(doc['lines'])}")
    for ln in doc["lines"][first - 1:last]:
        ln["start"] = round(max(0.0, ln["start"] + d), 2)
        ln["end"] = round(max(ln["start"] + 0.2, ln["end"] + d), 2)
    return f"Shifted lines {first}-{last} by {d:+.2f}s."


def set_title(doc, title):
    doc["title"] = str(title)
    return f"Title is now \"{doc['title']}\"."


def set_theme(doc, theme):
    doc["theme"] = str(theme)
    return f"Theme words are now: {doc['theme']}."


def set_card(doc, kind, enabled=True, text=None, subtitle=None, title=None, handle=None, tagline=None, at=None, until=None):
    ov = doc["overlays"]
    if kind == "title":
        if not enabled:
            ov["title_card"] = None
            return "Removed the title card."
        c = ov["title_card"] or {"text": doc["title"], "subtitle": doc["channel"]["name"], "in": 1.0, "out": 8.0}
        for k, v in (("text", text), ("subtitle", subtitle)):
            if v is not None:
                c[k] = str(v)
        if at is not None:
            c["in"] = _t(at, "at")
        if until is not None:
            c["out"] = _t(until, "until")
        ov["title_card"] = c
        return f"Title card: \"{c['text']}\" / \"{c.get('subtitle', '')}\" from {fmt(c['in'])} to {fmt(c['out'])}."
    if kind == "end":
        if not enabled:
            ov["end_card"] = None
            return "Removed the end card."
        c = ov["end_card"] or {"title": doc["title"], "handle": doc["channel"]["handle"], "tagline": "SUBSCRIBE FOR MORE MEZMUR", "in": max(0.0, doc["duration"] - 16)}
        for k, v in (("title", title), ("handle", handle), ("tagline", tagline)):
            if v is not None:
                c[k] = str(v)
        if at is not None:
            c["in"] = _t(at, "at")
        ov["end_card"] = c
        return f"End card from {fmt(c['in'])}: \"{c['title']}\", {c['handle']}."
    raise ValueError("kind must be 'title' or 'end'")


def add_popup(doc, at, tagline="Subscribe for more mezmur", dur=5.0, click=2.6):
    t = _t(at, "at")
    if t + float(dur) > doc["duration"]:
        raise ValueError("The pop-up would run past the end of the video.")
    doc["overlays"]["popups"].append({"at": t, "dur": float(dur), "click": float(click), "tagline": str(tagline)})
    doc["overlays"]["popups"].sort(key=lambda p: p["at"])
    return f"Added a subscribe pop-up at {fmt(t)}. There are {len(doc['overlays']['popups'])} pop-ups."


def remove_popup(doc, popup):
    pops = doc["overlays"]["popups"]
    if not 1 <= popup <= len(pops):
        raise ValueError(f"There is no pop-up {popup}: there are {len(pops)}.")
    p = pops.pop(popup - 1)
    return f"Removed the pop-up at {fmt(p['at'])}."


def set_logo(doc, appears=None, disappears=None):
    lg = doc["overlays"]["logo"]
    if appears is not None:
        lg["in"] = _t(appears, "appears")
    if disappears is not None:
        lg["out"] = None if disappears == "" else _t(disappears, "disappears")
    return f"Corner logo shows from {fmt(lg['in'] or 0)}" + (f" to {fmt(lg['out'])}." if lg["out"] is not None else " to the end.")


# ---------------------------------------------------------------- order, transitions, lyric look
def reorder_shot(doc, shot, to):
    """Move a shot to another place in the order. Every shot keeps its own length, so the total length is unchanged and later shots shift."""
    _item(doc, "shots", shot)
    if not isinstance(to, int) or not 1 <= to <= len(doc["shots"]):
        raise ValueError(f"'to' must be between 1 and {len(doc['shots'])}")
    shots = doc["shots"]
    lengths = [shot_end(doc, i) - s["at"] for i, s in enumerate(shots)]
    item = list(zip(shots, lengths))
    moved = item.pop(shot - 1)
    item.insert(to - 1, moved)
    t, out = 0.0, []
    for s, ln in item:
        out.append({**s, "at": round(t, 2)})
        t += ln
    doc["shots"][:] = out
    return f"Moved shot {shot} to position {to}. Each shot kept its length."


def set_transition(doc, shot, kind):
    """The transition INTO a shot (from the previous one). shot 'all' is not supported here; use a loop."""
    s = _item(doc, "shots", shot)
    if shot == 1:
        raise ValueError("Shot 1 is the first shot, so nothing comes into it. Set the transition on shot 2 or higher.")
    if kind not in project.TRANSITIONS:
        raise ValueError(f"transition must be one of: {', '.join(project.TRANSITIONS)}")
    s["transition"] = kind
    return f"The cut into shot {shot} now uses '{kind}'."


def set_all_transitions(doc, kind):
    if kind not in project.TRANSITIONS:
        raise ValueError(f"transition must be one of: {', '.join(project.TRANSITIONS)}")
    for s in doc["shots"][1:]:
        s["transition"] = kind
    return f"Every cut now uses '{kind}'."


def set_text_style(doc, preset=None, color=None, active=None, outline=None, scale=None, position=None, karaoke=None, glow=None, reveal=None):
    """Change how the lyrics look. preset: classic, gold, karaoke, soft, bold (then individual fields override it)."""
    st = dict(doc.get("subs") or textstyle.DEFAULT)
    if preset is not None:
        if preset not in textstyle.PRESETS:
            raise ValueError(f"preset must be one of: {', '.join(textstyle.PRESETS)}")
        st.update(textstyle.PRESETS[preset])
        st["preset"] = preset
    for k, v in (("color", color), ("active", active), ("outline", outline), ("scale", scale), ("position", position), ("karaoke", karaoke), ("glow", glow), ("reveal", reveal)):
        if v is not None:
            st[k] = v
            if preset is None:
                st["preset"] = "custom"
    doc["subs"] = textstyle.clean(st)
    s = doc["subs"]
    return f"Lyrics: {s['preset']} style, {'karaoke sweep' if s['karaoke'] else 'no sweep'}, {s['position']}, size x{s['scale']}, text {s['color']}" + (f", sung colour {s['active']}" if s["karaoke"] else "") + "."


# ---------------------------------------------------------------- effects (look, move, glow, dust, flashes, beat pulse)
def set_look(doc, shot, look):
    """A colour look for one shot: warm, night, film, mono, dramatic, dawn, or 'none'."""
    s = _item(doc, "shots", shot)
    if look in ("none", "", None):
        s["look"] = ""
        return f"Shot {shot} uses the normal colours."
    if look not in fx.LOOKS:
        raise ValueError(f"look must be one of: {', '.join(fx.LOOKS)}, none")
    s["look"] = look
    return f"Shot {shot} now has the '{look}' look ({fx.LOOKS[look][0]})."


def set_move(doc, shot, move):
    """The camera move of one 16:9 shot: in, out, left, right, up, still, or 'default'."""
    s = _item(doc, "shots", shot)
    if move in ("default", "", None):
        s["move"] = ""
        return f"Shot {shot} uses the default slow drift."
    if move not in fx.MOVES:
        raise ValueError(f"move must be one of: {', '.join(fx.MOVES)}, default")
    s["move"] = move
    return f"Shot {shot} now moves: {fx.MOVES[move]}."


def set_fx(doc, glow=None, dust=None, pulse=None, flash=None):
    """Project-wide effects: glow 0-1 (soft bloom), dust on/off (drifting light specks), pulse 0-0.12 (brightness pulse on bar starts), flash = list of seconds (a warm light flash)."""
    cur = dict(doc.get("fx") or fx.DEFAULT_FX)
    for k, v in (("glow", glow), ("dust", dust), ("pulse", pulse), ("flash", flash)):
        if v is not None:
            cur[k] = v
    doc["fx"] = fx.clean(cur)
    f = doc["fx"]
    return f"Effects: glow {f['glow']}, dust {'on' if f['dust'] else 'off'}, beat pulse {f['pulse']}, {len(f['flash'])} light flashes."
