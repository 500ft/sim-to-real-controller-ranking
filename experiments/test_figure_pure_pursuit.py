#!/usr/bin/env python3
"""Pure-pursuit sweep figures show the committed sweep results, and their words live in the captions.

The two heatmaps keep their cell numbers: the one text the figure rules allow inside a data area.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_pure_pursuit.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

RESULTS = rf.RUNS / "pure_pursuit_sweep" / "results.csv"
DOCS = ["reports/pure_pursuit_sweep.md"]


class PurePursuitFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_pure_pursuit)
        cls.results = pd.read_csv(RESULTS)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_heatmap_fields_and_cell_numbers_equal_results(self) -> None:
        for kind, column, digits in (("rms_cte", "rms_cte_m", 2), ("lap_time", "lap_time_s", 1)):
            fig = self.built[f"pure_pursuit_sweep_{kind}_heatmap.png"][0]
            _, _, grid, _ = rf.pp_grid(self.results, kind)
            field = fig.axes[0].images[0].get_array()
            np.testing.assert_array_equal(np.ma.filled(field, np.nan), grid)
            cells = sorted(t.get_text() for t in fig.axes[0].texts if t.get_gid() == "cell")
            expected = self.results[column] if kind == "rms_cte" else self.results[self.results["completed_lap"]][column]
            self.assertEqual(cells, sorted(f"{v:.{digits}f}" for v in expected))

    def test_region_markers_carry_class_and_fill(self) -> None:
        ax = self.built["pure_pursuit_sweep_regions.png"][0].axes[0]
        groups = [g for g in rf.CLASS_STYLE if (self.results["classification"] == g).any()]
        for line, key in zip(ax.lines[1:], groups):
            group = self.results[self.results["classification"] == key]
            np.testing.assert_array_equal(line.get_xdata(), group["lookahead_m"])
            np.testing.assert_array_equal(line.get_ydata(), group["vgain"])
            _, shape, filled = rf.CLASS_STYLE[key]
            self.assertEqual(line.get_marker(), shape)
            self.assertEqual(line.get_markerfacecolor(), "black" if filled else "white")
            self.assertEqual(filled, bool(group["completed_lap"].all()))

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)
        self.assertIn("11 of 30 settings complete a lap", self.built["pure_pursuit_sweep_regions.png"][1])


if __name__ == "__main__":
    unittest.main()
