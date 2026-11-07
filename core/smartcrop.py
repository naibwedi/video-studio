"""Smart 9:16 crop: for each shot, find where the interesting part of the picture is and set the crop position (pan) to follow it.

No model needed: a frame is turned into a 'what stands out' map (colour and brightness that differ from the rest of the picture,
plus edges), and the crop window of a vertical video is slid across it to find the position that keeps the most of what stands out.
The vertical render drifts the crop by 6% across a shot, so the best position is looked for across 3 frames of the shot.
"""
import io, subprocess
import numpy as np
from PIL import Image, ImageFilter
from . import paths, project

CROP_W = 9 / 16 / (16 / 9)       # a 9:16 window is this fraction of the width of a 16:9 frame (about 0.316)


def _frame(path, t, width=192):
    r = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", path, "-frames:v", "1", "-vf", f"scale={width}:-2",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def saliency(im):
    """Columns weight (0..1 per x): colour/brightness contrast against the whole picture + edge strength, blurred."""
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(2)).convert("LAB"), dtype=np.float32)
    mean = a.reshape(-1, 3).mean(axis=0)
    contrast = np.sqrt(((a - mean) ** 2).sum(axis=2))
    g = np.asarray(im.convert("L"), dtype=np.float32)
    edges = np.abs(np.diff(g, axis=1, prepend=g[:, :1])) + np.abs(np.diff(g, axis=0, prepend=g[:1]))
    s = contrast / (contrast.max() + 1e-6) + 0.6 * edges / (edges.max() + 1e-6)
    h, w = s.shape
    yy = np.linspace(-1, 1, h)[:, None]
    s = s * (1.0 - 0.25 * yy ** 2)                    # the middle rows matter a little more than the top and bottom
    return s


def best_pan(path, start, length):
    """Crop position 0..1 (0 = far left, 1 = far right) that keeps the most interesting part inside a 9:16 window."""
    cols = None
    for f in (0.15, 0.5, 0.85):
        im = _frame(path, start + length * f)
        if im is None:
            continue
        c = saliency(im).sum(axis=0)
        cols = c if cols is None else cols + c
    if cols is None:
        return 0.5
    w = len(cols)
    win = max(2, int(round(w * CROP_W)))
    csum = np.concatenate([[0], np.cumsum(cols)])
    scores = csum[win:] - csum[:-win]
    centre = (np.arange(len(scores)) + win / 2) / w
    scores = scores * (1.0 - 0.15 * np.abs(centre - 0.5))        # a small pull to the middle so flat pictures stay centred
    k = int(np.argmax(scores))
    pan = k / max(1, len(scores) - 1)
    # how clearly one position beats the rest: a flat landscape has no clear subject, so stay near the middle instead of an arbitrary edge
    ratio = float(scores.max() / (scores.mean() + 1e-9))
    strength = min(1.0, max(0.0, (ratio - 1.10) / 0.30))
    return round(min(0.95, max(0.05, 0.5 + (pan - 0.5) * strength)), 2)


def auto_pan(doc, name):
    """Set 'pan' on every shot of the doc. Returns a short report."""
    p = project.load(name)
    changed = 0
    for i, s in enumerate(doc["shots"]):
        end = doc["shots"][i + 1]["at"] if i + 1 < len(doc["shots"]) else doc["duration"]
        src = project.resolve_clip(p, s["clip"])
        if src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        pan = best_pan(src, s["start"], max(0.5, end - s["at"]))
        if abs(pan - s["pan"]) > 0.01:
            s["pan"] = pan
            changed += 1
    return f"Set the 9:16 crop of {changed} of {len(doc['shots'])} shots to follow what stands out in the picture."
