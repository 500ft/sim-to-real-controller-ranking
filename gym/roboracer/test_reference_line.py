"""Behavior checks for line geometry, map coordinates and telemetry accounting."""

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from roboracer.reference_line import map_clearance, qualify_line, resample_closed_line, speed_profile


class ReferenceLineTests(unittest.TestCase):
    def test_example_geometry_does_not_certify_legacy_speed(self):
        root = Path(__file__).resolve().parents[2]
        waypoints = np.loadtxt(root / "examples/example_waypoints.csv", delimiter=";", skiprows=3)
        import json
        rules = json.loads((root / "runs/controller_pipeline/protocol.json").read_text())["line_validation"]
        result = qualify_line(waypoints, root / "examples/example_map.yaml", rules)
        self.assertTrue(result["geometry_eligible"])
        self.assertFalse(result["source_speed_profile_eligible"])
        self.assertFalse(result["eligible"])

    def test_closed_ordered_line_and_speed_bounds(self):
        theta = np.linspace(0, 2 * math.pi, 121)
        xy = np.column_stack([3 * np.cos(theta), 3 * np.sin(theta)])
        xy[-1] = xy[0]
        points, heading, curvature = resample_closed_line(xy, 0.1)
        self.assertLess(np.linalg.norm(points[0] - points[-1]), 0.15)
        self.assertGreater(np.mean(curvature), 0.2)
        speed = speed_profile(curvature, 0.1, 4.0, 2.0, 4.0, 8.0)
        self.assertTrue(np.all(speed ** 2 * np.abs(curvature) <= 4.0 + 1e-8))
        self.assertTrue(np.all(np.roll(speed, -1) ** 2 - speed ** 2 <= 0.4 + 1e-8))
        self.assertTrue(np.all(speed ** 2 - np.roll(speed, -1) ** 2 <= 0.8 + 1e-8))
        with self.assertRaises(ValueError):
            resample_closed_line(xy[:-1], 0.1)

    def test_rotated_map_and_expanded_vehicle_clearance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = np.full((100, 100), 255, dtype=np.uint8)
            image[49, 50] = 0  # becomes row 50 after the simulator's vertical flip
            Image.fromarray(image).save(root / "map.png")
            (root / "map.yaml").write_text("image: map.png\nresolution: 0.1\norigin: [5, 5, 1.5707963267948966]\n")
            # Pixel (50,50) center maps to (-0.05,10.05) after rotation.
            clear = map_clearance(np.array([[-0.05, 10.05]]), np.array([0.0]), root / "map.yaml",
                                  0.58, 0.31, 0.05)
            self.assertEqual(clear, 0.0)
            far = map_clearance(np.array([[3.0, 8.0]]), np.array([0.0]), root / "map.yaml",
                                0.58, 0.31, 0.05)
            self.assertGreater(far, 0.0)


class TelemetryTests(unittest.TestCase):
    def test_independent_metrics_and_deadline(self):
        from experiments.controller_pipeline import independent_metrics
        frame = pd.DataFrame({"x_m": [-3.0, -0.5, 0.1, 0.5], "y_m": [0.0] * 4,
                              "reference_x_m": [-3.0, -0.5, 0.1, 0.5], "reference_y_m": [0.0] * 4,
                              "time_s": [0.1, 0.2, 0.3, 0.4], "progress_m": [0, 5, 8, 9],
                              "lap_time_s": [0.1, 0.2, 0.3, 0.4],
                              "collision": [0, 0, 0, 0], "completed_lap": [0, 0, 0, 1],
                              "control_compute_s": [0.002, float("nan"), 0.012, float("nan")]})
        waypoints = np.array([[0, 0, 0], [10, 1, 0]], dtype=float)
        result = independent_metrics(frame, waypoints, {"control_rate_hz": 100})
        self.assertAlmostEqual(result["independent_start_crossing_s"], 0.2833333333)
        self.assertEqual(result["control_deadline_misses"], 1)
        self.assertEqual(result["per_step_finish_count"], 1)
        self.assertEqual(result["rms_reference_distance_m"], 0)


if __name__ == "__main__":
    unittest.main()
