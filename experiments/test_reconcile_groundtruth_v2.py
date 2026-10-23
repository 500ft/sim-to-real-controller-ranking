"""Hand-calculated cases for the Groundtruth reconciliation variants."""

import unittest

import numpy as np

from experiments.reconcile_groundtruth_v2 import excluded_masks, recording_variants, retained_window


def encode(progress):
    angle = 2 * np.pi * np.asarray(progress, dtype=np.float32)
    return np.sin(angle).astype(np.float32), np.cos(angle).astype(np.float32)


class ReconcileTest(unittest.TestCase):
    def test_loader_masks_differ_only_on_a_run_crossing_a_boundary(self):
        # Recording A: rows 0-3, terminal from row 2. Recording B: rows 4-5, all
        # terminal. Recording C: rows 6-7, clean.
        terminal = np.array([0, 0, 1, 1, 1, 1, 0, 0], dtype=bool)
        masks = excluded_masks(terminal, np.array([0, 4, 6]), np.array([4, 6, 8]))
        self.assertEqual(masks["corrected"].tolist(), [False, False, False, True, False, True, False, False])
        self.assertEqual(masks["original"].tolist(), [False, False, False, True, True, True, False, False])
        self.assertEqual(retained_window(0, 4, masks["corrected"]), (0, 3))
        self.assertEqual(retained_window(4, 6, masks["corrected"]), (4, 5))
        self.assertIsNone(retained_window(4, 6, masks["original"]))

    def test_final_row_and_alignment_variants(self):
        # Four retained rows plus one lookahead row; a 0.1 threshold is crossed
        # between rows 2 and 3 and another between row 3 and the lookahead row.
        progress = [0.05, 0.08, 0.09, 0.12, 0.21]
        sin, cos = encode(progress)
        action = np.zeros((5, 2))
        action[:, 0] = 0.1
        previous = np.zeros(5, dtype=np.float32)
        stored = {name: np.arange(1, 6, dtype=float) for name in ("progress", "lifetime", "min_act", "checkpoint")}
        data = {"sin": sin, "cos": cos, "action": action, "previous": previous, "stored": stored}
        returns = recording_variants((10, 14), True, data)
        w = 0.99 ** np.arange(4)
        min_act = 1 - (0.1 / 0.4189) ** 2
        # Zero final row: arrival credits the crossing at row 3, which is then zeroed.
        zero = returns["zero/frozen_v2"]
        self.assertAlmostEqual(zero["checkpoint"], 0.0)
        self.assertAlmostEqual(zero["lifetime"], float(np.dot(w, [1, 1, 1, 0])))
        self.assertAlmostEqual(zero["progress"], float(np.dot(w, [3, 1, 3, 0])), places=4)
        # Departure alignment credits the same crossing one row earlier, so it survives zeroing.
        self.assertAlmostEqual(returns["zero/departure_aligned"]["checkpoint"], 10 * w[2])
        # Keep: the lookahead row feeds the final row for progress and checkpoint.
        keep = returns["keep/frozen_v2"]
        self.assertAlmostEqual(keep["lifetime"], float(np.dot(w, [1, 1, 1, 1])))
        self.assertAlmostEqual(keep["progress"], float(np.dot(w, [3, 1, 3, 9])), places=4)
        self.assertAlmostEqual(keep["checkpoint"], 10 * w[3])
        self.assertAlmostEqual(keep["min_act"], min_act * w.sum())
        self.assertAlmostEqual(returns["keep/departure_aligned"]["checkpoint"], 10 * w[2] + 10 * w[3])
        # Stored rows pass through; zero drops the final stored row.
        self.assertAlmostEqual(returns["keep/stored_new_rewards"]["progress"], float(np.dot(w, [1, 2, 3, 4])))
        self.assertAlmostEqual(returns["zero/stored_new_rewards"]["progress"], float(np.dot(w, [1, 2, 3, 0])))

    def test_keep_without_lookahead_retains_row_values(self):
        progress = [0.05, 0.08, 0.12]
        sin, cos = encode(progress)
        data = {"sin": sin, "cos": cos, "action": np.zeros((3, 2)), "previous": np.zeros(3, dtype=np.float32),
                "stored": {name: np.ones(3) for name in ("progress", "lifetime", "min_act", "checkpoint")}}
        returns = recording_variants((0, 3), False, data)
        w = 0.99 ** np.arange(3)
        for source in ("frozen_v2", "departure_aligned"):
            self.assertAlmostEqual(returns[f"keep/{source}"]["lifetime"], w.sum())
            self.assertAlmostEqual(returns[f"keep/{source}"]["min_act"], w.sum())
            self.assertAlmostEqual(returns[f"zero/{source}"]["lifetime"], w[:2].sum())
        self.assertAlmostEqual(returns["keep/departure_aligned"]["progress"], float(np.dot(w, [3, 4, 0])), places=4)


if __name__ == "__main__":
    unittest.main()
