"""Exact lyric timing from the singing.

1. Separate the voice from the music (demucs), cached per song.
2. Let a speech model (Meta's MMS aligner) find where each lyric line's sounds are sung in the isolated voice. Words are matched by their
   Latin transliteration (uroman), and a wildcard absorbs chanting or humming that is not in your lyrics.
3. Snap each line's edges to the nearest real breath in the voice's loudness.
If the speech model is unavailable, a fallback fits the lines to the quiet valleys by loudness and text length (less reliable).
`clarity` says how sure the result is. Lines can always be fixed by hand afterwards.
"""
import os, shutil, subprocess, sys, tempfile
import numpy as np
from . import edits, paths, project

HOP = 0.02          # seconds per envelope frame
SR = 44100


# ---------------------------------------------------------------- 1. the voice
def vocals_path(name):
    return os.path.join(paths.CACHE, "vocals", f"{name}.wav")


def _load_audio(path):
    """Stereo float32 at 44.1 kHz via ffmpeg."""
    raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy()


def separate(name, log=print):
    """Return the path of the isolated vocals for this project's song (made once, then reused)."""
    audio = project.load(name)["_audio"]
    out = vocals_path(name)
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(audio):
        return out
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    log("separating the voice from the music (first time only: about a minute or two)...")
    model = get_model("htdemucs")
    model.eval()
    wav = torch.from_numpy(_load_audio(audio))
    ref = wav.mean(0)
    norm = (wav - ref.mean()) / (ref.std() + 1e-8)
    with torch.no_grad():
        sources = apply_model(model, norm[None], device="cpu", split=True, overlap=0.15, shifts=0, progress=False)[0]
    voice = sources[model.sources.index("vocals")] * (ref.std() + 1e-8) + ref.mean()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sf.write(out, voice.numpy().T, SR)
    log("voice separated")
    return out


# ---------------------------------------------------------------- 2. loudness of the voice and its valleys
def envelope_db(samples, sr=SR, hop=HOP):
    """Loudness per frame in dB (smoothed over ~0.1 s)."""
    n = int(sr * hop)
    frames = len(samples) // n
    x = samples[: frames * n].reshape(frames, n)
    rms = np.sqrt((x.astype(np.float64) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    k = 5
    return np.convolve(np.pad(db, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")


def find_valleys(env, hop=HOP, min_prom_db=4.0, min_sep=0.8, window=2.0):
    """Quiet gaps between phrases. Each valley: centre time, prominence in dB (how much quieter than its surroundings) and its start/end."""
    w = int(window / hop)
    sm = np.convolve(np.pad(env, (3, 3), mode="edge"), np.ones(7) / 7, mode="valid")
    cands = []
    for i in range(2, len(sm) - 2):
        if sm[i] <= sm[i - 1] and sm[i] < sm[i + 1]:
            left, right = sm[max(0, i - w): i], sm[i + 1: i + 1 + w]
            if not len(left) or not len(right):
                continue
            prom = min(left.max(), right.max()) - sm[i]
            if prom >= min_prom_db:
                cands.append((i, prom))
    cands.sort(key=lambda c: -c[1])           # keep the deepest valley within any min_sep window
    kept = []
    for i, prom in cands:
        if all(abs(i - j) * hop >= min_sep for j, _ in kept):
            kept.append((i, prom))
    kept.sort()
    out = []
    for i, prom in kept:
        level = sm[i] + min(6.0, prom * 0.5)  # the valley is where it is within a few dB of its floor
        a = i
        while a > 0 and sm[a - 1] <= level and (i - a) * hop < 2.5:
            a -= 1
        b = i
        while b < len(sm) - 1 and sm[b + 1] <= level and (b - i) * hop < 2.5:
            b += 1
        out.append({"t": i * hop, "prom": float(prom), "start": a * hop, "end": (b + 1) * hop})
    return out


def sung_span(env, hop=HOP, margin_db=14.0):
    """First and last moment the voice is clearly present."""
    floor, peak = np.percentile(env, 8), np.percentile(env, 95)
    on = np.where(env > max(floor + margin_db, peak - 30))[0]
    if not len(on):
        return 0.0, len(env) * hop
    return on[0] * hop, (on[-1] + 1) * hop


# ---------------------------------------------------------------- 3. fit the lyric lines
def fit_lines(valleys, texts, t_first, t_last):
    """Choose len(texts)-1 valleys (in order) so that line lengths follow the amount of text and the valleys are deep.
    Returns (list of (start, end) per line, clarity 0..1)."""
    n = len(texts)
    span = max(0.1, t_last - t_first)
    if n == 1:
        return [(t_first, t_last)], 1.0
    weights = np.array([max(1, len(t.replace(" ", ""))) for t in texts], dtype=float)
    expect = t_first + span * np.cumsum(weights)[:-1] / weights.sum()          # expected boundary after each line but the last
    cands = [v for v in valleys if t_first < v["t"] < t_last]
    m = len(cands)
    if m < n - 1:
        starts = [t_first + span * i / n for i in range(n)]
        return [(starts[i] + (0.1 if i else 0.0), (starts[i + 1] if i + 1 < n else t_last) - 0.2) for i in range(n)], 0.0
    sigma = 0.16 * span / max(1, n) * 3.0 + 0.5
    NEG = -1e18
    score = np.full((n - 1, m), NEG)
    back = np.zeros((n - 1, m), dtype=int)

    def local(i, j):                                                              # how good is valley j as the boundary after line i
        v = cands[j]
        return v["prom"] / 6.0 - ((v["t"] - expect[i]) / sigma) ** 2 * 0.5
    for j in range(m):
        score[0, j] = local(0, j)
    for i in range(1, n - 1):
        for j in range(m):
            best, arg = NEG, 0
            for k in range(j):
                if score[i - 1, k] > best:
                    best, arg = score[i - 1, k], k
            if best > NEG:
                score[i, j], back[i, j] = best + local(i, j), arg
    j = int(np.argmax(score[n - 2]))
    chosen = [j]
    for i in range(n - 2, 0, -1):
        j = int(back[i, j])
        chosen.append(j)
    chosen = [cands[j] for j in reversed(chosen)]
    lines, prev = [], t_first
    for k in range(n):
        end = chosen[k]["start"] if k < n - 1 else t_last
        lines.append((round(prev, 2), round(max(end, prev + 0.3), 2)))
        prev = chosen[k]["end"] if k < n - 1 else prev
    chosen_prom = np.array([c["prom"] for c in chosen])
    rest = sorted((v["prom"] for v in cands if v not in chosen), reverse=True)
    clarity = float(np.clip((chosen_prom.min() - (rest[0] if rest else 0)) / 8.0 + 0.5, 0, 1))   # chosen valleys clearly deeper than the runner-up
    return lines, clarity


# ---------------------------------------------------------------- 2b. where the words are sung (speech model)
def ctc_lines(voice_path, texts, log=print):
    """Per line (start, end, confidence) from a CTC forced alignment of the romanised lyrics against the isolated voice."""
    import re
    import soundfile as sf
    import torch
    import torchaudio
    import torchaudio.functional as F
    import uroman
    from torchaudio.pipelines import MMS_FA as bundle
    data, sr = sf.read(voice_path, dtype="float32")
    wav = torchaudio.functional.resample(torch.from_numpy(data.mean(1))[None], sr, 16000)
    log("loading the speech model (first time only: it downloads about 1 GB)...")
    model = bundle.get_model()
    log("listening for the words...")
    with torch.inference_mode():
        emission, _ = model(wav)
    emission = torch.log_softmax(torch.cat([emission, torch.zeros(emission.shape[0], emission.shape[1], 1)], dim=2), dim=-1)
    dictionary = bundle.get_dict()
    u = uroman.Uroman()
    roman = []
    for t in texts:
        r = re.sub(r"[^a-z']", "", u.romanize_string(t, lcode="tir").lower())
        roman.append(r or "a")
    tokens, slices = [dictionary["*"]], []
    for r in roman:
        s = len(tokens)
        tokens.extend(dictionary[c] for c in r if c in dictionary)
        slices.append((s, len(tokens)))
        tokens.append(dictionary["*"])
    alignment, scores = F.forced_align(emission, torch.tensor([tokens], dtype=torch.int32), blank=0)
    spans = F.merge_tokens(alignment[0], scores[0].exp())
    ratio = wav.shape[1] / emission.shape[1] / 16000
    out = []
    for s, e in slices:
        sp = spans[s:e]
        out.append((sp[0].start * ratio, sp[-1].end * ratio, float(np.mean([x.score for x in sp]))))
    return out


def snap(lines, valleys, reach=0.7):
    """Move each line's start to the end of the nearest breath, and its end to the start of the nearest breath, when one is close.
    Returns (lines, number of edges that found a breath)."""
    out, hits = [], 0
    for s, e in lines:
        starts = [v["end"] for v in valleys if abs(v["end"] - s) <= reach]
        ends = [v["start"] for v in valleys if abs(v["start"] - e) <= reach]
        hits += bool(starts) + bool(ends)
        s2 = min(starts, key=lambda x: abs(x - s)) if starts else s
        e2 = min(ends, key=lambda x: abs(x - e)) if ends else e
        out.append((round(s2, 2), round(max(e2, s2 + 0.3), 2)))
    for i in range(len(out) - 1):                                   # lines never overlap
        if out[i][1] > out[i + 1][0]:
            mid = round((out[i][1] + out[i + 1][0]) / 2, 2)
            out[i], out[i + 1] = (out[i][0], mid), (mid, out[i + 1][1])
    return out, hits


# ---------------------------------------------------------------- the whole thing
def align(name, dry=False, log=print):
    """Time the project's lyric lines from the singing. Returns a report dict; writes the project unless dry."""
    import soundfile as sf
    doc = edits.load_doc(name)
    texts = [l["text"] for l in doc["lines"]]
    if not texts:
        raise ValueError("The project has no lyric lines yet. Paste the lyrics first.")
    voice = separate(name, log)
    log("analysing the singing...")
    data, sr = sf.read(voice, dtype="float32")
    mono = data.mean(1) if data.ndim > 1 else data
    env = envelope_db(mono, sr)
    valleys = find_valleys(env)
    method = "speech model"
    try:
        spans = ctc_lines(voice, texts, log)
        lines, hits = snap([(s, e) for s, e, _ in spans], valleys)
        score = float(np.clip((np.median([c for *_, c in spans]) - 0.1) / 0.4, 0, 1))      # how well the sounds matched the words
        clarity = round(0.5 * score + 0.5 * hits / (2 * len(lines)), 2)                    # ...and how many edges sit on a real breath
        t_first, t_last = lines[0][0], lines[-1][1]
    except Exception as e:                                          # offline, or the model could not run
        log(f"speech model not available ({type(e).__name__}); using loudness only (less reliable)")
        method = "loudness only"
        t_first, t_last = sung_span(env)
        lines, clarity = fit_lines(valleys, texts, t_first, t_last)
    report = {"lines": [{"text": t, "old": [l["start"], l["end"]], "new": list(n)} for t, l, n in zip(texts, doc["lines"], lines)],
              "clarity": clarity, "valleys": len(valleys), "sung": [round(t_first, 2), round(t_last, 2)], "method": method}
    if not dry:
        for l, (a, b) in zip(doc["lines"], lines):
            l["start"], l["end"] = a, b
        edits.save_doc(name, doc)
        log(f"wrote {len(lines)} line times (clarity {clarity:.2f})")
    return report
