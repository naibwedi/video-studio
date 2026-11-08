"""Creative effects for the render: a colour look and a camera move per shot, glow, drifting light dust, light flashes on cuts, and a soft pulse on the beat.

Everything is plain ffmpeg (no extra install). The look, the move and the glow belong to a shot (they are rendered into its cached segment);
dust, flashes and the beat pulse are applied once over the finished video.
"""
import os, subprocess
from . import paths

# name -> (label, ffmpeg filters applied after the base grade)
LOOKS = {
    "warm": ("Warm gold", "colorbalance=rs=0.06:gs=0.01:bs=-0.07:rm=0.05:bm=-0.05:rh=0.07:bh=-0.08,eq=saturation=1.08:contrast=1.04"),
    "night": ("Night blue", "colorbalance=rs=-0.06:bs=0.10:rm=-0.04:bm=0.08:bh=0.05,eq=brightness=-0.05:saturation=0.9:contrast=1.08"),
    "film": ("Faded film", "eq=saturation=0.78:contrast=0.92:brightness=0.02,curves=all='0/0.06 0.5/0.5 1/0.94',colorbalance=rs=0.03:bs=-0.03,noise=alls=6:allf=t+u"),
    "mono": ("Black and white", "hue=s=0,eq=contrast=1.15:brightness=-0.02,colorbalance=rm=0.03:bm=-0.03"),
    "dramatic": ("Deep contrast", "eq=contrast=1.22:saturation=1.05:brightness=-0.03,vignette=PI/4"),
    "dawn": ("Soft dawn", "colorbalance=rs=0.05:gs=-0.01:bs=-0.03:rh=0.08:gh=0.03:bh=-0.05,eq=saturation=1.1:brightness=0.025:contrast=0.98"),
}
MOVES = {"in": "Slow push in", "out": "Slow pull out", "left": "Drift left", "right": "Drift right", "up": "Rise", "still": "Hold still"}
DEFAULT_FX = {"glow": 0.0, "dust": False, "pulse": 0.0, "flash": []}


def clean(fx):
    """Validate the project-wide effects: glow 0..1 (soft bloom), dust on/off, pulse 0..0.12 (beat pulse), flash = times (seconds) of light flashes."""
    out = dict(DEFAULT_FX)
    fx = fx if isinstance(fx, dict) else {}
    try:
        out["glow"] = round(min(1.0, max(0.0, float(fx.get("glow", 0)))), 2)
        out["pulse"] = round(min(0.12, max(0.0, float(fx.get("pulse", 0)))), 3)
    except (TypeError, ValueError):
        pass
    out["dust"] = bool(fx.get("dust"))
    fl = []
    for t in fx.get("flash") or []:
        try:
            fl.append(round(float(t), 2))
        except (TypeError, ValueError):
            pass
    out["flash"] = sorted(set(fl))[:60]
    return out


def look_filter(name):
    return LOOKS[name][1] if name in LOOKS else ""


def glow_filter(amount):
    """Bloom: a blurred, brightened copy laid over the picture with 'screen' blending."""
    if not amount:
        return ""
    return (f"format=gbrp,split[ga][gb];[gb]gblur=sigma=26,eq=brightness=-0.10:contrast=1.2[gc];"
            f"[ga][gc]blend=all_mode=screen:all_opacity={0.18 + 0.45 * amount:.2f}")


def move_filter(move, W, H, L):
    """Camera move over a 16:9 shot of L seconds. None -> the older slow drift."""
    if move == "still":
        return f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    if move in ("in", "out"):
        k = "(1+0.13*t/%.3f)" % L if move == "in" else "(1.13-0.13*t/%.3f)" % L
        return (f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                f"scale=w='trunc({W}*{k}/2)*2':h='trunc({H}*{k}/2)*2':eval=frame:flags=bicubic,crop={W}:{H}")
    if move in ("left", "right", "up"):
        sx, sy = int(W * 1.10) // 2 * 2, int(H * 1.10) // 2 * 2
        x = {"left": f"(iw-ow)*(1-t/{L:.3f})", "right": f"(iw-ow)*(t/{L:.3f})", "up": "(iw-ow)/2"}[move]
        y = f"(ih-oh)*(1-t/{L:.3f})" if move == "up" else "(ih-oh)/2"
        return f"scale={sx}:{sy}:flags=lanczos:force_original_aspect_ratio=increase,setsar=1,crop={W}:{H}:x='{x}':y='{y}'"
    return None


def light_expr(flashes, beats, pulse):
    """An ffmpeg `eq` brightness expression: a quick warm flash at each flash time and a faint pulse on each beat."""
    # max(t-x,0) keeps the exponent <= 0: exp() of a large positive number overflows to infinity, and infinity * 0 is NaN (a black frame)
    terms = [f"between(t,{t:.2f},{t + 0.7:.2f})*0.17*exp(-8*max(t-{t:.2f},0))" for t in flashes]
    if pulse:
        terms += [f"between(t,{b:.2f},{b + 0.4:.2f})*{pulse:.3f}*exp(-10*max(t-{b:.2f},0))" for b in beats]
    return "+".join(terms)


def dust_video(W, H, fps, seconds=12):
    """A looping clip of slow, soft, golden light specks on black (made once and cached). Blend it over the video with 'screen'."""
    import numpy as np
    from PIL import Image, ImageFilter
    out = os.path.join(paths.CACHE, "fx", f"dust_{W}x{H}_{fps}.mp4")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rng = np.random.default_rng(7)
    n = 46
    sprites, parts = {}, []
    for i in range(n):
        r = int(H * rng.uniform(0.004, 0.017))
        big = i % 9 == 0
        if big:
            r = int(H * rng.uniform(0.02, 0.035))
        parts.append(dict(x=rng.uniform(0, W), y=rng.uniform(0, H), r=max(2, r), a=rng.uniform(0.35, 0.95) * (0.55 if big else 1),
                          vy=(2 if big else 1), wob=int(rng.integers(1, 4)), ph=rng.uniform(0, 6.28), amp=rng.uniform(0.01, 0.04) * W, tw=int(rng.integers(1, 4))))
    for pt in parts:
        s = pt["r"] * 4
        yy, xx = np.mgrid[:s, :s]
        d = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (pt["r"])
        sprites[id(pt)] = np.clip(1.0 - d, 0, 1) ** 1.6
    frames = int(seconds * fps)
    cmd = [paths.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", out + ".tmp.mp4"]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    colour = np.array([255, 226, 160], dtype=np.float32)
    for f in range(frames):
        ph = f / frames
        canvas = np.zeros((H, W, 3), dtype=np.float32)
        for pt in parts:
            x = (pt["x"] + pt["amp"] * np.sin(2 * np.pi * pt["wob"] * ph + pt["ph"])) % W
            y = (pt["y"] - pt["vy"] * H * ph) % H
            tw = 0.65 + 0.35 * np.sin(2 * np.pi * pt["tw"] * ph + pt["ph"])
            sp = sprites[id(pt)] * pt["a"] * tw
            s = sp.shape[0]
            x0, y0 = int(x - s / 2), int(y - s / 2)
            for ox in (0, -W, W) if x0 < 0 or x0 + s > W else (0,):
                for oy in (0, -H, H) if y0 < 0 or y0 + s > H else (0,):
                    xa, ya = x0 + ox, y0 + oy
                    xs, ys = max(0, -xa), max(0, -ya)
                    xe, ye = min(s, W - xa), min(s, H - ya)
                    if xe > xs and ye > ys:
                        canvas[ya + ys:ya + ye, xa + xs:xa + xe] += sp[ys:ye, xs:xe, None] * colour
        pr.stdin.write(np.clip(canvas, 0, 255).astype(np.uint8).tobytes())
    pr.stdin.close()
    pr.wait()
    os.replace(out + ".tmp.mp4", out)
    return out
