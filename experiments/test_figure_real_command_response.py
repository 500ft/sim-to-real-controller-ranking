#!/usr/bin/env python3
"""The live command-response figure shows the committed derivatives; its words live in the caption.

The rendering first published under runs/real_command_response/ is frozen and is not redrawn.

Run: MPLBACKEND=Agg python experiments/test_figure_real_command_response.py
"""
import json
import unittest

import numpy as np

import figure_style as fs
import plot_real_command_response as crr
from figure_checks import REPO_ROOT, FigureChecks

RUN = REPO_ROOT / "runs" / "real_command_response"
DOCS = ["reports/real_command_response.md"]


class CommandResponseFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.samples = np.genfromtxt(RUN / "comparison.csv", delimiter=",", names=True)
        cls.result = json.loads((RUN / "result.json").read_text())
        cls.profile = json.loads((RUN / "delay_profile.json").read_text())
        fs.apply()
        cls.fig = crr.render_figure(cls.samples, cls.profile, cls.result)

    @classmethod
    def tearDownClass(cls) -> None:
        fs.plt.close(cls.fig)

    def test_traces_equal_committed_derivatives(self) -> None:
        motion, command, profile = self.fig.axes
        drawn = lambda line: line.get_ydata()[~np.isnan(line.get_ydata())]
        np.testing.assert_array_equal(drawn(motion.lines[0]), self.samples["tracking_forward_m_s"])
        np.testing.assert_array_equal(drawn(motion.lines[1]), self.samples["delay_affine_m_s"])
        np.testing.assert_array_equal(drawn(command.lines[0]), self.samples["command_forward_m_s"])
        np.testing.assert_array_equal(profile.lines[0].get_ydata(), [p["rmse_m_s"] for p in self.profile])
        selected = [line for line in profile.lines if line.get_marker() == "o"][0]
        self.assertEqual(selected.get_xdata()[0], self.result["delay_affine"]["lag_s"])

    def test_canvas_and_caption(self) -> None:
        self.assert_clean_canvas(self.fig)
        text = crr.caption(self.profile, self.result)
        self.assert_caption(text, crr.OUTPUT, DOCS)
        self.assertIn("0.386 m/s RMSE", text)
        self.assertIn("0.22 s apparent delay", text)


if __name__ == "__main__":
    unittest.main()
