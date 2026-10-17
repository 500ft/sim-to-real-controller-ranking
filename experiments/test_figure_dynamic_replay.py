#!/usr/bin/env python3
"""Known-parameter replay figures show the committed trace, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_dynamic_replay.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

TRACE = rf.RUNS / "dynamic_model_replay" / "replay_trace.csv"
DOCS = ["reports/dynamic_model_replay.md"]


class DynamicReplayFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_dynamic_replay)
        cls.trace = pd.read_csv(TRACE)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_traces_equal_replay_file(self) -> None:
        axes = self.built["dynamic_replay_yaw_rate_overlay.png"][0].axes
        np.testing.assert_array_equal(axes[0].lines[0].get_ydata(), self.trace["gym_yaw_rate_radps"])
        np.testing.assert_array_equal(axes[0].lines[1].get_ydata(), self.trace["dynamic_yaw_rate_radps"])
        np.testing.assert_array_equal(axes[1].lines[1].get_ydata(), self.trace["kinematic_yaw_rate_radps"])
        np.testing.assert_array_equal(axes[2].lines[0].get_ydata(), self.trace["gym_steer_rad"])
        self.assertEqual(axes[0].get_ylim(), axes[1].get_ylim())
        errors = self.built["dynamic_replay_state_errors.png"][0].axes
        for ax, column in zip(errors, ("error_position_m", "error_yaw_rad", "error_yaw_rate_radps", "error_speed_mps")):
            np.testing.assert_array_equal(ax.lines[0].get_ydata(), self.trace[column])

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)
        self.assertIn("RMSE 0.026 rad/s", self.built["dynamic_replay_yaw_rate_overlay.png"][1])


if __name__ == "__main__":
    unittest.main()
