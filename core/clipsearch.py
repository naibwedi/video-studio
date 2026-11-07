"""Search the footage library by meaning ("a candle in a dark room") instead of by tag words.

Uses a small CLIP model (open_clip, ViT-B-32, about 350 MB, downloaded once on first use) that puts pictures and sentences in the same space.
Each library clip is represented by 3 frames; the index is cached in .cache/clipindex and only new clips are added later.
Optional: install with  pip install -r requirements-ai.txt
"""
import json, os, subprocess, threading
import numpy as np
from . import paths

MODEL, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
_M = {}
_LOCK = threading.Lock()
INDEX = os.path.join(paths.CACHE, "clipindex")


def available():
    try:
        import open_clip, torch, torchvision  # noqa: F401
        return True
    except Exception:
        return False


def _model():
    with _LOCK:
        if "m" not in _M:
            import open_clip, torch
            m, _, pre = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
            m.eval()
            _M.update(m=m, pre=pre, tok=open_clip.get_tokenizer(MODEL), torch=torch)
        return _M


def _frames(path, dur):
    """3 frames (20%, 50%, 80% into the clip) as PIL images."""
    from PIL import Image
    import io
    out = []
    for f in (0.2, 0.5, 0.8):
        r = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{max(0.0, dur * f):.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=336:-2",
                            "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
        if r.stdout:
            out.append(Image.open(io.BytesIO(r.stdout)).convert("RGB"))
    return out


def _ids():
    out = {}
    for f in sorted(os.listdir(paths.STOCK)) if os.path.isdir(paths.STOCK) else []:
        if f.endswith(".mp4"):
            out[f[:-4][1:] if f.startswith("p") and not f.startswith("pb") else f[:-4]] = os.path.join(paths.STOCK, f)
    return out


def build(log=print):
    """Add every library clip that is not in the index yet. Returns the number of clips indexed."""
    from . import stock
    m = _model()
    os.makedirs(INDEX, exist_ok=True)
    meta_p, vec_p = os.path.join(INDEX, "ids.json"), os.path.join(INDEX, "vectors.npy")
    ids = json.load(open(meta_p)) if os.path.exists(meta_p) else []
    vecs = np.load(vec_p) if os.path.exists(vec_p) else np.zeros((0, 512), dtype=np.float32)
    todo = [(i, p) for i, p in _ids().items() if i not in set(ids)]
    torch = m["torch"]
    for n, (cid, path) in enumerate(todo, 1):
        try:
            imgs = _frames(path, max(1.0, stock.duration_of(path)))
            if not imgs:
                continue
            with torch.no_grad():
                f = m["m"].encode_image(torch.stack([m["pre"](im) for im in imgs]))
                f = f / f.norm(dim=-1, keepdim=True)
                v = f.mean(dim=0)
                v = (v / v.norm()).numpy().astype(np.float32)
            ids.append(cid)
            vecs = np.vstack([vecs, v[None]])
        except Exception as e:      # one bad clip must not stop the rest
            log(f"  skipped {cid}: {e}")
        if n % 10 == 0:
            log(f"  indexed {n}/{len(todo)}")
    json.dump(ids, open(meta_p, "w"))
    np.save(vec_p, vecs)
    return len(todo)


def search(query, limit=12):
    """[(clip id, similarity 0..1)] best first. Builds the index on the first call (a minute or two)."""
    meta_p, vec_p = os.path.join(INDEX, "ids.json"), os.path.join(INDEX, "vectors.npy")
    have = set(json.load(open(meta_p))) if os.path.exists(meta_p) else set()
    if set(_ids()) - have:
        build()
    ids, vecs = json.load(open(meta_p)), np.load(vec_p)
    if not len(ids):
        return []
    m = _model()
    torch = m["torch"]
    with torch.no_grad():
        q = m["m"].encode_text(m["tok"]([query]))
        q = (q / q.norm(dim=-1, keepdim=True))[0].numpy().astype(np.float32)
    sims = vecs @ q
    order = np.argsort(-sims)[:limit]
    return [(ids[i], float(sims[i])) for i in order]
