#!/usr/bin/env python
"""Registered second-track controller runs using pinned public MapZoo geometry."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.closed_loop import run_closed_loop
from roboracer.controllers import LQRController, LinearPathModel, MPCController, PurePursuitController
from experiments.controller_pipeline import independent_metrics

OUT = ROOT / "runs/controller_pipeline/mapzoo_berlin"
SOURCE = ROOT / "third_party/mapzoo_berlin"
PROTOCOL = OUT / "expansion_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup():
    protocol = json.loads(PROTOCOL.read_text())
    qualification = OUT / "qualification.json"
    if sha(qualification) != protocol["qualification_sha256"]:
        raise ValueError("Pinned line qualification changed")
    if sha(OUT / "reference_constrained.csv") != protocol["derived_line_sha256"]:
        raise ValueError("Pinned constrained line changed")
    for name, digest in protocol["source_file_sha256"].items():
        if sha(SOURCE / name) != digest:
            raise ValueError(f"Pinned source changed: {name}")
    x, y, theta = protocol["start_pose_xytheta"]
    conf = Namespace(map_path=str(SOURCE / "berlin"), map_ext=".png",
                     wpt_path=str(OUT / "reference_constrained.csv"),
                     wpt_delim=";", wpt_rowskip=3, wpt_xind=1, wpt_yind=2,
                     wpt_thind=3, wpt_vind=5, sx=x, sy=y, stheta=theta)
    waypoints = np.loadtxt(conf.wpt_path, delimiter=conf.wpt_delim, skiprows=conf.wpt_rowskip)
    return protocol, conf, waypoints


def controller_for(name: str, conf: Namespace, protocol: dict, params: dict):
    baseline = protocol["baseline"]
    pp_params = baseline["pure_pursuit"]
    if name == "pure_pursuit":
        return PurePursuitController(conf, lookahead_m=params.get("lookahead_m", pp_params["lookahead_m"]),
                                     vgain=params.get("vgain", pp_params["vgain"]), name=name)
    model_params = protocol["controller_model"]
    model = LinearPathModel(model_params["control_dt_s"], model_params["v0_mps"],
                            model_params["kappa0_1pm"], np.asarray(model_params["q_diag"]),
                            np.asarray(model_params["r_diag"]))
    feedforward = PurePursuitController(conf, lookahead_m=pp_params["lookahead_m"],
                                        vgain=pp_params["vgain"], name=f"{name}_feedforward_pp")
    if name == "lqr":
        return LQRController(model, target_speed_mps=model_params["v0_mps"],
                             feedforward_controller=feedforward,
                             max_steer_correction_rad=params.get("max_steer_correction_rad", baseline[name]["max_steer_correction_rad"]),
                             name=name)
    if name == "mpc":
        return MPCController(model, target_speed_mps=model_params["v0_mps"],
                             feedforward_controller=feedforward,
                             horizon=params.get("horizon", baseline[name]["horizon"]),
                             max_steer_correction_rad=baseline[name]["max_steer_correction_rad"],
                             name=name)
    raise ValueError(name)


def run(name: str, phase: str, params: dict | None = None, offset_m: float = 0.0) -> dict:
    protocol, conf, waypoints = setup()
    params = params or {}
    controller = controller_for(name, conf, protocol, params)
    run_id = f"{phase}_{name}"
    frame, result = run_closed_loop(controller, conf, waypoints,
                                    integration_dt=protocol["integration_dt_s"],
                                    control_rate_hz=protocol["control_rate_hz"],
                                    max_sim_time_s=protocol["max_sim_time_s"],
                                    init_lateral_offset_m=offset_m,
                                    seed=protocol["seed"], run_id=run_id)
    path = OUT / f"{run_id}.csv.gz"
    with gzip.open(path, "wt", compresslevel=6, newline="") as stream:
        frame.to_csv(stream, index=False)
    result.update(independent_metrics(frame, waypoints, protocol))
    if name == "mpc":
        result.update(controller.runtime_summary())
    result.update({"track": "MapZoo Berlin", "source_commit": protocol["source_commit"],
                   "line_sha256": protocol["derived_line_sha256"],
                   "protocol_sha256": sha(PROTOCOL), "seed": protocol["seed"],
                   "parameters": params, "initial_offset_m": offset_m,
                   "n_steps": len(frame), "telemetry": str(path.relative_to(ROOT)),
                   "telemetry_sha256": sha(path)})
    (OUT / f"{run_id}.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"{run_id}: {result['termination_reason']} at {result['final_time_s']:.3f} s")
    return result


def freeze() -> dict:
    protocol, _, _ = setup()
    selections = {}
    for name in ("pure_pursuit", "lqr", "mpc"):
        candidates = [json.loads((OUT / f"tune{i}_{name}.json").read_text())
                      for i in range(protocol["tuning"]["candidates_per_controller"])]
        completed = [r for r in candidates if r["completed_lap"] and not r["collision"]]
        if not completed:
            selections[name] = {"status": "no completing candidate", "candidates": [r["run_id"] for r in candidates]}
        else:
            chosen = min(completed, key=lambda r: r["rms_reference_distance_m"])
            selections[name] = {"status": "selected", "run_id": chosen["run_id"],
                                "parameters": chosen["parameters"],
                                "candidates": [r["run_id"] for r in candidates]}
    artifact = {"protocol_sha256": sha(PROTOCOL), "line_sha256": protocol["derived_line_sha256"],
                "selections": selections}
    (OUT / "frozen_selection.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["baseline", "tune", "freeze", "evaluate"])
    args = parser.parse_args()
    protocol, _, _ = setup()
    if args.phase == "baseline":
        for name in ("pure_pursuit", "lqr", "mpc"):
            run(name, "baseline")
    elif args.phase == "tune":
        spec = protocol["tuning"]
        for name in ("pure_pursuit", "lqr", "mpc"):
            for index in range(spec["candidates_per_controller"]):
                params = ({"lookahead_m": spec["pure_pursuit_lookahead_m"][index], "vgain": 1.0}
                          if name == "pure_pursuit" else
                          {"max_steer_correction_rad": spec["lqr_max_steer_correction_rad"][index]}
                          if name == "lqr" else {"horizon": spec["mpc_horizon"][index]})
                run(name, f"tune{index}", params, spec["tuning_lateral_offset_m"])
    elif args.phase == "freeze":
        print(json.dumps(freeze(), indent=2))
    else:
        frozen = json.loads((OUT / "frozen_selection.json").read_text())
        if frozen["protocol_sha256"] != sha(PROTOCOL):
            raise ValueError("Protocol changed after selection freeze")
        for name, selection in frozen["selections"].items():
            if selection["status"] == "selected":
                run(name, "evaluation", selection["parameters"], protocol["tuning"]["evaluation_lateral_offset_m"])


if __name__ == "__main__":
    main()
