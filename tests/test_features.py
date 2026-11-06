"""Checks for draft / tags / pop-up / teaser planning / qc rules. No ffmpeg or media needed."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import draft, popup, qc, teaser  # noqa: E402

LINES = [{"text": "a", "start": 10.0, "end": 17.0}, {"text": "b", "start": 18.0, "end": 25.0},
         {"text": "c", "start": 26.0, "end": 33.0}, {"text": "d", "start": 34.0, "end": 41.0}]


class TagTests(unittest.TestCase):
    def test_plurals_match(self):
        self.assertEqual(draft.norm("candles"), "candle")
        self.assertEqual(draft.norm("glass"), "glass")

    def test_theme_words_expand(self):
        self.assertIn("candle", draft.expand(["prayer"]))
        self.assertEqual(draft.expand(["roots"]), ["root"])

    def test_pick_avoids_used_and_people(self):
        tags = {"1": {"people": 0, "tags": ["candle", "dark"], "dur": 20},
                "2": {"people": 2, "tags": ["candle"], "dur": 20},
                "3": {"people": 0, "tags": ["candle"], "dur": 20}}
        old = draft.paths.stock_path
        draft.paths.stock_path = lambda c: __file__      # pretend every clip file exists
        try:
            first = draft.pick(tags, ["candle", "dark"], set(), 1, 5, "x")
            second = draft.pick(tags, ["candle", "dark"], {first}, 1, 5, "x")
        finally:
            draft.paths.stock_path = old
        self.assertEqual(first, "1")
        self.assertEqual(second, "3")        # clip 2 shows a face and is skipped


class PopupTests(unittest.TestCase):
    def test_slide_expression_is_offscreen_then_on_then_off(self):
        e = popup.x_expr(10.0, 15.0, 800, 60)
        self.assertIn("pow(1-clip((t-10.0)/0.55,0,1),3)", e)
        self.assertIn("clip((t-(15.0-0.45))/0.45,0,1)", e)

    def test_normalize_accepts_numbers_and_objects(self):
        p = {"channel": {"handle": "@x"}}
        out = popup.normalize(p, [49, {"at": 99, "tagline": "Hi"}])
        self.assertEqual([o["at"] for o in out], [49.0, 99.0])
        self.assertEqual(out[0]["handle"], "@x")
        self.assertEqual(out[1]["tagline"], "Hi")


class TeaserTests(unittest.TestCase):
    def test_auto_segments_cover_start_middle_and_end(self):
        segs = teaser.auto_segments({"subtitles": {"lines": LINES}, "duration": 60.0})
        self.assertEqual(segs[0][0], 5.0)             # 5 s lead-in before the first line
        self.assertEqual(segs[-1][1], 60.0)           # closes on the end of the video
        self.assertTrue(all(b > a for a, b in segs))

    def test_parse_segments(self):
        self.assertEqual(teaser.parse_segments("17-31,70.5-84"), [[17.0, 31.0], [70.5, 84.0]])


class QcTests(unittest.TestCase):
    def project(self, lines, shots, dur=60.0):
        return {"subtitles": {"lines": lines}, "duration": dur, "_shots": shots,
                "overlays": {"title_card": None, "end_card": None, "popups": [58]}}

    def test_flags_overlap_long_and_short_shot(self):
        lines = [{"text": "a", "start": 1, "end": 14}, {"text": "b", "start": 10, "end": 12}]
        notes = qc.project_checks(self.project(lines, [{"at": 0, "clip": "1"}, {"at": 0.5, "clip": "2"}]))
        text = " ".join(t for _, t in notes)
        self.assertIn("overlap", text)
        self.assertIn("long", text)
        self.assertIn("only", text)
        self.assertIn("run past the end", text)

    def test_clean_project_has_no_errors(self):
        lines = [{"text": "a", "start": 1, "end": 6}, {"text": "b", "start": 7, "end": 12}]
        notes = qc.project_checks(self.project(lines, [{"at": 0, "clip": "1"}, {"at": 5, "clip": "2"}]))
        self.assertFalse([n for n in notes if n[0] == "ERROR"])


if __name__ == "__main__":
    unittest.main()
