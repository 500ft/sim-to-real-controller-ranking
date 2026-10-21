#!/usr/bin/env python
"""Render only committed controller-development results."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import figure_style as style

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/controller_pipeline"
BERLIN = BASE / "mapzoo_berlin"
FIG = ROOT / "reports/figures"
NAMES = ("pure_pursuit", "lqr", "mpc")


def read(path):
    return json.loads(path.read_text())


def offline_progress():
    selected = read(BERLIN / "offline_frozen_choice.json")
    chosen = selected["chosen_weight"]
    weights = tuple(int(key) for key in selected["candidates"])
    means = [selected["candidates"][str(weight)]["mean_tuning_gym_finish_s"] for weight in weights]
    deltas = [read(BERLIN / f"offline_w{chosen}_evaluation_{name}.json")["lap_time_s"] -
              read(BERLIN / f"evaluation_{name}.json")["lap_time_s"] for name in NAMES]
    style.apply("controller-offline-progress")
    fig, axes = style.subplots(1, 2, height_in=3.0, width_in=7.3)
    ax = axes[0]
    ax.plot(range(len(weights)), means, color="black", marker="o", mfc="white", lw=1)
    ax.set_xticks(range(len(weights)), [str(i) for i in range(len(weights))])
    ax.set_xlabel("Offline candidate order")
    ax.set_ylabel("Mean tuning Gym finish [s]")
    style.letter(ax, 0)
    ax = axes[1]
    style.zero_line(ax)
    ax.plot(range(3), deltas, color="black", marker="s", mfc="white", lw=1)
    ax.set_xticks(range(3), ["PP", "LQR", "MPC"])
    ax.set_xlabel("Controller")
    ax.set_ylabel("Final minus source line [s]")
    style.letter(ax, 1)
    caption = ("MapZoo Berlin simulation development. Panel (a): mean Gym finish of the three "
               "independently selected controllers on each registered line candidate, in candidate order "
               f"({', '.join(str(w) for w in weights)} smoothing weights). Panel (b): one frozen zero-offset "
               "evaluation per controller on the chosen line minus its earlier frozen source-line evaluation. "
               "Negative values are faster; all three final runs exceed the registered 4 m/s² target "
               "in the speed-times-yaw-rate proxy, so speed improvement is not qualified. Source: "
               "runs/controller_pipeline/mapzoo_berlin/offline_frozen_choice.json and the linked evaluation JSONs.")
    style.save(fig, FIG / "controller_offline_progress.png", caption, formats=("png", "svg"))


def offline_overlay():
    selected = read(BERLIN / "offline_frozen_choice.json")
    chosen = selected["chosen_weight"]
    reference = np.loadtxt(BERLIN / "reference_constrained.csv", delimiter=";", skiprows=3)
    final_line = np.loadtxt(BERLIN / f"offline_line_weight_{chosen}.csv", delimiter=";", skiprows=3)
    distances, _ = cKDTree(final_line[:, 1:3]).query(reference[:, 1:3])
    center = reference[int(np.argmax(distances)), 1:3]
    style.apply("controller-offline-overlay")
    fig, axes = style.subplots(1, 3, height_in=2.65, width_in=7.5, sharex=True, sharey=True)
    def zoomed(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        inside = (np.abs(x - center[0]) < 1.7) & (np.abs(y - center[1]) < 1.7)
        return np.where(inside, x, np.nan), np.where(inside, y, np.nan)

    for index, (ax, name) in enumerate(zip(axes, NAMES)):
        before = pd.read_csv(BERLIN / f"evaluation_{name}.csv.gz")
        after = pd.read_csv(BERLIN / f"offline_w{chosen}_evaluation_{name}.csv.gz")
        ax.plot(*zoomed(reference[:, 1], reference[:, 2]), color="0.6", ls=":", lw=1.0)
        ax.plot(*zoomed(final_line[:, 1], final_line[:, 2]), color="0.4", ls="-.", lw=1.0)
        ax.plot(*zoomed(before["x_m"][::25], before["y_m"][::25]), color="black", ls="--", lw=0.9)
        ax.plot(*zoomed(after["x_m"][::25], after["y_m"][::25]), color="black", ls="-", lw=1.0)
        ax.set_xlim(float(center[0] - 2), float(center[0] + 2))
        ax.set_ylim(float(center[1] - 2), float(center[1] + 2))
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x [m]")
        if index == 0:
            ax.set_ylabel("y [m]")
        style.letter(ax, index)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color="0.6", ls=":", lw=1.0, label="source line"),
               Line2D([], [], color="0.4", ls="-.", lw=1.0, label="selected line"),
               Line2D([], [], color="black", ls="--", lw=0.8, label="source-line replay"),
               Line2D([], [], color="black", ls="-", lw=1.0, label="selected-line replay")]
    style.legend(fig, handles, ncol=2)
    caption = ("MapZoo Berlin simulated x-y positions sampled from the retained 2 ms telemetry without "
               "invented interpolation. Panels (a), (b), (c) are PP, LQR and MPC, zoomed to the "
               "largest nearest-point line displacement. Dotted and dash-dot are the source and selected "
               "lines; dashed and solid are the earlier frozen source-line evaluation and selected-line "
               "evaluation on the same world start. The selected line passed footprint "
               "clearance and target speed-profile checks, but the speed-times-yaw-rate proxy in every "
               "selected-line run exceeded the registered target. Source: per-run compressed telemetry "
               "under runs/controller_pipeline/mapzoo_berlin/.")
    style.save(fig, FIG / "controller_offline_overlay.png", caption, formats=("png", "svg"))


def model_dispersion():
    summary = read(BASE / "model_sensitivity/summary.json")
    protocol = read(BASE / "model_sensitivity_protocol.json")
    models = tuple(protocol["models"])
    pairs = ("pure_pursuit|lqr", "pure_pursuit|mpc", "lqr|mpc")
    style.apply("controller-model-dispersion")
    fig, axes = style.subplots(1, 3, height_in=3.1, width_in=7.5, sharey=True)
    for index, (ax, pair) in enumerate(zip(axes, pairs)):
        ax.axhspan(-protocol["near_tie_s"], protocol["near_tie_s"], color="0.88", zorder=0)
        style.zero_line(ax)
        for track, linestyle, marker in (("example", "-", "o"), ("mapzoo_berlin", "--", "s")):
            rows = [next(item for item in summary["comparisons"] if item["track"] == track and
                         item["model"] == model and item["pair"] == pair) for model in models]
            y = [row["delta_lap_s"] for row in rows]
            ax.plot(range(len(models)), y, color="black", ls=linestyle, marker=marker,
                    mfc="white", ms=3.5, lw=0.9)
        ax.set_xticks(range(len(models)), ["N", "NL", "QL", "QM"])
        ax.set_xlabel("Model variant")
        if index == 0:
            ax.set_ylabel("Paired Gym finish difference [s]")
        style.letter(ax, index)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Line2D([], [], color="black", ls="-", marker="o", mfc="white", label="example"),
               Line2D([], [], color="black", ls="--", marker="s", mfc="white", label="MapZoo Berlin"),
               Patch(facecolor="0.88", edgecolor="none", label="near tie")]
    style.legend(fig, handles, ncol=3)
    caption = ("Development simulation only. Panels (a), (b), (c) show PP minus LQR, PP minus MPC "
               "and LQR minus MPC Gym finish time. N, NL, QL, QM are nominal, noise-low, "
               "quantization-low and quantization-medium paired stiffness fits from prior synthetic "
               "identification. They are deterministic sensitivity assumptions, not physical uncertainty "
               "draws. The grey ±0.1 s band is the registered near-tie region, not a confidence interval. "
               "Source: runs/controller_pipeline/model_sensitivity/summary.json.")
    style.save(fig, FIG / "controller_model_dispersion.png", caption, formats=("png", "svg"))


if __name__ == "__main__":
    offline_progress()
    offline_overlay()
    model_dispersion()
