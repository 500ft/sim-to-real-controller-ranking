#!/usr/bin/env python3
"""RK4 vs Euler figures show the committed first-lap telemetry, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_integrator.py
"""
import unittest

import numpy as np

import figure_style as fs
import plot_integrator_comparison as pic
from figure_checks import FigureChecks

DOC = ["reports/first_run.md"]


class IntegratorFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.telemetry, cls.waypoints, cls.x_col, cls.y_col = pic.load_inputs()
        cls.facts = pic.facts(cls.telemetry)
        fs.apply()

    def build(self, name):
        figures = {
            "combined": lambda: pic.figure_combined(self.waypoints, self.x_col, self.y_col, self.facts),
            "trajectory": lambda: pic.figure_trajectory(self.waypoints, self.x_col, self.y_col, self.facts),
            "tracking": lambda: pic.figure_tracking(self.facts),
            "summary": lambda: pic.figure_summary(self.facts),
        }
        fig = figures[name]()
        self.addCleanup(fs.plt.close, fig)
        return fig

    def run_of(self, key):
        return self.telemetry[self.telemetry["integrator"] == key].sort_values("time_s")

    def test_trajectories_and_errors_equal_telemetry(self) -> None:
        axes = self.build("combined").axes
        for ax_path, ax_cte, (key, _) in zip(axes[:2], axes[2:], pic.INTEGRATORS):
            run = self.run_of(key)
            np.testing.assert_array_equal(ax_path.lines[1].get_xdata(), run["x_m"])
            np.testing.assert_array_equal(ax_path.lines[1].get_ydata(), run["y_m"])
            traces = [line for line in ax_cte.lines if len(line.get_xdata()) > 1]
            np.testing.assert_array_equal(np.concatenate([line.get_ydata() for line in traces]), run["abs_cte_m"])
            collided = bool(run["collision"].max())
            self.assertEqual(ax_path.lines[2].get_markerfacecolor(), fs.FILL[not collided])

    def test_summary_markers_equal_run_summary(self) -> None:
        fig = self.build("summary")
        summary = pic.summarize_run(self.telemetry).set_index("Integrator")
        for ax, (column, _, _) in zip(fig.axes, pic.METRICS):
            for line, (key, name) in zip(ax.lines, pic.INTEGRATORS):
                row = summary.loc[name.upper()]
                self.assertEqual(line.get_ydata()[0], row[column])
                self.assertEqual(line.get_markerfacecolor(), fs.FILL[not row["Collision"]])

    def test_canvas_and_captions(self) -> None:
        captions = {"combined": (pic.caption_combined, pic.COMBINED_PATH),
                    "trajectory": (pic.caption_trajectory, pic.TRAJECTORY_PATH),
                    "tracking": (pic.caption_tracking, pic.TRACKING_ERROR_PATH),
                    "summary": (pic.caption_summary, pic.SUMMARY_METRICS_PATH)}
        for name, (caption, path) in captions.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(self.build(name))
                self.assert_caption(caption(self.facts), path, DOC)
        text = pic.caption_combined(self.facts)
        self.assertIn("Euler collides after 7.14 s, 64.7 m along the path", text)


if __name__ == "__main__":
    unittest.main()
