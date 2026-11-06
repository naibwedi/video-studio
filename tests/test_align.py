"""Lyric alignment maths on synthetic singing (no demucs, no audio files needed)."""
import os, sys, unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import align  # noqa: E402

HOP = align.HOP


def singing(phrases, gap=0.9, lead=1.0, tail=1.0, loud=-20.0, quiet=-60.0, dip=None, seed=1):
    """A loudness curve: silence, then phrases of the given lengths (s) separated by gaps. dip=(phrase_index, depth_dB) adds a breath inside a phrase."""
    rng = np.random.default_rng(seed)
    parts, edges, t = [np.full(int(lead / HOP), quiet)], [], lead
    for k, d in enumerate(phrases):
        n = int(d / HOP)
        seg = loud + rng.normal(0, 1.2, n) + 2 * np.sin(np.linspace(0, 9, n))
        if dip and dip[0] == k:
            seg[n // 2 - 8: n // 2 + 8] -= dip[1]
        parts.append(seg)
        edges.append((t, t + d))
        t += d
        if k < len(phrases) - 1:
            parts.append(np.full(int(gap / HOP), quiet) + rng.normal(0, 1.0, int(gap / HOP)))
            t += gap
    parts.append(np.full(int(tail / HOP), quiet))
    return np.concatenate(parts), edges


def smooth(env):
    return np.convolve(np.pad(env, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid")


class AlignTests(unittest.TestCase):
    def test_the_real_gaps_are_the_deepest_valleys(self):
        env, edges = singing([4.0, 5.0, 4.5, 6.0])
        deepest = sorted(align.find_valleys(smooth(env)), key=lambda x: -x["prom"])[:3]
        for a, b in zip(edges[:-1], edges[1:]):
            gap = (a[1] + b[0]) / 2
            self.assertTrue(any(abs(v["t"] - gap) < 0.25 for v in deepest), f"no deep valley near {gap:.1f}s")

    def test_sung_span_ignores_the_silence_around(self):
        env, edges = singing([4.0, 5.0], lead=2.0, tail=3.0)
        a, b = align.sung_span(smooth(env))
        self.assertAlmostEqual(a, edges[0][0], delta=0.15)
        self.assertAlmostEqual(b, edges[-1][1], delta=0.15)

    def test_lines_land_on_the_phrases(self):
        env, edges = singing([4.0, 5.0, 4.5, 6.0])
        env = smooth(env)
        lines, clarity = align.fit_lines(align.find_valleys(env), ["aaaa aaaa", "bbbbb bbbb", "cccc cccc", "dddddd dddd"], *align.sung_span(env))
        self.assertGreater(clarity, 0.5)
        for (s, e), (a, b) in zip(lines, edges):
            self.assertAlmostEqual(s, a, delta=0.3)
            self.assertAlmostEqual(e, b, delta=0.3)

    def test_a_breath_inside_a_line_is_not_taken_for_a_line_break(self):
        # phrase 2 (index 1) has a breath inside it, but the lyric has only 3 lines: the real gaps are deeper and match the text lengths
        env, edges = singing([4.0, 8.0, 4.0], dip=(1, 12.0))
        env = smooth(env)
        lines, _ = align.fit_lines(align.find_valleys(env), ["x" * 20, "y" * 40, "z" * 20], *align.sung_span(env))
        for (s, e), (a, b) in zip(lines, edges):
            self.assertAlmostEqual(s, a, delta=0.3)
            self.assertAlmostEqual(e, b, delta=0.3)

    def test_without_enough_gaps_it_spreads_evenly_and_says_it_is_unsure(self):
        env, _ = singing([12.0])
        env = smooth(env)
        lines, clarity = align.fit_lines(align.find_valleys(env), ["a", "b", "c"], *align.sung_span(env))
        self.assertEqual(clarity, 0.0)
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(e > s for s, e in lines))
        self.assertTrue(lines[0][0] < lines[1][0] < lines[2][0])


if __name__ == "__main__":
    unittest.main()
