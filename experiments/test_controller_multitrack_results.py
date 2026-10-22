"""Check executed multi-track traces, frozen selections and paired differences."""

import csv
import hashlib
import itertools
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from roboracer.reference_line import qualify_line

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/controller_pipeline"
BERLIN = BASE / "mapzoo_berlin"
NAMES = ("pure_pursuit", "lqr", "mpc")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MultiTrackResultTests(unittest.TestCase):
    def test_source_line_and_track_coverage(self):
        protocol = read(BERLIN / "expansion_protocol.json")
        source = ROOT / "third_party/mapzoo_berlin"
        for filename, digest in protocol["source_file_sha256"].items():
            self.assertEqual(sha(source / filename), digest)
        qualification = read(BERLIN / "qualification.json")
        self.assertTrue(qualification["derived_line"]["eligible"])
        self.assertFalse(qualification["source_line"]["eligible"])
        frozen = read(BERLIN / "frozen_selection.json")
        self.assertEqual(frozen["line_sha256"], sha(BERLIN / "reference_constrained.csv"))
        for name in NAMES:
            result = read(BERLIN / f"evaluation_{name}.json")
            self.assertTrue(result["completed_lap"])
            self.assertFalse(result["collision"])
            self.assertEqual(result["parameters"], frozen["selections"][name]["parameters"])
            self.assertEqual(result["line_sha256"], frozen["line_sha256"])
            trace = ROOT / result["telemetry"]
            self.assertEqual(sha(trace), result["telemetry_sha256"])
            frame = pd.read_csv(trace)
            self.assertEqual(len(frame), result["n_steps"])
            distance = np.hypot(frame["x_m"] - frame["reference_x_m"],
                                frame["y_m"] - frame["reference_y_m"])
            self.assertAlmostEqual(float(np.sqrt(np.mean(distance ** 2))),
                                   result["rms_reference_distance_m"], places=6)

    def test_offline_line_freeze_and_evaluation(self):
        protocol = read(BERLIN / "offline_line_protocol.json")
        geometry = read(BERLIN / "offline_line_geometry.json")
        frozen = read(BERLIN / "offline_frozen_choice.json")
        self.assertEqual(frozen["protocol_sha256"], sha(BERLIN / "offline_line_protocol.json"))
        self.assertEqual(sha(BERLIN / "offline_line_weight_0.csv"), protocol["source_line_sha256"])
        eligible = []
        for weight in protocol["candidate_weights"]:
            item = frozen["candidates"][str(weight)]
            line_path = BERLIN / f"offline_line_weight_{weight}.csv"
            self.assertEqual(item["line_sha256"], sha(line_path))
            self.assertTrue(geometry["candidates"][str(weight)]["geometry"]["eligible"])
            checked = qualify_line(np.loadtxt(line_path, delimiter=";", skiprows=3),
                                   ROOT / "third_party/mapzoo_berlin/berlin.yaml",
                                   read(BASE / "protocol.json")["line_validation"],
                                   speed_tolerance=protocol["numeric_speed_tolerance_mps2"])
            self.assertTrue(checked["eligible"])
            self.assertAlmostEqual(checked["min_expanded_footprint_clearance_m"],
                                   geometry["candidates"][str(weight)]["geometry"]["min_expanded_footprint_clearance_m"])
            for name in NAMES:
                candidates = [read(BERLIN / (f"tune{i}_{name}.json" if weight == 0 else
                                             f"offline_w{weight}_tune{i}_{name}.json"))
                              for i in range(protocol["controller_settings"]["candidates_per_controller"])]
                qualified = [x for x in candidates if x["completed_lap"] and not x["collision"]]
                selected = item["controller_selections"][name]
                self.assertEqual(selected["run_id"],
                                 min(qualified, key=lambda x: x["rms_reference_distance_m"])["run_id"])
            if item["eligible"]:
                eligible.append((weight, item["mean_tuning_gym_finish_s"]))
        self.assertEqual(frozen["chosen_weight"], min(eligible, key=lambda x: x[1])[0])
        chosen = frozen["chosen_weight"]
        for name in NAMES:
            result = read(BERLIN / f"offline_w{chosen}_evaluation_{name}.json")
            self.assertEqual(result["line_sha256"], frozen["chosen_line_sha256"])
            self.assertEqual(result["parameters"], frozen["candidates"][str(chosen)]["controller_selections"][name]["parameters"])
            self.assertEqual(result["initial_world_pose_xytheta"], protocol["fixed_world_evaluation_pose_xytheta"])

    def test_paired_model_sensitivity(self):
        protocol = read(BASE / "model_sensitivity_protocol.json")
        summary = read(BASE / "model_sensitivity/summary.json")
        self.assertEqual(summary["protocol_sha256"], sha(BASE / "model_sensitivity_protocol.json"))
        for source, expected in (("source_results", "source_results_sha256"),
                                 ("source_metadata", "source_metadata_sha256"),
                                 ("simulator_source", "simulator_source_sha256")):
            self.assertEqual(sha(ROOT / protocol[source]), protocol[expected])
        with (ROOT / protocol["source_results"]).open() as stream:
            fitted = {row["scenario"]: row for row in csv.DictReader(stream)}
        for model in ("noise_low", "quantization_low", "quantization_medium"):
            self.assertEqual(fitted[model]["acceptance_passed"], "True")
            for key in ("C_Sf", "C_Sr"):
                self.assertAlmostEqual(protocol["models"][model][key],
                                       float(fitted[model][f"fitted_{key}"]), places=12)
        for key in ("C_Sf", "C_Sr"):
            self.assertEqual(protocol["models"]["nominal"][key], protocol["default_vehicle_params"][key])
        expected_comparisons = len(protocol["tracks"]) * len(protocol["models"]) * 3
        self.assertEqual(len(summary["comparisons"]), expected_comparisons)
        for track, model in itertools.product(protocol["tracks"], protocol["models"]):
            runs = {name: read(BASE / "model_sensitivity" / f"{track}_{model}_{name}.json") for name in NAMES}
            for run in runs.values():
                self.assertEqual(run["seed"], protocol["tracks"][track]["seed"])
                self.assertEqual(run["line_sha256"], sha(ROOT / protocol["tracks"][track]["line"]))
                self.assertEqual(run["model_parameters"], protocol["models"][model])
                self.assertEqual(sha(ROOT / run["telemetry"]), run["telemetry_sha256"])
            for pair in itertools.combinations(NAMES, 2):
                item = next(x for x in summary["comparisons"] if x["track"] == track and
                            x["model"] == model and x["pair"] == "|".join(pair))
                a, b = (runs[name] for name in pair)
                if a["completed_lap"] and b["completed_lap"] and not (a["collision"] or b["collision"]):
                    self.assertAlmostEqual(item["delta_lap_s"], a["lap_time_s"] - b["lap_time_s"])
                else:
                    self.assertIsNone(item["delta_lap_s"])


if __name__ == "__main__":
    unittest.main()
