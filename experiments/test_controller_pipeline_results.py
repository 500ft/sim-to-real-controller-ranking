"""Independent checks of committed controller traces and frozen selections."""

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_pipeline"


def read(path):
    return json.loads(path.read_text())


class ControllerPipelineResultTests(unittest.TestCase):
    def test_legacy_comparison_reproduced(self):
        old = pd.read_csv(ROOT / "runs/controller_comparison/results.csv")
        for name in ("pure_pursuit", "lqr", "mpc"):
            source = old.loc[old["controller"] == name].iloc[0]
            replay = read(OUT / f"baseline_nominal_{name}.json")
            self.assertAlmostEqual(replay["lap_time_s"], source["lap_time_s"], places=3)
            self.assertAlmostEqual(replay["rms_cte_m"], source["rms_cte_m"], places=6)

    def test_trace_metrics_and_terminal_flags(self):
        runs = [read(path) for path in OUT.glob("*.json")]
        runs = [run for run in runs if "telemetry" in run]
        self.assertGreaterEqual(len(runs), 20)
        for result in runs:
            path = ROOT / result["telemetry"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result["telemetry_sha256"])
            frame = pd.read_csv(path)
            self.assertEqual(len(frame), result["n_steps"])
            self.assertTrue(np.all(np.diff(frame["time_s"].to_numpy(float)) > 0))
            distance = np.hypot(frame["x_m"] - frame["reference_x_m"],
                                frame["y_m"] - frame["reference_y_m"])
            self.assertAlmostEqual(float(np.sqrt(np.mean(distance ** 2))),
                                   result["rms_reference_distance_m"], places=6)
            calls = frame["control_compute_s"].dropna().to_numpy(float)
            self.assertEqual(int(np.sum(calls > 0.01)), result["control_deadline_misses"])
            self.assertLessEqual(int(frame["collision"].sum()), 1)
            self.assertLessEqual(int(frame["completed_lap"].sum()), 1)
            self.assertEqual(bool(frame["completed_lap"].iloc[-1]), bool(result["completed_lap"]))
            self.assertEqual(bool(frame["collision"].iloc[-1]), bool(result["collision"]))

    def test_frozen_selection_is_minimum_eligible_error(self):
        settings = read(OUT / "tuning_constrained_protocol.json")
        frozen = read(OUT / "frozen_constrained_selection.json")
        self.assertEqual(frozen["protocol_sha256"],
                         hashlib.sha256((OUT / "tuning_constrained_protocol.json").read_bytes()).hexdigest())
        self.assertEqual(frozen["line_sha256"],
                         hashlib.sha256((OUT / "reference_constrained.csv").read_bytes()).hexdigest())
        for name, selected in frozen["selections"].items():
            candidates = [read(OUT / f"ctune{i}_nominal_{name}.json")
                          for i in range(settings["budget_per_controller_candidates"])]
            eligible = [run for run in candidates if run["completed_lap"] and not run["collision"]]
            self.assertEqual(selected["run_id"],
                             min(eligible, key=lambda run: run["rms_reference_distance_m"])["run_id"])
            evaluated = read(OUT / f"ceval_nominal_{name}.json")
            self.assertEqual(evaluated["parameters"], selected["parameters"])
            self.assertEqual(evaluated["line_sha256"], frozen["line_sha256"])
            self.assertEqual(evaluated["initial_offset_m"], settings["evaluation_start_offset_m"])

    def test_registered_pair_differences(self):
        sensitivity = read(OUT / "delay_sensitivity.json")
        for item in sensitivity["comparisons"]:
            a, b = item["pair"].split("|")
            left = read(OUT / f"baseline_{item['scenario']}_{a}.json")
            right = read(OUT / f"baseline_{item['scenario']}_{b}.json")
            self.assertEqual(left["initial_offset_m"], right["initial_offset_m"])
            self.assertEqual(left["scenario"], right["scenario"])
            self.assertAlmostEqual(item["delta_lap_s"], left["lap_time_s"] - right["lap_time_s"])
            self.assertEqual(item["near_tie"], abs(item["delta_lap_s"]) <= sensitivity["near_tie_s"])


if __name__ == "__main__":
    unittest.main()
