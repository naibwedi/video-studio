"""Where things live, and how to find ffmpeg / the Pexels key."""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.path.join(ROOT, "projects")
LIBRARY = os.path.join(ROOT, "library")
STOCK = os.path.join(LIBRARY, "stock")
EXPORTS = os.path.join(ROOT, "exports")
CACHE = os.path.join(ROOT, ".cache")
FONTS_DIR = r"C:\Windows\Fonts"


def load_env():
    """Read KEY=value lines from .env (never committed) into the environment."""
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ffmpeg():
    exe = os.environ.get("FFMPEG") or os.path.join(ROOT, "tools", "bin", "ffmpeg.exe")
    if os.path.exists(exe):
        return exe
    found = shutil.which("ffmpeg")
    if found:
        return found
    sys.exit("ffmpeg not found. Put ffmpeg.exe in tools/bin/ or install it and add it to PATH.")


def rel(path):
    """Path relative to ROOT with forward slashes, so ffmpeg command lines stay short."""
    return os.path.relpath(path, ROOT).replace("\\", "/")


def stock_path(clip_id):
    """'6988904' -> p6988904.mp4 (Pexels);  'pb12345' -> pb12345.mp4 (Pixabay)."""
    name = str(clip_id) if str(clip_id).startswith("pb") else f"p{clip_id}"
    return os.path.join(STOCK, name + ".mp4")
