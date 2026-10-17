#!/usr/bin/env python3
"""Kinematic replay figures show the committed trace, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_kinematic_replay.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

TRACE = rf.RUNS / "model_vs_gym_comparison" / "replay_trace.csv"
DOCS = ["reports/model_vs_gym_comparison.md"]


class KinematicReplayFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_kinematic_replay)
        cls.trace = pd.read_csv(TRACE)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_traces_equal_replay_file(self) -> None:
        ax = self.built["model_vs_gym_trajectory_error.png"][0].axes[0]
        np.testing.assert_array_equal(ax.lines[0].get_xdata(), self.trace["gym_x_m"])
        np.testing.assert_array_equal(ax.lines[1].get_ydata(), self.trace["model_y_m"])
        errors = self.built["model_vs_gym_state_errors.png"][0].axes
        for ax, column in zip(errors, ("error_position_m", "error_yaw_rad", "error_speed_mps")):
            np.testing.assert_array_equal(ax.lines[0].get_ydata(), self.trace[column])

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)


if __name__ == "__main__":
    unittest.main()
