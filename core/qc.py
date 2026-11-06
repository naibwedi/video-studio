"""`studio qc`: look for problems before you watch.

Project checks (no render needed): lyric lines out of order / too long, shots too short, missing clips, overlays past the end.
File checks (on a rendered video): black frames, long silences, loudness and clipping.
"""
import os, re, subprocess
from . import paths, project


def project_checks(p):
    notes = []   # (level, text)
    lines = p["subtitles"]["lines"]
    dur = p["duration"]
    for i, ln in enumerate(lines, 1):
        a, b = float(ln["start"]), float(ln["end"])
        if b <= a:
            notes.append(("ERROR", f"lyric line {i}: ends before it starts ({a} -> {b})"))
        if b - a > 10:
            notes.append(("WARN", f"lyric line {i}: stays on screen {b - a:.1f}s (long)"))
        if a < 0 or b > dur + 0.01:
            notes.append(("ERROR", f"lyric line {i}: outside the video (0 - {dur:.1f}s)"))
        if i > 1 and a < float(lines[i - 2]["end"]) - 0.01:
            notes.append(("WARN", f"lyric lines {i - 1} and {i} overlap"))
    cuts = [s["at"] for s in p["_shots"]] + [dur]
    for i, s in enumerate(p["_shots"]):
        if cuts[i + 1] - cuts[i] < 1.5:
            notes.append(("WARN", f"shot {i + 1} ({s['clip']}) is only {cuts[i + 1] - cuts[i]:.1f}s long"))
        if s["at"] > dur:
            notes.append(("ERROR", f"shot {i + 1} starts after the end of the song"))
    if p["_shots"] and p["_shots"][0]["at"] > 0.01:
        notes.append(("WARN", "the first shot does not start at 0 (it will be moved to 0)"))
    ov = p["overlays"]
    for key in ("title_card", "end_card"):
        if ov.get(key) and float(ov[key].get("in", 0)) > dur:
            notes.append(("ERROR", f"{key} starts after the end"))
    for e in ov.get("popups") or []:
        t = e if isinstance(e, (int, float)) else e.get("at", 0)
        length = 5.0 if isinstance(e, (int, float)) else e.get("dur", 5.0)
        if t + length > dur:
            notes.append(("WARN", f"the subscribe pop-up at {t}s would run past the end of the video"))
    return notes


def file_checks(path, dur, fade_in=1.0, fade_out=2.5):
    notes, info = [], {}
    ff = paths.ffmpeg()
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", path, "-vf", "blackdetect=d=0.4:pix_th=0.04",
                        "-af", "ebur128=peak=true,silencedetect=n=-50dB:d=1.5", "-f", "null", "-"], capture_output=True, text=True)
    err = r.stderr
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", err):
        a, b = float(m[1]), float(m[2])
        if (a < 0.05 and b <= fade_in + 0.6) or b >= dur - 0.1:
            continue   # the fade in / fade out
        notes.append(("WARN", f"black frames from {a:.1f}s to {b:.1f}s"))
    for m in re.finditer(r"silence_start: ([\d.]+)", err):
        a = float(m[1])
        if a < dur - fade_out - 1:
            notes.append(("WARN", f"silence starting at {a:.1f}s"))
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    if lufs:
        info["loudness"] = float(lufs[-1])
        if info["loudness"] > -9:
            notes.append(("WARN", f"very loud: {info['loudness']} LUFS (YouTube turns it down; -14 is typical)"))
        elif info["loudness"] < -22:
            notes.append(("WARN", f"quiet: {info['loudness']} LUFS"))
    if peak:
        info["peak"] = float(peak[-1])
        if info["peak"] > -0.5:
            notes.append(("WARN", f"audio peaks at {info['peak']} dBFS (may clip)"))
    return notes, info


def run(name, file=None):
    p = project.load(name)
    notes = project_checks(p)
    target = file or os.path.join(paths.EXPORTS, name, f"{name}_16x9.mp4")
    info = {}
    if os.path.exists(target):
        n2, info = file_checks(target, p["duration"], p["fade_in"], p["fade_out"])
        notes += n2
    else:
        print(f"(no rendered video at {paths.rel(target)}: only project checks)")
    for level, text in notes:
        print(f"  {level:5} {text}")
    if info:
        print(f"  info  loudness {info.get('loudness', '?')} LUFS, peak {info.get('peak', '?')} dBFS")
    errors = [n for n in notes if n[0] == "ERROR"]
    print(f"{len(errors)} errors, {len(notes) - len(errors)} warnings" if notes else "No problems found.")
    return not errors
