#!/usr/bin/env python
"""Convert the pinned MapZoo Berlin line to a checked F1TENTH target line."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.reference_line import qualify_line, resample_closed_line, speed_profile

SOURCE = ROOT / "third_party/mapzoo_berlin"
OUT = ROOT / "runs/controller_pipeline/mapzoo_berlin"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_native(path: Path, rows: np.ndarray, description: str) -> None:
    with path.open("w") as stream:
        stream.write(f"# {description}\n")
        stream.write("# Coordinates and heading in the pinned map frame\n")
        stream.write("# s_m; x_m; y_m; psi_rad; kappa_1pm; vx_mps; ax_mps2\n")
        np.savetxt(stream, rows, fmt="%.9f", delimiter="; ")


def prepare() -> dict:
    register = json.loads((SOURCE / "SOURCE.json").read_text())
    for name, digest in register["files_sha256"].items():
        if sha(SOURCE / name) != digest:
            raise ValueError(f"Pinned MapZoo source changed: {name}")
    original = pd.read_csv(SOURCE / "berlin_racing_line.csv", sep=";")
    columns = [" s_m", " x_m", " y_m", " psi_rad", " kappa_radpm", " vx_mps", " ax_mps2"]
    native = original[columns].to_numpy(float)
    if not np.all(np.isfinite(native)):
        raise ValueError("Nonfinite source line")
    rules = json.loads((ROOT / "runs/controller_pipeline/protocol.json").read_text())["line_validation"]
    source_result = qualify_line(native, SOURCE / "berlin.yaml", rules)
    if not source_result["geometry_eligible"]:
        raise ValueError(f"Source geometry failed: {source_result}")
    OUT.mkdir(parents=True, exist_ok=True)
    source_native = OUT / "native_source.csv"
    write_native(source_native, native, "MapZoo Berlin 11-column source converted by explicit column names")

    points, heading, curvature = resample_closed_line(native[:, 1:3], rules["resample_spacing_m"])
    ds = source_result["length_m"] / len(points)
    speeds = speed_profile(curvature, ds, rules["lateral_accel_limit_mps2"],
                           rules["longitudinal_accel_limit_mps2"], rules["brake_limit_mps2"],
                           rules["speed_cap_mps"])
    accel = (np.roll(speeds, -1) ** 2 - speeds ** 2) / (2 * ds)
    rows = np.column_stack([np.arange(len(points) + 1) * ds,
                            np.vstack([points, points[0]]), np.r_[heading, heading[0]],
                            np.r_[curvature, curvature[0]], np.r_[speeds, speeds[0]],
                            np.r_[accel, accel[0]]])
    constrained = OUT / "reference_constrained.csv"
    write_native(constrained, rows, "Deterministic arc-length line from the pinned MapZoo Berlin geometry")
    qualified = qualify_line(rows, SOURCE / "berlin.yaml", rules)
    if not qualified["eligible"]:
        raise ValueError(f"Derived target line failed: {qualified}")
    result = {"source": register, "source_line": source_result, "derived_line": qualified,
              "native_source_sha256": sha(source_native),
              "derived_line_sha256": sha(constrained),
              "model_operating_speed_mps": float(np.median(speeds)),
              "model_operating_curvature_1pm": float(np.median(curvature)),
              "start_pose_xytheta": [float(points[0, 0]), float(points[0, 1]),
                                     float(heading[0])],
              "source_rows": len(native), "derived_rows": len(rows)}
    (OUT / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
