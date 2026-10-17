#!/usr/bin/env python3
"""Identification-robustness figures show the committed fits, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_parameter_id_robustness.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

RESULTS = rf.RUNS / "parameter_id_robustness" / "results.csv"
DOCS = ["reports/parameter_id_robustness.md"]


class RobustnessFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_parameter_id_robustness)
        cls.results = pd.read_csv(RESULTS)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_markers_carry_errors_and_acceptance(self) -> None:
        for kind in ("noise", "latency"):
            ax = self.built[f"parameter_id_{kind}_degradation.png"][0].axes[0]
            subset = self.results[self.results["kind"].isin(["nominal", kind])]
            markers = [line for line in ax.lines if len(line.get_xdata()) == 1]
            expected = [(row[f"{param}_oracle_relative_error"], bool(row["acceptance_passed"]), shape)
                        for param, _, shape, _ in rf.STIFFNESS for _, row in subset.iterrows()]
            got = [(line.get_ydata()[0], line.get_markerfacecolor() == "black", line.get_marker()) for line in markers]
            self.assertEqual(got, expected)
        ax = self.built["parameter_id_condition_number.png"][0].axes[0]
        dots = [line for line in ax.lines if line.get_marker() == "o"][0]
        np.testing.assert_array_equal(dots.get_xdata(), self.results["jacobian_condition_number"].iloc[::-1])

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)


if __name__ == "__main__":
    unittest.main()
