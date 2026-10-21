#!/usr/bin/env python
"""Prospective quadratic line smoothing on the qualified MapZoo Berlin corridor."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import diags, eye
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.reference_line import qualify_line, resample_closed_line, speed_profile
from roboracer.closed_loop import initial_pose, run_closed_loop
from experiments.controller_pipeline import independent_metrics
from experiments.run_mapzoo_berlin import controller_for, setup as track_setup

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


def run_candidate(weight: int, name: str, phase: str, params: dict) -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    geometry = json.loads((OUT / "offline_line_geometry.json").read_text())
    quality = geometry["candidates"][str(weight)]
    if not quality["geometry"]["eligible"]:
        raise ValueError(f"Candidate weight {weight} failed geometry")
    line_path = OUT / f"offline_line_weight_{weight}.csv"
    if sha(line_path) != quality["line_sha256"]:
        raise ValueError("Candidate line changed")
    expansion, conf, base = track_setup()
    frozen_start = (protocol["fixed_world_tuning_pose_xytheta"] if phase.startswith("tune")
                    else protocol["fixed_world_evaluation_pose_xytheta"])
    if phase.startswith("tune"):
        if not np.allclose(initial_pose(conf, base, 0.25), frozen_start, atol=1e-12):
            raise ValueError("Shared tuning pose differs from original registered runs")
    conf.wpt_path = str(line_path)
    conf.sx, conf.sy, conf.stheta = frozen_start
    waypoints = np.loadtxt(line_path, delimiter=";", skiprows=3)
    controller = controller_for(name, conf, expansion, params)
    run_id = f"offline_w{weight}_{phase}_{name}"
    frame, result = run_closed_loop(controller, conf, waypoints,
                                    integration_dt=protocol["integration_dt_s"],
                                    control_rate_hz=protocol["control_rate_hz"],
                                    max_sim_time_s=protocol["max_sim_time_s"],
                                    seed=protocol["seed"], run_id=run_id)
    result.update(independent_metrics(frame, waypoints, protocol))
    if name == "mpc":
        result.update(controller.runtime_summary())
    trace = OUT / f"{run_id}.csv.gz"
    with gzip.open(trace, "wt", compresslevel=6, newline="") as stream:
        frame.to_csv(stream, index=False)
    result.update({"track": "MapZoo Berlin", "line_weight": weight,
                   "line_sha256": sha(line_path), "protocol_sha256": sha(PROTOCOL),
                   "parameters": params, "initial_world_pose_xytheta": frozen_start,
                   "seed": protocol["seed"], "n_steps": len(frame),
                   "telemetry": str(trace.relative_to(ROOT)), "telemetry_sha256": sha(trace)})
    (OUT / f"{run_id}.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"{run_id}: {result['termination_reason']} at {result['final_time_s']:.3f} s")
    return result


def _candidate_results(weight: int, name: str, protocol: dict) -> list[dict]:
    records = []
    for index in range(protocol["controller_settings"]["candidates_per_controller"]):
        filename = (f"tune{index}_{name}.json" if weight == 0
                    else f"offline_w{weight}_tune{index}_{name}.json")
        record = json.loads((OUT / filename).read_text())
        expected_hash = json.loads((OUT / "offline_line_geometry.json").read_text())["candidates"][str(weight)]["line_sha256"]
        if record["line_sha256"] != expected_hash:
            raise ValueError(f"Wrong line in {filename}")
        if weight == 0 and record["seed"] != protocol["seed"]:
            raise ValueError("Baseline tuning seed differs")
        records.append(record)
    return records


def freeze() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    geometry = json.loads((OUT / "offline_line_geometry.json").read_text())
    candidates = {}
    for weight in protocol["candidate_weights"]:
        selected = {}
        for name in ("pure_pursuit", "lqr", "mpc"):
            runs = _candidate_results(weight, name, protocol)
            eligible = [run for run in runs if run["completed_lap"] and not run["collision"]]
            if eligible:
                chosen = min(eligible, key=lambda run: run["rms_reference_distance_m"])
                selected[name] = {"status": "selected", "run_id": chosen["run_id"],
                                  "lap_time_s": chosen["lap_time_s"],
                                  "parameters": chosen["parameters"],
                                  "all_run_ids": [run["run_id"] for run in runs]}
            else:
                selected[name] = {"status": "no completion", "all_run_ids": [run["run_id"] for run in runs]}
        complete = all(item["status"] == "selected" for item in selected.values())
        mean_lap = float(np.mean([item["lap_time_s"] for item in selected.values()])) if complete else None
        candidates[str(weight)] = {"eligible": complete and geometry["candidates"][str(weight)]["geometry"]["eligible"],
                                   "mean_tuning_gym_finish_s": mean_lap,
                                   "line_sha256": geometry["candidates"][str(weight)]["line_sha256"],
                                   "controller_selections": selected}
    eligible = [(int(weight), item) for weight, item in candidates.items() if item["eligible"]]
    choice = min(eligible, key=lambda pair: pair[1]["mean_tuning_gym_finish_s"])[0] if eligible else None
    result = {"protocol_sha256": sha(PROTOCOL), "candidate_geometry_sha256": sha(OUT / "offline_line_geometry.json"),
              "candidates": candidates, "chosen_weight": choice,
              "chosen_line_sha256": candidates[str(choice)]["line_sha256"] if choice is not None else None}
    (OUT / "offline_frozen_choice.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "tune", "freeze", "evaluate"])
    args = parser.parse_args()
    if args.phase == "prepare":
        print(json.dumps(prepare(), indent=2))
    elif args.phase == "tune":
        protocol = json.loads(PROTOCOL.read_text())
        settings = protocol["controller_settings"]
        for weight in protocol["candidate_weights"]:
            if weight == 0:
                continue  # exact previously registered runs are checked at freeze
            for name in ("pure_pursuit", "lqr", "mpc"):
                for index in range(settings["candidates_per_controller"]):
                    params = ({"lookahead_m": settings["pure_pursuit_lookahead_m"][index], "vgain": 1.0}
                              if name == "pure_pursuit" else
                              {"max_steer_correction_rad": settings["lqr_max_steer_correction_rad"][index]}
                              if name == "lqr" else {"horizon": settings["mpc_horizon"][index]})
                    run_id = f"offline_w{weight}_tune{index}_{name}"
                    existing = OUT / f"{run_id}.json"
                    if existing.exists():
                        prior = json.loads(existing.read_text())
                        if prior["protocol_sha256"] != sha(PROTOCOL):
                            raise ValueError(f"Stale checkpoint: {existing}")
                        continue
                    run_candidate(weight, name, f"tune{index}", params)
    elif args.phase == "freeze":
        print(json.dumps(freeze(), indent=2))
    else:
        frozen = json.loads((OUT / "offline_frozen_choice.json").read_text())
        if frozen["protocol_sha256"] != sha(PROTOCOL):
            raise ValueError("Protocol changed after offline freeze")
        weight = frozen["chosen_weight"]
        if weight is None:
            raise RuntimeError("No eligible optimized line")
        for name, selection in frozen["candidates"][str(weight)]["controller_selections"].items():
            run_candidate(weight, name, "evaluation", selection["parameters"])


if __name__ == "__main__":
    main()
