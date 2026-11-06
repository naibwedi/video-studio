"""Fast checks that need no ffmpeg and no media:  python -m unittest discover tests"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import overlays, paths, project, stock  # noqa: E402

LINES = [{"text": "one", "start": 10.0, "end": 14.0}, {"text": "two", "start": 20.0, "end": 26.0}]


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = paths.PROJECTS
        paths.PROJECTS = self.tmp.name
        d = os.path.join(self.tmp.name, "demo")
        os.makedirs(os.path.join(d, "audio"))
        open(os.path.join(d, "audio", "s.wav"), "wb").write(b"x")
        open(os.path.join(d, "clip.mp4"), "wb").write(b"x")
        json.dump({"audio": "audio/s.wav", "duration": 30, "subtitles": {"lines": LINES},
                   "shots": [{"at": "L2m", "clip": "clip.mp4"}, {"at": 0, "clip": "clip.mp4", "start": 2}]},
                  open(os.path.join(d, "project.json"), "w"))

    def tearDown(self):
        paths.PROJECTS = self.old
        self.tmp.cleanup()

    def test_defaults_and_sorting(self):
        p = project.load("demo")
        self.assertEqual(p["fps"], 24)
        self.assertEqual([s["at"] for s in p["_shots"]], [0.0, 23.0])   # L2m = middle of 20..26, sorted by time

    def test_time_references(self):
        self.assertEqual(project.at_time("L1", LINES), 10.0)
        self.assertEqual(project.at_time("L1m", LINES), 12.0)
        self.assertEqual(project.at_time("L2e", LINES), 26.0)
        self.assertEqual(project.at_time("17", LINES), 17.0)
        with self.assertRaises(SystemExit):
            project.at_time("bogus", LINES)

    def test_missing_clip_is_a_clear_error(self):
        with self.assertRaises(SystemExit):
            project.resolve_clip(project.load("demo"), "999999999")

    def test_srt_and_ass(self):
        p = project.load("demo")
        srt = os.path.join(self.tmp.name, "a.srt")
        overlays.write_srt(p, srt)
        text = open(srt, encoding="utf-8").read()
        self.assertIn("00:00:10,050 --> 00:00:13,950", text)
        ass = os.path.join(self.tmp.name, "a.ass")
        overlays.write_ass(p, "16x9", 1920, 1080, ass)
        self.assertEqual(open(ass, encoding="utf-8").read().count("Dialogue:"), 2)


class StockTests(unittest.TestCase):
    def test_pick_file_prefers_1080p(self):
        v = {"video_files": [{"width": 640, "height": 360, "file_type": "video/mp4", "link": "sd"},
                             {"width": 1920, "height": 1080, "file_type": "video/mp4", "link": "hd"}]}
        self.assertEqual(stock.pick_file(v)["link"], "hd")

    def test_stock_names(self):
        self.assertTrue(paths.stock_path("123").endswith("p123.mp4"))
        self.assertTrue(paths.stock_path("pb77").endswith("pb77.mp4"))


if __name__ == "__main__":
    unittest.main()
