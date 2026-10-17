#!/usr/bin/env python3
"""Steering-excitation figures show the committed telemetry, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_sysid_excitation.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

TELEMETRY = rf.RUNS / "sysid_steering_excitation" / "telemetry.csv"
DOCS = ["reports/sysid_steering_excitation.md"]


class ExcitationFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_sysid_excitation)
        cls.df = pd.read_csv(TELEMETRY)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_traces_equal_telemetry(self) -> None:
        columns = {"sysid_steering_input.png": ("command_steer_rad", "steer_rad"),
                   "sysid_yaw_response.png": ("yaw_rate_radps", "slip_angle_rad"),
                   "sysid_speed_hold.png": ("command_speed_mps", "speed_mps")}
        for name, pair in columns.items():
            axes = self.built[name][0].axes
            for ax, column in zip(axes, pair):
                np.testing.assert_array_equal(ax.lines[0].get_ydata(), self.df[column], err_msg=name)
            if name != "sysid_yaw_response.png":  # commanded and achieved share axes
                self.assertEqual(axes[0].get_ylim(), axes[1].get_ylim())

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)
        self.assertIn("0.2 to 2 Hz chirp", self.built["sysid_yaw_response.png"][1])


if __name__ == "__main__":
    unittest.main()
