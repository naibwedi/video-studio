"""A stand-in for the `claude` program, for tests and demos: it speaks the same stream-json format and calls the REAL studio MCP tools,
so the chat backend, the MCP server and the editor can be tested without a login. Usage: fake_claude.py [claude flags...] < prompt"""
import json, os, subprocess, sys


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    argv = sys.argv[1:]
    if argv[:2] == ["auth", "status"]:
        print(json.dumps({"loggedIn": True}))
        return
    cfg = json.load(open(argv[argv.index("--mcp-config") + 1], encoding="utf-8"))["mcpServers"]["studio"]
    resumed = argv[argv.index("--resume") + 1] if "--resume" in argv else None
    prompt = sys.stdin.read()
    env = {**os.environ, **cfg["env"]}
    mcp = subprocess.Popen([cfg["command"], *cfg["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8")
    nid = [0]

    def rpc(method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify:
            nid[0] += 1
            msg["id"] = nid[0]
        mcp.stdin.write(json.dumps(msg) + "\n")
        mcp.stdin.flush()
        return None if notify else json.loads(mcp.stdout.readline())["result"]

    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "fake-claude", "version": "0"}})
    rpc("notifications/initialized", notify=True)
    emit({"type": "system", "subtype": "init", "session_id": resumed or "fake-session-1"})

    script = [("get_project", {})]
    if os.environ.get("FAKE_LOOK"):
        script.append(("look", {"time": 10}))
    if "refuse" in prompt:
        script.append(("move_cut", {"shot": 1, "time": 3}))            # an invalid request: the tool must answer with an error
    else:
        script += [("set_card", {"kind": "title", "text": "Hello Claude", "subtitle": "co-edited"}), ("move_cut", {"shot": 3, "time": 14})]
    n = 0
    for name, args in script:
        n += 1
        tid = f"toolu_{n}"
        emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "mcp__studio__" + name, "input": args}]}})
        res = rpc("tools/call", {"name": name, "arguments": args})
        content = []
        for c in res["content"]:
            content.append({"type": "text", "text": c["text"]} if c["type"] == "text"
                           else {"type": "image", "source": {"type": "base64", "media_type": c["mimeType"], "data": c["data"]}})
        emit({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": content, "is_error": res.get("isError", False)}]}})
    answer = "I tried, but that was not possible." if "refuse" in prompt else "Done. I added a title card and moved the cut before shot 3 to 14 s."
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": answer}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": answer, "session_id": resumed or "fake-session-1", "num_turns": n})
    mcp.stdin.close()
    mcp.wait(timeout=10)


if __name__ == "__main__":
    main()
