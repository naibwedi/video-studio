"""How the lyrics look: colours, size, position, and the karaoke sweep (each word fills with colour as it is sung).

The editor's preview (editor/src/engine/compositor.ts) uses the same numbers, so what you see is what is rendered.
"""
import re

DEFAULT = {"preset": "classic", "color": "#F5F5F5", "active": "#E9BE5C", "outline": 3, "outline_color": "#000000",
           "scale": 1.0, "position": "bottom", "karaoke": False}

PRESETS = {
    "classic": {"color": "#F5F5F5", "active": "#F5F5F5", "outline": 3, "scale": 1.0, "karaoke": False, "position": "bottom"},
    "gold": {"color": "#F5EBD0", "active": "#E9BE5C", "outline": 3, "scale": 1.0, "karaoke": True, "position": "bottom"},
    "karaoke": {"color": "#FFFFFF", "active": "#FFD54A", "outline": 4, "scale": 1.1, "karaoke": True, "position": "bottom"},
    "soft": {"color": "#FFFFFF", "active": "#FFFFFF", "outline": 1, "scale": 0.95, "karaoke": False, "position": "bottom"},
    "bold": {"color": "#FFFFFF", "active": "#FF6B6B", "outline": 5, "scale": 1.25, "karaoke": True, "position": "middle"},
}
POSITIONS = ("bottom", "middle", "top")
LEAD = 0.1          # seconds after a line appears before the sweep starts
SWEEP = 0.9         # the sweep covers this part of the remaining time, so the last word is filled just before the line fades


def clean(style):
    """Validate a style dict from the editor / Claude; unknown keys are dropped, bad values fall back to the defaults."""
    s = {**DEFAULT, **{k: v for k, v in (style or {}).items() if k in DEFAULT}}
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(s["color"])):
        s["color"] = DEFAULT["color"]
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(s["active"])):
        s["active"] = DEFAULT["active"]
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(s["outline_color"])):
        s["outline_color"] = DEFAULT["outline_color"]
    s["color"], s["active"], s["outline_color"] = str(s["color"]).upper(), str(s["active"]).upper(), str(s["outline_color"]).upper()
    s["outline"] = max(0, min(10, float(s["outline"])))
    s["scale"] = round(max(0.6, min(1.8, float(s["scale"]))), 2)
    s["position"] = s["position"] if s["position"] in POSITIONS else "bottom"
    s["karaoke"] = bool(s["karaoke"])
    s["preset"] = str(s["preset"])[:20]
    return s


def ass_colour(hex_rgb, alpha=0):
    h = hex_rgb.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}"


def weights(text):
    """Words of a line and how much of the sweep each gets (about the number of sung syllables, a Ge'ez letter is one syllable)."""
    words = text.split()
    return words, [max(1, len(w)) for w in words]


def sweep_times(text, start, end, pad=0.05):
    """[(word, start_second, end_second)] of the karaoke sweep inside a line."""
    words, w = weights(text)
    if not words:
        return []
    a = start + pad + LEAD
    total = SWEEP * max(0.2, (end - pad) - a)
    out, t, whole = [], a, sum(w)
    for word, k in zip(words, w):
        d = total * k / whole
        out.append((word, round(t, 3), round(t + d, 3)))
        t += d
    return out


def karaoke_text(text, start, end, pad=0.05):
    """ASS text with \\kf tags (centiseconds, summing exactly to the sweep so rounding never drifts)."""
    spans = sweep_times(text, start, end, pad)
    if not spans:
        return text
    lead = round(LEAD * 100)
    parts, used = [f"{{\\k{lead}}}"], 0
    cs_total = round((spans[-1][2] - spans[0][1]) * 100)
    for n, (word, a, b) in enumerate(spans):
        cs = round((b - spans[0][1]) * 100) - used if n < len(spans) - 1 else cs_total - used
        used += cs
        parts.append(f"{{\\kf{max(1, cs)}}}{word}" + (" " if n < len(spans) - 1 else ""))
    return "".join(parts)
