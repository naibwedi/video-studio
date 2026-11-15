"""YouTube pack: title, description (with lyrics and times), tags and hashtags, written to exports/<name>/YouTube/.

This is a ready-to-paste draft built from the project; nothing is uploaded. Claude can polish the wording when asked.
"""
import json, os, re
from . import paths, project

BASE_TAGS = ["Eritrean Orthodox", "Tewahedo mezmur", "Tigrinya mezmur", "Orthodox Tewahedo", "ኦርቶዶክስ ተዋህዶ", "መዝሙር", "Eritrean mezmur", "Orthodox hymn",
             "new mezmur", "lyrics video", "ትግርኛ"]


def clock(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def credits(p):
    """Credit lines for the photos used that need one (CC BY / CC BY-SA); public-domain and CC0 need none."""
    try:
        src = json.load(open(os.path.join(paths.ROOT, "library", "sources.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for sh in p.get("_shots") or p.get("shots") or []:
        s = src.get(str(sh.get("clip")))
        if s and str(s.get("license", "")).upper().startswith("CC BY"):
            line = f"{s['title'].rsplit('.', 1)[0]} - {re.sub('<[^>]+>', '', s.get('author', '')).strip()} - {s['license']} - {s.get('page', '')}"
            if line not in out:
                out.append(line)
    return out


def make(name):
    p = project.load(name)
    ch = p["channel"]
    title = p["title"] or name
    lines = sorted(p["subtitles"]["lines"], key=lambda l: l["start"])
    theme = [w for w in p.get("theme") or []]
    yt_title = f"{title} | New Tigrinya Orthodox Mezmur (Lyrics) | {ch['name']}"[:100]
    desc = [f"{title}", f"Tigrinya Orthodox Tewahedo mezmur with lyrics, from {ch['name']}.", "",
            "Subscribe for more mezmur: " + (ch.get("handle") or ""), "Please like, share and leave a prayer or a blessing in the comments.", ""]
    if lines:
        desc += ["Lyrics / ግጥሚ:", ""]
        desc += [f"{clock(l['start'])}  {l['text']}" for l in lines]
        desc += [""]
    cred = credits(p)
    if cred:
        desc += ["Image credits:"] + cred + [""]
    desc += ["#EritreanOrthodox #TewahedoMezmur #TigrinyaMezmur " + " ".join("#" + w.replace(" ", "") for w in theme[:3]).strip()]
    tags = list(dict.fromkeys(theme + BASE_TAGS + [title]))
    total = 0
    kept = []
    for t in tags:                                     # YouTube allows about 500 characters of tags
        if total + len(t) + 1 > 480:
            break
        kept.append(t)
        total += len(t) + 1
    text = ("TITLE\n" + yt_title + "\n\nDESCRIPTION\n" + "\n".join(desc).strip() + "\n\nTAGS (comma separated)\n" + ", ".join(kept) + "\n")
    out = os.path.join(paths.EXPORTS, name, "YouTube")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "youtube.txt")
    open(path, "w", encoding="utf-8").write(text)
    return path, text
