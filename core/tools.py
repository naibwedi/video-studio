"""check / pack / tap-sync / swap / import-srt helpers."""
import json, os, re, shutil, subprocess, sys
from . import paths, project, render, overlays


def check(file):
    """Decode the whole file and report: duration, streams, number of decode errors (0 = clean)."""
    ff = paths.ffmpeg()
    info = subprocess.run([ff, "-hide_banner", "-i", file], capture_output=True, text=True).stderr
    dur = re.search(r"Duration: ([\d:.]+)", info)
    video = re.search(r"Video: .*?(\d{3,4}x\d{3,4})", info)
    audio = "Audio:" in info
    errs = subprocess.run([ff, "-v", "error", "-i", file, "-f", "null", "-"], capture_output=True, text=True).stderr.strip()
    n = len(errs.splitlines()) if errs else 0
    print(f"{os.path.basename(file)}: {dur[1] if dur else '?'}  {video[1] if video else '?'}  "
          f"audio={'yes' if audio else 'no'}  decode errors={n}")
    return n == 0


def pack(p):
    """Everything CapCut needs, in exports/<name>/CapCut: silent video, audio, subtitles."""
    out = os.path.join(paths.EXPORTS, p["_name"], "CapCut")
    os.makedirs(out, exist_ok=True)
    for size in p["sizes"]:
        src = render.output_path(p, size, "video_only", False)
        if not os.path.exists(src):
            render.build(p, size, "video_only")
        shutil.copy(src, os.path.join(out, f"1_VIDEO_only_{size}.mp4"))
    subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error", "-i", p["_audio"], "-b:a", "320k",
                    os.path.join(out, "2_AUDIO.mp3")], check=True)
    overlays.write_srt(p, os.path.join(out, "3_SUBTITLES.srt"))
    print("packed ->", paths.rel(out))


def tap_html(p):
    """A tap-sync page for this project's lyrics + audio. Tap Space at each line start, download the SRT, import it."""
    tpl = open(os.path.join(paths.ROOT, "tools", "tap_sync_template.html"), encoding="utf-8").read()
    lines = [l["text"] for l in p["subtitles"]["lines"]]
    arr = "const LINES = [\n" + "".join(f"  {json.dumps(t, ensure_ascii=False)},\n" for t in lines) + "];"
    tpl = re.sub(r"const LINES = \[.*?\];", lambda m: arr, tpl, count=1, flags=re.S)
    bdir = os.path.join(p["_dir"], "build")
    os.makedirs(bdir, exist_ok=True)
    audio_rel = os.path.relpath(p["_audio"], bdir).replace("\\", "/")
    tpl = re.sub(r'src="[^"]*"', f'src="{audio_rel}"', tpl, count=1)
    path = os.path.join(bdir, "tap_sync.html")
    open(path, "w", encoding="utf-8").write(tpl)
    print("open this in your browser:", path)
    return path


def import_srt(name, srt):
    """Put exact times from a tapped .srt into the project's lyric lines (text stays as it is in project.json)."""
    blocks = re.findall(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", open(srt, encoding="utf-8").read())
    times = [(int(a) * 3600 + int(b) * 60 + int(c) + int(d) / 1000, int(e) * 3600 + int(f) * 60 + int(g) + int(h) / 1000)
             for a, b, c, d, e, f, g, h in blocks]

    def mutate(raw):
        lines = raw["subtitles"]["lines"]
        if len(times) != len(lines):
            sys.exit(f"The SRT has {len(times)} lines but the project has {len(lines)}.")
        for ln, (a, b) in zip(lines, times):
            ln["start"], ln["end"] = round(a, 2), round(b, 2)
    project.save_raw(name, mutate)
    print(f"updated {len(times)} lyric times in projects/{name}/project.json (backup: project.json.bak)")


def swap(name, at, clip, start=None, pan=None):
    """Replace the clip of the shot that starts at `at` (seconds, or L3 / L3m)."""
    p = project.load(name)
    target = project.at_time(at, p["subtitles"]["lines"])

    def mutate(raw):
        best = min(raw["shots"], key=lambda s: abs(project.at_time(s["at"], p["subtitles"]["lines"]) - target))
        when = project.at_time(best["at"], p["subtitles"]["lines"])
        if abs(when - target) > 1.5:
            sys.exit(f"No shot starts near {target:.1f}s (closest starts at {when:.1f}s). Use that time, or edit project.json.")
        print(f"shot at {when:.1f}s: {best['clip']} -> {clip}")
        best["clip"] = str(clip)
        if start is not None:
            best["start"] = start
        if pan is not None:
            best["pan"] = pan
    project.save_raw(name, mutate)


def doctor():
    """Check the setup and say what to fix."""
    import shutil as sh
    ok = True

    def line(good, text, fix=""):
        nonlocal ok
        print(("  OK    " if good else "  FIX   ") + text + (f"   -> {fix}" if fix and not good else ""))
        ok = ok and good

    ff = None
    try:
        ff = paths.ffmpeg()
        ver = subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        line(True, ver[:60])
    except SystemExit:
        line(False, "ffmpeg", "run setup.ps1, or put ffmpeg.exe in tools\bin")
    if ff:
        if render.gpu_ok():
            print("  OK    GPU encoding on (fast)")
        else:
            print("  info  GPU encoding off, using the CPU (works, just slower). To enable: update the NVIDIA driver to 610 or newer")
    try:
        import PIL
        line(True, f"Pillow {PIL.__version__}")
    except ImportError:
        line(False, "Pillow", "pip install -r requirements.txt")
    for f in ("ebrima.ttf", "ebrimabd.ttf", "georgia.ttf"):
        line(os.path.exists(os.path.join(paths.FONTS_DIR, f)), f"font {f}", "needed for Ge'ez text; comes with Windows 10/11")
    line(os.path.exists(os.path.join(paths.ROOT, "library", "brand", "logo.jpg")), "logo library/brand/logo.jpg", "add your logo")
    for f in ("popup_h.mov", "popup_v.mov"):
        if not os.path.exists(os.path.join(paths.LIBRARY, "overlays", f)):
            print(f"  info  library/overlays/{f} missing: subscribe pop-ups will be skipped")
    try:
        from . import chat
        cs = chat.status(True)
        if not cs["available"]:
            print("  info  Claude Code not found: the Claude co-editor panel will be unavailable (install the Claude desktop app, or set CLAUDE_BIN in .env)")
        elif cs["signedIn"]:
            print(f"  OK    Claude co-editor ready ({cs['auth']})")
        else:
            print(f"  info  Claude Code found but not signed in: run  {cs['loginCommand']}  once, or put ANTHROPIC_API_KEY in .env")
    except Exception as e:
        print(f"  info  could not check Claude Code: {e}")
    n = len([x for x in os.listdir(paths.STOCK) if x.endswith(".mp4")]) if os.path.isdir(paths.STOCK) else 0
    print(f"  info  {n} stock clips in the library")
    keys = [k for k in ("PIXABAY_API_KEY", "PEXELS_API_KEY") if os.environ.get(k, "").strip() and not os.environ[k].startswith("PASTE")]
    print("  info  keys set: " + (", ".join(keys) if keys else "none (fine: Claude can find clips for you)"))
    free = sh.disk_usage(paths.ROOT).free // 2**30
    line(free >= 5, f"{free} GB free disk", "renders and clips need space")
    print("\nAll good." if ok else "\nFix the FIX lines above, then run doctor again.")
