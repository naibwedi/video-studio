"""The tools Claude uses to co-edit a video: look at things, search footage, change the edit, start renders.

One registry, used by the MCP server (core/mcp_server.py), so the same tools work for the chat panel in the editor and for any other Claude.
Every tool takes the project name from the session, so Claude never needs file paths. Indices are 1-based, like the editor shows them.
"""
import base64, contextlib, io, json, os, subprocess, urllib.request
from PIL import Image, ImageDraw
from . import beats, clipsearch, draft, edits, overlays, paths, project, qc, smartcrop, textstyle, youtube

TOOLS = {}
EDIT_TOOLS = set()      # tools that change the project (the editor reloads after these)


def tool(name, description, props=None, required=(), writes=False):
    def deco(fn):
        TOOLS[name] = {"description": description, "props": props or {}, "required": list(required), "fn": fn}
        if writes:
            EDIT_TOOLS.add(name)
        return fn
    return deco


def specs():
    return [{"name": n, "description": t["description"], "inputSchema": {"type": "object", "properties": t["props"], "required": t["required"]}}
            for n, t in TOOLS.items()]


def call(name, args, project_name):
    """Run a tool. Returns an MCP result: {"content": [...], "isError": bool}."""
    if name not in TOOLS:
        return {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True}
    try:
        out = TOOLS[name]["fn"](project_name, **(args or {}))
    except (ValueError, KeyError, SystemExit, TypeError) as e:
        return {"content": [{"type": "text", "text": f"Could not do that: {e}"}], "isError": True}
    text, images = out if isinstance(out, tuple) else (out, [])
    content = [{"type": "text", "text": text}]
    for jpg in images:
        content.append({"type": "image", "data": base64.b64encode(jpg).decode(), "mimeType": "image/jpeg"})
    return {"content": content, "isError": False}


NUM = {"type": "number"}
INT = {"type": "integer", "minimum": 1}
STR = {"type": "string"}


# ---------------------------------------------------------------- looking
@tool("get_project", "Read the whole edit: title, length, theme, every shot (number, time range, clip, tags) and every lyric line with its times, the cards and pop-ups, and things to check. Call this first.")
def get_project(name):
    d = edits.load_doc(name)
    ov = d["overlays"]
    out = [f"Title: {d['title']}   Length: {edits.fmt(d['duration'])} ({d['duration']:.1f}s)   Theme words: {d['theme'] or '(none)'}",
           f"Channel: {d['channel']['name']} {d['channel']['handle']}", "", f"SHOTS ({len(d['shots'])}), each runs until the next one starts:"]
    out += [edits.describe_shot(d, i) for i in range(len(d["shots"]))]
    out += ["", f"LYRIC LINES ({len(d['lines'])}):"] + [edits.describe_line(d, i) for i in range(len(d["lines"]))]
    tc, ec = ov["title_card"], ov["end_card"]
    out += ["", "CARDS: " + (f"title card \"{tc['text']}\" {edits.fmt(tc['in'])}-{edits.fmt(tc['out'])}" if tc else "no title card")
            + "; " + (f"end card from {edits.fmt(ec['in'])}" if ec else "no end card"),
            f"Corner logo: from {edits.fmt(ov['logo']['in'] or 0)}" + (f" to {edits.fmt(ov['logo']['out'])}" if ov["logo"]["out"] is not None else " to the end")]
    sb = d["subs"]
    out += [f"Lyrics look: {sb['preset']} style, {'karaoke sweep' if sb['karaoke'] else 'plain'}, {sb['position']}, size x{sb['scale']}, text {sb['color']}" + (f", sung colour {sb['active']}" if sb["karaoke"] else "")]
    out += [f"Subscribe pop-up {i + 1}: at {edits.fmt(p['at'])} for {p['dur']}s: \"{p['tagline']}\"" for i, p in enumerate(ov["popups"])]
    notes = qc.project_checks(project.load(name))
    out += ["", "THINGS TO CHECK: " + ("none" if not notes else "")] + [f"- {lv}: {tx}" for lv, tx in notes]
    return "\n".join(out)


@tool("search_clips", "Search the footage library by words (what the picture shows: candle, roots, dark water, sunrise, church...). Theme words like repentance, hope, prayer also work. Returns clip numbers with their tags. Faces are excluded unless asked for.",
      {"query": STR, "limit": {"type": "integer", "minimum": 1, "maximum": 30}, "include_faces": {"type": "boolean"}}, ["query"])
def search_clips(name, query, limit=12, include_faces=False):
    hits = draft.search(query, int(limit), bool(include_faces))
    if not hits:
        return f"No clips match '{query}'. Try other words (the library is tagged in English: e.g. candle, chains, fog, roots, sunrise)."
    return f"{len(hits)} clips for '{query}':\n" + "\n".join(f"#{h['clip']}  {' '.join(h['tags'])}" + ("  [person visible]" if h["people"] == 2 else "") + (f"  ({h['seconds']}s)" if h["seconds"] else "") for h in hits)


def _frame_jpeg(src, seconds, vf):
    r = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{max(0.0, seconds):.3f}", "-i", src, "-frames:v", "1", "-vf", vf,
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "pipe:1"], capture_output=True, cwd=paths.ROOT)
    if not r.stdout:
        raise ValueError("could not read a frame from that clip")
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def _shot_frame(name, doc, t, size, width):
    i = edits.index_at(doc, t)
    s = doc["shots"][i]
    src = project.resolve_clip(project.load(name), s["clip"])
    base = s["at"] - 0.3 if i > 0 else 0.0
    off = s["start"] + max(0.0, t - base)
    vf = (f"scale=-2:{int(width * 16 / 9)},crop={width}:{int(width * 16 / 9)}:(iw-{width})*{s['pan']}:0" if size == "9x16" else f"scale={width}:-2")
    return _frame_jpeg(src, off, vf), i


def _caption(im, text, text2=""):
    d = ImageDraw.Draw(im, "RGBA")
    h = 22 + (24 if text2 else 0)
    d.rectangle((0, im.height - h, im.width, im.height), fill=(0, 0, 0, 190))
    d.text((6, im.height - h + 4), text, font=overlays.font(14, bold=False), fill=(255, 255, 255, 255))
    if text2:
        d.text((6, im.height - 26), text2, font=overlays.font(18), fill=(245, 235, 208, 255))
    return im


def _jpeg(im, q=82):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return b.getvalue()


@tool("look", "See the picture at a moment of the video (the footage frame plus the lyric line sung then). Use it before judging a shot, and after changing one.",
      {"time": {**NUM, "description": "seconds from the start"}, "size": {"type": "string", "enum": ["16x9", "9x16"]}}, ["time"])
def look(name, time, size="16x9"):
    doc = edits.load_doc(name)
    t = max(0.0, min(float(time), doc["duration"]))
    im, i = _shot_frame(name, doc, t, size, 720 if size == "16x9" else 405)
    ln = next((l for l in doc["lines"] if l["start"] <= t <= l["end"]), None)
    _caption(im, f"{edits.fmt(t)}  shot {i + 1}  #{doc['shots'][i]['clip']}", ln["text"] if ln else "")
    return f"At {edits.fmt(t)}: shot {i + 1} (#{doc['shots'][i]['clip']})" + (f", lyric: \"{ln['text']}\"" if ln else ", no lyric line"), [_jpeg(im)]


@tool("contact_sheet", "A grid of frames across a time range, with times and shot numbers: use it to judge pacing, variety and flow between shots.",
      {"start": NUM, "end": NUM, "frames": {"type": "integer", "minimum": 2, "maximum": 12}, "size": {"type": "string", "enum": ["16x9", "9x16"]}}, ["start", "end"])
def contact_sheet(name, start, end, frames=8, size="16x9"):
    doc = edits.load_doc(name)
    a, b = max(0.0, float(start)), min(float(end), doc["duration"])
    if b <= a:
        raise ValueError("end must be after start")
    n = max(2, min(12, int(frames)))
    cols = 4 if size == "16x9" else 6
    tw, th = (320, 180) if size == "16x9" else (180, 320)
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "black")
    for k in range(n):
        t = a + (b - a) * (k + 0.5) / n
        im, i = _shot_frame(name, doc, t, size, 320 if size == "16x9" else 180)
        im = im.resize((tw, th))
        _caption(im, f"{edits.fmt(t)}  shot {i + 1}  #{doc['shots'][i]['clip']}")
        sheet.paste(im, ((k % cols) * tw, (k // cols) * th))
    return f"{n} frames from {edits.fmt(a)} to {edits.fmt(b)}.", [_jpeg(sheet, 78)]


@tool("check_project", "Run the project checks: lyric lines overlapping or too long, shots that are too short, pop-ups past the end.")
def check_project(name):
    notes = qc.project_checks(project.load(name))
    return "No problems found." if not notes else "\n".join(f"{lv}: {tx}" for lv, tx in notes)


# ---------------------------------------------------------------- changing the edit
_current = [None]          # the project a write tool is working on (tools that need its song, like the beat snap, read it)


def _w(fn):
    def run(name, **kw):
        _current[0] = name
        return edits.edit(name, lambda doc: fn(doc, **kw))
    return run


def _reg(name, description, props, required, fn):
    TOOLS[name] = {"description": description, "props": props, "required": list(required), "fn": _w(fn)}
    EDIT_TOOLS.add(name)


_reg("split_shot", "Cut the shot under a time into two shots (same footage continues). The time must be at least 0.5s inside the shot.", {"time": NUM}, ["time"], edits.split_shot)
_reg("delete_shot", "Delete a shot; the previous shot covers its time (shot 1: the next one).", {"shot": INT}, ["shot"], edits.delete_shot)
_reg("move_cut", "Move the cut at the START of a shot (shot 2 or higher) to a new time. Changes the length of this shot and the one before it.", {"shot": INT, "time": NUM}, ["shot", "time"], edits.move_cut)
_reg("swap_clip", "Replace the footage of a shot with another library clip (use search_clips for numbers). 'start' is the seconds into the new clip where it begins (default 1).",
     {"shot": INT, "clip": {"type": "string", "description": "library clip number"}, "start": NUM}, ["shot", "clip"], lambda doc, shot, clip, start=None: edits.set_clip(doc, shot, clip, start))
_reg("set_shot", "Change where in its clip a shot starts ('start', seconds) and/or the 9:16 crop position ('pan', 0 = left, 1 = right).", {"shot": INT, "start": NUM, "pan": NUM}, ["shot"], edits.set_shot)
_reg("set_line", "Change a lyric line: its text, start/end time (seconds), or keywords (words used by drafts to choose footage).",
     {"line": INT, "text": STR, "start": NUM, "end": NUM, "keywords": STR}, ["line"], edits.set_line)
_reg("add_line", "Add a lyric line.", {"text": STR, "start": NUM, "end": NUM}, ["text", "start", "end"], edits.add_line)
_reg("delete_line", "Delete a lyric line.", {"line": INT}, ["line"], edits.delete_line)
_reg("shift_lines", "Move lyric lines earlier (negative) or later (positive) by some seconds; optionally only lines first_line..last_line.",
     {"seconds": NUM, "first_line": INT, "last_line": INT}, ["seconds"], lambda doc, seconds, first_line=1, last_line=None: edits.shift_lines(doc, seconds, first_line, last_line))
_reg("set_title", "Set the video's title.", {"title": STR}, ["title"], edits.set_title)
_reg("set_theme", "Set the theme words used when drafting shots (for example: repentance candle rain).", {"theme": STR}, ["theme"], edits.set_theme)
_reg("set_card", "Create, change or remove the title card or the end card. kind is 'title' or 'end'. enabled=false removes it.",
     {"kind": {"type": "string", "enum": ["title", "end"]}, "enabled": {"type": "boolean"}, "text": STR, "subtitle": STR, "title": STR, "handle": STR, "tagline": STR,
      "appears_at": NUM, "hides_at": NUM}, ["kind"],
     lambda doc, kind, enabled=True, text=None, subtitle=None, title=None, handle=None, tagline=None, appears_at=None, hides_at=None:
     edits.set_card(doc, kind, enabled, text, subtitle, title, handle, tagline, appears_at, hides_at))
_reg("add_popup", "Add an animated 'Subscribe' pop-up at a time.", {"at": NUM, "tagline": STR, "duration": NUM, "click_after": NUM}, ["at"],
     lambda doc, at, tagline="Subscribe for more mezmur", duration=5.0, click_after=2.6: edits.add_popup(doc, at, tagline, duration, click_after))
_reg("remove_popup", "Remove a subscribe pop-up by its number.", {"popup": INT}, ["popup"], edits.remove_popup)
_reg("set_logo", "Set when the corner logo appears and disappears (omit 'disappears' to leave it; pass an empty string to keep it to the end).",
     {"appears": NUM, "disappears": {"type": ["number", "string"]}}, [], edits.set_logo)


@tool("draft_shots", "Write a whole new shot list from the lyric lines using the tagged footage library (replaces the current shots; the user can undo). Use dry=true to preview the plan without changing anything.",
      {"theme": STR, "shots_per_line": {"type": "integer", "minimum": 1, "maximum": 3}, "allow_faces": {"type": "boolean"}, "seed": {"type": "integer"}, "dry": {"type": "boolean"}}, writes=True)
def draft_shots(name, theme=None, shots_per_line=2, allow_faces=False, seed=0, dry=False):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        draft.draft(name, per_line=int(shots_per_line), max_people=2 if allow_faces else 1, theme=theme or None, seed=int(seed), dry=bool(dry))
    return buf.getvalue().strip()


@tool("render", "Start a render job in the editor's queue (it runs in the background; the user sees progress). action: build (video), teaser, thumb (thumbnails), qc, pack (CapCut set). Previews are fast (about a minute); full builds take minutes.",
      {"action": {"type": "string", "enum": ["build", "teaser", "thumb", "qc", "pack"]}, "size": {"type": "string", "enum": ["all", "16x9", "9x16"]},
       "preview": {"type": "boolean"}, "variant": {"type": "string", "enum": ["full", "nosubs", "video_only"]}}, ["action"])
def render(name, action, size="all", preview=True, variant="full"):
    url, token = os.environ.get("STUDIO_URL"), os.environ.get("STUDIO_TOKEN")
    if not url or not token:
        raise ValueError("Renders can only be started from the editor session. Ask the user to use the Render menu.")
    req = urllib.request.Request(url + "/api/job", data=json.dumps({"project": name, "action": action, "size": size, "preview": bool(preview), "variant": variant}).encode(),
                                 headers={"Content-Type": "application/json", "X-Studio-Token": token})
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.load(r)
    return f"Queued: {j['title']} (job {j['id']}). It runs in the background."


@tool("auto_time_lyrics", "Re-time every lyric line from the actual singing (separates the voice, then finds where each line is sung). Runs in the background for a few minutes; the editor updates when it finishes. "
      "It replaces the current line times (the user can undo). Use it when line times look wrong or are only a rough draft.")
def auto_time_lyrics(name):
    url, token = os.environ.get("STUDIO_URL"), os.environ.get("STUDIO_TOKEN")
    if not url or not token:
        raise ValueError("Start this from the editor's Lyrics section, or run: studio align " + name)
    req = urllib.request.Request(url + "/api/job", data=json.dumps({"project": name, "action": "align"}).encode(),
                                 headers={"Content-Type": "application/json", "X-Studio-Token": token})
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.load(r)
    return f"Started: {j['title']} (job {j['id']}). It takes a few minutes; the lyric times change when it finishes. Call get_project afterwards to see them."


# ---------------------------------------------------------------- order, transitions, lyric look, beats, crop, meaning search
_reg("reorder_shot", "Move a shot to another place in the order (1-based). Every shot keeps its own length, so the video length stays the same and the shots between shift.",
     {"shot": INT, "to": INT}, ["shot", "to"], edits.reorder_shot)
_reg("set_transition", "Choose how the cut INTO a shot looks (shot 2 or higher). kinds: " + ", ".join(project.TRANSITIONS) + ". 'fade' is the soft default.",
     {"shot": INT, "kind": {"type": "string", "enum": list(project.TRANSITIONS)}}, ["shot", "kind"], edits.set_transition)
_reg("set_all_transitions", "Use one transition kind for every cut in the video.", {"kind": {"type": "string", "enum": list(project.TRANSITIONS)}}, ["kind"], edits.set_all_transitions)
_reg("set_text_style", "Change how the lyrics look. preset: " + ", ".join(textstyle.PRESETS) + " (karaoke styles fill each word with colour as it is sung). Other fields override the preset: "
     "color and active are #RRGGBB, outline 0-10, scale 0.6-1.8, position bottom|middle|top, karaoke true|false.",
     {"preset": {"type": "string", "enum": list(textstyle.PRESETS)}, "color": STR, "active": STR, "outline": NUM, "scale": NUM,
      "position": {"type": "string", "enum": list(textstyle.POSITIONS)}, "karaoke": {"type": "boolean"}}, [], edits.set_text_style)


@tool("beat_grid", "The song's tempo and beats: bpm, bar starts, and how loud each bar is. Use it to cut on the beat or to find calm and big parts of the song.")
def beat_grid(name):
    b = beats.analyse(name)
    bars = b["bars"]
    peak = max((x["level"] for x in bars), default=1) or 1
    rows = [f"bar {i + 1} at {edits.fmt(x['start'])}: {'#' * max(1, round(10 * x['level'] / peak))}" for i, x in enumerate(bars)]
    return f"About {b['bpm']} beats per minute, {len(b['beats'])} beats, {len(b['downbeats'])} bars (a bar is about {60 / b['bpm'] * 4:.1f}s)." + chr(10) + "Loudness per bar (# = louder):" + chr(10) + chr(10).join(rows)


_reg("snap_cuts_to_beats", "Move every cut to the nearest beat (or bar start with bars_only) if one is within max_move seconds. Keeps shots at least 0.5s long.",
     {"bars_only": {"type": "boolean"}, "max_move": NUM}, [],
     lambda doc, bars_only=False, max_move=0.6: _snap(doc, bars_only, max_move))


def _snap(doc, bars_only, max_move):
    b = beats.analyse(_current[0])
    n = beats.snap_cuts(doc, b["downbeats"] if bars_only else b["beats"], float(max_move))
    return f"Moved {n} cuts onto the {'bar starts' if bars_only else 'beat'} (about {b['bpm']} bpm)."


@tool("auto_crop_vertical", "Set the 9:16 crop position of every shot so the vertical video keeps the part of the picture that stands out (instead of always the middle).", writes=True)
def auto_crop_vertical(name):
    return edits.edit(name, lambda doc: smartcrop.auto_pan(doc, name))


@tool("search_by_meaning", "Search the footage library by what a picture MEANS or looks like, in a full sentence (for example: 'a single candle in a dark room', 'hands raised in prayer at sunrise'). "
      "Better than search_clips for ideas that tags miss. Needs the optional AI install; falls back to words if it is missing.",
      {"query": STR, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, ["query"])
def search_by_meaning(name, query, limit=8):
    if not clipsearch.available():
        return "Search by meaning is not installed on this PC (pip install -r requirements-ai.txt). Use search_clips with words instead."
    tags = draft.load()
    hits = clipsearch.search(query, int(limit))
    return f"{len(hits)} clips that match '{query}' best:" + chr(10) + chr(10).join(f"#{c}  match {s:.2f}  {' '.join(tags.get(c, {}).get('tags', [])[:6])}" for c, s in hits)


@tool("youtube_pack", "Write the YouTube title, description (with lyrics and times) and tags for this video to exports/<name>/YouTube/youtube.txt and return the text.")
def youtube_pack(name):
    path, text = youtube.make(name)
    return text + chr(10) + f"(saved to {paths.rel(path)})"
