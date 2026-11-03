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


def write_all(out: Path = DATA) -> list[Path]:
    return [p for step in (integrator, convergence, ekf, fmea, parameter_id) for p in step(out)]


if __name__ == "__main__":
    for written in write_all():
        print(f"Wrote {written.relative_to(rf.REPO_ROOT)}")
