"""`studio ui`: the local dashboard. Standard library only; listens on 127.0.0.1 so only this PC can open it.

Pages and API live here; the page itself is core/ui/index.html. Long jobs (renders) go through ONE queue, one at a time,
because two renders at once have damaged files before.
"""
import array, contextlib, io, json, mimetypes, os, queue, re, secrets, subprocess, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import chat, draft, paths, project, qc, tools
from .edits import save_project

TOKEN = secrets.token_hex(16)          # the page carries it; other websites cannot know it
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
UI = os.path.join(UI_DIR, "index.html")
EDITOR_DIST = os.path.join(paths.ROOT, "editor", "dist")
JOBS, JOB_Q, JOB_LOCK = [], queue.Queue(), threading.Lock()
THUMB_LOCK = threading.Lock()
PORT = 8765


# ---------------------------------------------------------------- jobs
def add_job(title, args):
    with JOB_LOCK:
        job = {"id": len(JOBS) + 1, "title": title, "args": args, "status": "queued", "log": [], "started": None, "ended": None, "proc": None}
        JOBS.append(job)
    JOB_Q.put(job)
    return job


def worker():
    while True:
        job = JOB_Q.get()
        if job["status"] == "cancelled":
            continue
        job["status"], job["started"] = "running", time.time()
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            proc = subprocess.Popen([sys.executable, os.path.join(paths.ROOT, "studio.py")] + job["args"], cwd=paths.ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            job["proc"] = proc
            for line in proc.stdout:
                job["log"].append(line.rstrip())
                del job["log"][:-400]
            code = proc.wait()
            job["status"] = "cancelled" if job["status"] == "cancelled" else ("done" if code == 0 else "failed")
        except Exception as e:   # pragma: no cover
            job["log"].append(f"could not start: {e}")
            job["status"] = "failed"
        job["ended"] = time.time()


def cancel_job(j):
    if j["status"] == "queued":
        j["status"] = "cancelled"
    elif j["status"] == "running" and j["proc"]:
        j["status"] = "cancelled"
        subprocess.run(["taskkill", "/PID", str(j["proc"].pid), "/T", "/F"], capture_output=True)   # also stops ffmpeg children


def job_progress(j):
    """0..1 from the build log ('shot 12/32 ...' lines, then the final pass). Rough, but moves."""
    if j["status"] == "done":
        return 1.0
    seen = [m for m in (re.search(r"shot\s+(\d+)/(\d+)", l) for l in j["log"]) if m]
    if not seen:
        return 0.02 if j["status"] == "running" else 0.0
    done, total = len(seen), int(seen[-1][2])
    return min(0.97, 0.7 * min(1.0, done / max(1, total)) + (0.25 if any("wrote" in l for l in j["log"]) else 0.0))


def job_view(j, full=False):
    return {"id": j["id"], "title": j["title"], "status": j["status"], "started": j["started"], "ended": j["ended"],
            "progress": job_progress(j), "log": j["log"][-(400 if full else 3):]}


# ---------------------------------------------------------------- data
def project_names():
    return sorted(d for d in os.listdir(paths.PROJECTS) if os.path.exists(project.json_path(d)))


def export_files(name):
    d = os.path.join(paths.EXPORTS, name)
    out = []
    if os.path.isdir(d):
        for root, _, files in os.walk(d):
            for f in sorted(files):
                full = os.path.join(root, f)
                out.append({"path": os.path.relpath(full, d).replace("\\", "/"), "mb": round(os.path.getsize(full) / 2 ** 20, 1),
                            "time": os.path.getmtime(full)})
    return sorted(out, key=lambda x: -x["time"])


def project_payload(name):
    raw = json.load(open(project.json_path(name), encoding="utf-8"))
    p = project.load(name)
    tags = draft.load()
    return {"name": name, "raw": raw, "duration": p["duration"], "title": p["title"],
            "shots": [{"at": s["at"], "clip": s["clip"], "start": s["start"], "pan": s["pan"],
                       "tags": tags.get(s["clip"], {}).get("tags", [])} for s in p["_shots"]],
            "exports": export_files(name), "audio": os.path.basename(p["_audio"]), "channel": p["channel"], "overlays": p["overlays"],
            "export_dir": os.path.join(paths.EXPORTS, name),
            "notes": [{"level": a, "text": b} for a, b in qc.project_checks(p)]}


def clip_list():
    tags = draft.load()
    out = []
    for f in sorted(os.listdir(paths.STOCK)) if os.path.isdir(paths.STOCK) else []:
        if f.endswith(".mp4"):
            cid = f[:-4][1:] if f.startswith("p") and not f.startswith("pb") else f[:-4]
            t = tags.get(cid, {})
            out.append({"id": cid, "tags": t.get("tags", []), "people": t.get("people", 0), "dur": t.get("dur")})
    return out


_LOCKS = {}


def _frame(src, out, at, width):
    """Cached JPEG frame of a video; one lock per output file so different thumbnails render in parallel."""
    lock = _LOCKS.setdefault(out, threading.Lock())
    with lock:
        if not os.path.exists(out):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error", "-ss", str(at), "-i", src, "-frames:v", "1",
                            "-vf", f"scale={width}:-2", "-q:v", "5", out], cwd=paths.ROOT)
    return out if os.path.exists(out) else None


def thumb_for(cid):
    src = paths.stock_path(cid)
    return _frame(src, os.path.join(paths.CACHE, "thumbs", f"{cid}.jpg"), 1.5, 320) if os.path.exists(src) else None


def poster_for(name, rel):
    base = os.path.realpath(os.path.join(paths.EXPORTS, name))
    src = os.path.realpath(os.path.join(base, rel))
    if not src.startswith(base + os.sep) or not os.path.isfile(src):
        return None
    key = re.sub(r"[^\w.-]", "_", f"{name}_{rel}")
    return _frame(src, os.path.join(paths.CACHE, "posters", key + ".jpg"), 3, 480)


def warm_thumbs():
    """Make every library thumbnail once, in the background, so the library opens instantly."""
    for c in clip_list():
        thumb_for(c["id"])


def peaks_for(name, buckets=3000):
    """Loudness envelope of the song (0..100 per bucket) for the timeline waveform. Cached next to the audio's name."""
    audio = project.load(name)["_audio"]
    cache = os.path.join(paths.CACHE, "peaks", f"{name}_{buckets}.json")
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(audio):
        return json.load(open(cache))
    raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-i", audio, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    n = max(1, len(samples) // buckets)
    peaks = [min(100, int(max(map(abs, samples[i * n:(i + 1) * n]), default=0) * 100 / 32768 * 1.15)) for i in range(buckets)]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    json.dump({"peaks": peaks, "seconds": len(samples) / 8000}, open(cache, "w"))
    return {"peaks": peaks, "seconds": len(samples) / 8000}


def strip_for(cid):
    """A 768x54 filmstrip (8 frames across the clip) for timeline clips."""
    src = paths.stock_path(cid)
    if not os.path.exists(src):
        return None
    out = os.path.join(paths.CACHE, "strips", f"{cid}.jpg")
    lock = _LOCKS.setdefault(out, threading.Lock())
    with lock:
        if not os.path.exists(out):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            from . import stock
            dur = max(1.0, stock.duration_of(src))
            subprocess.run([paths.ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-vf",
                            f"fps={8 / dur:.4f},scale=96:54:force_original_aspect_ratio=increase,crop=96:54,tile=8x1", "-frames:v", "1", "-q:v", "6", out], cwd=paths.ROOT)
    return out if os.path.exists(out) else None


def valid_name(n):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,40}", n or ""))


def create_project(name, title, filename, body):
    d = project.project_dir(name)
    if os.path.exists(d):
        raise ValueError(f"A project named '{name}' already exists")
    os.makedirs(os.path.join(d, "audio"))
    audio = os.path.join("audio", re.sub(r"[^\w.\- ]", "_", filename))
    open(os.path.join(d, audio), "wb").write(body)
    raw = {"title": title or name, "audio": audio.replace("\\", "/"), "sizes": ["16x9", "9x16"], "theme": [],
           "subtitles": {"lines": [{"text": "first lyric line", "start": 0.0, "end": 5.0}]},
           "overlays": {"logo": {"image": "library/brand/logo.jpg", "in": 3.0, "out": None},
                        "title_card": {"text": title or name, "subtitle": "", "in": 1.0, "out": 6.0}, "popups": []},
           "shots": []}
    json.dump(raw, open(project.json_path(name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    server_version = "studio"

    def log_message(self, *a):
        pass

    # --- helpers
    def host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, download=False):
        if not path or not os.path.isfile(path):
            return self.send_json({"error": "not found"}, 404)
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and (m := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if m[1]:
                start = int(m[1])
                end = int(m[2]) if m[2] else size - 1
            elif m[2]:
                start = max(0, size - int(m[2]))
            end = min(end, size - 1)
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # --- GET
    def do_GET(self):
        if not self.host_ok():
            return self.send_json({"error": "bad host"}, 403)
        u = urllib.parse.urlparse(self.path)
        path, q = u.path, urllib.parse.parse_qs(u.query)
        try:
            if m := re.fullmatch(r"/assets/([\w.\-]+)", path):
                return self.send_file(os.path.join(EDITOR_DIST, "assets", m[1]))
            if path == "/api/chat/status":
                return self.send_json(chat.status(refresh="refresh" in q))
            if m := re.fullmatch(r"/api/chat/([\w-]+)", path):
                sess = chat.get(m[1])
                since = int(q.get("since", ["0"])[0])
                return self.send_json({"events": sess.since(since), "running": sess.running, "session": bool(sess.session_id)})
            if m := re.fullmatch(r"/api/look/([0-9a-f]{16})\.jpg", path):
                return self.send_file(os.path.join(chat.LOOKS, m[1] + ".jpg"))
            if m := re.fullmatch(r"/api/peaks/([\w-]+)", path):
                return self.send_json(peaks_for(m[1], int(q.get("n", ["3000"])[0])))
            if m := re.fullmatch(r"/api/strip/((?:pb)?\d+)", path):
                return self.send_file(strip_for(m[1]))
            if path == "/api/brand/logo":
                return self.send_file(os.path.join(paths.ROOT, "library", "brand", "logo.jpg"))
            if path in ("/", "/classic"):
                page = os.path.join(EDITOR_DIST, "index.html")
                html = open(page if path == "/" and os.path.exists(page) else UI, encoding="utf-8").read().replace("__TOKEN__", TOKEN)
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if m := re.fullmatch(r"/ui/(vendor/)?([\w.\-]+\.(?:js|css|svg|png))", path):
                return self.send_file(os.path.join(UI_DIR, (m[1] or "").rstrip("/"), m[2]))
            if m := re.fullmatch(r"/api/clip/((?:pb)?\d+)", path):
                return self.send_file(paths.stock_path(m[1]))
            if path == "/api/doctor":
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    tools.doctor()
                return self.send_json({"text": buf.getvalue()})
            if path == "/api/projects":
                out = []
                for n in project_names():
                    p = project.load(n)
                    ex = export_files(n)
                    out.append({"name": n, "title": p["title"], "duration": p["duration"], "shots": len(p["_shots"]),
                                "lines": len(p["subtitles"]["lines"]), "cover": p["_shots"][min(3, len(p["_shots"]) - 1)]["clip"] if p["_shots"] else None,
                                "warnings": len(qc.project_checks(p)), "exports": len(ex), "updated": ex[0]["time"] if ex else None})
                return self.send_json(out)
            if m := re.fullmatch(r"/api/project/([\w-]+)", path):
                return self.send_json(project_payload(m[1]))
            if path == "/api/clips":
                return self.send_json(clip_list())
            if m := re.fullmatch(r"/api/poster/([\w-]+)/(.+)", path):
                return self.send_file(poster_for(m[1], urllib.parse.unquote(m[2])))
            if m := re.fullmatch(r"/api/thumb/((?:pb)?\d+)", path):
                return self.send_file(thumb_for(m[1]))
            if path == "/api/jobs":
                return self.send_json([job_view(j) for j in JOBS[-30:]])
            if m := re.fullmatch(r"/api/job/(\d+)", path):
                j = JOBS[int(m[1]) - 1]
                return self.send_json(job_view(j, full=True))
            if m := re.fullmatch(r"/audio/([\w-]+)", path):
                return self.send_file(project.load(m[1])["_audio"])
            if m := re.fullmatch(r"/files/([\w-]+)/(.+)", path):
                base = os.path.realpath(os.path.join(paths.EXPORTS, m[1]))
                full = os.path.realpath(os.path.join(base, urllib.parse.unquote(m[2])))
                if not full.startswith(base + os.sep):
                    return self.send_json({"error": "forbidden"}, 403)
                return self.send_file(full, download="download" in q)
            return self.send_json({"error": "not found"}, 404)
        except SystemExit as e:       # project loading reports problems with sys.exit(message)
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:
            return self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)

    # --- POST
    def do_POST(self):
        if not self.host_ok() or self.headers.get("X-Studio-Token") != TOKEN:
            return self.send_json({"error": "forbidden"}, 403)
        u = urllib.parse.urlparse(self.path)
        path, q = u.path, urllib.parse.parse_qs(u.query)
        try:
            if m := re.fullmatch(r"/api/project/([\w-]+)/save", path):
                save_project(m[1], self.body_json())
                return self.send_json(project_payload(m[1]))
            if m := re.fullmatch(r"/api/job/(\d+)/cancel", path):
                cancel_job(JOBS[int(m[1]) - 1])
                return self.send_json(job_view(JOBS[int(m[1]) - 1]))
            if m := re.fullmatch(r"/api/chat/([\w-]+)/(send|stop|reset)", path):
                name, verb = m[1], m[2]
                if name not in project_names():
                    return self.send_json({"error": "unknown project"}, 400)
                if verb == "send":
                    d = self.body_json()
                    msg = str(d.get("message", "")).strip()
                    if not msg:
                        return self.send_json({"error": "empty message"}, 400)
                    chat.send(name, msg[:4000], str(d.get("context", ""))[:600], f"http://127.0.0.1:{self.server.server_address[1]}", TOKEN)
                elif verb == "stop":
                    chat.stop(name)
                else:
                    chat.reset(name)
                return self.send_json({"ok": True})
            if path == "/api/open":
                name = self.body_json().get("project", "")
                if name in project_names():
                    d = os.path.join(paths.EXPORTS, name)
                    os.makedirs(d, exist_ok=True)
                    os.startfile(d)
                    return self.send_json({"ok": True})
                return self.send_json({"error": "unknown project"}, 400)
            if path == "/api/tag":
                d = self.body_json()
                info = draft.add_tag(str(d["id"]), " ".join(d.get("tags", [])) if isinstance(d.get("tags"), list) else d.get("tags", ""),
                                     int(d.get("people", 0)))
                return self.send_json(info)
            if path == "/api/draft":
                d = self.body_json()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    shots = draft.draft(d["project"], per_line=int(d.get("per_line", 2)), max_people=2 if d.get("people") else 1,
                                        intro=int(d.get("intro", 3)), outro=int(d.get("outro", 3)), theme=d.get("theme") or None,
                                        seed=int(d.get("seed", 0)), dry=bool(d.get("dry")))
                return self.send_json({"plan": buf.getvalue(), "count": len(shots)})
            if path == "/api/job":
                d = self.body_json()
                name, action = d["project"], d["action"]
                if not valid_name(name) or name not in project_names():
                    return self.send_json({"error": "unknown project"}, 400)
                size = d.get("size", "all")
                if size not in ("16x9", "9x16", "all"):
                    return self.send_json({"error": "bad size"}, 400)
                prev = ["--preview"] if d.get("preview") else []
                if action == "build":
                    variant = d.get("variant", "full")
                    if variant not in ("full", "nosubs", "video_only", "all"):
                        return self.send_json({"error": "bad variant"}, 400)
                    job = add_job(f"build {name} {size} {variant}{' (preview)' if prev else ''}",
                                  ["build", name, "--size", size, "--variant", variant] + prev)
                elif action == "teaser":
                    job = add_job(f"teaser {name} {size}", ["teaser", name, "--size", size] + prev)
                elif action == "thumb":
                    job = add_job(f"thumbnails {name}", ["thumb", name] + prev)
                elif action == "qc":
                    job = add_job(f"quality check {name}", ["qc", name])
                elif action == "pack":
                    job = add_job(f"CapCut pack {name}", ["pack", name])
                else:
                    return self.send_json({"error": "unknown action"}, 400)
                return self.send_json(job_view(job))
            if path == "/api/upload":
                name, filename = q.get("name", [""])[0], q.get("filename", ["song.wav"])[0]
                if not valid_name(name):
                    return self.send_json({"error": "Use letters, numbers, - or _ for the project name"}, 400)
                n = int(self.headers.get("Content-Length") or 0)
                create_project(name, q.get("title", [""])[0], filename, self.rfile.read(n))
                return self.send_json({"name": name})
            return self.send_json({"error": "not found"}, 404)
        except SystemExit as e:
            return self.send_json({"error": str(e)}, 400)
        except (ValueError, KeyError) as e:
            return self.send_json({"error": f"{type(e).__name__}: {e}"}, 400)
        except Exception as e:
            return self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)


def serve(port=PORT, open_browser=True):
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=warm_thumbs, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"video-studio dashboard: {url}   (Ctrl+C to stop; only this PC can open it)")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
