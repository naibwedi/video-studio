"""v0.7: lyric look + karaoke, reorder, transitions, beats, versions, templates, YouTube text, smart crop. No ffmpeg needed except where noted."""
import json, math, os, struct, sys, unittest, wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_edits import Base  # noqa: E402
from core import agent, beats, edits, overlays, paths, project, smartcrop, textstyle, versions, youtube  # noqa: E402


class TextStyleTests(Base):
    def test_clean_fixes_bad_values(self):
        s = textstyle.clean({"color": "red", "scale": 9, "position": "side", "outline": -3, "karaoke": 1, "nonsense": 5})
        self.assertEqual((s["color"], s["scale"], s["position"], s["outline"], s["karaoke"]), ("#F5F5F5", 1.8, "bottom", 0, True))
        self.assertNotIn("nonsense", s)

    def test_sweep_adds_up_and_ends_before_the_line_does(self):
        spans = textstyle.sweep_times("ab cde f", 10, 20)
        self.assertEqual([w for w, *_ in spans], ["ab", "cde", "f"])
        self.assertAlmostEqual(spans[0][1], 10 + 0.05 + textstyle.LEAD, places=2)
        self.assertLess(spans[-1][2], 20 - 0.05)
        self.assertGreater(spans[1][2] - spans[1][1], spans[0][2] - spans[0][1])            # the longer word gets longer
        tags = textstyle.karaoke_text("ab cde f", 10, 20)
        cs = [int(x) for x in __import__("re").findall(r"\\kf(\d+)", tags)]
        self.assertEqual(sum(cs), round((spans[-1][2] - spans[0][1]) * 100))

    def test_ass_has_karaoke_and_position(self):
        name = self.make("look")
        edits.edit(name, lambda d: edits.set_text_style(d, preset="gold"))
        edits.edit(name, lambda d: edits.set_text_style(d, position="top", scale=1.2))
        p = project.load(name)
        out = os.path.join(self.tmp.name, "t.ass")
        overlays.write_ass(p, "16x9", 1920, 1080, out)
        text = open(out, encoding="utf-8").read()
        self.assertIn("\\kf", text)
        self.assertIn(",8,60,60,", text)                                                    # alignment 8 = top
        self.assertIn("&H005CBEE9", text)                                                   # #E9BE5C in BGR order
        edits.edit(name, lambda d: edits.set_text_style(d, preset="classic"))
        overlays.write_ass(project.load(name), "16x9", 1920, 1080, out)
        self.assertNotIn("\\kf", open(out, encoding="utf-8").read())

    def test_bad_preset(self):
        name = self.make("look2")
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d: edits.set_text_style(d, preset="neon"))


class ShotOrderTests(Base):
    def test_reorder_keeps_lengths(self):
        name = self.make("ord")
        edits.edit(name, lambda d: edits.split_shot(d, 5))           # shots 0-5, 5-10, 10-20, 20-30
        edits.edit(name, lambda d: edits.reorder_shot(d, 3, 1))      # the 10 s shot goes first
        d = edits.load_doc(name)
        self.assertEqual([s["at"] for s in d["shots"]], [0, 10, 15, 20])
        self.assertEqual(d["shots"][0]["clip"], "222")
        self.assertEqual(d["shots"][0]["start"], 1.0)
        self.assertEqual(d["duration"], 30)
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d2: edits.reorder_shot(d2, 1, 9))

    def test_transitions_round_trip_and_render_filter(self):
        name = self.make("tr")
        edits.edit(name, lambda d: edits.set_transition(d, 2, "wipeleft"))
        self.assertEqual(edits.load_doc(name)["shots"][1]["transition"], "wipeleft")
        with open(project.json_path(name), encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["shots"][1]["transition"], "wipeleft")
        self.assertNotIn("transition", raw["shots"][2])                                     # the default is not written
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d: edits.set_transition(d, 1, "fade"))
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d: edits.set_transition(d, 2, "spin"))
        edits.edit(name, lambda d: edits.set_all_transitions(d, "dissolve"))
        self.assertTrue(all(s["transition"] == "dissolve" for s in edits.load_doc(name)["shots"][1:]))


def click_track(bpm=120, seconds=20, sr=22050):
    import numpy as np
    x = np.zeros(int(sr * seconds), dtype=np.float32)
    t, k = 0.0, 0
    tone = np.sin(2 * np.pi * 1000 * np.arange(400) / sr) * np.exp(-np.arange(400) / 80)
    while t < seconds - 0.1:
        i = int(t * sr)
        x[i:i + 400] += (1.0 if k % 4 == 0 else 0.6) * tone[: len(x) - i][:400]
        t += 60 / bpm
        k += 1
    return x


class BeatTests(Base):
    def test_finds_the_tempo_of_a_click_track(self):
        env = beats.onset_strength(click_track(120, 20))
        bpm = beats.tempo(env)
        self.assertAlmostEqual(bpm, 120, delta=4)
        frames = beats.track(env, bpm)
        gaps = [y - x for x, y in zip(frames / beats.FPS, (frames / beats.FPS)[1:])]
        self.assertLess(max(gaps) - min(gaps), 0.12)
        self.assertAlmostEqual(sum(gaps) / len(gaps), 0.5, delta=0.02)
        self.assertGreaterEqual(len(frames), 35)

    def test_snap_cuts(self):
        doc = {"duration": 30, "shots": [{"at": 0}, {"at": 10.2}, {"at": 20.5}]}
        n = beats.snap_cuts(doc, [5.0, 10.0, 15.0, 20.0, 25.0], max_move=0.6)
        self.assertEqual((n, doc["shots"][1]["at"], doc["shots"][2]["at"]), (2, 10.0, 20.0))
        doc = {"duration": 30, "shots": [{"at": 0}, {"at": 10.2}, {"at": 10.6}]}                       # would make a shot too short
        beats.snap_cuts(doc, [10.0, 10.4], max_move=0.6)
        self.assertGreaterEqual(doc["shots"][2]["at"] - doc["shots"][1]["at"], 0.5)


class VersionTests(Base):
    def test_snapshot_dedupe_restore_and_templates(self):
        name = self.make("ver")
        a = versions.snapshot(name, "saved")
        self.assertIsNotNone(a)
        self.assertIsNone(versions.snapshot(name, "saved"))                                  # nothing changed
        edits.edit(name, lambda d: edits.set_title(d, "Changed"))
        self.assertIsNone(versions.snapshot(name, "auto"))                                   # too soon for an automatic one
        b = versions.snapshot(name, "named", force=True)
        self.assertEqual(len(versions.listing(name)), 2)
        versions.restore(name, a)
        self.assertEqual(edits.load_doc(name)["title"], "Demo")
        self.assertGreaterEqual(len(versions.listing(name)), 3)                              # the restore is itself undoable
        self.assertTrue(b)
        with self.assertRaises(ValueError):
            versions.restore(name, "../../etc")

        versions.TEMPLATES = os.path.join(self.tmp.name, "templates")
        edits.edit(name, lambda d: edits.set_text_style(d, preset="karaoke"))
        versions.save_template("mine", name)
        raw = {"title": "New", "audio": "a.wav"}
        versions.apply_template(raw, "mine", "New song")
        self.assertTrue(raw["subtitles"]["style"]["karaoke"])
        self.assertNotIn("lines", raw["subtitles"])
        with self.assertRaises(ValueError):
            versions.apply_template({}, "missing", "x")


class YoutubeAndCropTests(Base):
    def test_youtube_text(self):
        name = self.make("yt")
        paths.EXPORTS = os.path.join(self.tmp.name, "exports")
        path, text = youtube.make(name)
        self.assertTrue(os.path.exists(path))
        self.assertIn("TITLE", text)
        self.assertIn("0:02  one", text)                                                     # lyrics with times
        self.assertLessEqual(len(text.split("TITLE\n")[1].split("\n")[0]), 100)

    def test_saliency_prefers_the_busy_side(self):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (192, 108), (40, 40, 40))
        ImageDraw.Draw(im).ellipse((140, 30, 180, 80), fill=(250, 220, 40))                 # a bright object on the right
        cols = smartcrop.saliency(im).sum(axis=0)
        self.assertGreater(cols[140:180].sum(), cols[0:40].sum() * 3)


class ToolsTests(Base):
    def test_tools_registered(self):
        for t in ("reorder_shot", "set_transition", "set_all_transitions", "set_text_style", "beat_grid", "snap_cuts_to_beats", "auto_crop_vertical", "search_by_meaning", "youtube_pack"):
            self.assertIn(t, agent.TOOLS)
        for t in ("reorder_shot", "set_transition", "set_text_style", "snap_cuts_to_beats", "auto_crop_vertical"):
            self.assertIn(t, agent.EDIT_TOOLS)

    def test_claude_can_style_and_reorder(self):
        name = self.make("tool")
        r = agent.call("set_text_style", {"preset": "bold"}, name)
        self.assertFalse(r["isError"])
        r = agent.call("reorder_shot", {"shot": 2, "to": 3}, name)
        self.assertFalse(r["isError"], r)
        self.assertEqual(edits.load_doc(name)["subs"]["preset"], "bold")
        self.assertTrue(agent.call("set_transition", {"shot": 1, "kind": "fade"}, name)["isError"])
        self.assertIn("Lyrics look: bold", agent.call("get_project", {}, name)["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
