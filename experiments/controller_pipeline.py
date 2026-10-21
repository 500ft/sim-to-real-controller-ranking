#!/usr/bin/env python
"""Frozen, simulation-only controller replay and line qualification."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.closed_loop import run_closed_loop
from roboracer.controllers import LQRController, LinearPathModel, MPCController, PurePursuitController
from roboracer.reference_line import qualify_line, resample_closed_line, speed_profile

OUT = ROOT / "runs" / "controller_pipeline"
PROTOCOL = OUT / "protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(line_kind: str = "legacy"):
    protocol = json.loads(PROTOCOL.read_text())
    for item in protocol["maps"].values():
        for key in ("map_yaml", "image", "line"):
            path = item.get(key)
            if path and item.get(key + "_sha256") and sha256(ROOT / path) != item[key + "_sha256"]:
                raise ValueError(f"Source changed: {path}")
    for path, digest in protocol["source"]["vendored_source_sha256"].items():
        # The runner and projection instrumentation are intentionally newer.
        if path == "gym/roboracer/closed_loop.py":
            continue
        if sha256(ROOT / path) != digest:
            raise ValueError(f"Source changed: {path}")
    with (ROOT / "examples/config_example_map.yaml").open() as stream:
        config = yaml.safe_load(stream)
    from argparse import Namespace
    config["map_path"] = str(ROOT / "examples/example_map")
    config["wpt_path"] = str(ROOT / ("examples/example_waypoints.csv" if line_kind == "legacy"
                                     else "runs/controller_pipeline/reference_constrained.csv"))
    if line_kind == "constrained":
        qualification = json.loads((OUT / "line_qualification.json").read_text())
        if sha256(Path(config["wpt_path"])) != qualification["constrained_line_sha256"]:
            raise ValueError("Constrained line changed after qualification")
    conf = Namespace(**config)
    waypoints = np.loadtxt(conf.wpt_path, delimiter=conf.wpt_delim, skiprows=conf.wpt_rowskip)
    return protocol, conf, waypoints


def controller_for(name: str, conf, params: dict | None = None):
    p, _, _ = setup()
    baseline = p["baseline"]
    pp = dict(baseline["pp"])
    if Path(conf.wpt_path).name == "reference_constrained.csv":
        pp["vgain"] = 1.0
    if name == "pure_pursuit":
        pp.update(params or {})
        return PurePursuitController(conf, **pp, name=name)
    model_data = json.loads((ROOT / "runs/lqr_controller/linear_model.json").read_text())
    model = LinearPathModel(1 / baseline["control_rate_hz"], model_data["operating_speed_mps"],
                            model_data["operating_curvature_1pm"],
                            np.asarray(baseline["lqr"]["q_diag"]), np.asarray(baseline["lqr"]["r_diag"]))
    feedforward = PurePursuitController(conf, **pp, name=f"{name}_feedforward_pp")
    if name == "lqr":
        controls = dict(baseline["lqr"])
        controls.update(params or {})
        return LQRController(model, target_speed_mps=model.v0_mps,
                             feedforward_controller=feedforward,
                             max_steer_correction_rad=controls["max_steer_correction_rad"], name=name)
    if name == "mpc":
        controls = dict(baseline["mpc"])
        controls.update(params or {})
        return MPCController(model, target_speed_mps=model.v0_mps, horizon=controls["horizon"],
                             feedforward_controller=feedforward,
                             max_steer_correction_rad=controls["max_steer_correction_rad"], name=name)
    raise ValueError(name)


def independent_metrics(frame: pd.DataFrame, waypoints: np.ndarray, rules: dict) -> dict:
    """Compute metrics from positions and reference points, separate from runner summary."""
    xy = frame[["x_m", "y_m"]].to_numpy(float)
    ref = frame[["reference_x_m", "reference_y_m"]].to_numpy(float)
    error = np.linalg.norm(xy - ref, axis=1)
    times = frame["time_s"].to_numpy(float)
    tangent = waypoints[1, 1:3] - waypoints[0, 1:3]
    tangent /= np.linalg.norm(tangent)
    start = waypoints[0, 1:3]
    signed = (xy - start) @ tangent
    progress = frame["progress_m"].to_numpy(float)
    crossing = None
    for i in range(1, len(times)):
        if (max(progress[:i + 1]) > 0.5 * waypoints[-1, 0]
                and np.max(np.linalg.norm(xy[:i + 1] - start, axis=1)) > 2.0
                and signed[i - 1] < 0 <= signed[i]
                and np.linalg.norm(xy[i] - start) < 2.0):
            fraction = -signed[i - 1] / (signed[i] - signed[i - 1])
            crossing = float(times[i - 1] + fraction * (times[i] - times[i - 1]))
            break
    calls = frame["control_compute_s"].dropna().to_numpy(float)
    out = {"rms_reference_distance_m": float(np.sqrt(np.mean(error ** 2))),
           "max_reference_distance_m": float(np.max(error)),
           "independent_start_crossing_s": crossing,
           "gym_finish_s": float(frame["lap_time_s"].iloc[-1]),
           "per_step_collision_count": int(frame["collision"].sum()),
           "per_step_finish_count": int(frame["completed_lap"].sum()),
           "control_call_count": int(len(calls)),
           "control_compute_p95_s": float(np.percentile(calls, 95)),
           "control_compute_max_s": float(np.max(calls)),
           "control_deadline_misses": int(np.sum(calls > 1 / rules["control_rate_hz"]))}
    return out


def qualify():
    protocol, _, waypoints = setup()
    result = qualify_line(waypoints, ROOT / "examples/example_map.yaml", protocol["line_validation"])
    result["map"] = "example"
    result["line_sha256"] = protocol["maps"]["example"]["line_sha256"]
    result["source"] = "qualified checked-in example line; no generated trajectory substituted"
    if result["geometry_eligible"]:
        rules = protocol["line_validation"]
        xy = waypoints[:, 1:3]
        points, heading, curvature = resample_closed_line(xy, rules["resample_spacing_m"])
        spacing = result["length_m"] / len(points)
        speed = speed_profile(curvature, spacing, rules["lateral_accel_limit_mps2"],
                              rules["longitudinal_accel_limit_mps2"], rules["brake_limit_mps2"],
                              rules["speed_cap_mps"])
        acceleration = (np.roll(speed, -1) ** 2 - speed ** 2) / (2 * spacing)
        target = np.arange(len(points) + 1) * spacing
        derived = np.column_stack([target, np.vstack([points, points[0]]),
                                   np.r_[heading, heading[0]], np.r_[curvature, curvature[0]],
                                   np.r_[speed, speed[0]], np.r_[acceleration, acceleration[0]]])
        destination = OUT / "reference_constrained.csv"
        with destination.open("w") as stream:
            stream.write("# Derived from examples/example_waypoints.csv under protocol.json\n")
            stream.write("# Closed, arc-length resampled, deterministic bounded speed profile\n")
            stream.write("# s_m; x_m; y_m; psi_rad; kappa_1pm; vx_mps; ax_mps2\n")
            np.savetxt(stream, derived, fmt="%.9f", delimiter="; ")
        result["constrained_line_sha256"] = sha256(destination)
        result["constrained_profile_max_lateral_accel_mps2"] = float(np.max(speed ** 2 * np.abs(curvature)))
        result["constrained_profile_max_forward_accel_mps2"] = float(np.max(acceleration))
        result["constrained_profile_max_braking_mps2"] = float(-np.min(acceleration))
    (OUT / "line_qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result["geometry_eligible"]


def run(name: str, scenario: str = "nominal", params: dict | None = None,
        offset_m: float = 0.0, prefix: str = "baseline", line_kind: str = "legacy") -> dict:
    protocol, conf, waypoints = setup(line_kind)
    if not json.loads((OUT / "line_qualification.json").read_text())["geometry_eligible"]:
        raise RuntimeError("Line geometry did not qualify")
    base = protocol["baseline"]
    delay = {"nominal": 0, "control_delay_20ms": 2, "control_delay_50ms": 5}[scenario]
    controller = controller_for(name, conf, params)
    run_id = f"{prefix}_{scenario}_{name}"
    frame, summary = run_closed_loop(controller, conf, waypoints,
                                     integration_dt=base["integration_dt_s"],
                                     control_rate_hz=base["control_rate_hz"],
                                     max_sim_time_s=base["max_sim_time_s"],
                                     init_lateral_offset_m=offset_m,
                                     control_delay_steps=delay,
                                     seed=base["environment_seed"],
                                     run_id=run_id)
    path = OUT / f"{run_id}.csv.gz"
    with gzip.open(path, "wt", compresslevel=6, newline="") as stream:
        frame.to_csv(stream, index=False)
    summary.update(independent_metrics(frame, waypoints, base))
    if name == "mpc":
        summary.update(controller.runtime_summary())
    summary.update({"scenario": scenario, "parameters": params or {},
                    "initial_offset_m": offset_m, "telemetry": str(path.relative_to(ROOT)),
                    "telemetry_sha256": sha256(path), "n_steps": len(frame),
                    "line_kind": line_kind, "line_sha256": sha256(Path(conf.wpt_path)),
                    "effective_seed": base["environment_seed"]})
    (OUT / f"{run_id}.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(f"{run_id}: {summary['termination_reason']} at {summary['final_time_s']:.3f} s, "
          f"RMS {summary['rms_cte_m']:.4f} m")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["qualify", "baseline", "constrained_baseline", "sensitivity", "tune", "freeze", "evaluate"])
    args = parser.parse_args()
    if args.phase == "qualify":
        if not qualify():
            raise SystemExit(1)
    elif args.phase == "baseline":
        for name in ("pure_pursuit", "lqr", "mpc"):
            run(name)
    elif args.phase == "constrained_baseline":
        for name in ("pure_pursuit", "lqr", "mpc"):
            run(name, params={"vgain": 1.0} if name == "pure_pursuit" else None,
                prefix="constrained", line_kind="constrained")
    elif args.phase == "sensitivity":
        for scenario in ("control_delay_20ms", "control_delay_50ms"):
            for name in ("pure_pursuit", "lqr", "mpc"):
                run(name, scenario)
    elif args.phase == "tune":
        protocol, _, _ = setup()
        for name, values in protocol["tuning"]["candidate_ranges"].items():
            for index in range(protocol["tuning"]["budget_per_controller_candidates"]):
                params = {key: value[index] if len(value) > 1 else value[0]
                          for key, value in values.items()}
                run(name, params=params, offset_m=protocol["tuning"]["tuning_start_offset_m"],
                    prefix=f"tune{index}")
    elif args.phase == "freeze":
        protocol, _, _ = setup()
        selections = {}
        for name in protocol["tuning"]["candidate_ranges"]:
            candidates = []
            for index in range(protocol["tuning"]["budget_per_controller_candidates"]):
                path = OUT / f"tune{index}_nominal_{name}.json"
                if not path.exists():
                    raise FileNotFoundError(path)
                data = json.loads(path.read_text())
                candidates.append(data)
            eligible = [item for item in candidates if item["completed_lap"] and not item["collision"]]
            if not eligible:
                selections[name] = {"status": "no completing candidate", "candidates": [c["run_id"] for c in candidates]}
            else:
                chosen = min(eligible, key=lambda item: item["rms_reference_distance_m"])
                selections[name] = {"status": "selected", "run_id": chosen["run_id"],
                                    "parameters": chosen["parameters"],
                                    "rms_reference_distance_m": chosen["rms_reference_distance_m"],
                                    "candidates": [c["run_id"] for c in candidates]}
        artifact = {"line_sha256": protocol["maps"]["example"]["line_sha256"],
                    "protocol_sha256": sha256(PROTOCOL), "selections": selections}
        (OUT / "frozen_selection.json").write_text(json.dumps(artifact, indent=2) + "\n")
        print(json.dumps(artifact, indent=2))
    elif args.phase == "evaluate":
        protocol, _, _ = setup()
        frozen = json.loads((OUT / "frozen_selection.json").read_text())
        if frozen["protocol_sha256"] != sha256(PROTOCOL):
            raise ValueError("Protocol changed after freeze")
        for name, chosen in frozen["selections"].items():
            if chosen["status"] == "selected":
                run(name, params=chosen["parameters"],
                    offset_m=protocol["tuning"]["evaluation_start_offset_m"], prefix="evaluation")


if __name__ == "__main__":
    main()
