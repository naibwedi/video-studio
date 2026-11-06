"""The editing operations, the MCP protocol, and the chat flow (with a stand-in for Claude). No ffmpeg or login needed."""
import json, os, stat, sys, tempfile, time, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
from core import agent, chat, edits, mcp_server, paths, project  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old = (paths.PROJECTS, paths.STOCK, paths.CACHE, os.environ.get("STUDIO_PROJECTS"), os.environ.get("STUDIO_STOCK"))
        paths.PROJECTS = os.path.join(cls.tmp.name, "projects")
        paths.STOCK = os.path.join(cls.tmp.name, "stock")
        paths.CACHE = os.path.join(cls.tmp.name, "cache")
        os.environ["STUDIO_PROJECTS"], os.environ["STUDIO_STOCK"] = paths.PROJECTS, paths.STOCK
        os.makedirs(paths.STOCK)
        for cid in ("111", "222"):
            open(os.path.join(paths.STOCK, f"p{cid}.mp4"), "wb").write(b"x")

    @classmethod
    def tearDownClass(cls):
        paths.PROJECTS, paths.STOCK, paths.CACHE = cls.old[:3]
        for k, v in zip(("STUDIO_PROJECTS", "STUDIO_STOCK"), cls.old[3:]):
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        cls.tmp.cleanup()

    def make(self, name="demo"):
        d = os.path.join(paths.PROJECTS, name)
        os.makedirs(os.path.join(d, "audio"), exist_ok=True)
        open(os.path.join(d, "audio", "s.wav"), "wb").write(b"x")
        json.dump({"title": "Demo", "audio": "audio/s.wav", "duration": 30,
                   "subtitles": {"lines": [{"text": "one", "start": 2, "end": 8}, {"text": "two", "start": 10, "end": 16}]},
                   "shots": [{"at": 0, "clip": "111", "start": 2}, {"at": 10, "clip": "222", "start": 1}, {"at": 20, "clip": "111", "start": 0}]},
                  open(os.path.join(d, "project.json"), "w"))
        return name


class OpsTests(Base):
    def test_split_and_delete(self):
        name = self.make()
        msg = edits.edit(name, lambda d: edits.split_shot(d, 14))
        self.assertIn("4 shots", msg)
        doc = edits.load_doc(name)
        self.assertEqual([s["at"] for s in doc["shots"]], [0, 10, 14, 20])
        self.assertEqual(doc["shots"][2]["start"], 5.0)                      # 1 s offset + 4 s into the shot
        edits.edit(name, lambda d: edits.delete_shot(d, 3))
        self.assertEqual([s["at"] for s in edits.load_doc(name)["shots"]], [0, 10, 20])

    def test_errors_do_not_change_the_file(self):
        name = self.make()
        before = open(project.json_path(name), "rb").read()
        for fn in (lambda d: edits.split_shot(d, 10.2), lambda d: edits.move_cut(d, 1, 3), lambda d: edits.delete_shot(d, 9),
                   lambda d: edits.set_clip(d, 1, "999"), lambda d: edits.set_line(d, 1, start=9, end=5), lambda d: edits.add_popup(d, 29)):
            with self.assertRaises(ValueError):
                edits.edit(name, fn)
        self.assertEqual(open(project.json_path(name), "rb").read(), before)

    def test_move_cut_is_limited_by_neighbours(self):
        name = self.make()
        msg = edits.edit(name, lambda d: edits.move_cut(d, 3, 99))
        self.assertIn("limited", msg)
        self.assertEqual(edits.load_doc(name)["shots"][2]["at"], 29.5)

    def test_lines_cards_and_popups(self):
        name = self.make()
        edits.edit(name, lambda d: edits.shift_lines(d, 1.5))
        edits.edit(name, lambda d: edits.set_card(d, "title", text="Hi", subtitle="Sub", at=1, until=7))
        edits.edit(name, lambda d: edits.add_popup(d, 12, "Join us"))
        doc = edits.load_doc(name)
        self.assertEqual([(l["start"], l["end"]) for l in doc["lines"]], [(3.5, 9.5), (11.5, 17.5)])
        self.assertEqual(doc["overlays"]["title_card"]["text"], "Hi")
        self.assertEqual(doc["overlays"]["popups"][0]["tagline"], "Join us")
        edits.edit(name, lambda d: edits.set_card(d, "title", enabled=False))
        self.assertIsNone(edits.load_doc(name)["overlays"]["title_card"])

    def test_swap_clip_needs_a_library_clip(self):
        name = self.make()
        edits.edit(name, lambda d: edits.set_clip(d, 2, "222", 3))
        self.assertEqual(edits.load_doc(name)["shots"][1]["start"], 3.0)
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d: edits.set_clip(d, 2, "../../x"))


class McpTests(Base):
    def rpc(self, method, params=None, mid=1):
        return mcp_server.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_handshake_and_tools(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18"})
        self.assertEqual(r["result"]["serverInfo"]["name"], "studio")
        names = {t["name"] for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertTrue({"get_project", "look", "split_shot", "swap_clip", "render", "search_clips"} <= names)
        self.assertIsNone(mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIn("error", self.rpc("nope"))

    def test_tool_calls_return_text_or_a_clear_error(self):
        name = self.make()
        mcp_server._state["project"] = name
        ok = self.rpc("tools/call", {"name": "split_shot", "arguments": {"time": 14}})["result"]
        self.assertFalse(ok["isError"])
        bad = self.rpc("tools/call", {"name": "split_shot", "arguments": {"time": 10.1}})["result"]
        self.assertTrue(bad["isError"])
        self.assertIn("Could not do that", bad["content"][0]["text"])
        text = self.rpc("tools/call", {"name": "get_project", "arguments": {}})["result"]["content"][0]["text"]
        self.assertIn("SHOTS (4)", text)
        self.assertTrue(self.rpc("tools/call", {"name": "no_such_tool", "arguments": {}})["result"]["isError"])
        mcp_server._state["project"] = None


class ChatTests(Base):
    def test_events_from_claude_code_stream_lines(self):
        sess = chat.Session("demo")
        self.assertEqual(chat.events_from({"type": "system", "subtype": "init", "session_id": "abc"}, sess), [])
        self.assertEqual(sess.session_id, "abc")
        ev = chat.events_from({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi"}, {"type": "tool_use", "id": "t1", "name": "mcp__studio__split_shot", "input": {"time": 5}}]}}, sess)
        self.assertEqual([e["type"] for e in ev], ["text", "tool"])
        self.assertEqual(ev[1]["name"], "split_shot")
        ev = chat.events_from({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "Split."}]}]}}, sess)
        self.assertEqual([e["type"] for e in ev], ["tool_result", "changed"])       # an edit tool succeeded: the editor must reload
        ev = chat.events_from({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "x"}]}}, sess)
        self.assertEqual([e["type"] for e in ev], ["tool_result"])                  # a failed edit changes nothing
        ev = chat.events_from({"type": "result", "is_error": False, "result": "ok", "session_id": "abc", "num_turns": 2}, sess)
        self.assertEqual(ev[0]["type"], "done")

    def test_claude_runs_with_only_the_studio_tools(self):
        cmd = chat.command("claude", "cfg.json", "sid-1")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")                       # no built-in file or shell tools
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "mcp__studio")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(cmd[cmd.index("--resume") + 1], "sid-1")

    def run_turn(self, name, message, extra_env=None):
        wrapper = os.path.join(self.tmp.name, "claude.bat" if os.name == "nt" else "claude")
        script = os.path.join(HERE, "fake_claude.py")
        open(wrapper, "w").write(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n' if os.name == "nt" else f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        os.chmod(wrapper, os.stat(wrapper).st_mode | stat.S_IEXEC)
        os.environ["CLAUDE_BIN"] = wrapper
        chat._AUTH.update(t=0.0, v=None)
        chat.SESSIONS.clear()
        sess = chat.get(name)
        chat.send(name, message, "[ctx]", "http://127.0.0.1:1", "tok")
        for _ in range(200):
            if not sess.running and any(e["type"] == "done" for e in sess.events):
                break
            time.sleep(0.1)
        return sess

    def test_a_whole_turn_with_the_stand_in(self):
        name = self.make()
        try:
            sess = self.run_turn(name, "add a title card and move the cut")
        finally:
            os.environ.pop("CLAUDE_BIN", None)
        kinds = [e["type"] for e in sess.events]
        self.assertEqual(kinds[0], "user")
        self.assertEqual(kinds.count("changed"), 2)
        self.assertEqual(sess.events[-1]["type"], "done")
        self.assertTrue(sess.events[-1]["ok"])
        self.assertEqual(sess.session_id, "fake-session-1")
        doc = edits.load_doc(name)
        self.assertEqual(doc["overlays"]["title_card"]["text"], "Hello Claude")
        self.assertEqual(doc["shots"][2]["at"], 14.0)

    def test_a_refused_edit_is_reported_and_changes_nothing(self):
        name = self.make("demo2")
        before = open(project.json_path(name), "rb").read()
        try:
            sess = self.run_turn(name, "please refuse this")
        finally:
            os.environ.pop("CLAUDE_BIN", None)
        errors = [e for e in sess.events if e["type"] == "tool_result" and e["error"]]
        self.assertEqual(len(errors), 1)
        self.assertNotIn("changed", [e["type"] for e in sess.events])
        self.assertEqual(open(project.json_path(name), "rb").read(), before)


if __name__ == "__main__":
    unittest.main()
