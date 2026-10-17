#!/usr/bin/env python3
"""RK4 convergence figures show the committed sweep, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_convergence.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

RESULTS = rf.RUNS / "integrator_convergence" / "convergence_results.csv"
DOCS = ["reports/integrator_convergence.md"]


class ConvergenceFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_integrator_convergence)
        cls.results = pd.read_csv(RESULTS).sort_values("dt_s")

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_points_equal_results_and_fill_marks_collision(self) -> None:
        fig = self.built["integrator_convergence_metrics.png"][0]
        collided = rf._collided(self.results)
        for ax, column in zip(fig.axes, ("final_progress_m", "rms_cte_m", "max_abs_cte_m")):
            ok, bad = ax.lines[0], ax.lines[1]
            np.testing.assert_array_equal(ok.get_ydata(), self.results[~collided][column])
            np.testing.assert_array_equal(bad.get_ydata(), self.results[collided][column])
            self.assertEqual(ok.get_markerfacecolor(), "black")
            self.assertEqual(bad.get_markerfacecolor(), "white")
        fig = self.built["integrator_convergence_position_error.png"][0]
        data = self.results[self.results["dt_s"] > self.results["dt_s"].min()]
        ok = data[~rf._collided(data)]
        np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), ok["rms_position_error_vs_ref_progress_m"])
        np.testing.assert_array_equal(fig.axes[1].lines[2].get_ydata(), ok["max_position_change_vs_next_finer_dt_progress_m"])

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)
        caption = self.built["integrator_convergence_position_error.png"][1]
        self.assertIn("both refinement tolerances hold from 2 ms down", caption)
        self.assertIn("0.05 m and 0.2 m", caption)


if __name__ == "__main__":
    unittest.main()
