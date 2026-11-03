#!/usr/bin/env python3
"""Rebuild every report figure from committed run outputs, with captions in a scratch directory.

Checks that each figure builds, that nothing printed touches anything else
(figure_style.save refuses otherwise) and that each figure gets a caption file.
For every figure it also checks the committed MATLAB pair: a PNG at the shared
resolution and a vector PDF beside it, and that the derived tables in
reports/figures/data/ match a fresh export. Committed figures and run files are
not touched. Per-family value and caption checks live in test_figure_*.py.

Run: PYTHONPATH=gym MPLBACKEND=Agg python experiments/test_report_figures.py
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import figure_data
import figure_style as fs
import plot_integrator_comparison
import report_figures as rf


class ReportFigureTest(unittest.TestCase):
    def test_redraw_from_committed_outputs(self) -> None:
        written = []
        original = fs.save

        def recorded(fig, path, caption, formats=("png",), preview_dir=None):
            paths = original(fig, path, caption, formats, preview_dir)
            written.extend(paths)
            return paths

        fs.save = recorded
        saved = {name: getattr(plot_integrator_comparison, name)
                 for name in ("COMBINED_PATH", "TRAJECTORY_PATH", "TRACKING_ERROR_PATH", "SUMMARY_METRICS_PATH")}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                for name, path in saved.items():
                    setattr(plot_integrator_comparison, name, out / path.name)
                plot_integrator_comparison.main()
                rf.draw_integrator_convergence(figure_dir=out)
                rf.draw_dynamic_replay(figure_dir=out)
                rf.draw_kinematic_replay(figure_dir=out)
                rf.draw_sysid_excitation(figure_dir=out)
                rf.draw_parameter_fit(rf.RUNS / "dynamic_parameter_identification",
                                      out / "dynamic_parameter_fit.png", out / "dynamic_parameter_residuals.png")
                rf.draw_pure_pursuit(figure_dir=out)
                rf.draw_ekf(figure_dir=out)
                rf.draw_fmea(figure_dir=out)
                rf.draw_parameter_id_robustness(figure_dir=out)
                rf.draw_item11(figure_dir=out / "item11")
                committed = {p.name for p in rf.FIGURES.glob("*.png")} | {
                    p.name for p in (rf.ITEM11 / "figures").glob("*.png")}
                names = {p.name for p in written}
                self.assertEqual(len(written), 29)
                self.assertLessEqual(names, committed, "redraw wrote a figure name that is not committed")
                for path in written:
                    self.assertTrue(fs.caption_path(path).exists(), path.name)
                    image = (rf.ITEM11 / "figures" if path.parent.name == "item11" else rf.FIGURES) / path.name
                    dpi = Image.open(image).info.get("dpi", (0, 0))[0]
                    self.assertAlmostEqual(dpi, fs.DPI, delta=0.5, msg=image.name)
                    self.assertTrue(image.with_suffix(".pdf").exists(), image.name)
        finally:
            fs.save = original
            for name, path in saved.items():
                setattr(plot_integrator_comparison, name, path)

    def test_matlab_pairs_for_the_other_generators(self) -> None:
        for name in ("ope_structure", "real_command_response"):
            image = rf.FIGURES / f"{name}.png"
            self.assertAlmostEqual(Image.open(image).info.get("dpi", (0, 0))[0], fs.DPI, delta=0.5, msg=name)
            self.assertTrue(image.with_suffix(".pdf").exists(), name)

    def test_derived_tables_match_a_fresh_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for path in figure_data.write_all(Path(tmp)):
                committed = figure_data.DATA / path.name
                self.assertEqual(path.read_bytes(), committed.read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
