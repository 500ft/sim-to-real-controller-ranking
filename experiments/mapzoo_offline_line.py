#!/usr/bin/env python
"""Prospective quadratic line smoothing on the qualified MapZoo Berlin corridor."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import diags, eye
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.reference_line import qualify_line, resample_closed_line, speed_profile

OUT = ROOT / "runs/controller_pipeline/mapzoo_berlin"
PROTOCOL = OUT / "offline_line_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smooth_periodic(points: np.ndarray, weight: float) -> np.ndarray:
    """Minimize ||p-p0||² + weight*||periodic second difference(p)||²."""
    if weight < 0:
        raise ValueError("Smoothing weight must be nonnegative")
    n = len(points)
    second = diags([np.ones(n), -2 * np.ones(n), np.ones(n)], [-1, 0, 1], shape=(n, n), format="lil")
    second[0, n - 1] = 1.0
    second[n - 1, 0] = 1.0
    d = second.tocsr()
    system = eye(n, format="csr") + weight * (d.T @ d)
    return np.column_stack([spsolve(system, points[:, axis]) for axis in (0, 1)])


def prepare() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    source = OUT / "reference_constrained.csv"
    if sha(source) != protocol["source_line_sha256"]:
        raise ValueError("Source line changed")
    base = np.loadtxt(source, delimiter=";", skiprows=3)
    points = base[:-1, 1:3]
    rules = json.loads((ROOT / "runs/controller_pipeline/protocol.json").read_text())["line_validation"]
    records = {}
    for weight in protocol["candidate_weights"]:
        name = str(weight)
        target = OUT / f"offline_line_weight_{name}.csv"
        if weight == 0:
            target.write_bytes(source.read_bytes())
            line = base
            shift = np.zeros(len(points))
        else:
            smoothed = smooth_periodic(points, weight)
            shift = np.linalg.norm(smoothed - points, axis=1)
            resampled, heading, curvature = resample_closed_line(
                np.vstack([smoothed, smoothed[0]]), rules["resample_spacing_m"])
            closed = np.vstack([resampled, resampled[0]])
            length = float(np.linalg.norm(np.diff(closed, axis=0), axis=1).sum())
            spacing = length / len(resampled)
            speed = speed_profile(curvature, spacing, rules["lateral_accel_limit_mps2"],
                                  rules["longitudinal_accel_limit_mps2"], rules["brake_limit_mps2"],
                                  rules["speed_cap_mps"])
            accel = (np.roll(speed, -1) ** 2 - speed ** 2) / (2 * spacing)
            line = np.column_stack([np.arange(len(resampled) + 1) * spacing,
                                    closed, np.r_[heading, heading[0]],
                                    np.r_[curvature, curvature[0]],
                                    np.r_[speed, speed[0]], np.r_[accel, accel[0]]])
            with target.open("w") as stream:
                stream.write(f"# Quadratic periodic second-difference smoothing weight {weight}\n")
                stream.write("# Derived from frozen MapZoo Berlin target line; source SHA in offline_line_protocol.json\n")
                stream.write("# s_m; x_m; y_m; psi_rad; kappa_1pm; vx_mps; ax_mps2\n")
                np.savetxt(stream, line, fmt="%.9f", delimiter="; ")
        exported = np.loadtxt(target, delimiter=";", skiprows=3)
        quality = qualify_line(exported, ROOT / "third_party/mapzoo_berlin/berlin.yaml", rules,
                               speed_tolerance=protocol["numeric_speed_tolerance_mps2"])
        records[name] = {"line_sha256": sha(target), "geometry": quality,
                         "max_shift_m": float(np.max(shift)),
                         "rms_shift_m": float(np.sqrt(np.mean(shift ** 2)))}
    result = {"source_line_sha256": protocol["source_line_sha256"],
              "candidate_weights": protocol["candidate_weights"], "candidates": records}
    (OUT / "offline_line_geometry.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
