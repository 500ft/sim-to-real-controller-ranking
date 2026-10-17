#!/usr/bin/env python3
"""The live structural-census figure shows the committed result; its words live in the caption.

The census figure first published under runs/ope_qualification/ is frozen and is not redrawn.

Run: MPLBACKEND=Agg python experiments/test_figure_ope_structure.py
"""
import json
import subprocess
import sys
import unittest

import numpy as np

import figure_style as fs
import plot_ope_structure as ope
from figure_checks import REPO_ROOT, FigureChecks

RESULT = REPO_ROOT / "runs" / "ope_qualification" / "result.json"
DOCS = ["README.md", "reports/ope_qualification.md"]


class OpeStructureFigureTest(FigureChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text())
        fs.apply()
        cls.fig = ope.render_figure(cls.result)

    @classmethod
    def tearDownClass(cls) -> None:
        fs.plt.close(cls.fig)

    def test_counts_equal_result(self) -> None:
        archives = [self.result["archives"][name] for name in ope.ARCHIVES]
        seg_ax, name_ax, flag_ax = self.fig.axes
        np.testing.assert_array_equal(seg_ax.lines[-1].get_xdata(), [a["segments"] for a in archives])
        np.testing.assert_array_equal(name_ax.lines[-1].get_xdata(), [a["policy_names"] for a in archives])
        widths = [bar.get_width() for bar in flag_ax.patches]
        early = [a["flags_before_segment_end"] for a in archives]
        self.assertEqual(widths, [a["done_or_truncated_rows"] - e for a, e in zip(archives, early)] + early)

    def test_canvas_and_caption(self) -> None:
        self.assert_clean_canvas(self.fig)
        self.assert_caption(ope.caption(self.result), ope.OUTPUT, DOCS)
        self.assertIn("Real v1 alone raises flags before a segment ends (10,502 rows)", ope.caption(self.result))

    def test_refuses_to_overwrite_the_frozen_figure(self) -> None:
        run = subprocess.run([sys.executable, str(REPO_ROOT / "experiments" / "plot_ope_structure.py"), "--result",
                              str(RESULT), "--output", str(REPO_ROOT / "runs" / "ope_qualification" / "structure.png")],
                             capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("frozen", run.stderr)


if __name__ == "__main__":
    unittest.main()
