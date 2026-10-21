#!/usr/bin/env python
"""Execute frozen paired simulator-parameter sensitivity on two qualified tracks."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gym"))
from roboracer.closed_loop import run_closed_loop
from experiments import controller_pipeline as example
from experiments import run_mapzoo_berlin as berlin

OUT = ROOT / "runs/controller_pipeline/model_sensitivity"
PROTOCOL = ROOT / "runs/controller_pipeline/model_sensitivity_protocol.json"
NAMES = ("pure_pursuit", "lqr", "mpc")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(track: str):
    protocol = json.loads(PROTOCOL.read_text())
    spec = protocol["tracks"][track]
    line = ROOT / spec["line"]
    frozen = ROOT / spec["frozen"]
    if track == "example":
        _, conf, waypoints = example.setup("constrained")
    else:
        _, conf, waypoints = berlin.setup()
    selection = json.loads(frozen.read_text())
    if sha(line) != selection["line_sha256"]:
        raise ValueError(f"Frozen line changed: {track}")
    return protocol, spec, conf, waypoints, selection


def run(track: str, model: str, name: str, *, pilot: bool = False) -> dict:
    protocol, spec, conf, waypoints, selection = setup(track)
    for source_key, hash_key in (("source_results", "source_results_sha256"),
                                 ("source_metadata", "source_metadata_sha256"),
                                 ("simulator_source", "simulator_source_sha256")):
        if sha(ROOT / protocol[source_key]) != protocol[hash_key]:
            raise ValueError(f"Changed input: {protocol[source_key]}")
    params = dict(protocol["default_vehicle_params"])
    params.update(protocol["models"][model])
    chosen = selection["selections"][name]
    if chosen["status"] != "selected":
        raise ValueError(f"No frozen configuration for {track}/{name}")
    controller = (example.controller_for(name, conf, chosen["parameters"])
                  if track == "example" else
                  berlin.controller_for(name, conf, json.loads(berlin.PROTOCOL.read_text()), chosen["parameters"]))
    run_id = f"{track}_{model}_{name}" + ("_pilot" if pilot else "")
    duration = 2.0 if pilot else spec["max_sim_time_s"]
    frame, result = run_closed_loop(controller, conf, waypoints,
                                    integration_dt=protocol["integration_dt_s"],
                                    control_rate_hz=protocol["control_rate_hz"],
                                    max_sim_time_s=duration,
                                    init_lateral_offset_m=spec["start_offset_m"],
                                    seed=spec["seed"], vehicle_params=params, run_id=run_id)
    result.update(example.independent_metrics(frame, waypoints, protocol))
    if name == "mpc":
        result.update(controller.runtime_summary())
    OUT.mkdir(parents=True, exist_ok=True)
    trace = OUT / f"{run_id}.csv.gz"
    with gzip.open(trace, "wt", compresslevel=6, newline="") as stream:
        frame.to_csv(stream, index=False)
    result.update({"track": track, "model": model, "pilot": pilot,
                   "model_parameters": protocol["models"][model],
                   "default_vehicle_params_sha256": hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest(),
                   "protocol_sha256": sha(PROTOCOL), "line_sha256": sha(ROOT / spec["line"]),
                   "frozen_selection_sha256": sha(ROOT / spec["frozen"]),
                   "controller_parameters": chosen["parameters"], "seed": spec["seed"],
                   "n_steps": len(frame), "telemetry": str(trace.relative_to(ROOT)),
                   "telemetry_sha256": sha(trace)})
    (OUT / f"{run_id}.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"{run_id}: {result['termination_reason']} at {result['final_time_s']:.3f} s", flush=True)
    return result


def verify_nominal() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    for track in protocol["tracks"]:
        for name in NAMES:
            new = json.loads((OUT / f"{track}_nominal_{name}.json").read_text())
            old_path = (ROOT / f"runs/controller_pipeline/ceval_nominal_{name}.json"
                        if track == "example" else
                        ROOT / f"runs/controller_pipeline/mapzoo_berlin/evaluation_{name}.json")
            old = json.loads(old_path.read_text())
            if not (new["completed_lap"] and old["completed_lap"] and
                    abs(new["lap_time_s"] - old["lap_time_s"]) <= 0.002 and
                    abs(new["rms_reference_distance_m"] - old["rms_reference_distance_m"]) <= 1e-5):
                raise ValueError(f"Explicit-params nominal does not reproduce frozen {track}/{name}")


def analyze() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    near = protocol["near_tie_s"]
    rows = []
    for track in protocol["tracks"]:
        for a, b in itertools.combinations(NAMES, 2):
            nominal = [json.loads((OUT / f"{track}_nominal_{name}.json").read_text()) for name in (a, b)]
            nominal_delta = nominal[0]["lap_time_s"] - nominal[1]["lap_time_s"]
            for model in protocol["models"]:
                left, right = [json.loads((OUT / f"{track}_{model}_{name}.json").read_text()) for name in (a, b)]
                complete = all(r["completed_lap"] and not r["collision"] for r in (left, right))
                delta = left["lap_time_s"] - right["lap_time_s"] if complete else None
                rows.append({"track": track, "model": model, "pair": f"{a}|{b}",
                             "a_status": left["termination_reason"], "b_status": right["termination_reason"],
                             "delta_lap_s": delta,
                             "near_tie": abs(delta) <= near if complete else None,
                             "sign_reversal_outside_tie": bool(abs(nominal_delta) > near and abs(delta) > near and
                                                              np.sign(nominal_delta) != np.sign(delta)) if complete else None})
    result = {"protocol_sha256": sha(PROTOCOL), "near_tie_s": near,
              "scope": protocol["scope"], "comparisons": rows}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "nominal", "variants", "analyze"])
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    if args.phase == "pilot":
        result = run("example", "nominal", "pure_pursuit", pilot=True)
        if result["collision"] or result["n_steps"] < 900 or not np.isfinite(result["rms_reference_distance_m"]):
            raise RuntimeError("Pilot did not qualify")
    elif args.phase in ("nominal", "variants"):
        models = ("nominal",) if args.phase == "nominal" else tuple(protocol["models"])[1:]
        if args.phase == "variants":
            verify_nominal()
        for model in models:
            for track in protocol["tracks"]:
                for name in NAMES:
                    path = OUT / f"{track}_{model}_{name}.json"
                    if path.exists():
                        previous = json.loads(path.read_text())
                        if previous["protocol_sha256"] != sha(PROTOCOL):
                            raise ValueError(f"Stale checkpoint: {path}")
                        continue
                    run(track, model, name)
        if args.phase == "nominal":
            verify_nominal()
    else:
        print(json.dumps(analyze(), indent=2))


if __name__ == "__main__":
    main()
