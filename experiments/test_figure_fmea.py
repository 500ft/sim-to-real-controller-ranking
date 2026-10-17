#!/usr/bin/env python3
"""FMEA figures show the committed scores and signals, and their words live in the captions.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_figure_fmea.py
"""
import unittest

import pandas as pd

import report_figures as rf
from figure_checks import FigureChecks, capture, close_all

RESULTS = rf.RUNS / "failure_mode_fmea" / "results.csv"
DOCS = ["reports/failure_mode_fmea.md"]


class FmeaFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.built = capture(rf.draw_fmea)
        cls.results = pd.read_csv(RESULTS)

    @classmethod
    def tearDownClass(cls) -> None:
        close_all(cls.built)

    def test_bars_and_markers_equal_results(self) -> None:
        ax = self.built["fmea_rpn_bar.png"][0].axes[0]
        ordered = self.results.sort_values("rpn")
        self.assertEqual([bar.get_width() for bar in ax.patches], ordered["rpn"].tolist())
        self.assertEqual([bar.get_facecolor()[:3] == (0.0, 0.0, 0.0) for bar in ax.patches], ordered["reproduced"].tolist())
        fig = self.built["fmea_detection_signals.png"][0]
        plotted = {}
        for ax in fig.axes:
            names = [t.get_text() for t in ax.get_yticklabels()]
            points = [line for line in ax.lines if line.get_marker() == "o"]
            for name, line in zip(names, points):
                plotted[name] = (line.get_xdata()[0], line.get_markerfacecolor() == "black")
        expected = {rf.FMEA_NAMES[r.scenario]: (r.detection_metric, bool(r.reproduced)) for r in self.results.itertuples()}
        self.assertEqual(plotted, expected)

    def test_canvas_and_captions(self) -> None:
        for name, (fig, caption, path) in self.built.items():
            with self.subTest(figure=name):
                self.assert_clean_canvas(fig)
                self.assert_caption(caption, path, DOCS)
        self.assertIn("100 ms control latency 200 = 8 × 5 × 5", self.built["fmea_rpn_bar.png"][1])


if __name__ == "__main__":
    unittest.main()
