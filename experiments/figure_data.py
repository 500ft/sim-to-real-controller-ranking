#!/usr/bin/env python
"""Write the small derived tables that the MATLAB figure scripts read.

The MATLAB scripts in experiments/matlab/ draw the report figures. They read the
committed run files directly. This module writes only the few plotted values
that need Python logic first: the reference path parsed from the waypoint file,
per-run summaries, display labels and tolerances kept as module constants.

    PYTHONPATH=gym python experiments/figure_data.py

Output goes to reports/figures/data/. Nothing under runs/ or evidence/*/metrics changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import plot_integrator_comparison as pic
import report_figures as rf

DATA = rf.FIGURES / "data"


def _csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")
    return path


def integrator(out: Path) -> list[Path]:
    """Reference path and per-integrator summary for the RK4 vs Euler figures."""
    telemetry, waypoints, x_col, y_col = pic.load_inputs()
    f = pic.facts(telemetry)
    path = pd.DataFrame({"x_m": waypoints[x_col].astype(float), "y_m": waypoints[y_col].astype(float)})
    summary = f["summary"].reset_index()
    summary = pd.DataFrame({
        "integrator": summary["Integrator"].str.lower(),
        "label": summary["Integrator"].map({"RK4": "RK4", "EULER": "Euler"}),
        "collision": summary["Collision"].astype(int),
        "final_time_s": summary["Final time [s]"],
        "rms_cte_m": summary["RMS CTE [m]"],
        "max_cte_m": summary["Max CTE [m]"],
        "mean_speed_mps": summary["Mean speed [m/s]"],
    })
    return [_csv(path, out / "integrator_reference_path.csv"), _csv(summary, out / "integrator_summary.csv")]


def convergence(out: Path) -> list[Path]:
    source = rf.REPO_ROOT / "experiments" / "integrator_convergence.py"
    values = {"rms_refinement_tol_m": rf.module_constant(source, "RMS_REFINEMENT_TOL_M"),
              "max_refinement_tol_m": rf.module_constant(source, "MAX_REFINEMENT_TOL_M")}
    path = out / "integrator_convergence_tolerances.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    return [path]


def ekf(out: Path) -> list[Path]:
    summary = pd.read_csv(rf.RUNS / "ekf_study" / "summary.csv")
    order = [s for s in rf.SCENARIO_NAMES if s in set(summary["scenario"])]
    pivot = summary.pivot(index="scenario", columns="estimator", values="position_rmse_m").loc[order]
    frame = pd.DataFrame({"scenario": order, "label": [rf.SCENARIO_NAMES[s] for s in order],
                          "ekf_position_rmse_m": pivot["ekf"].to_numpy(),
                          "dead_reckoning_position_rmse_m": pivot["dead_reckoning"].to_numpy()})
    return [_csv(frame, out / "ekf_rmse_summary.csv")]


def fmea(out: Path) -> list[Path]:
    results = pd.read_csv(rf.RUNS / "failure_mode_fmea" / "results.csv")
    frame = pd.DataFrame({"scenario": results["scenario"],
                          "label": [rf.FMEA_NAMES.get(s, s) for s in results["scenario"]],
                          "reproduced": results["reproduced"].astype(bool).astype(int),
                          "rpn": results["rpn"],
                          "signal_group": results["detection_signal"].map(rf._signal_group),
                          "detection_metric": results["detection_metric"]})
    return [_csv(frame, out / "fmea.csv")]


def parameter_id(out: Path) -> list[Path]:
    results = pd.read_csv(rf.RUNS / "parameter_id_robustness" / "results.csv")
    frame = pd.DataFrame({"scenario": results["scenario"], "label": results["scenario"].map(rf._scenario_label),
                          "kind": results["kind"],
                          "C_Sf_oracle_relative_error": results["C_Sf_oracle_relative_error"],
                          "C_Sr_oracle_relative_error": results["C_Sr_oracle_relative_error"],
                          "acceptance_passed": results["acceptance_passed"].astype(bool).astype(int),
                          "jacobian_condition_number": results["jacobian_condition_number"]})
    return [_csv(frame, out / "parameter_id_robustness.csv")]


CONTROLLERS = {"pure_pursuit": "PP", "lqr": "LQR", "mpc": "MPC"}
PAIRS = ("pure_pursuit|lqr", "pure_pursuit|mpc", "lqr|mpc")


def _pair_label(pair: str) -> str:
    a, b = pair.split("|")
    return f"{CONTROLLERS[a]} - {CONTROLLERS[b]}"


def controller_pipeline(out: Path) -> list[Path]:
    """Plotted values of the four controller-pipeline figures, read from committed run JSON and telemetry."""
    import numpy as np

    base = rf.RUNS / "controller_pipeline"
    berlin = base / "mapzoo_berlin"
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    written = []

    delay = read(base / "delay_sensitivity.json")
    labels = {"nominal": "Nominal", "control_delay_20ms": "20 ms", "control_delay_50ms": "50 ms"}
    rows = [{"pair": c["pair"], "pair_label": _pair_label(c["pair"]), "scenario": c["scenario"],
             "delay_label": labels[c["scenario"]], "delta_lap_s": c["delta_lap_s"]} for c in delay["comparisons"]]
    written.append(_csv(pd.DataFrame(rows), out / "controller_delay_sensitivity.csv"))

    protocol = read(base / "model_sensitivity_protocol.json")
    summary = read(base / "model_sensitivity" / "summary.json")
    short = dict(zip(protocol["models"], ("N", "NL", "QL", "QM")))
    rows = []
    for pair in PAIRS:
        for track in ("example", "mapzoo_berlin"):
            for model in protocol["models"]:
                item = next(c for c in summary["comparisons"]
                            if c["track"] == track and c["model"] == model and c["pair"] == pair)
                rows.append({"pair": pair, "pair_label": _pair_label(pair), "track": track, "model": model,
                             "model_label": short[model], "delta_lap_s": item["delta_lap_s"]})
    written.append(_csv(pd.DataFrame(rows), out / "controller_model_dispersion.csv"))

    choice = read(berlin / "offline_frozen_choice.json")
    chosen = choice["chosen_weight"]
    weights = [int(key) for key in choice["candidates"]]
    rows = [{"order": i, "smoothing_weight": w,
             "mean_tuning_gym_finish_s": choice["candidates"][str(w)]["mean_tuning_gym_finish_s"]}
            for i, w in enumerate(weights)]
    written.append(_csv(pd.DataFrame(rows), out / "controller_offline_candidates.csv"))
    rows = []
    for name, label in CONTROLLERS.items():
        final = read(berlin / f"offline_w{chosen}_evaluation_{name}.json")
        source = read(berlin / f"evaluation_{name}.json")
        rows.append({"controller": name, "label": label,
                     "final_minus_source_s": final["lap_time_s"] - source["lap_time_s"]})
    written.append(_csv(pd.DataFrame(rows), out / "controller_offline_deltas.csv"))

    # Zoom window of controller_multitrack_figures.offline_overlay: +-1.7 m around the
    # reference point farthest from the selected line; telemetry every 25th 2 ms sample.
    reference = np.loadtxt(berlin / "reference_constrained.csv", delimiter=";", skiprows=3)
    final_line = np.loadtxt(berlin / f"offline_line_weight_{chosen}.csv", delimiter=";", skiprows=3)
    gaps = np.sqrt(((reference[:, None, 1:3] - final_line[None, :, 1:3]) ** 2).sum(axis=2)).min(axis=1)
    center = reference[int(np.argmax(gaps)), 1:3]
    rows = []

    def keep(controller, series, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        inside = (np.abs(x - center[0]) < 1.7) & (np.abs(y - center[1]) < 1.7)
        segment = np.cumsum(np.r_[True, inside[1:] & ~inside[:-1]]) if len(inside) else inside
        for xi, yi, si in zip(x[inside], y[inside], segment[inside]):
            rows.append({"controller": controller, "series": series, "segment": int(si), "x_m": xi, "y_m": yi})

    keep("all", "source_line", reference[:, 1], reference[:, 2])
    keep("all", "selected_line", final_line[:, 1], final_line[:, 2])
    for name in CONTROLLERS:
        before = pd.read_csv(berlin / f"evaluation_{name}.csv.gz", usecols=["x_m", "y_m"])
        after = pd.read_csv(berlin / f"offline_w{chosen}_evaluation_{name}.csv.gz", usecols=["x_m", "y_m"])
        keep(name, "source_replay", before["x_m"][::25], before["y_m"][::25])
        keep(name, "selected_replay", after["x_m"][::25], after["y_m"][::25])
    written.append(_csv(pd.DataFrame(rows), out / "controller_offline_overlay.csv"))
    bands = {"delay_near_tie_s": delay["near_tie_s"], "model_near_tie_s": protocol["near_tie_s"],
             "overlay_center_x_m": float(center[0]), "overlay_center_y_m": float(center[1]),
             "overlay_half_width_m": 2.0, "chosen_weight": chosen}
    path = out / "controller_pipeline_bands.json"
    path.write_text(json.dumps(bands, indent=2) + "\n", encoding="utf-8")
    written.append(path)
    return written


def write_all(out: Path = DATA) -> list[Path]:
    return [p for step in (integrator, convergence, ekf, fmea, parameter_id,
                                     controller_pipeline) for p in step(out)]


if __name__ == "__main__":
    for written in write_all():
        print(f"Wrote {written.relative_to(rf.REPO_ROOT)}")
