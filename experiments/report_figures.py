#!/usr/bin/env python
"""Draw the simulator and ROS-capture report figures and their captions from committed run outputs.

The experiment scripts call the draw_* functions after they write their run
files, so a full rerun and this redraw use the same plotting code. Run this file
alone to redraw figures without a simulation, fit or bag:

    PYTHONPATH=gym MPLBACKEND=Agg python experiments/report_figures.py
    PYTHONPATH=gym MPLBACKEND=Agg python experiments/report_figures.py --only ekf

Nothing here writes to runs/ or evidence/*/metrics; only PNG and caption files
change. Each figure's words (finding, sample size, conditions, sources) are in
the caption written beside it, never on the canvas.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

import figure_style as fs

plt = fs.plt
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS = REPO_ROOT / "runs"
FIGURES = REPO_ROOT / "reports" / "figures"
ITEM11 = REPO_ROOT / "evidence" / "item11"

# Evidence classes from docs/data-and-figures.md; each caption opens with one.
SIMULATOR = "Simulator output, F1TENTH Gym"
SIMULATOR_ROS = "Simulator-backed ROS 2 capture, F1TENTH Gym"


def module_constant(path: Path, name: str):
    """Read a literal module constant without importing the module (and its Gym import)."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {path}")


def metric_map(path: Path) -> dict[str, float]:
    frame = pd.read_csv(path)
    return {str(row.metric): float(row.value) for row in frame.itertuples(index=False)}


SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def sci(value: float) -> str:
    """One significant figure in a × 10ⁿ form, e.g. 9 × 10⁻¹⁰ (caption text, not canvas)."""
    mantissa, exponent = f"{value:.0e}".split("e")
    return f"{mantissa} × 10{str(int(exponent)).translate(SUPERSCRIPT)}"


def rel(path: Path) -> str:
    """Repository-relative source path for a caption (absolute when the run lives elsewhere)."""
    path = Path(path).resolve()
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def ms_ticks(ax, values_s) -> None:
    """Log timestep axis labelled in milliseconds at the tested values."""
    ax.set_xscale("log")
    ax.set_xticks(values_s, [f"{v * 1000:g}" for v in values_s])
    ax.minorticks_off()


def marker(ax, x, y, shape: str, filled: bool = True, **kwargs):
    return ax.plot(x, y, marker=shape, mfc=fs.FILL[filled], **{**fs.MARKER, **kwargs})[0]


def marker_handle(shape: str, label: str, filled: bool = True, **kwargs):
    return Line2D([], [], marker=shape, label=label, **{**fs.MARKER, "mfc": fs.FILL[filled], **kwargs})


def span_handle(label: str):
    return Patch(label=label, **fs.SPAN)


def overlay(ax, t, reference, model, every: int, model_entity: str = "fit") -> None:
    """A reference trace as a line and a model on it as sparse hollow markers, so both stay visible."""
    fs.line(ax, t, reference, "reference", zorder=2)
    ax.plot(t, model, ls="none", marker=fs.STYLE[model_entity]["marker"], markevery=every, ms=3.5,
            mfc="white", mec=fs.INK, mew=0.7, zorder=3)


def overlay_handles(reference: str, model: str, model_entity: str = "fit"):
    return [fs.handle("reference", reference, marker=False),
            Line2D([], [], ls="none", marker=fs.STYLE[model_entity]["marker"], ms=3.5, mfc="white",
                   mec=fs.INK, mew=0.7, label=model)]


# --- RK4 timestep convergence -------------------------------------------------

def draw_integrator_convergence(run_dir: Path = RUNS / "integrator_convergence", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    results = pd.read_csv(run_dir / "convergence_results.csv").sort_values("dt_s")
    source = REPO_ROOT / "experiments" / "integrator_convergence.py"
    rms_tol = module_constant(source, "RMS_REFINEMENT_TOL_M")
    max_tol = module_constant(source, "MAX_REFINEMENT_TOL_M")
    src = rel(run_dir / "convergence_results.csv")
    return [convergence_position_error(results, figure_dir / "integrator_convergence_position_error.png", rms_tol, max_tol, src),
            convergence_metrics(results, figure_dir / "integrator_convergence_metrics.png", src)]


def _collided(results: pd.DataFrame) -> pd.Series:
    return results["collision"].astype(bool) | ~results["completed_lap"].astype(bool)


def _crash_note(results: pd.DataFrame) -> str:
    crashed = results[_collided(results)]
    if crashed.empty:
        return ""
    row = crashed.iloc[0]
    return (f" The {row['dt_s'] * 1000:g} ms run collided at {row['final_time_s']:.2f} s, so its values cover a "
            "partial lap and are drawn hollow.")


CONVERGENCE_STYLES = {"rms": ("o", "-"), "max": ("s", (0, (5, 2)))}


def convergence_position_error(results: pd.DataFrame, path: Path, rms_tol: float, max_tol: float, source: str) -> Path:
    ref_dt = float(results["dt_s"].min())
    fig, axes = fs.subplots(1, 2, height_in=3.0, sharey=True)
    panels = [("vs_ref_progress_m", "position_error"), ("vs_next_finer_dt_progress_m", "position_change")]
    for ax, (suffix, stem) in zip(axes, panels):
        data = results[(results["dt_s"] > ref_dt) & results[f"rms_{stem}_{suffix}"].notna()]
        ok, bad = data[~_collided(data)], data[_collided(data)]
        for kind, (shape, ls) in CONVERGENCE_STYLES.items():
            column = f"{kind}_{stem}_{suffix}"
            ax.plot(ok["dt_s"], ok[column], marker=shape, mfc=fs.FILL[True], **{**fs.MARKER, "ls": ls})
            if not bad.empty:
                marker(ax, bad["dt_s"], bad[column], shape, filled=False)
        ms_ticks(ax, results["dt_s"].tolist())
        ax.set_yscale("log")
        ax.set_xlabel("RK4 timestep [ms]")
        ax.margins(x=0.08, y=0.12)
    axes[1].axhline(rms_tol, zorder=1, **fs.REFERENCE)
    axes[1].axhline(max_tol, zorder=1, color=fs.INK, lw=0.6, ls=(0, (6, 2, 1, 2)))
    axes[0].set_ylabel("Position difference [m]")
    fs.letters(axes)
    fs.legend(fig, [Line2D([], [], marker="o", mfc=fs.FILL[True], label="RMS", **{**fs.MARKER, "ls": "-"}),
                    Line2D([], [], marker="s", mfc=fs.FILL[True], label="Maximum", **{**fs.MARKER, "ls": (0, (5, 2))}),
                    Line2D([], [], label="RMS tolerance", **fs.REFERENCE),
                    Line2D([], [], label="Maximum tolerance", color=fs.INK, lw=0.6, ls=(0, (6, 2, 1, 2)))], ncol=4)
    change = results.dropna(subset=["rms_position_change_vs_next_finer_dt_progress_m"])
    passing = change[(~_collided(change)) & (change["rms_position_change_vs_next_finer_dt_progress_m"] < rms_tol)
                     & (change["max_position_change_vs_next_finer_dt_progress_m"] < max_tol)]["dt_s"]
    largest = float(passing.max())
    assert set(passing) == set(change[change["dt_s"] <= largest]["dt_s"]), "tolerance pass set is not contiguous"
    caption = (f"{SIMULATOR}, RK4 integrator, pure pursuit. Position error shrinks with the timestep; both refinement "
               f"tolerances hold from {largest * 1000:g} ms down. Panel (a): progress-aligned position error against "
               f"the {ref_dt * 1000:g} ms run. Panel (b): progress-aligned position change against the next finer "
               "timestep, with the RMS tolerance (dotted) and maximum tolerance (dash-dot), "
               f"{rms_tol:g} m and {max_tol:g} m. Circles on solid lines are RMS differences; squares on dashed lines "
               "are maximum differences. Both axes are logarithmic. "
               f"n = {len(results)} timesteps, one closed-loop lap each, so there are no error bars."
               f"{_crash_note(results)} Source: {source}.")
    return fs.save(fig, path, caption)[0]


def convergence_metrics(results: pd.DataFrame, path: Path, source: str) -> Path:
    failed = _collided(results)
    ok, bad = results[~failed], results[failed]
    fig, axes = fs.subplots(1, 3, height_in=2.7, sharex=True)
    specs = [("final_progress_m", "Final progress [m]"),
             ("rms_cte_m", "RMS cross-track error [m]"),
             ("max_abs_cte_m", "Peak cross-track error [m]")]
    for ax, (column, ylabel) in zip(axes, specs):
        ax.plot(ok["dt_s"], ok[column], marker="o", mfc=fs.FILL[True], **{**fs.MARKER, "ls": "-"})
        if not bad.empty:
            marker(ax, bad["dt_s"], bad[column], "o", filled=False)
        ms_ticks(ax, results["dt_s"].tolist())
        ax.set_ylabel(ylabel)
        ax.set_xlabel("RK4 timestep [ms]")
        ax.margins(x=0.08, y=0.15)
    fs.letters(axes)
    fs.legend(fig, [marker_handle("o", "Completed lap"), marker_handle("o", "Collided, partial lap", filled=False)])
    finding = f"Every timestep from {ok['dt_s'].max() * 1000:g} ms down completes the lap"
    if not bad.empty:
        row = bad.iloc[0]
        finding += f"; the {row['dt_s'] * 1000:g} ms run collides at {row['final_time_s']:.2f} s"
    caption = (f"{SIMULATOR}, RK4 integrator, pure pursuit. {finding}. Panels show (a) the progress reached when the "
               "run stopped, (b) RMS cross-track error and (c) peak absolute cross-track error against the RK4 "
               "timestep (logarithmic axis). Filled circles are completed laps; a hollow circle is a collided run, "
               "whose errors cover a partial lap and are not peers of the completed laps. "
               f"n = {len(results)} timesteps, one closed-loop lap each, so there are no error bars. Source: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Known-parameter dynamic replay ------------------------------------------

def draw_dynamic_replay(run_dir: Path = RUNS / "dynamic_model_replay", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    trace = pd.read_csv(run_dir / "replay_trace.csv")
    metrics = metric_map(run_dir / "metrics.csv")
    # test_replay_metrics.py replays into a scratch run directory; the caption names the committed source.
    src = "runs/dynamic_model_replay/replay_trace.csv and runs/dynamic_model_replay/metrics.csv"
    return [dynamic_replay_yaw_rate(trace, metrics, figure_dir / "dynamic_replay_yaw_rate_overlay.png", src),
            dynamic_replay_state_errors(trace, metrics, figure_dir / "dynamic_replay_state_errors.png", src)]


EVERY = 40  # model markers along a 100 Hz trace: one every 0.4 s


def dynamic_replay_yaw_rate(trace: pd.DataFrame, metrics: dict[str, float], path: Path, source: str) -> Path:
    fig, axes = fs.subplots(3, 1, height_in=5.2, sharex=True, gridspec_kw={"height_ratios": [1.6, 1.6, 1]})
    t = trace["time_s"]
    overlay(axes[0], t, trace["gym_yaw_rate_radps"], trace["dynamic_yaw_rate_radps"], EVERY, "dynamic")
    fs.line(axes[1], t, trace["gym_yaw_rate_radps"], "reference", zorder=2)
    fs.line(axes[1], t, trace["kinematic_yaw_rate_radps"], "kinematic", zorder=3, lw=0.6)
    low = min(trace[c].min() for c in ("gym_yaw_rate_radps", "dynamic_yaw_rate_radps", "kinematic_yaw_rate_radps"))
    high = max(trace[c].max() for c in ("gym_yaw_rate_radps", "dynamic_yaw_rate_radps", "kinematic_yaw_rate_radps"))
    pad = 0.06 * (high - low)
    for ax in axes[:2]:
        ax.set(ylim=(low - pad, high + pad), ylabel="Yaw rate [rad/s]")
    fs.line(axes[2], t, trace["gym_steer_rad"], "reference")
    axes[2].set(ylabel="Steering [rad]", xlabel="Time [s]")
    for ax in axes:
        ax.axvline(2.0, zorder=1, **fs.REFERENCE)
        fs.zero_line(ax)
    fig.align_ylabels(axes)
    fs.letters(axes)
    fs.legend(fig, overlay_handles("Gym (reference)", "Dynamic replay", "dynamic")
              + [fs.handle("kinematic", "Kinematic yaw law", marker=False)])
    caption = (f"{SIMULATOR}, known parameters. The dynamic replay follows the Gym yaw rate (RMSE "
               f"{metrics['dynamic_yaw_rate_rmse_radps']:.3f} rad/s); the kinematic yaw law does not "
               f"({metrics['kinematic_yaw_rate_rmse_radps']:.2f} rad/s). Panel (a): Gym yaw rate (solid) with the "
               "dynamic replay as hollow triangles, one every 0.4 s. Panel (b): Gym yaw rate (solid) and the kinematic "
               "yaw law (dashed), on the same axes as (a). Panel (c): achieved steering angle in the Gym. The dotted "
               "vertical line marks t = 2.0 s. "
               f"First-lap RK4 telemetry, n = {int(metrics['num_samples']):,} samples over {metrics['duration_s']:.1f} s; "
               f"both models replay the same inputs. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def _state_error_rows(fig_axes, trace, rows):
    for ax, (column, label) in zip(fig_axes, rows):
        fs.line(ax, trace["time_s"], trace[column], "reference")
        fs.zero_line(ax)
        ax.set_ylabel(label)
        ax.margins(y=0.12)
    fig_axes[-1].set_xlabel("Time [s]")
    fig_axes[0].figure.align_ylabels(fig_axes)
    fs.letters(fig_axes)


def dynamic_replay_state_errors(trace: pd.DataFrame, metrics: dict[str, float], path: Path, source: str) -> Path:
    fig, axes = fs.subplots(4, 1, height_in=5.0, sharex=True)
    rows = [("error_position_m", "Position\nerror [m]"), ("error_yaw_rad", "Yaw\nerror [rad]"),
            ("error_yaw_rate_radps", "Yaw-rate\nerror [rad/s]"), ("error_speed_mps", "Speed\nerror [m/s]")]
    _state_error_rows(axes, trace, rows)
    caption = (f"{SIMULATOR}, known parameters. The dynamic replay stays within {metrics['max_position_error_m']:.2f} m "
               f"of the Gym trajectory over {metrics['duration_s']:.1f} s. Panels show (a) position, (b) yaw, (c) yaw-rate "
               "and (d) speed error, each the dynamic replay minus the Gym state; the dotted line is zero. "
               f"n = {int(metrics['num_samples']):,} RK4 samples. RMSE: position {metrics['rmse_position_m']:.3f} m, "
               f"yaw rate {metrics['rmse_yaw_rate_radps']:.3f} rad/s. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Kinematic replay ----------------------------------------------------------

def draw_kinematic_replay(run_dir: Path = RUNS / "model_vs_gym_comparison", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    trace = pd.read_csv(run_dir / "replay_trace.csv")
    metrics = metric_map(run_dir / "metrics.csv")
    src = f"{rel(run_dir / 'replay_trace.csv')} and {rel(run_dir / 'metrics.csv')}"
    return [kinematic_trajectory(trace, metrics, figure_dir / "model_vs_gym_trajectory_error.png", src),
            kinematic_state_errors(trace, metrics, figure_dir / "model_vs_gym_state_errors.png", src)]


def kinematic_trajectory(trace: pd.DataFrame, metrics: dict[str, float], path: Path, source: str) -> Path:
    fig, ax = fs.subplots(height_in=5.0, width_in=6.0)
    fs.line(ax, trace["gym_x_m"], trace["gym_y_m"], "reference")
    fs.line(ax, trace["model_x_m"], trace["model_y_m"], "kinematic")
    marker(ax, trace["gym_x_m"].iloc[0], trace["gym_y_m"].iloc[0], "o", ms=10, zorder=5).set_markerfacecolor("none")
    marker(ax, trace["gym_x_m"].iloc[-1], trace["gym_y_m"].iloc[-1], "s", zorder=4)
    marker(ax, trace["model_x_m"].iloc[-1], trace["model_y_m"].iloc[-1], "^", zorder=4)
    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(0.05)
    ax.set_xlabel("$x$ [m]")
    ax.set_ylabel("$y$ [m]")
    fs.legend(fig, [fs.handle("reference", "Gym RK4 (reference)", marker=False),
                    fs.handle("kinematic", "Kinematic replay", marker=False),
                    marker_handle("o", "Start", filled=False, ms=10, mfc="none"), marker_handle("s", "Gym end"), marker_handle("^", "Replay end")],
              ncol=3)
    caption = (f"{SIMULATOR}, first lap. The kinematic replay leaves the Gym path: "
               f"{metrics['final_position_error_m']:.1f} m apart after {metrics['duration_replayed_s']:.1f} s "
               f"(maximum {metrics['max_position_error_m']:.1f} m). The Gym RK4 trajectory is solid and the kinematic "
               "bicycle replay of the same inputs is dashed; the open ring marks the start, the square the Gym end "
               f"and the triangle the replay end. n = {int(metrics['num_samples']):,} samples at "
               f"{metrics['dt_mean_s'] * 1000:g} ms. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def kinematic_state_errors(trace: pd.DataFrame, metrics: dict[str, float], path: Path, source: str) -> Path:
    fig, axes = fs.subplots(3, 1, height_in=4.2, sharex=True)
    _state_error_rows(axes, trace, [("error_position_m", "Position\nerror [m]"),
                                    ("error_yaw_rad", "Wrapped yaw\nerror [rad]"),
                                    ("error_speed_mps", "Speed\nerror [m/s]")])
    speed_max = float(trace["error_speed_mps"].abs().max())
    caption = (f"{SIMULATOR}, first lap. The kinematic replay position error reaches "
               f"{metrics['max_position_error_m']:.1f} m while speed error stays below "
               f"{np.ceil(speed_max * 100) / 100:.2f} m/s. Panels show (a) position, (b) yaw and (c) speed error, each "
               "the kinematic replay minus the Gym state; yaw error is wrapped to ±π rad and the dotted line is zero. "
               f"n = {int(metrics['num_samples']):,} samples. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Steering excitation -------------------------------------------------------

def draw_sysid_excitation(run_dir: Path = RUNS / "sysid_steering_excitation", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    telemetry = pd.read_csv(run_dir / "telemetry.csv")
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    quality = metric_map(run_dir / "quality_metrics.csv")
    src = f"{rel(run_dir / 'telemetry.csv')}, {rel(run_dir / 'metadata.json')} and {rel(run_dir / 'quality_metrics.csv')}"
    return [sysid_steering_input(telemetry, metadata, quality, figure_dir / "sysid_steering_input.png", src),
            sysid_yaw_response(telemetry, metadata, quality, figure_dir / "sysid_yaw_response.png", src),
            sysid_speed_hold(telemetry, metadata, quality, figure_dir / "sysid_speed_hold.png", src)]


def _chirp_label(metadata: dict) -> str:
    profile = metadata["selected_profile"]
    return (f"{metadata['frequency_start_hz']:g} to {metadata['frequency_end_hz']:g} Hz chirp, "
            f"{profile['amplitude_rad']:g} rad amplitude, {profile['duration_s']:g} s at {metadata['target_speed_mps']:g} m/s")


def sysid_steering_input(df: pd.DataFrame, metadata: dict, quality: dict, path: Path, source: str) -> Path:
    fig, ax = fs.subplots(height_in=2.6)
    fs.line(ax, df["time_s"], df["steer_rad"], "reference", zorder=2)
    fs.line(ax, df["time_s"], df["command_steer_rad"], "command", zorder=3)
    fs.zero_line(ax)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Steering angle [rad]")
    fs.legend(fig, [fs.handle("command", "Commanded", marker=False), fs.handle("reference", "Achieved (Gym state)", marker=False)])
    peak = float(df[["command_steer_rad", "steer_rad"]].abs().max().max())
    limit = float(metadata["saturation_threshold_rad"])
    caption = (f"{SIMULATOR}, open occupancy map. The steering chirp stays within ±{peak:.3f} rad, far inside the "
               f"±{limit:.2f} rad steering limit, which lies outside the plotted range; saturated fraction "
               f"{quality['steering_saturation_fraction']:g}. Commanded steering is dash-dot and the achieved Gym "
               f"steering state is solid; the dotted line is zero. {_chirp_label(metadata)}; "
               f"n = {int(quality['num_samples']):,} samples. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def sysid_yaw_response(df: pd.DataFrame, metadata: dict, quality: dict, path: Path, source: str) -> Path:
    fig, axes = fs.subplots(2, 1, height_in=3.6, sharex=True)
    fs.line(axes[0], df["time_s"], df["yaw_rate_radps"], "reference")
    axes[0].set_ylabel("Yaw rate [rad/s]")
    fs.line(axes[1], df["time_s"], df["slip_angle_rad"], "reference")
    axes[1].set_ylabel("Slip angle [rad]")
    axes[1].set_xlabel("Time [s]")
    for ax in axes:
        fs.zero_line(ax)
    fig.align_ylabels(axes)
    fs.letters(axes)
    slip_range = float(df["slip_angle_rad"].max() - df["slip_angle_rad"].min())
    caption = (f"{SIMULATOR}, open occupancy map. The chirp excites yaw rate over a "
               f"{quality['yaw_rate_range_radps']:.2f} rad/s range and slip angle over {slip_range:.3f} rad. Panel (a): "
               "Gym yaw rate; panel (b): Gym slip angle; the dotted line is zero. "
               f"{_chirp_label(metadata)}; n = {int(quality['num_samples']):,} Gym states. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def sysid_speed_hold(df: pd.DataFrame, metadata: dict, quality: dict, path: Path, source: str) -> Path:
    target = float(metadata["target_speed_mps"])
    low, high = 0.85 * target, 1.15 * target
    fig, ax = fs.subplots(height_in=2.6)
    ax.axhspan(low, high, zorder=0, **fs.SPAN)
    fs.line(ax, df["time_s"], df["speed_mps"], "reference", zorder=2)
    fs.line(ax, df["time_s"], df["command_speed_mps"], "command", zorder=3)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Speed [m/s]")
    ax.set_ylim(bottom=0)
    fs.legend(fig, [fs.handle("command", "Commanded", marker=False),
                    fs.handle("reference", "Achieved (Gym state)", marker=False),
                    span_handle("$\\pm$15 % band")])
    outside = df[(df["speed_mps"] < low) | (df["speed_mps"] > high)]
    settle = float(outside["time_s"].max()) if not outside.empty else 0.0
    caption = (f"{SIMULATOR}, open occupancy map. After {settle:.1f} s of start-up, speed stays inside the ±15 % band "
               f"(shaded) around {target:g} m/s. Commanded speed is dash-dot and the achieved Gym speed is solid. "
               f"{_chirp_label(metadata)}. Mean {quality['speed_mean_mps']:.2f} m/s, coefficient of variation "
               f"{quality['speed_cv'] * 100:.1f} %; n = {int(quality['num_samples']):,}. Sources: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Dynamic parameter identification -------------------------------------------

def draw_parameter_fit(run_dir: Path, fit_path: Path, residual_path: Path, evidence: str = SIMULATOR) -> list[Path]:
    fs.apply()
    fit_trace = pd.read_csv(run_dir / "fit_trace.csv")
    validation = pd.read_csv(run_dir / "heldout_replay_trace.csv")
    return [parameter_fit(fit_trace, fit_path, evidence, rel(run_dir / "fit_trace.csv")),
            parameter_residuals(validation, residual_path, evidence, rel(run_dir / "heldout_replay_trace.csv"))]


def parameter_fit(fit_trace: pd.DataFrame, path: Path, evidence: str, source: str) -> Path:
    heldout = fit_trace[fit_trace["partition"] == "heldout"]
    start, end = float(heldout["time_s"].iloc[0]), float(fit_trace["time_s"].iloc[-1])
    fig, axes = fs.subplots(2, 1, height_in=3.8, sharex=True)
    rows = [("yaw_rate_radps", "Yaw rate [rad/s]"), ("slip_angle_rad", "Slip angle [rad]")]
    every = max(len(fit_trace) // 60, 1)
    for ax, (stem, label) in zip(axes, rows):
        ax.axvspan(start, end, zorder=0, **fs.SPAN)
        overlay(ax, fit_trace["time_s"], fit_trace[f"measured_{stem}"], fit_trace[f"predicted_{stem}"], every)
        fs.zero_line(ax)
        ax.set_ylabel(label)
    axes[-1].set_xlabel("Time [s]")
    fig.align_ylabels(axes)
    fs.letters(axes)
    fs.legend(fig, overlay_handles("Gym (measured)", "Fitted model, one step ahead") + [span_handle("Held-out intervals")])
    worst = float(fit_trace[["yaw_rate_residual_radps", "slip_angle_residual_rad"]].abs().max().max())
    counts = fit_trace["partition"].value_counts()
    caption = (f"{evidence}. The fitted single-track model matches the Gym within {sci(worst)} on training and held-out "
               "intervals. Panel (a): yaw rate; panel (b): slip angle. The Gym state is solid and the fitted model's "
               f"one-step-ahead prediction is drawn as hollow squares on every {every}th interval; the shaded span holds "
               f"the held-out intervals. Intervals: {counts.get('train', 0):,} training, {counts.get('heldout', 0):,} "
               "held out (final 30 %). A simulator-recovery test with Gym internal states, not vehicle identification. "
               f"Source: {source}.")
    return fs.save(fig, path, caption)[0]


def parameter_residuals(validation: pd.DataFrame, path: Path, evidence: str, source: str) -> Path:
    fig, axes = fs.subplots(3, 1, height_in=4.4, sharex=True)
    rows = [("yaw_rate_error_radps", "Yaw-rate error\n[$10^{-9}$ rad/s]"),
            ("slip_angle_error_rad", "Slip-angle error\n[$10^{-9}$ rad]"),
            ("yaw_error_rad", "Yaw error\n[$10^{-9}$ rad]")]
    for ax, (column, label) in zip(axes, rows):
        fs.line(ax, validation["time_s"], validation[column] * 1e9, "reference")
        fs.zero_line(ax)
        ax.set_ylabel(label)
        ax.margins(y=0.12)
    axes[-1].set_xlabel("Time [s]")
    fig.align_ylabels(axes)
    fs.letters(axes)
    worst = float(validation[[r[0] for r in rows]].abs().max().max())
    duration = float(validation["time_s"].iloc[-1] - validation["time_s"].iloc[0])
    caption = (f"{evidence}. Held-out rollout residuals stay below {sci(worst)} over {duration:.1f} s. Panels show the "
               "(a) yaw-rate, (b) slip-angle and (c) yaw residual, each the fitted model minus the Gym, in units of "
               f"10⁻⁹; the dotted line is zero. Independent rollout of the fitted model over the held-out {duration:.1f} s; "
               f"n = {len(validation):,} samples. Source: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Pure-pursuit sweep ----------------------------------------------------------

CLASS_STYLE = {  # classification -> (label, marker, filled); hollow means no completed lap
    "stable": ("Stable", "o", True),
    "oscillatory": ("Oscillatory", "^", True),
    "corner_cutting": ("Corner cutting", "D", True),
    "incomplete": ("No lap within time limit", "s", False),
    "collision": ("Collision", "X", False),
}
HATCH = {"incomplete": "////", "collision": "xxxx"}


def draw_pure_pursuit(run_dir: Path = RUNS / "pure_pursuit_sweep", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    results = pd.read_csv(run_dir / "results.csv")
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    src = f"{rel(run_dir / 'results.csv')} and {rel(run_dir / 'metadata.json')}"
    return [pp_heatmap(results, metadata, "rms_cte", figure_dir / "pure_pursuit_sweep_rms_cte_heatmap.png", src),
            pp_heatmap(results, metadata, "lap_time", figure_dir / "pure_pursuit_sweep_lap_time_heatmap.png", src),
            pp_regions(results, metadata, figure_dir / "pure_pursuit_sweep_regions.png", src)]


def _pp_note(results: pd.DataFrame, metadata: dict) -> str:
    return (f"n = {len(results)} closed-loop runs, one per setting; integration step {metadata['integration_dt_s'] * 1000:g} ms, "
            f"control {metadata['control_rate_hz']:g} Hz.")


def _baseline(results: pd.DataFrame) -> pd.Series:
    rows = results[results["selected_baseline"].astype(bool)]
    assert len(rows) == 1, "expected one selected baseline"
    return rows.iloc[0]


def pp_grid(results: pd.DataFrame, kind: str):
    """Rows by velocity gain (descending), columns by lookahead; NaN where a lap time does not exist."""
    lookaheads = sorted(results["lookahead_m"].unique())
    gains = sorted(results["vgain"].unique(), reverse=True)
    column = "rms_cte_m" if kind == "rms_cte" else "lap_time_s"
    grid = np.full((len(gains), len(lookaheads)), np.nan)
    status = np.empty(grid.shape, dtype=object)
    for row in results.itertuples(index=False):
        i, j = gains.index(row.vgain), lookaheads.index(row.lookahead_m)
        status[i, j] = row.classification
        if kind == "rms_cte" or bool(row.completed_lap):
            grid[i, j] = getattr(row, column)
    return lookaheads, gains, grid, status


def pp_heatmap(results: pd.DataFrame, metadata: dict, kind: str, path: Path, source: str) -> Path:
    lookaheads, gains, grid, status = pp_grid(results, kind)
    completed = results["completed_lap"].astype(bool)
    fig, ax = fs.subplots(height_in=3.6, width_in=6.0)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    image = ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, aspect="auto")
    norm = image.norm
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if status[i, j] in HATCH:
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch=HATCH[status[i, j]],
                                       edgecolor="0.55", linewidth=0))
            value = grid[i, j]
            if np.isnan(value):
                continue
            r, g, b, _ = cmap(norm(value))
            ink = "black" if (0.299 * r + 0.587 * g + 0.114 * b) > 0.5 else "white"
            ax.text(j, i, f"{value:.2f}" if kind == "rms_cte" else f"{value:.1f}", ha="center", va="center",
                    fontsize=fs.TICK_SIZE, color=ink, gid="cell")
    base = _baseline(results)
    bi, bj = gains.index(base["vgain"]), lookaheads.index(base["lookahead_m"])
    ax.add_patch(Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False, edgecolor=fs.INK, linewidth=1.6))
    ax.set_xticks(range(len(lookaheads)), [f"{v:g}" for v in lookaheads])
    ax.set_yticks(range(len(gains)), [f"{v:g}" for v in gains])
    ax.set_xlabel("Lookahead distance [m]")
    ax.set_ylabel("Velocity gain")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    bar = fig.colorbar(image, ax=ax, shrink=0.9)
    bar.outline.set_visible(False)
    present = [k for k in HATCH if (status == k).any()]
    handles = [Patch(facecolor="white", edgecolor="0.55", hatch=HATCH[k], label=CLASS_STYLE[k][0]) for k in present]
    handles.append(Patch(facecolor="white", edgecolor=fs.INK, linewidth=1.6, label="Selected baseline"))
    fs.legend(fig, handles)
    done = results[completed]
    if kind == "rms_cte":
        bar.set_label("RMS cross-track error [m]")
        _check_monotone(done, "rms_cte_m", increasing=True)
        caption = (f"{SIMULATOR}, pure pursuit. Among completed laps, RMS cross-track error grows with lookahead and "
                   "velocity gain. Each cell is one run, coloured and labelled by its RMS cross-track error [m]; the "
                   "colour bar gives the scale. Hatched cells did not complete a lap (diagonal: no lap within the time "
                   "limit; crossed: collision), so their RMS covers the partial run. The black box marks the selected "
                   f"baseline ({base['lookahead_m']:g} m lookahead, gain {base['vgain']:g}). {_pp_note(results, metadata)} "
                   f"Sources: {source}.")
    else:
        bar.set_label("Lap time [s]")
        _check_monotone(done, "lap_time_s", increasing=False, along="vgain")
        caption = (f"{SIMULATOR}, pure pursuit. Completed laps get faster as velocity gain rises "
                   f"({done['lap_time_s'].min():.1f} to {done['lap_time_s'].max():.1f} s). Each cell is one run, coloured "
                   "and labelled by its lap time [s]; the colour bar gives the scale. "
                   f"{int((~completed).sum())} runs did not complete a lap and have no lap time: their cells are white "
                   "and hatched (diagonal: no lap within the time limit; crossed: collision). The black box marks the "
                   f"selected baseline ({base['lookahead_m']:g} m lookahead, gain {base['vgain']:g}). "
                   f"{_pp_note(results, metadata)} Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def _check_monotone(done: pd.DataFrame, column: str, increasing: bool, along: str | None = None) -> None:
    """Caption claims hold for every completed run: test them before rendering."""
    axes = [along] if along else ["vgain", "lookahead_m"]
    for axis in axes:
        other = "lookahead_m" if axis == "vgain" else "vgain"
        for _, group in done.groupby(other):
            values = group.sort_values(axis)[column].to_numpy()
            steps = np.diff(values)
            assert (steps > 0).all() if increasing else (steps < 0).all(), f"{column} is not monotone in {axis}"


def pp_regions(results: pd.DataFrame, metadata: dict, path: Path, source: str) -> Path:
    fig, ax = fs.subplots(height_in=3.4, width_in=6.0)
    base = _baseline(results)
    marker(ax, [base["lookahead_m"]], [base["vgain"]], "o", filled=False, ms=13, mew=0.8, zorder=2)
    handles, counts = [], []
    for key, (label, shape, filled) in CLASS_STYLE.items():
        group = results[results["classification"] == key]
        if group.empty:
            continue
        marker(ax, group["lookahead_m"], group["vgain"], shape, filled=filled, ms=6, zorder=3)
        handles.append(marker_handle(shape, label, filled=filled, ms=6))
        counts.append(f"{label.lower()} {len(group)}")
    handles.append(marker_handle("o", "Selected baseline", filled=False, ms=13, mew=0.8))
    values_x, values_y = sorted(results["lookahead_m"].unique()), sorted(results["vgain"].unique())
    ax.set_xticks(values_x, [f"{v:g}" for v in values_x])
    ax.set_yticks(values_y, [f"{v:g}" for v in values_y])
    ax.set_xlabel("Lookahead distance [m]")
    ax.set_ylabel("Velocity gain")
    ax.margins(0.08)
    fs.legend(fig, handles, ncol=3)
    completed = int(results["completed_lap"].astype(bool).sum())
    assert base["classification"] == "stable"
    caption = (f"{SIMULATOR}, pure pursuit. {completed} of {len(results)} settings complete a lap; the selected baseline "
               f"({base['lookahead_m']:g} m lookahead, gain {base['vgain']:g}, large ring) is stable. Each marker is one "
               "setting, its shape giving the run class from experiments/pure_pursuit_sweep.py; filled markers "
               "completed a lap and hollow markers did not. Counts: " + ", ".join(counts) + ". "
               f"{_pp_note(results, metadata)} Sources: {source}.")
    return fs.save(fig, path, caption)[0]


# --- EKF study ---------------------------------------------------------------------

SCENARIO_NAMES = {
    "clean_measurements": "Clean measurements",
    "low_noise": "Low noise",
    "high_noise": "High noise",
    "dropout_1s": "1 s dropout",
    "dropout_3s": "3 s dropout",
}


def draw_ekf(run_dir: Path = RUNS / "ekf_study", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    trace = pd.read_csv(run_dir / "trace.csv")
    summary = pd.read_csv(run_dir / "summary.csv")
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    src = f"{rel(run_dir / 'trace.csv')}, {rel(run_dir / 'summary.csv')} and {rel(run_dir / 'metadata.json')}"
    return [ekf_position_error(trace, metadata, figure_dir / "ekf_position_error_over_time.png", src),
            ekf_rmse_summary(summary, figure_dir / "ekf_rmse_summary.png", rel(run_dir / "summary.csv")),
            ekf_dropout_zoom(trace, metadata, figure_dir / "ekf_dropout_zoom.png", src)]


def _windows(metadata: dict, scenario: str) -> list[tuple[float, float]]:
    return [(w["start_s"], w["start_s"] + w["duration_s"]) for w in metadata["scenarios"][scenario]["dropout_windows"]]


def _ekf_note(metadata: dict, trace: pd.DataFrame) -> str:
    return (f"Same nominal pure-pursuit lap ({trace['time_s'].max():.1f} s) for every scenario; seed {metadata['seed']}, "
            f"{metadata['integration_dt_s'] * 1000:g} ms steps. Dead reckoning uses no measurements, so its error is the "
            "same in every scenario.")


def ekf_position_error(trace: pd.DataFrame, metadata: dict, path: Path, source: str) -> Path:
    dead = trace[(trace["estimator"] == "dead_reckoning")]
    first = dead[dead["scenario"] == "low_noise"]
    for scenario, group in dead.groupby("scenario"):
        assert np.array_equal(group["position_error_m"].to_numpy(), first["position_error_m"].to_numpy()), scenario
    scenarios = ("low_noise", "dropout_1s")
    fig, axes = fs.subplots(len(scenarios), 1, height_in=3.8, sharex=True, sharey=True)
    peaks = []
    for ax, scenario in zip(axes, scenarios):
        group = trace[(trace["scenario"] == scenario) & (trace["estimator"] == "ekf")]
        peaks.append(float(group["position_error_m"].max()))
        for start, stop in _windows(metadata, scenario):
            ax.axvspan(start, stop, zorder=0, **fs.SPAN)
        fs.line(ax, first["time_s"], first["position_error_m"], "dead_reckoning")
        fs.line(ax, group["time_s"], group["position_error_m"], "ekf")
        ax.set_yscale("log")
        ax.set_ylabel("Position error [m]")
    axes[-1].set_xlabel("Time [s]")
    fs.letters(axes)
    fs.legend(fig, [fs.handle("ekf", "EKF", marker=False), fs.handle("dead_reckoning", "Dead reckoning", marker=False),
                    span_handle("Measurement dropout")])
    (start, stop), = _windows(metadata, "dropout_1s")
    caption = (f"{SIMULATOR}, simulated sensor noise. The EKF keeps position error below "
               f"{np.ceil(max(peaks) * 10) / 10:.1f} m; dead reckoning drifts to {first['position_error_m'].max():.0f} m. "
               "Panel (a): low-noise scenario; panel (b): 1 s dropout scenario, with all measurement channels withheld "
               f"from {start:g} to {stop:g} s (shaded). The EKF is solid and dead reckoning dashed, on a logarithmic "
               f"axis shared by both panels. {_ekf_note(metadata, trace)} Sources: {source}.")
    return fs.save(fig, path, caption)[0]


def ekf_rmse_summary(summary: pd.DataFrame, path: Path, source: str) -> Path:
    order = [s for s in SCENARIO_NAMES if s in set(summary["scenario"])]
    pivot = summary.pivot(index="scenario", columns="estimator", values="position_rmse_m").loc[order]
    fig, ax = fs.subplots(height_in=2.6)
    y = np.arange(len(order))[::-1]
    ax.hlines(y, pivot["ekf"], pivot["dead_reckoning"], color=fs.INK, linewidth=0.5, zorder=1)
    marker(ax, pivot["dead_reckoning"], y, "s", zorder=3)
    marker(ax, pivot["ekf"], y, "o", zorder=3)
    ax.set_yticks(y, [SCENARIO_NAMES[s] for s in order])
    ax.set_xscale("log")
    ax.set_xlabel("Position RMSE [m]")
    ax.margins(x=0.08, y=0.12)
    fs.legend(fig, [marker_handle("o", "EKF"), marker_handle("s", "Dead reckoning")])
    values = "; ".join(f"{SCENARIO_NAMES[s].lower()} {pivot.loc[s, 'ekf']:.4f} m" for s in order)
    caption = (f"{SIMULATOR}, simulated sensor noise. EKF position RMSE stays below "
               f"{np.ceil(pivot['ekf'].max() * 100) / 100:.2f} m in every scenario; dead reckoning reaches "
               f"{pivot['dead_reckoning'].max():.1f} m. Whole-lap position RMSE per scenario for the EKF (circles) and "
               "dead reckoning (squares), on a logarithmic axis; lower is better. EKF values: " + values + ". "
               f"n = 1 seeded run per scenario and estimator ({len(order)} scenarios), so there are no error bars. "
               f"Source: {source}.")
    return fs.save(fig, path, caption)[0]


def ekf_dropout_zoom(trace: pd.DataFrame, metadata: dict, path: Path, source: str) -> Path:
    (start, stop), = _windows(metadata, "dropout_3s")
    lo, hi = start - 1.5, stop + 1.0
    window = trace[(trace["scenario"] == "dropout_3s") & trace["time_s"].between(lo, hi)]
    fig, ax = fs.subplots(height_in=2.8)
    ax.axvspan(start, stop, zorder=0, **fs.SPAN)
    for estimator in ("dead_reckoning", "ekf"):
        group = window[window["estimator"] == estimator]
        fs.line(ax, group["time_s"], group["position_error_m"], estimator)
    ax.set_yscale("log")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Position error [m]")
    fs.legend(fig, [fs.handle("ekf", "EKF", marker=False), fs.handle("dead_reckoning", "Dead reckoning", marker=False),
                    span_handle("Measurement dropout")])
    ekf = window[window["estimator"] == "ekf"]
    caption = (f"{SIMULATOR}, 3 s dropout scenario. During the dropout the EKF error grows to "
               f"{ekf['position_error_m'].max():.1f} m, then falls to {ekf['position_error_m'].iloc[-1]:.2f} m by "
               f"{ekf['time_s'].iloc[-1]:.0f} s. All measurement channels are withheld from {start:g} to {stop:g} s "
               "(shaded). The EKF is solid and dead reckoning dashed, on a logarithmic axis. "
               + _ekf_note(metadata, trace).split("; ")[0] + f". Sources: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Failure-mode screen ----------------------------------------------------------

FMEA_NAMES = {
    "euler_instability": "Euler instability",
    "bad_lookahead_small": "Lookahead too small",
    "bad_lookahead_large": "Lookahead too large",
    "latency_100ms": "100 ms control latency",
    "steering_saturation": "Steering saturation",
    "sensor_noise_high": "High sensor noise",
    "measurement_dropout_3s": "3 s measurement dropout",
}


def draw_fmea(run_dir: Path = RUNS / "failure_mode_fmea", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    results = pd.read_csv(run_dir / "results.csv")
    src = rel(run_dir / "results.csv")
    return [fmea_rpn(results, figure_dir / "fmea_rpn_bar.png", src),
            fmea_detection_signals(results, figure_dir / "fmea_detection_signals.png", src)]


def fmea_rpn(results: pd.DataFrame, path: Path, source: str) -> Path:
    ordered = results.sort_values("rpn", ascending=True)
    fig, ax = fs.subplots(height_in=2.9)
    y = np.arange(len(ordered))
    reproduced = ordered["reproduced"].astype(bool).to_numpy()
    ax.barh(y, ordered["rpn"], height=0.6, color=[fs.FILL[r] for r in reproduced], edgecolor=fs.INK, linewidth=0.8)
    ax.set_yticks(y, [FMEA_NAMES.get(s, s) for s in ordered["scenario"]])
    ax.set_xlim(0, ordered["rpn"].max() * 1.08)
    ax.set_xlabel("Risk priority number (RPN)")
    fs.legend(fig, [Patch(facecolor=fs.FILL[True], edgecolor=fs.INK, label="Reproduced in simulation"),
                    Patch(facecolor=fs.FILL[False], edgecolor=fs.INK, label="Not reproduced")])
    top = ordered.iloc[-1]
    assert (results["rpn"] < top["rpn"]).sum() == len(results) - 1, "RPN maximum is tied"
    scores = "; ".join(f"{FMEA_NAMES.get(r.scenario, r.scenario).lower()} {r.rpn} = {r.severity_1_to_10} × "
                       f"{r.occurrence_1_to_10} × {r.detectability_1_to_10}" for r in ordered[::-1].itertuples(index=False))
    caption = (f"{SIMULATOR}, failure-mode screen. {FMEA_NAMES.get(top['scenario'], top['scenario'])} carries the highest "
               f"risk priority (RPN {top['rpn']}). RPN = severity × occurrence × detectability, each scored 1 to 10. "
               "Filled bars: failure reproduced in simulation; hollow bars: not reproduced. Scores, highest first: "
               f"{scores}. Source: {source}.")
    return fs.save(fig, path, caption)[0]


def _signal_group(signal: str) -> str:
    text = signal.lower()
    if text.startswith("collision at"):
        return "time"
    if "steer" in text:
        return "steer"
    return "position"


FMEA_GROUPS = [("time", "Time to collision [s]", "detected as a collision"),
               ("position", "Position error [m]", "detected as tracking or estimate error"),
               ("steer", "Steering command at limit [rad]", "detected as steering dwell at the limit")]


def fmea_detection_signals(results: pd.DataFrame, path: Path, source: str) -> Path:
    data = results.assign(group=results["detection_signal"].map(_signal_group))
    sizes = [max(int((data["group"] == g).sum()), 1) for g, _, _ in FMEA_GROUPS]
    fig, axes = fs.subplots(len(FMEA_GROUPS), 1, height_in=4.6, gridspec_kw={"height_ratios": sizes})
    panels = []
    for letter_index, (ax, (key, xlabel, meaning)) in enumerate(zip(axes, FMEA_GROUPS)):
        part = data[data["group"] == key].sort_values("detection_metric")
        y = np.arange(len(part))
        reproduced = part["reproduced"].astype(bool).to_numpy()
        ax.hlines(y, 0, part["detection_metric"], color=fs.INK, linewidth=0.5, zorder=1)
        for yi, value, r in zip(y, part["detection_metric"], reproduced):
            marker(ax, value, yi, "o", filled=bool(r), zorder=3)
        ax.set_yticks(y, [FMEA_NAMES.get(s, s) for s in part["scenario"]])
        ax.set_ylim(-0.6, len(part) - 0.4)
        ax.set_xlim(0, part["detection_metric"].max() * 1.12)
        ax.set_xlabel(xlabel)
        values = ", ".join(f"{FMEA_NAMES.get(r.scenario, r.scenario).lower()} {r.detection_metric:.3g}"
                           for r in part.itertuples(index=False))
        panels.append(f"({'abc'[letter_index]}) {meaning}: {values}")
    fs.letters(axes)
    fs.legend(fig, [marker_handle("o", "Reproduced in simulation"), marker_handle("o", "Not reproduced", filled=False)])
    collisions = data[data["group"] == "time"]
    caption = (f"{SIMULATOR}, failure-mode screen. Lookahead and latency faults collide within "
               f"{np.ceil(collisions['detection_metric'].max() * 10) / 10:.1f} s; noise and dropout show only as EKF "
               "position error. Each failure mode has its own detection signal, so each unit gets its own panel: "
               + "; ".join(panels) + ". Filled markers: failure reproduced in simulation; hollow markers: not "
               f"reproduced. Source: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Parameter-identification robustness -----------------------------------------

def draw_parameter_id_robustness(run_dir: Path = RUNS / "parameter_id_robustness", figure_dir: Path = FIGURES) -> list[Path]:
    fs.apply()
    results = pd.read_csv(run_dir / "results.csv")
    src = rel(run_dir / "results.csv")
    return [parameter_id_degradation(results, "noise", figure_dir / "parameter_id_noise_degradation.png", src),
            parameter_id_degradation(results, "latency", figure_dir / "parameter_id_latency_degradation.png", src),
            parameter_id_condition(results, figure_dir / "parameter_id_condition_number.png", src)]


def _scenario_label(name: str) -> str:
    if name == "nominal":
        return "Nominal"
    kind, _, level = name.partition("_")
    return {"noise": f"{level.capitalize()} noise", "latency": level.replace("ms", " ms"),
            "quantization": f"{level.capitalize()} quantization", "combined": f"Combined {level}"}.get(kind, name)


STIFFNESS = (("C_Sf", "Front, $C_{Sf}$", "o", "-"), ("C_Sr", "Rear, $C_{Sr}$", "s", (0, (5, 2))))


def parameter_id_degradation(results: pd.DataFrame, kind: str, path: Path, source: str) -> Path:
    subset = results[results["kind"].isin(["nominal", kind])].reset_index(drop=True)
    x = np.arange(len(subset))
    passed = subset["acceptance_passed"].astype(bool).to_numpy()
    fig, ax = fs.subplots(height_in=3.0, width_in=6.0)
    for param, _, shape, ls in STIFFNESS:
        values = subset[f"{param}_oracle_relative_error"].to_numpy()
        ax.plot(x, values, color=fs.INK, lw=0.9, ls=ls, zorder=2)
        for xi, value, ok in zip(x, values, passed):
            marker(ax, xi, value, shape, filled=bool(ok), zorder=3)
    ax.set_xticks(x, [_scenario_label(s) for s in subset["scenario"]])
    ax.set_yscale("log")
    ax.set_ylabel("Relative error vs Gym value")
    ax.set_xlabel("Telemetry noise level" if kind == "noise" else "Added telemetry latency")
    ax.margins(x=0.12)
    fs.legend(fig, [Line2D([], [], marker=shape, mfc=fs.FILL[True], label=label, **{**fs.MARKER, "ls": ls})
                    for _, label, shape, ls in STIFFNESS]
              + [marker_handle("s", "Hollow: failed an acceptance gate", filled=False)])
    perturbed = subset[subset["kind"] == kind]
    front, rear = perturbed["C_Sf_oracle_relative_error"], perturbed["C_Sr_oracle_relative_error"]
    if kind == "noise":
        assert (np.diff(subset["C_Sf_oracle_relative_error"]) > 0).all() and (np.diff(subset["C_Sr_oracle_relative_error"]) > 0).all()
        finding = (f"Cornering-stiffness error rises with every noise step, to {front.iloc[-1]:.0%} front "
                   f"and {rear.iloc[-1]:.0%} rear")
    else:
        assert (perturbed["first_failed_gate"] == "oracle_recovery").all()
        finding = (f"Every tested latency fails parameter recovery: front error {front.min():.0%} to {front.max():.0%}, "
                   f"rear {rear.min():.0%} to {rear.max():.0%}")
    caption = (f"{SIMULATOR}, perturbed excitation telemetry. {finding}. Relative error of the fitted front (circles, "
               "solid) and rear (squares, dashed) cornering stiffness against the Gym value, on a logarithmic axis. "
               "Filled markers passed every acceptance gate; hollow markers failed at least one. One seeded fit per "
               f"setting, so there are no error bars. Source: {source}.")
    return fs.save(fig, path, caption)[0]


def parameter_id_condition(results: pd.DataFrame, path: Path, source: str) -> Path:
    data = results.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(data))
    fig, ax = fs.subplots(height_in=3.4, width_in=5.6)
    ax.hlines(y, 1.0, data["jacobian_condition_number"], color=fs.INK, linewidth=0.5, zorder=1)
    marker(ax, data["jacobian_condition_number"], y, "o", zorder=3)
    ax.axvline(1.0, zorder=1, **fs.REFERENCE)
    ax.set_yticks(y, [_scenario_label(s) for s in data["scenario"]])
    ax.set_xlim(0.95, data["jacobian_condition_number"].max() * 1.08)
    ax.set_xlabel("Normalized Jacobian condition number")
    values = results["jacobian_condition_number"]
    caption = (f"{SIMULATOR}, perturbed excitation telemetry. The Jacobian condition number stays between "
               f"{np.floor(values.min() * 10) / 10:.1f} and {np.ceil(values.max() * 10) / 10:.1f} under every "
               "perturbation, far from the acceptance limit of 100. The dotted line marks the ideal value of 1. "
               f"n = {len(results)} settings, one seeded fit each, so there are no error bars. Source: {source}.")
    return fs.save(fig, path, caption)[0]


# --- Item 11 ROS-backed capture ------------------------------------------------------

def draw_item11(evidence_dir: Path = ITEM11, figure_dir: Path | None = None) -> list[Path]:
    fs.apply()
    figure_dir = figure_dir or evidence_dir / "figures"
    enriched = pd.read_csv(evidence_dir / "telemetry" / "enriched_bridge.csv")
    preflight = json.loads((evidence_dir / "metrics" / "enriched_preflight.json").read_text(encoding="utf-8"))
    paths = [item11_steering(enriched, preflight, figure_dir / "steering_command_vs_achieved.png")]
    paths += draw_parameter_fit(evidence_dir / "metrics" / "enriched_fit", figure_dir / "enriched_ros_fit.png",
                                figure_dir / "enriched_ros_residuals.png", SIMULATOR_ROS)
    return paths


def item11_steering(enriched: pd.DataFrame, preflight: dict, path: Path) -> Path:
    m = preflight["metrics"]
    fig, ax = fs.subplots(height_in=2.6)
    fs.line(ax, enriched["time_s"], enriched["steer_rad"], "reference", zorder=2)
    fs.line(ax, enriched["time_s"], enriched["command_steer_rad"], "command", zorder=3)
    fs.zero_line(ax)
    ax.set_xlabel("Simulator time [s]")
    ax.set_ylabel("Steering angle [rad]")
    fs.legend(fig, [fs.handle("command", "Commanded", marker=False), fs.handle("reference", "Achieved (native state)", marker=False)])
    caption = (f"{SIMULATOR_ROS}. Achieved steering follows the command within {m['command_achieved_rmse_rad']:.3f} rad "
               f"RMSE (maximum {m['command_achieved_max_abs_rad']:.3f} rad). Commanded steering is dash-dot and the "
               "achieved native steering state is solid; the dotted line is zero. "
               f"Enriched bridge bag, n = {len(enriched):,} samples. Best command shift "
               f"{int(m['best_command_lag_samples'])} samples ({m['best_command_lag_s']:.3f} s). Simulator steering "
               "controller, not a physical actuator. Sources: evidence/item11/telemetry/enriched_bridge.csv and "
               "evidence/item11/metrics/enriched_preflight.json.")
    return fs.save(fig, path, caption)[0]


GROUPS = {
    "integrator": None,  # experiments/plot_integrator_comparison.py
    "convergence": draw_integrator_convergence,
    "dynamic-replay": draw_dynamic_replay,
    "kinematic-replay": draw_kinematic_replay,
    "excitation": draw_sysid_excitation,
    "parameter-fit": lambda: draw_parameter_fit(RUNS / "dynamic_parameter_identification",
                                                FIGURES / "dynamic_parameter_fit.png",
                                                FIGURES / "dynamic_parameter_residuals.png"),
    "pure-pursuit": draw_pure_pursuit,
    "ekf": draw_ekf,
    "fmea": draw_fmea,
    "parameter-id-robustness": draw_parameter_id_robustness,
    "item11": draw_item11,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=sorted(GROUPS), help="figure groups to redraw (default: all)")
    args = parser.parse_args()
    for name in args.only or list(GROUPS):
        if name == "integrator":
            import plot_integrator_comparison
            plot_integrator_comparison.main()
            continue
        for path in GROUPS[name]():
            print(f"Wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
