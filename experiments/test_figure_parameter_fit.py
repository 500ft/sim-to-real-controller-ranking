#!/usr/bin/env python3
"""Parameter-fit figures (Gym run and ROS-backed capture) show the committed traces; words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_parameter_fit.py
"""
import unittest

import numpy as np
import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

CASES = {  # run directory -> (fit image, residual image, docs)
    rf.RUNS / "dynamic_parameter_identification": (
        rf.FIGURES / "dynamic_parameter_fit.png", rf.FIGURES / "dynamic_parameter_residuals.png",
        ["reports/dynamic_parameter_identification.md"]),
    rf.ITEM11 / "metrics" / "enriched_fit": (
        rf.ITEM11 / "figures" / "enriched_ros_fit.png", rf.ITEM11 / "figures" / "enriched_ros_residuals.png",
        ["evidence/item11/enriched_identification.md"]),
}


class ParameterFitFigureTest(FigureChecks, unittest.TestCase):
    def test_fit_and_residuals(self) -> None:
        for run_dir, (fit_path, residual_path, docs) in CASES.items():
            evidence = rf.SIMULATOR_ROS if "evidence" in run_dir.parts else rf.SIMULATOR
            built = capture(rf.draw_parameter_fit, run_dir, fit_path, residual_path, evidence)
            self.addCleanup(close_all, built)
            fit_trace = pd.read_csv(run_dir / "fit_trace.csv")
            validation = pd.read_csv(run_dir / "heldout_replay_trace.csv")
            with self.subTest(run=run_dir.name):
                fig = built[fit_path.name][0]
                for ax, stem in zip(fig.axes, ("yaw_rate_radps", "slip_angle_rad")):
                    np.testing.assert_array_equal(ax.lines[0].get_ydata(), fit_trace[f"measured_{stem}"])
                    np.testing.assert_array_equal(ax.lines[1].get_ydata(), fit_trace[f"predicted_{stem}"])
                fig = built[residual_path.name][0]
                for ax, column in zip(fig.axes, ("yaw_rate_error_radps", "slip_angle_error_rad", "yaw_error_rad")):
                    np.testing.assert_array_equal(ax.lines[0].get_ydata(), validation[column] * 1e9)
                for name, (fig, caption, path) in built.items():
                    self.assert_clean_canvas(fig)
                    self.assert_caption(caption, path, docs)
                    self.assertTrue(caption.startswith(evidence), name)


class Item11SteeringFigureTest(FigureChecks, unittest.TestCase):
    def test_steering(self) -> None:
        built = capture(rf.draw_item11)
        self.addCleanup(close_all, built)
        fig, caption, path = built["steering_command_vs_achieved.png"]
        enriched = pd.read_csv(rf.ITEM11 / "telemetry" / "enriched_bridge.csv")
        np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), enriched["command_steer_rad"])
        np.testing.assert_array_equal(fig.axes[1].lines[0].get_ydata(), enriched["steer_rad"])
        self.assert_clean_canvas(fig)
        self.assert_caption(caption, path, ["evidence/item11/report.md"])


if __name__ == "__main__":
    unittest.main()
