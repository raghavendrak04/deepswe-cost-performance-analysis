#!/usr/bin/env python3
"""Unit tests for patch selectors."""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from select_patch import changed_lines, jaccard, pick_random, pick_consensus


class TestChangedLines(unittest.TestCase):
    def test_basic_diff(self):
        patch = """\
--- a/foo.py
+++ b/foo.py
+added line
-removed line
 unchanged line
+another add"""
        result = changed_lines(patch)
        self.assertEqual(result, {"added line", "removed line", "another add"})

    def test_empty_patch(self):
        self.assertEqual(changed_lines(""), set())

    def test_ignores_file_headers(self):
        patch = "--- a/foo.py\n+++ b/foo.py\n+real change"
        result = changed_lines(patch)
        self.assertEqual(result, {"real change"})

    def test_strips_whitespace(self):
        patch = "+  spaced  "
        result = changed_lines(patch)
        self.assertEqual(result, {"spaced"})


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        s = {"a", "b", "c"}
        self.assertAlmostEqual(jaccard(s, s), 1.0)

    def test_disjoint(self):
        self.assertAlmostEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_partial_overlap(self):
        self.assertAlmostEqual(jaccard({"a", "b"}, {"b", "c"}), 1 / 3)

    def test_both_empty(self):
        self.assertAlmostEqual(jaccard(set(), set()), 0.0)


class TestPickRandom(unittest.TestCase):
    def test_in_range(self):
        rng = random.Random(42)
        for _ in range(100):
            idx = pick_random(5, rng)
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, 5)


class TestPickConsensus(unittest.TestCase):
    def test_identical_patches_returns_first(self):
        patches = ["+fix\n+common", "+fix\n+common", "+fix\n+common"]
        idx = pick_consensus(patches)
        self.assertEqual(idx, 0)  # All equal, returns first

    def test_outlier_patch(self):
        # Two similar patches, one different
        patches = [
            "+fix A\n+common line\n+shared fix",
            "+fix B\n+common line\n+shared fix",
            "+totally different\n+unique stuff\n+random change",
        ]
        idx = pick_consensus(patches)
        # Should pick one of the first two (more overlap)
        self.assertIn(idx, [0, 1])

    def test_all_empty(self):
        patches = ["", "", ""]
        idx = pick_consensus(patches)
        self.assertEqual(idx, 0)  # Fallback to first

    def test_single_nonempty(self):
        patches = ["", "+fix", ""]
        idx = pick_consensus(patches)
        self.assertEqual(idx, 1)  # Only non-empty patch


class TestEndToEnd(unittest.TestCase):
    """Verify the synthetic pipeline produces expected outputs."""

    def test_synthetic_pool_shape(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from analyze import generate_synthetic_pool

        pool = generate_synthetic_pool(n_tasks=10, n_attempts=8, seed=42)
        self.assertEqual(len(pool), 80)
        self.assertEqual(len(pool.task.unique()), 10)
        self.assertTrue(all(col in pool.columns for col in [
            "task", "passed", "cost_usd", "latency_s", "model_calls"
        ]))
        # Cost should be positive
        self.assertTrue((pool.cost_usd > 0).all())
        # Pass rate should vary across tasks
        pr = pool.groupby("task").passed.mean()
        self.assertGreater(pr.max(), 0.5)  # Some easy tasks
        self.assertEqual(pr.min(), 0.0)     # Some impossible tasks


if __name__ == "__main__":
    unittest.main()
