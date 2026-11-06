"""MCP server (stdio) exposing the studio's editing tools to Claude.

Used two ways:
  - by the chat panel in the editor (core/chat.py starts Claude Code with this server and STUDIO_PROJECT set)
  - by any other Claude, e.g. Claude Code:   claude mcp add studio -- <python> <studio.py> mcp
Messages are newline-delimited JSON-RPC on stdin/stdout. Nothing else may be printed to stdout.
"""
import json, os, sys
from . import agent, project

VERSION = "0.5.0"
INSTRUCTIONS = ("Tools to co-edit Ge'ez/Tigrinya lyric videos. Call get_project first. Look at frames before judging footage. "
                "Indices are 1-based. Times are seconds from the start of the song.")
LOCKED = bool(os.environ.get("STUDIO_PROJECT"))
_state = {"project": os.environ.get("STUDIO_PROJECT") or None}


def current():
    if _state["project"]:
        return _state["project"]
    names = sorted(d for d in os.listdir(project.paths.PROJECTS) if os.path.exists(project.json_path(d)))
    if len(names) == 1:
        return names[0]
    raise ValueError("Several videos exist: call list_projects, then use_project with the name.")


def _list_projects(_name=None):
    names = sorted(d for d in os.listdir(project.paths.PROJECTS) if os.path.exists(project.json_path(d)))
    return "Videos: " + ", ".join(names) + (f". Current: {_state['project']}" if _state["project"] else "")


def _use_project(_name=None, name=None):
    if LOCKED:
        raise ValueError(f"This session is tied to the video '{_state['project']}'.")
    if not os.path.exists(project.json_path(str(name))):
        raise ValueError(f"No video named {name!r}")
    _state["project"] = str(name)
    return f"Now editing {name}."


def tool_specs():
    extra = [] if LOCKED else [
        {"name": "list_projects", "description": "List the videos in the studio.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "use_project", "description": "Choose which video to edit.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]
    return extra + agent.specs()


def handle(msg):
    """One JSON-RPC message in, response dict (or None for notifications) out."""
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:                                   # notification: nothing to answer
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion") or "2025-06-18", "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "studio", "version": VERSION}, "instructions": INSTRUCTIONS})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": tool_specs()})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        try:
            if name == "list_projects" and not LOCKED:
                return ok({"content": [{"type": "text", "text": _list_projects()}], "isError": False})
            if name == "use_project" and not LOCKED:
                return ok({"content": [{"type": "text", "text": _use_project(**args)}], "isError": False})
            return ok(agent.call(name, args, current()))
        except ValueError as e:
            return ok({"content": [{"type": "text", "text": f"Could not do that: {e}"}], "isError": True})
        except Exception as e:   # a bug in a tool must not kill the session
            return ok({"content": [{"type": "text", "text": f"Internal error in {name}: {type(e).__name__}: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
