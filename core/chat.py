"""Chat with Claude inside the editor.

We run the Claude Code program installed on this PC (`claude -p`) with NO file/shell tools: the only thing it can touch is the studio's
MCP server (core/mcp_server.py), tied to the video you have open. Authentication is whatever Claude Code already uses on this PC
(your Claude login), or ANTHROPIC_API_KEY from .env if you set one. We never read or copy any login token.
"""
import base64, glob, hashlib, json, os, re, shutil, subprocess, sys, threading, time
from . import agent, paths, versions

SYSTEM = """You are Claude, a co-editor inside video-studio, a lyric-video editor for an Eritrean Orthodox Tewahedo channel (ሰብአ ሰገል, The Magis).
The user is editing ONE video. You have tools to read the edit, look at frames, search the footage library and change the edit.

How to work:
- Start with get_project (again after big changes). You cannot see footage unless you call look or contact_sheet: never describe a picture you have not looked at; tags are only a hint.
- Indices are 1-based, as in the editor. Times are seconds from the start of the song. Shots are contiguous: a shot runs until the next one starts.
- Do the edit with the tools instead of only describing it. The user can undo your whole turn with Ctrl+Z. Afterwards say briefly what you changed (shot numbers, times) and, when it matters, look at the result.
- Be concise: the chat panel is narrow. Short paragraphs, no headings, no big tables. Ge'ez text is fine.
- You can read the lyrics (Tigrinya in Ge'ez script). Turn their meaning into imagery when choosing footage; search the library with English words (candle, roots, fog, chains, sunrise...).
- Keep the channel's reverent tone. Faces are excluded from searches by default; keep it that way unless asked. Avoid footage that clashes with an Orthodox Christian setting.
- Ask one short question only when a request is truly ambiguous; otherwise do your best and say what you assumed.
- Start renders (render tool) only when asked or when the user needs to check a preview; previews are cheap."""

LOOKS = os.path.join(paths.CACHE, "looks")
SESSIONS = {}
EVENT_CAP = 600


def find_claude():
    """The Claude Code program. The Claude desktop app is a Microsoft Store app: it shows its files at %APPDATA%\\Claude only to its own
    processes, so we look in the real package folder (visible to everyone) first."""
    env = os.environ.get("CLAUDE_BIN")
    if env and os.path.exists(env):
        return env
    found = shutil.which("claude")
    if found:
        return found
    local, roaming = os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", "")
    pats = [(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude", "claude-code", "*", "*", "claude.exe"), 1),
            (os.path.join(roaming, "Claude", "claude-code", "*", "*", "claude.exe"), 0)]
    cands = [(p, pref) for pat, pref in pats for p in glob.glob(pat)]

    def key(item):
        p, pref = item
        v = os.path.basename(os.path.dirname(os.path.dirname(p)))
        return (tuple(int(x) if x.isdigit() else 0 for x in v.split(".")), pref)
    return max(cands, key=key)[0] if cands else None


_AUTH = {"t": 0.0, "v": None}


def signed_in(claude, force=False):
    """True if Claude Code can talk to Claude: an API key in the environment, or a login on this PC (`claude auth status`)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if not force and _AUTH["v"] is not None and time.time() - _AUTH["t"] < 60:
        return _AUTH["v"]
    try:
        r = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=25)
        v = json.loads(r.stdout).get("loggedIn") is True
    except Exception:
        v = False
    _AUTH.update(t=time.time(), v=v)
    return v


def status(refresh=False):
    path = find_claude()
    key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {"available": bool(path), "path": path, "signedIn": bool(path) and signed_in(path, refresh), "auth": "API key from .env" if key else "your Claude login",
            "loginCommand": f'"{path}" auth login' if path else None}


class Session:
    def __init__(self, project):
        self.project, self.events, self.running = project, [], False
        self.proc, self.session_id, self.lock = None, None, threading.Lock()
        self.tool_names = {}
        self.buf, self.flushed = "", 0.0

    def add(self, ev):
        with self.lock:
            ev["n"] = (self.events[-1]["n"] + 1) if self.events else 1
            self.events.append(ev)
            del self.events[:-EVENT_CAP]

    def since(self, n):
        with self.lock:
            return [e for e in self.events if e["n"] > n]


def get(project):
    return SESSIONS.setdefault(project, Session(project))


def short(name):
    return name.replace("mcp__studio__", "")


def save_image(b64):
    os.makedirs(LOOKS, exist_ok=True)
    raw = base64.b64decode(b64)
    h = hashlib.sha1(raw).hexdigest()[:16]
    path = os.path.join(LOOKS, h + ".jpg")
    if not os.path.exists(path):
        open(path, "wb").write(raw)
    return f"/api/look/{h}.jpg"


def events_from(obj, sess):
    """Turn one stream-json line from Claude Code into simple events for the chat panel."""
    t, out = obj.get("type"), []
    if t == "stream_event":                                    # text as it is written: batched, so the panel is not flooded
        ev = obj.get("event") or {}
        delta = ev.get("delta") or {}
        if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
            sess.buf += delta.get("text", "")
            if time.time() - sess.flushed > 0.25 and sess.buf:
                out.append({"type": "delta", "text": sess.buf})
                sess.buf, sess.flushed = "", time.time()
        return out
    if t == "assistant" and sess.buf:
        out.append({"type": "delta", "text": sess.buf})
        sess.buf = ""
    if t == "system" and obj.get("subtype") == "init":
        if obj.get("session_id"):
            sess.session_id = obj["session_id"]
    elif t == "assistant":
        for b in (obj.get("message") or {}).get("content") or []:
            if b.get("type") == "text" and b.get("text", "").strip():
                out.append({"type": "text", "text": b["text"]})
            elif b.get("type") == "tool_use":
                sess.tool_names[b["id"]] = short(b["name"])
                out.append({"type": "tool", "id": b["id"], "name": short(b["name"]), "input": b.get("input") or {}})
    elif t == "user":
        for b in (obj.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_result":
                continue
            parts = b.get("content")
            texts, images = [], []
            for p in (parts if isinstance(parts, list) else [{"type": "text", "text": str(parts or "")}]):
                if p.get("type") == "text":
                    texts.append(p.get("text", ""))
                elif p.get("type") == "image" and (p.get("source") or {}).get("data"):
                    images.append(save_image(p["source"]["data"]))
            name = sess.tool_names.get(b.get("tool_use_id"), "")
            out.append({"type": "tool_result", "id": b.get("tool_use_id"), "name": name, "text": "\n".join(texts)[:700], "error": bool(b.get("is_error")), "images": images})
            if name in agent.EDIT_TOOLS and not b.get("is_error"):
                out.append({"type": "changed"})
    elif t == "result":
        if obj.get("session_id"):
            sess.session_id = obj["session_id"]
        out.append({"type": "done", "ok": not obj.get("is_error"), "text": obj.get("result") or "", "turns": obj.get("num_turns")})
    return out


def _mcp_config(project, url, token):
    os.makedirs(os.path.join(paths.CACHE, "claude"), exist_ok=True)
    cfg = os.path.join(paths.CACHE, "claude", f"mcp_{project}.json")
    json.dump({"mcpServers": {"studio": {"command": sys.executable, "args": [os.path.join(paths.ROOT, "studio.py"), "mcp"],
                                         "env": {"STUDIO_PROJECT": project, "STUDIO_URL": url, "STUDIO_TOKEN": token, "PYTHONUTF8": "1"}}}},
              open(cfg, "w", encoding="utf-8"))
    return cfg


def command(claude, cfg, session_id):
    cmd = [claude, "-p", "--output-format", "stream-json", "--verbose", "--mcp-config", cfg, "--strict-mcp-config", "--tools", "",
           "--allowedTools", "mcp__studio", "--permission-mode", "dontAsk", "--include-partial-messages", "--append-system-prompt", SYSTEM]
    if os.environ.get("STUDIO_CLAUDE_MODEL"):
        cmd += ["--model", os.environ["STUDIO_CLAUDE_MODEL"]]
    if session_id:
        cmd += ["--resume", session_id]
    return cmd


def send(project, message, context, url, token):
    sess = get(project)
    if sess.running:
        raise ValueError("Claude is still working on the last request.")
    claude = find_claude()
    if not claude:
        raise ValueError("Claude Code was not found on this PC. Install the Claude desktop app (or Claude Code), or set CLAUDE_BIN in .env.")
    if not signed_in(claude, True):
        raise ValueError("Claude Code is not signed in on this PC yet. Run the sign-in command shown in the chat panel once (or put ANTHROPIC_API_KEY in .env).")
    versions.snapshot(project, "before-claude", force=True)       # so a whole Claude turn can be rolled back from the history too
    sess.add({"type": "user", "text": message})
    sess.running = True
    cfg = _mcp_config(project, url, token)
    cwd = os.path.join(paths.CACHE, "claude", "cwd")
    os.makedirs(cwd, exist_ok=True)
    prompt = (context + "\n\n" if context else "") + message

    def run():
        saw_done, err_tail = False, []
        try:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            sess.proc = subprocess.Popen(command(claude, cfg, sess.session_id), cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, encoding="utf-8", errors="replace")
            threading.Thread(target=lambda: [err_tail.append(l.rstrip()) or err_tail.__setitem__(slice(None, -12), []) for l in sess.proc.stderr], daemon=True).start()
            sess.proc.stdin.write(prompt)
            sess.proc.stdin.close()
            for line in sess.proc.stdout:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for ev in events_from(obj, sess):
                    saw_done = saw_done or ev["type"] == "done"
                    sess.add(ev)
            code = sess.proc.wait()
            if not saw_done:
                hint = " ".join(err_tail[-4:])[:400]
                sess.add({"type": "done", "ok": False, "text": "" if code == 0 else f"Claude stopped (exit {code}). {hint}".strip()})
        except Exception as e:
            sess.add({"type": "done", "ok": False, "text": f"Could not start Claude: {e}"})
        finally:
            sess.running = False
            sess.proc = None

    threading.Thread(target=run, daemon=True).start()


def stop(project):
    sess = get(project)
    if sess.proc and sess.running:
        subprocess.run(["taskkill", "/PID", str(sess.proc.pid), "/T", "/F"], capture_output=True)
        sess.add({"type": "done", "ok": False, "text": "Stopped."})


def reset(project):
    stop(project)
    SESSIONS[project] = Session(project)
