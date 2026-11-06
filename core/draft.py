"""Clip tags and `studio draft`: write a first shot list for a project from its lyric lines.

Every clip in library/stock is tagged in library/tags.json:  {"6988904": {"people": 0, "tags": ["roots", "moss", ...]}}
  people: 0 none, 1 silhouette or hands only (fine), 2 a face / person clearly visible (avoided by default)
A lyric line can carry "keywords": ["chains", "dark"]; otherwise the project's "theme" words are used.
"""
import json, os, re
from collections import Counter
from . import paths, project, stock

TAGS = os.path.join(paths.LIBRARY, "tags.json")

# Words you can use in a theme/keywords that stand for several tags.
THEMES = {
    "repentance": "dark rain chains thorns cracked dry candle roots lonely ruins gate smoke bowed night",
    "sorrow": "rain dark night bowed lonely clouds window water gray fog",
    "mourning": "candle dark rain night smoke snuffed lonely",
    "prayer": "candle church altar icon censer incense hands book bible",
    "praise": "sunrise light rays church altar candle sky clouds hope",
    "hope": "sunrise dawn light rays fog mountain sky hope",
    "journey": "road path desert mountain sand footsteps walking lonely dusk",
    "nature": "forest trees leaves grass wheat water sea",
    "bondage": "chains lock gate thorns dark rust",
    "emptiness": "dry cracked desert dead bare empty ruins",
    "church": "church altar icon candle censer incense stone chapel book",
}


def load():
    return json.load(open(TAGS, encoding="utf-8")) if os.path.exists(TAGS) else {}


def save(tags):
    json.dump(tags, open(TAGS, "w", encoding="utf-8"), indent=0, sort_keys=True)


def add_tag(clip_id, words, people=0):
    tags = load()
    cur = tags.get(str(clip_id), {"people": people, "tags": []})
    cur["tags"] = sorted(set(cur["tags"]) | set(words.split()))
    cur["people"] = people
    tags[str(clip_id)] = cur
    save(tags)
    return cur


def norm(word):
    """candles -> candle (so plurals match)."""
    w = word.lower()
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def expand(words):
    out = []
    for w in words:
        out += THEMES.get(w.lower(), w).split()
    return [norm(w) for w in out]


def clip_seconds(tags, cid):
    """Length of a clip (cached in tags.json)."""
    info = tags[cid]
    if "dur" not in info:
        info["dur"] = round(stock.duration_of(paths.stock_path(cid)), 1)
    return info["dur"]


def pick(tags, wanted, used, max_people, need_seconds, rng_key, usage=None):
    best, best_score = None, -99.0
    usage = usage or Counter()
    ordered = sorted(tags, key=lambda c: (hash((c, rng_key)) % 1000, c))   # stable but varied tie-break
    for cid in ordered:
        info = tags[cid]
        if cid in used or info["people"] > max_people or not os.path.exists(paths.stock_path(cid)):
            continue
        hit = len({norm(t) for t in info["tags"]} & set(wanted))
        if hit == 0:
            continue
        seen = sum(usage[norm(t)] for t in info["tags"])          # how often this look was already used
        score = hit + (0.3 if info["people"] == 0 else 0) - 0.18 * seen
        if score > best_score and clip_seconds(tags, cid) >= need_seconds:
            best, best_score = cid, score
    return best


def draft(name, per_line=2, max_people=1, intro=3, outro=3, theme=None, seed=0, dry=False):
    p = project.load(name)
    lines = p["subtitles"]["lines"]
    if not lines:
        raise SystemExit("The project has no lyric lines yet (subtitles.lines).")
    tags = load()
    if not tags:
        raise SystemExit("library/tags.json is empty.")
    theme_words = expand(theme.split() if theme else (p.get("theme") or ["nature", "hope"]))
    used, shots, why, usage = set(), [], [], Counter()

    def add(at, wanted, label, seglen):
        cid = pick(tags, wanted, used, max_people, seglen + 1.5, f"{seed}-{label}", usage)
        if cid is None:
            cid = pick(tags, theme_words, used, max_people, seglen + 1.5, f"{seed}-{label}", usage)
        if cid is None:
            return
        used.add(cid)
        usage.update(norm(t) for t in tags[cid]["tags"])
        dur = clip_seconds(tags, cid)
        shots.append({"at": at, "clip": cid, "start": round(max(0.0, min(2.0, dur - seglen - 1.2)), 1), "pan": 0.5})
        why.append((at, cid, label))

    first = float(lines[0]["start"])
    last_end = float(lines[-1]["end"])
    if intro and first > 1.0:
        step = first / intro
        for k in range(intro):
            add(round(step * k, 2), expand(["nature", "fog", "moon", "dawn", "quiet"]), "intro", step)
    for i, ln in enumerate(lines, 1):
        words = expand(ln.get("keywords") or []) or theme_words
        span = float(ln["end"]) - float(ln["start"])
        for k in range(per_line):
            at = f"L{i}" if k == 0 else (f"L{i}m" if per_line == 2 else round(float(ln["start"]) + span * k / per_line, 2))
            add(at, words, f"line {i}", span / per_line + 0.6)
    outro_t = p["duration"] - last_end
    if outro and outro_t > 2.0:
        step = outro_t / outro
        for k in range(outro):
            add(round(last_end + step * k + 0.2, 2), expand(["sunrise", "church", "candle", "hope", "light"]), "outro", step)

    if dry:
        for at, cid, label in why:
            print(f"  {str(at):>6}  {cid:>9}  {label:8} {' '.join(tags[cid]['tags'][:5])}")
        print(f"(dry run, {len(shots)} shots, nothing written)")
        return shots

    def mutate(raw):
        raw["shots"] = shots
    project.save_raw(name, mutate)
    save(tags)   # keeps newly measured clip lengths
    for at, cid, label in why:
        print(f"  {str(at):>6}  {cid:>9}  {label:8} {' '.join(tags[cid]['tags'][:5])}")
    print(f"wrote {len(shots)} shots to projects/{name}/project.json (backup: project.json.bak)")
    return shots


def find(words):
    """List library clips whose tags match all words."""
    tags = load()
    want = {norm(w) for w in words}
    return [(cid, i) for cid, i in sorted(tags.items()) if want <= {norm(t) for t in i["tags"]}]


def search(query, limit=12, faces=False):
    """Library clips matching the words of `query` (theme words like 'repentance' count too), best first."""
    tags = load()
    words = set(expand(query.split()))
    scored = []
    for cid, info in tags.items():
        if not os.path.exists(paths.stock_path(cid)) or (info["people"] == 2 and not faces):
            continue
        hit = len(words & {norm(t) for t in info["tags"]})
        if hit:
            scored.append((hit + (0.2 if info["people"] == 0 else 0), cid, info))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"clip": cid, "tags": info["tags"], "people": info["people"], "seconds": info.get("dur")} for _, cid, info in scored[:limit]]
