"""Beat grid: tempo, beat times and bar starts of the song, found from the audio itself (numpy only; no extra install).

Method: the loudness change in a few frequency bands (onset strength) -> the tempo that repeats most -> a beat track that follows it
(dynamic programming, like the classic Ellis beat tracker). Bars start where the strongest beat of every 4 falls.
Cached in .cache/beats, keyed by the song file.
"""
import json, os, subprocess
import numpy as np
from . import paths, project

SR, N_FFT, HOP = 22050, 1024, 256
FPS = SR / HOP


def _samples(path):
    raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw[: len(raw) // 4 * 4], dtype=np.float32)


def onset_strength(x):
    """Frame-by-frame 'something new started' signal (positive spectral change in 4 bands, log compressed)."""
    if len(x) < N_FFT * 4:
        raise ValueError("The song is too short to find a beat.")
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (len(x) - N_FFT) // HOP
    frames = np.lib.stride_tricks.sliding_window_view(x, N_FFT)[::HOP][:n] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    edges = [30, 150, 600, 2500, 9000]
    bands = np.stack([mag[:, (freqs >= a) & (freqs < b)].sum(axis=1) for a, b in zip(edges[:-1], edges[1:])], axis=1)
    lg = np.log1p(bands * 8)
    flux = np.maximum(0, np.diff(lg, axis=0, prepend=lg[:1]))
    env = flux.sum(axis=1)
    env = env - np.convolve(env, np.ones(int(FPS)) / int(FPS), mode="same")      # remove the slow level
    env = np.maximum(env, 0)
    return env / (env.std() + 1e-9)


def tempo(env, lo=60, hi=180):
    """Beats per minute whose period repeats most in the onset signal (with a mild liking for 90-130 bpm)."""
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    best, best_s = 0.0, -1.0
    for bpm in np.arange(lo, hi + 0.5, 0.5):
        lag = FPS * 60 / bpm
        i = int(round(lag))
        if i + 2 >= len(ac):
            continue
        s = ac[i] + 0.5 * ac[min(len(ac) - 1, 2 * i)] + 0.25 * ac[int(round(lag / 2))]      # the beat, its double and its half should repeat
        s *= np.exp(-0.5 * (np.log2(bpm / 110) / 0.8) ** 2)                                  # prefer the common range
        if s > best_s:
            best, best_s = bpm, s
    return float(best)


def track(env, bpm, tight=40.0):
    """Beat frames that sit on strong onsets and stay about one period apart."""
    period = FPS * 60 / bpm
    n = len(env)
    score, prev = env.copy(), np.full(n, -1)
    lo, hi = int(period / 2), int(period * 2)
    lags = np.arange(lo, hi + 1)
    pen = -tight * (np.log(lags / period)) ** 2
    for i in range(lo, n):
        js = i - lags
        ok = js >= 0
        cand = score[js[ok]] + pen[ok]
        k = int(np.argmax(cand))
        if cand[k] > 0:
            score[i] = env[i] + cand[k]
            prev[i] = js[ok][k]
    tail = int(np.argmax(score[max(0, n - int(period * 2)):])) + max(0, n - int(period * 2))
    beats = [tail]
    while prev[beats[-1]] >= 0:
        beats.append(int(prev[beats[-1]]))
    return np.array(beats[::-1])


def analyse(name):
    p = project.load(name)
    audio = p["_audio"]
    cache = os.path.join(paths.CACHE, "beats", f"{name}.json")
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(audio):
        return json.load(open(cache))
    x = _samples(audio)
    env = onset_strength(x)
    bpm = tempo(env)
    frames = track(env, bpm)
    beats = frames / FPS
    # the bar starts: of the 4 possible phases, the one whose beats carry the most onset energy
    energy = np.array([env[max(0, f - 1):f + 2].sum() for f in frames])
    phase = int(np.argmax([energy[k::4].sum() for k in range(4)])) if len(frames) >= 8 else 0
    downs = beats[phase::4]
    gaps = np.diff(beats)
    real_bpm = round(60 / float(np.median(gaps)), 1) if len(gaps) else bpm
    # how loud each bar is (relative), so Claude and the editor can tell calm parts from big ones
    peak = float(np.abs(x).max() or 1)
    bars = []
    for a, b in zip(downs, list(downs[1:]) + [len(x) / SR]):
        seg = x[int(a * SR):int(b * SR)]
        bars.append({"start": round(float(a), 2), "level": round(float(np.sqrt((seg ** 2).mean()) / peak) if len(seg) else 0.0, 3)})
    out = {"bpm": real_bpm, "beats": [round(float(b), 3) for b in beats], "downbeats": [round(float(b), 3) for b in downs], "bars": bars,
           "seconds": round(len(x) / SR, 2)}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump(out, open(cache, "w"))
    return out


# ---------------------------------------------------------------- using the grid on a doc (shared by the Claude tools)
def nearest(grid, t):
    return min(grid, key=lambda g: abs(g - t)) if grid else t


def snap_cuts(doc, grid, max_move=0.6, min_shot=0.5):
    """Move each cut to the nearest beat (not further than max_move seconds, never making a shot shorter than min_shot). Returns how many moved."""
    moved = 0
    shots = doc["shots"]
    for i in range(1, len(shots)):
        t = shots[i]["at"]
        cand = [g for g in grid if abs(g - t) <= max_move]
        if not cand:
            continue
        g = round(min(cand, key=lambda x: abs(x - t)), 2)
        lo = shots[i - 1]["at"] + min_shot
        hi = (shots[i + 1]["at"] if i + 1 < len(shots) else doc["duration"]) - min_shot
        if lo <= g <= hi and abs(g - t) > 0.005:
            shots[i]["at"] = g
            moved += 1
    return moved

