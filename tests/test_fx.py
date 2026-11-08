"""Creative effects: validation, shot look/move round trip, and that the light expression can never overflow to a black frame."""
import math, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_edits import Base  # noqa: E402
from core import edits, fx, textstyle  # noqa: E402


class FxTests(Base):
    def test_clean(self):
        f = fx.clean({"glow": 5, "pulse": 9, "dust": 1, "flash": ["3", 1.234, "x", 3]})
        self.assertEqual((f["glow"], f["pulse"], f["dust"]), (1.0, 0.12, True))
        self.assertEqual(f["flash"], [1.23, 3.0])

    def test_look_move_round_trip_and_errors(self):
        name = self.make("fxrt")
        edits.edit(name, lambda d: edits.set_look(d, 2, "warm"))
        edits.edit(name, lambda d: edits.set_move(d, 2, "in"))
        edits.edit(name, lambda d: edits.set_fx(d, glow=0.4, dust=True, flash=[5, 2]))
        d = edits.load_doc(name)
        self.assertEqual((d["shots"][1]["look"], d["shots"][1]["move"], d["shots"][0]["look"]), ("warm", "in", ""))
        self.assertEqual((d["fx"]["glow"], d["fx"]["dust"], d["fx"]["flash"]), (0.4, True, [2.0, 5.0]))
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d2: edits.set_look(d2, 1, "neon"))
        with self.assertRaises(ValueError):
            edits.edit(name, lambda d2: edits.set_move(d2, 1, "spin"))
        edits.edit(name, lambda d2: edits.set_look(d2, 2, "none"))
        self.assertEqual(edits.load_doc(name)["shots"][1]["look"], "")

    def test_light_expression_never_overflows(self):
        expr = fx.light_expr([22.0, 60.9], [i * 0.6 for i in range(140)], 0.05)
        import re
        for t in (0.0, 3.0, 30.0, 84.9):
            # every exp() argument must be <= 0 at every time, otherwise exp overflows and (inf * 0) turns the frame black
            for m in re.finditer(r"exp\(-(\d+)\*max\(t-([\d.]+),0\)\)", expr):
                self.assertLessEqual(-float(m[1]) * max(t - float(m[2]), 0), 0)
        self.assertNotIn("exp(-8*(t-", expr)

    def test_lyric_glow_in_ass(self):
        name = self.make("fxass")
        edits.edit(name, lambda d: edits.set_text_style(d, preset="gold", glow=True, reveal=True))
        from core import overlays, project
        out = os.path.join(self.tmp.name, "g.ass")
        overlays.write_ass(project.load(name), "16x9", 1920, 1080, out)
        text = open(out, encoding="utf-8").read()
        self.assertIn(chr(92) + "blur", text)
        self.assertIn(chr(92) + "fscx90", text)
        self.assertIn("Dialogue: 1,", text)
        self.assertTrue(textstyle.clean({"glow": 1})["glow"])


if __name__ == "__main__":
    unittest.main()
