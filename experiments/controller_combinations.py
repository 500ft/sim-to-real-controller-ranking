#!/usr/bin/env python
"""Checkpointed two-track simulation development comparison of controller combinations."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.closed_loop import run_closed_loop
from roboracer.controller_combinations import CombinationController
from experiments import controller_pipeline as example
from experiments import run_mapzoo_berlin as berlin

OUT = ROOT / "runs/controller_combinations"
PROTOCOL = OUT / "protocol.json"
MODEL_PROTOCOL = ROOT / "runs/controller_pipeline/model_sensitivity_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def setup(track: str):
    protocol = read(PROTOCOL)
    spec = protocol["tracks"][track]
    if sha(ROOT / spec["line"]) != spec["line_sha256"]:
        raise ValueError("Line differs from registered source")
    if track == "example":
        _, conf, waypoints = example.setup("constrained")
    else:
        _, conf, waypoints = berlin.setup()
    frozen = read(ROOT / protocol["frozen_selection"][track])
    if frozen["line_sha256"] != spec["line_sha256"]:
        raise ValueError("Frozen selection uses a different line")
    return protocol, spec, conf, waypoints, frozen


def make_controller(track: str, name: str, conf, frozen: dict, protocol: dict,
                    *, weight: float = 0.5, fault: str | None = None):
    def factory(component: str):
        params = frozen["selections"][component]["parameters"]
        if track == "example":
            return example.controller_for(component, conf, params)
        return berlin.controller_for(component, conf, read(berlin.PROTOCOL), params)
    return CombinationController(name, factory, protocol["shared_limits"],
                                 blend_lqr_weight=weight, fault=fault,
                                 control_period_s=1.0 / protocol["simulation"]["control_rate_hz"])


def run(track: str, scenario: str, name: str, timing: str, *, tuning_weight: float | None = None,
        pilot: bool = False) -> dict:
    protocol, spec, conf, waypoints, frozen = setup(track)
    conditions = protocol["scenarios"][scenario]
    model_protocol = read(MODEL_PROTOCOL)
    params = dict(model_protocol["default_vehicle_params"])
    params.update(model_protocol["models"][conditions["model"]])
    if tuning_weight is not None:
        run_id = f"tune_{track}_blend_{tuning_weight:.2f}"
    else:
        run_id = f"{track}_{scenario}_{timing}_{name}" + ("_pilot" if pilot else "")
    result_path = OUT / f"{run_id}.json"
    if result_path.exists():
        old = read(result_path)
        trace = ROOT / old["telemetry"]
        if old["protocol_sha256"] != sha(PROTOCOL) or not trace.exists() or sha(trace) != old["telemetry_sha256"]:
            raise ValueError(f"Invalid checkpoint: {result_path}")
        return old
    weight = 0.5 if tuning_weight is None else tuning_weight
    if tuning_weight is None and name == "pp_blend" and (OUT / "frozen_blend.json").exists():
        choice = read(OUT / "frozen_blend.json")
        if choice["protocol_sha256"] != sha(PROTOCOL):
            raise ValueError("Blend selection predates changed protocol")
        weight = choice["tracks"][track]["weight"]
    controller = make_controller(track, name, conf, frozen, protocol, weight=weight, fault=conditions["fault"])
    source_offset = (0.25 if tuning_weight is not None else conditions["offset_m"])
    sim = protocol["simulation"]
    duration = 2.0 if pilot else spec["max_sim_time_s"]
    frame, result = run_closed_loop(controller, conf, waypoints,
                                    integration_dt=sim["integration_dt_s"],
                                    control_rate_hz=sim["control_rate_hz"], max_sim_time_s=duration,
                                    init_lateral_offset_m=source_offset, seed=spec["seed"],
                                    vehicle_params=params, timing_mode=timing,
                                    command_delay_s=conditions["command_delay_s"], run_id=run_id)
    result.update(example.independent_metrics(frame, waypoints, sim))
    limits = protocol["shared_limits"]
    speed = frame["speed_mps"].to_numpy(float)
    lat = frame["accel_y_mps2"].to_numpy(float)
    longitudinal = frame["accel_x_mps2"].to_numpy(float)
    call_rows = frame.loc[frame["control_compute_s"].notna()]
    times = call_rows["control_compute_s"].to_numpy(float) + call_rows["injected_compute_delay_s"].to_numpy(float)
    result.update({
        "track": track, "scenario": scenario, "architecture": name, "timing_mode": timing,
        "model": conditions["model"], "model_parameters": model_protocol["models"][conditions["model"]],
        "start_offset_m": source_offset, "command_delay_s": conditions["command_delay_s"],
        "fault": conditions["fault"], "blend_lqr_weight": weight if name == "pp_blend" else None,
        "pilot": pilot, "max_sim_time_s": duration, "seed": spec["seed"],
        "line_sha256": spec["line_sha256"], "protocol_sha256": sha(PROTOCOL),
        "frozen_selection_sha256": sha(ROOT / protocol["frozen_selection"][track]),
        "max_abs_lateral_proxy_mps2": float(np.max(np.abs(lat))),
        "max_forward_accel_mps2": float(np.max(longitudinal)),
        "max_brake_abs_mps2": float(max(0.0, -np.min(longitudinal))),
        "motion_constraint_pass": bool(np.max(speed) <= limits["closed_loop_speed_max_mps"] + limits["numeric_tolerance"]
                                       and np.max(np.abs(lat)) <= limits["closed_loop_lateral_proxy_abs_mps2"] + limits["numeric_tolerance"]
                                       and np.max(longitudinal) <= limits["closed_loop_forward_accel_mps2"] + limits["numeric_tolerance"]
                                       and -np.min(longitudinal) <= limits["closed_loop_brake_abs_mps2"] + limits["numeric_tolerance"]),
        "whole_compute_p95_s": float(np.percentile(times, 95)),
        "whole_compute_max_s": float(np.max(times)),
        "whole_compute_deadline_misses": int(np.sum(times > 1.0 / sim["control_rate_hz"])),
        "switch_count": int(np.sum(call_rows["switch_reason"].isin(["mpc_failure_or_deadline", "mpc_recovered"]))),
        "fault_rejections": int(np.sum(call_rows["switch_reason"] == "invalid_mpc_hold")),
        "n_steps": len(frame), "n_control_calls": len(call_rows),
    })
    OUT.mkdir(parents=True, exist_ok=True)
    trace = OUT / f"{run_id}.csv.gz"
    with gzip.open(trace, "wt", compresslevel=6, newline="") as stream:
        frame.to_csv(stream, index=False)
    result.update({"telemetry": str(trace.relative_to(ROOT)), "telemetry_sha256": sha(trace)})
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"{run_id}: {result['termination_reason']} {result['final_time_s']:.3f}s, "
          f"calls={len(call_rows)}, misses={result['whole_compute_deadline_misses']}", flush=True)
    return result


def freeze_blend() -> dict:
    protocol = read(PROTOCOL)
    tracks = {}
    for track in protocol["tracks"]:
        items = [read(OUT / f"tune_{track}_blend_{weight:.2f}.json")
                 for weight in protocol["tuning"]["blend_lqr_weight_candidates"]]
        eligible = [x for x in items if x["completed_lap"] and not x["collision"] and x["motion_constraint_pass"]]
        ordered = eligible if eligible else [x for x in items if x["completed_lap"] and not x["collision"]]
        if not ordered:
            tracks[track] = {"status": "no completing blend", "weight": None}
        else:
            chosen = min(ordered, key=lambda x: x["rms_reference_distance_m"])
            tracks[track] = {"status": "constraint_pass" if eligible else "constraint_failed_selection",
                             "weight": chosen["blend_lqr_weight"], "run_id": chosen["run_id"],
                             "candidates": [x["run_id"] for x in items]}
    artifact = {"protocol_sha256": sha(PROTOCOL), "tracks": tracks}
    (OUT / "frozen_blend.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "tune", "freeze", "evaluate"])
    args = parser.parse_args()
    protocol = read(PROTOCOL)
    if args.phase == "pilot":
        for name in ("pp_lqr", "lqr_active_mpc_shadow"):
            run("example", "nominal", name, "ideal", pilot=True)
    elif args.phase == "tune":
        for track in protocol["tracks"]:
            for weight in protocol["tuning"]["blend_lqr_weight_candidates"]:
                run(track, "nominal", "pp_blend", "ideal", tuning_weight=weight)
    elif args.phase == "freeze":
        print(json.dumps(freeze_blend(), indent=2))
    else:
        choice = read(OUT / "frozen_blend.json")
        if choice["protocol_sha256"] != sha(PROTOCOL):
            raise ValueError("Blend selection changed after tuning")
        for track in protocol["tracks"]:
            for timing, scenarios in protocol["timing_modes"].items():
                for scenario in scenarios:
                    for name in protocol["architecture_order"]:
                        run(track, scenario, name, timing)


if __name__ == "__main__":
    main()
