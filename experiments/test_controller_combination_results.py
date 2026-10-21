"""Independent checks of executed combination telemetry and frozen rankings."""

import hashlib
import itertools
import json
import math
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_combinations"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CombinationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = read(OUT / "protocol.json")
        cls.ranking = read(OUT / "ranking.json")
        cls.cases = [(track, scenario, timing)
                     for track in cls.protocol["tracks"]
                     for timing, scenarios in cls.protocol["timing_modes"].items()
                     for scenario in scenarios]

    def test_sources_freeze_and_complete_coverage(self):
        self.assertEqual(self.ranking["protocol_sha256"], sha(OUT / "protocol.json"))
        frozen = read(OUT / "frozen_blend.json")
        self.assertEqual(frozen["protocol_sha256"], sha(OUT / "protocol.json"))
        self.assertEqual(self.ranking["run_count"], len(self.cases) * len(self.protocol["architecture_order"]))
        for track, spec in self.protocol["tracks"].items():
            self.assertEqual(sha(ROOT / spec["line"]), spec["line_sha256"])
            for timing, scenarios in self.protocol["timing_modes"].items():
                for scenario in scenarios:
                    cohort = [read(OUT / f"{track}_{scenario}_{timing}_{name}.json")
                              for name in self.protocol["architecture_order"]]
                    self.assertEqual(len({r["line_sha256"] for r in cohort}), 1)
                    self.assertEqual(len({r["seed"] for r in cohort}), 1)
                    self.assertEqual(len({r["start_offset_m"] for r in cohort}), 1)
                    self.assertEqual(len({json.dumps(r["model_parameters"], sort_keys=True) for r in cohort}), 1)
                    for result in cohort:
                        self.assertEqual(result["protocol_sha256"], sha(OUT / "protocol.json"))
                        trace = ROOT / result["telemetry"]
                        self.assertEqual(sha(trace), result["telemetry_sha256"])
                        frame = pd.read_csv(trace)
                        self.assertEqual(len(frame), result["telemetry_rows"])
                        self.assertEqual(int(frame["step"].iloc[-1]), result["n_steps"])
                        self.assertEqual(str(frame["termination_reason"].iloc[-1]), result["termination_reason"])
                        self.assertTrue((frame["command_generated_at_s"].dropna() <=
                                         frame["command_applied_at_s"].dropna() + 1e-9).all())
                        self.assertTrue((frame["command_applied_at_s"].dropna() <=
                                         frame["time_s"].loc[frame["command_applied_at_s"].notna()] + 1e-9).all())

    def test_applied_commands_obey_shared_finite_bounds(self):
        limits = self.protocol["shared_limits"]
        for track, scenario, timing in self.cases:
            for name in self.protocol["architecture_order"]:
                frame = pd.read_csv(OUT / f"{track}_{scenario}_{timing}_{name}_control.csv.gz")
                steer = frame["command_steer_rad"].to_numpy(float)
                speed = frame["command_speed_mps"].to_numpy(float)
                self.assertTrue(np.isfinite(steer).all() and np.isfinite(speed).all())
                self.assertLessEqual(float(np.max(np.abs(steer))), limits["command_steer_abs_rad"] + 1e-8)
                self.assertGreaterEqual(float(np.min(speed)), limits["command_speed_min_mps"] - 1e-8)
                self.assertLessEqual(float(np.max(speed)), limits["command_speed_max_mps"] + 1e-8)
                self.assertLessEqual(float(np.max(np.abs(np.diff(np.r_[0.0, steer])))),
                                     limits["command_steer_rate_abs_radps"] / self.protocol["simulation"]["control_rate_hz"] + 1e-8)
                self.assertLessEqual(float(np.max(np.abs(np.diff(np.r_[0.0, speed])))),
                                     limits["command_speed_rate_abs_mps2"] / self.protocol["simulation"]["control_rate_hz"] + 1e-8)

    def test_ideal_shadows_do_not_change_active_plant_trace(self):
        for track in self.protocol["tracks"]:
            for active, shadow in (("pp_lqr", "lqr_active_mpc_shadow"),
                                   ("pp_mpc", "mpc_active_lqr_shadow")):
                left = pd.read_csv(OUT / f"{track}_nominal_ideal_{active}_control.csv.gz")
                right = pd.read_csv(OUT / f"{track}_nominal_ideal_{shadow}_control.csv.gz")
                self.assertEqual(len(left), len(right))
                for field in ("time_s", "x_m", "y_m", "theta_rad", "speed_mps",
                              "command_steer_rad", "command_speed_mps"):
                    np.testing.assert_array_equal(left[field], right[field])

    def test_ranking_uses_all_logged_runs(self):
        by_name = {row["architecture"]: row for row in self.ranking["ranking"]}
        for name in self.protocol["architecture_order"]:
            records = [read(OUT / f"{track}_{scenario}_{timing}_{name}.json")
                       for track, scenario, timing in self.cases]
            completed = [r for r in records if r["completed_lap"] and not r["collision"]]
            row = by_name[name]
            self.assertEqual(row["attempted"], len(records))
            self.assertEqual(row["completed"], len(completed))
            self.assertEqual(row["motion_failed_runs"], sum(not r["motion_constraint_pass"] for r in records))
            self.assertEqual(row["deadline_aware_misses"], sum(r["whole_compute_deadline_misses"] for r in records if r["timing_mode"] == "deadline_aware"))
            if completed:
                self.assertTrue(math.isclose(row["mean_completed_gym_finish_s"],
                                             math.fsum(r["lap_time_s"] for r in completed) / len(completed), abs_tol=1e-10))
        first = self.ranking["overall_order"][0]
        self.assertEqual(first, self.ranking["ranking"][0]["architecture"])


if __name__ == "__main__":
    unittest.main()
