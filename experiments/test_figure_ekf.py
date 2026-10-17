#!/usr/bin/env python3
"""EKF figures show the committed trace and summary, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_ekf.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

RUN = rf.RUNS / "ekf_study"
DOCS = ["reports/ekf_study.md"]


class EkfFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_ekf)
        cls.trace = pd.read_csv(RUN / "trace.csv")
        cls.summary = pd.read_csv(RUN / "summary.csv")

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def series(self, scenario, estimator):
        return self.trace[(self.trace["scenario"] == scenario) & (self.trace["estimator"] == estimator)]

    def test_traces_and_rmse_equal_run_files(self) -> None:
        axes = self.built["ekf_position_error_over_time.png"][0].axes
        for ax, scenario in zip(axes, ("low_noise", "dropout_1s")):
            np.testing.assert_array_equal(ax.lines[0].get_ydata(), self.series("low_noise", "dead_reckoning")["position_error_m"])
            np.testing.assert_array_equal(ax.lines[1].get_ydata(), self.series(scenario, "ekf")["position_error_m"])
        ax = self.built["ekf_rmse_summary.png"][0].axes[0]
        order = [s for s in rf.SCENARIO_NAMES if s in set(self.summary["scenario"])]
        pivot = self.summary.pivot(index="scenario", columns="estimator", values="position_rmse_m").loc[order]
        markers = [line for line in ax.lines if line.get_marker() in ("o", "s")]
        np.testing.assert_array_equal(markers[0].get_xdata(), pivot["dead_reckoning"])
        np.testing.assert_array_equal(markers[1].get_xdata(), pivot["ekf"])

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)


if __name__ == "__main__":
    unittest.main()
