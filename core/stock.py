"""Free stock footage from Pexels: search + download (needs a free API key) or download by known id (no key).
Also builds the contact sheets used to choose clips."""
import json, os, re, subprocess, sys, urllib.parse, urllib.request
from PIL import Image, ImageDraw
from . import paths

UA = {"User-Agent": "Mozilla/5.0"}
FPS_GUESS = (25, 30, 24, 50, 60, 29)


def api_key():
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key or key.startswith("PASTE"):
        sys.exit("No Pexels key yet. See README.md ('Pexels key') - it takes 2 minutes. "
                 "Without a key you can still use: python studio.py fetch-ids 6988904:30 ...")
    return key


def api_get(url):
    req = urllib.request.Request(url, headers={**UA, "Authorization": api_key()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pick_file(video):
    """Best download: 1920x1080 if there is one, else the smallest file at least 1280 wide."""
    files = [f for f in video["video_files"] if f.get("width") and f["file_type"] == "video/mp4"]
    exact = [f for f in files if f["width"] == 1920 and f["height"] == 1080]
    if exact:
        return exact[0]
    big = sorted([f for f in files if f["width"] >= 1280], key=lambda f: f["width"])
    return big[0] if big else (files[0] if files else None)


def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, dest)


def search(query, count=12, orientation="landscape"):
    q = urllib.parse.urlencode({"query": query, "per_page": count, "orientation": orientation})
    return api_get(f"https://api.pexels.com/videos/search?{q}")["videos"]


def fetch(query, count=12, orientation="landscape"):
    os.makedirs(paths.STOCK, exist_ok=True)
    got = []
    for v in search(query, count, orientation):
        f = pick_file(v)
        if not f:
            continue
        dest = paths.stock_path(v["id"])
        if not os.path.exists(dest):
            print(f"  downloading {v['id']}  ({v['duration']}s, {f['width']}x{f['height']})", flush=True)
            download(f["link"], dest)
        got.append(dest)
    return got


def fetch_ids(specs):
    """specs: '6988904' or '6988904:30' (id[:fps]). Works without a key by trying the usual CDN file names."""
    os.makedirs(paths.STOCK, exist_ok=True)
    got = []
    for spec in specs:
        cid, _, fps = spec.partition(":")
        dest = paths.stock_path(cid)
        if os.path.exists(dest):
            got.append(dest)
            continue
        ok = False
        for f in ([int(fps)] if fps else []) + [x for x in FPS_GUESS if str(x) != fps]:
            url = f"https://videos.pexels.com/video-files/{cid}/{cid}-hd_1920_1080_{f}fps.mp4"
            try:
                download(url, dest)
                ok = True
                print(f"  downloaded {cid} ({f}fps)")
                break
            except Exception:
                continue
        if ok:
            got.append(dest)
        else:
            print(f"  could not download {cid}: give its fps (id:fps), or use a search with a key")
    return got


def duration_of(path):
    r = subprocess.run([paths.ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def sheet(files, out, cols=5, tw=400, th=225):
    """Contact sheet: one frame per clip, labelled with its id and length."""
    rows = (len(files) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw, rows * th), "black")
    d = ImageDraw.Draw(img)
    tmp = os.path.join(paths.CACHE, "_t.png")
    os.makedirs(paths.CACHE, exist_ok=True)
    for i, f in enumerate(files):
        secs = duration_of(f)
        subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error", "-ss", str(min(2.0, secs / 2)), "-i", f, "-frames:v", "1",
                        "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}", tmp], check=True)
        x, y = (i % cols) * tw, (i // cols) * th
        img.paste(Image.open(tmp), (x, y))
        d.rectangle((x, y, x + 150, y + 18), fill="black")
        d.text((x + 3, y + 3), f"{os.path.basename(f)[1:-4]}  {secs:.0f}s", fill="yellow")
    img.save(out)
    return out
