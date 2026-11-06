"""Dashboard server checks: security rules, saving, validation. Needs no ffmpeg and no media."""
import json, os, re, sys, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import paths, server  # noqa: E402


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old = (paths.PROJECTS, paths.EXPORTS)
        paths.PROJECTS = os.path.join(cls.tmp.name, "projects")
        paths.EXPORTS = os.path.join(cls.tmp.name, "exports")
        d = os.path.join(paths.PROJECTS, "demo")
        os.makedirs(os.path.join(d, "audio"))
        os.makedirs(os.path.join(paths.EXPORTS, "demo"))
        open(os.path.join(d, "audio", "s.wav"), "wb").write(b"x")
        open(os.path.join(d, "clip.mp4"), "wb").write(b"x")
        open(os.path.join(paths.EXPORTS, "demo", "out.mp4"), "wb").write(b"0123456789")
        open(os.path.join(cls.tmp.name, "secret.txt"), "w").write("secret")
        json.dump({"title": "Demo", "audio": "audio/s.wav", "duration": 30,
                   "subtitles": {"lines": [{"text": "a", "start": 1, "end": 5}]},
                   "shots": [{"at": 0, "clip": "clip.mp4"}]}, open(os.path.join(d, "project.json"), "w"))
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.token = re.search(r'const TOKEN = "(\w+)"', cls.call("/")[2].decode())[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        paths.PROJECTS, paths.EXPORTS = cls.old
        cls.tmp.cleanup()

    @classmethod
    def call(cls, path, obj=None, token=True, host=None, headers=None):
        data = json.dumps(obj).encode() if obj is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{cls.port}{path}", data=data)
        if token and data is not None:
            req.add_header("X-Studio-Token", cls.token)
        if host:
            req.add_header("Host", host)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_page_and_ui_files(self):
        st, _, body = self.call("/")
        self.assertEqual(st, 200)
        self.assertNotIn(b"__TOKEN__", body)
        for f in ("app.js", "app.css", "vendor/wavesurfer.min.js", "vendor/Sortable.min.js"):
            self.assertEqual(self.call("/ui/" + f)[0], 200, f)
        self.assertEqual(self.call("/ui/../server.py")[0], 404)
        self.assertEqual(self.call("/ui/nope.js")[0], 404)

    def test_foreign_host_is_refused(self):
        self.assertEqual(self.call("/api/projects", host="evil.example.com")[0], 403)

    def test_post_needs_the_token(self):
        self.assertEqual(self.call("/api/project/demo/save", {"title": "x"}, token=False)[0], 403)

    def test_projects_and_project(self):
        names = [p["name"] for p in json.loads(self.call("/api/projects")[2])]
        self.assertEqual(names, ["demo"])
        d = json.loads(self.call("/api/project/demo")[2])
        self.assertEqual(d["duration"], 30)
        self.assertEqual(d["channel"]["handle"], "@ሰብአሰገልThemagis")
        self.assertEqual([e["path"] for e in d["exports"]], ["out.mp4"])

    def test_save_validates_and_keeps_backup(self):
        bad = self.call("/api/project/demo/save", {"shots": [{"at": "soon", "clip": "clip.mp4"}]})
        self.assertEqual(bad[0], 400)
        self.assertEqual(self.call("/api/project/demo/save", {"shots": [{"at": 1, "clip": "../../etc/passwd"}]})[0], 400)
        ok = self.call("/api/project/demo/save", {"title": "New", "theme": "candle rain",
                                                  "lines": [{"text": "x", "start": 2, "end": 6, "keywords": ["a"]}],
                                                  "shots": [{"at": "L1", "clip": "clip.mp4", "start": 1.5}],
                                                  "overlays": {"popups": [{"at": 10, "dur": 4}], "title_card": None}})
        self.assertEqual(ok[0], 200)
        raw = json.load(open(os.path.join(paths.PROJECTS, "demo", "project.json")))
        self.assertEqual(raw["title"], "New")
        self.assertEqual(raw["theme"], ["candle", "rain"])
        self.assertEqual(raw["shots"][0]["at"], "L1")
        self.assertEqual(raw["overlays"]["popups"][0]["at"], 10.0)
        self.assertTrue(os.path.exists(os.path.join(paths.PROJECTS, "demo", "project.json.bak")))

    def test_exports_are_served_with_ranges_and_cannot_escape(self):
        st, hdr, body = self.call("/files/demo/out.mp4", headers={"Range": "bytes=2-4"})
        self.assertEqual((st, body), (206, b"234"))
        self.assertEqual(hdr["Content-Range"], "bytes 2-4/10")
        self.assertEqual(self.call("/files/demo/..%2F..%2Fsecret.txt")[0], 403)
        self.assertEqual(self.call("/files/demo/../../secret.txt")[0], 403)

    def test_upload_name_rules(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/upload?name=../bad&filename=s.wav", data=b"x", method="POST")
        req.add_header("X-Studio-Token", self.token)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_unknown_project_and_action_are_rejected(self):
        self.assertEqual(self.call("/api/job", {"project": "nope", "action": "qc"})[0], 400)
        self.assertEqual(self.call("/api/job", {"project": "demo", "action": "format-disk"})[0], 400)
        self.assertEqual(self.call("/api/job", {"project": "demo", "action": "build", "size": "huge"})[0], 400)


class JobTests(unittest.TestCase):
    def test_progress_follows_the_log(self):
        job = {"status": "running", "log": []}
        self.assertEqual(server.job_progress(job), 0.02)
        job["log"] = ["  shot  1/10  1  rendered", "  shot  2/10  2  rendered"]
        self.assertAlmostEqual(server.job_progress(job), 0.14)
        job["log"] += [f"  shot {i}/10 x" for i in range(3, 11)] + ["  wrote exports/x.mp4"]
        self.assertGreater(server.job_progress(job), 0.9)
        job["status"] = "done"
        self.assertEqual(server.job_progress(job), 1.0)

    def test_cancel_a_queued_job(self):
        job = {"status": "queued", "proc": None}
        server.cancel_job(job)
        self.assertEqual(job["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
