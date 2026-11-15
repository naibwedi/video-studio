import os, unittest
from core import fonts, textstyle


class FontsTest(unittest.TestCase):
    def test_every_font_file_exists(self):
        for fid, (_label, file, _fam, _bold) in fonts.FONTS.items():
            if file:
                self.assertTrue(os.path.isfile(os.path.join(fonts.LIB, file)), fid)

    def test_unknown_font_falls_back(self):
        self.assertEqual(textstyle.clean({"font": "nope"})["font"], "ebrima")
        self.assertEqual(textstyle.clean({"font": "agbalumo"})["font"], "agbalumo")
        self.assertEqual(textstyle.clean(None)["font"], "ebrima")

    def test_render_dir_holds_only_the_chosen_font(self):
        d = fonts.render_dir("bela-bereka")
        names = os.listdir(d)
        self.assertIn("bela-bereka.ttf", names)
        self.assertNotIn("agbalumo.ttf", names)


if __name__ == "__main__":
    unittest.main()
