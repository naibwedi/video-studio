"""Lyric fonts you can pick in the editor. The files live in library/fonts; Ebrima (the default) comes from Windows.

Each font is rendered from its own small folder (.cache/fonts/<id>), so the name in the subtitle file can only mean that one face.
"""
import os, shutil
from . import paths

# id -> (label, file in library/fonts or None for the Windows default, family name inside the file, bold)
FONTS = {
    "ebrima": ("Ebrima (default)", None, "Ebrima", True),
    "habesha-zibriqriq": ("Habesha Serif - Zibriqriq", "habesha-serif-zibriqriq.ttf", "Habesha Serif Zibriqriq", False),
    "habesha-distort": ("Habesha Serif - Distort", "habesha-serif-distort.ttf", "Habesha Serif Distort", False),
    "habesha-distort-italic": ("Habesha Serif - Distort Italic", "habesha-serif-distort-italic.ttf", "Habesha Serif Distort Italic", False),
    "agbalumo": ("Agbalumo", "agbalumo.ttf", "Agbalumo", False),
    "bela-bereka": ("Bela Bereka", "bela-bereka.ttf", "Bela Bereka", False),
}
DEFAULT = "ebrima"
LIB = os.path.join(paths.ROOT, "library", "fonts")


def clean(font_id):
    return font_id if font_id in FONTS else DEFAULT


def family(font_id):
    return FONTS[clean(font_id)][2]


def bold(font_id):
    return FONTS[clean(font_id)][3]


def render_dir(font_id):
    """A folder holding the chosen font (plus Ebrima for any letters it lacks); this is what ffmpeg's `ass` filter reads fonts from."""
    fid = clean(font_id)
    out = os.path.join(paths.CACHE, "fonts", fid)
    os.makedirs(out, exist_ok=True)
    files = [os.path.join(paths.FONTS_DIR, n) for n in ("ebrima.ttf", "ebrimabd.ttf")]
    if FONTS[fid][1]:
        files.insert(0, os.path.join(LIB, FONTS[fid][1]))
    for f in files:
        dst = os.path.join(out, os.path.basename(f))
        if os.path.isfile(f) and not os.path.exists(dst):
            shutil.copyfile(f, dst)
    return out
