#!/usr/bin/env python
"""Draw the RK4 vs Euler integrator sensitivity figures and their captions from the committed first-lap run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

import figure_style as fs

REPO_ROOT = Path(__file__).resolve().parents[1]

TELEMETRY_PATH = REPO_ROOT / "runs" / "first_lap" / "telemetry.csv"
METADATA_PATH = REPO_ROOT / "runs" / "first_lap" / "metadata.json"
CONFIG_PATH = REPO_ROOT / "examples" / "config_example_map.yaml"
WAYPOINTS_PATH = REPO_ROOT / "examples" / "example_waypoints.csv"
COMBINED_PATH = REPO_ROOT / "reports" / "figures" / "first_integrator_comparison.png"
TRAJECTORY_PATH = REPO_ROOT / "reports" / "figures" / "integrator_trajectory_overlay.png"
TRACKING_ERROR_PATH = REPO_ROOT / "reports" / "figures" / "integrator_tracking_error_vs_progress.png"
SUMMARY_METRICS_PATH = REPO_ROOT / "reports" / "figures" / "integrator_summary_metrics.png"


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {description}: {path}")


def load_metadata(path: Path) -> dict[str, Any]:
    ensure_exists(path, "metadata file")
    with path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)
    if not isinstance(metadata, dict):
        raise ValueError(f"Metadata did not load as a dictionary: {path}")
    return metadata


def load_telemetry(path: Path) -> pd.DataFrame:
    ensure_exists(path, "telemetry file")
    df = pd.read_csv(path)
    required = [
        "integrator",
        "time_s",
        "x_m",
        "y_m",
        "speed_mps",
        "cte_m",
        "abs_cte_m",
        "progress_m",
        "collision",
        "termination_reason",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            f"Telemetry missing required columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    for column in ["time_s", "x_m", "y_m", "speed_mps", "cte_m", "abs_cte_m", "progress_m", "collision"]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    df["integrator"] = df["integrator"].astype(str)
    return df


def load_map_config(path: Path) -> dict[str, Any]:
    ensure_exists(path, "map config")
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Map config did not load as a dictionary: {path}")
    return config


def config_value(config: dict[str, Any], candidates: list[str]) -> Any | None:
    lower_map = {str(key).lower(): value for key, value in config.items()}
    for key in candidates:
        if key.lower() in lower_map:
            return lower_map[key.lower()]
    return None


def normalize_delimiter(delimiter: Any | None) -> str | None:
    if delimiter is None:
        return None
    value = str(delimiter)
    if value.lower() in {"whitespace", "space", r"\s+", "regex_whitespace"}:
        return r"\s+"
    return value


def read_waypoint_csv(path: Path, delimiter_hint: Any | None) -> tuple[pd.DataFrame, bool]:
    delimiter = normalize_delimiter(delimiter_hint)
    f1tenth_style = False

    with path.open("r", encoding="utf-8") as file:
        first_data_line = ""
        for line in file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            first_data_line = stripped
            break

    if not first_data_line:
        raise ValueError(f"Waypoint file has no data rows after comments: {path}")

    if delimiter is None:
        delimiter = ";" if ";" in first_data_line else None
    if delimiter == ";":
        f1tenth_style = True

    read_kwargs: dict[str, Any] = {"comment": "#"}
    if delimiter == r"\s+":
        read_kwargs.update({"sep": delimiter, "engine": "python"})
    elif delimiter is not None:
        read_kwargs["sep"] = delimiter

    # F1TENTH waypoint examples are comment-headered and data-only; keep the
    # first numeric row as data instead of accidentally treating it as headers.
    if f1tenth_style:
        waypoint_df = pd.read_csv(path, header=None, **read_kwargs)
        waypoint_df.columns = list(range(waypoint_df.shape[1]))
        return waypoint_df, True

    waypoint_df = pd.read_csv(path, **read_kwargs)
    if waypoint_df.shape[1] >= 2:
        return waypoint_df, False

    waypoint_df = pd.read_csv(path, header=None, **read_kwargs)
    waypoint_df.columns = list(range(waypoint_df.shape[1]))
    return waypoint_df, False


def load_waypoints(path: Path, config: dict[str, Any]) -> tuple[pd.DataFrame, bool]:
    ensure_exists(path, "waypoint file")
    delimiter_hint = config_value(
        config,
        [
            "wpt_delim",
            "waypoint_delimiter",
            "waypoints_delimiter",
            "waypoint_sep",
            "waypoints_sep",
            "csv_delimiter",
            "delimiter",
            "sep",
        ],
    )
    waypoints, f1tenth_style = read_waypoint_csv(path, delimiter_hint)
    if waypoints.shape[1] < 2:
        raise ValueError(
            f"Waypoint file has fewer than 2 columns after parsing: {path}\n"
            f"Columns found: {list(waypoints.columns)}"
        )
    return waypoints, f1tenth_style


def infer_xy_columns(waypoints: pd.DataFrame, config: dict[str, Any], f1tenth_style: bool) -> tuple[Any, Any]:
    x_hint = config_value(config, ["wpt_xind", "waypoint_x_col", "x_col", "x_column", "waypoints_x_col", "waypoints_x"])
    y_hint = config_value(config, ["wpt_yind", "waypoint_y_col", "y_col", "y_column", "waypoints_y_col", "waypoints_y"])

    if x_hint is not None and y_hint is not None:
        x_column = int(x_hint) if f1tenth_style and str(x_hint).isdigit() else x_hint
        y_column = int(y_hint) if f1tenth_style and str(y_hint).isdigit() else y_hint
        if x_column in waypoints.columns and y_column in waypoints.columns:
            return x_column, y_column
        raise ValueError(
            "Waypoint x/y columns were specified in config but were not found in CSV.\n"
            f"x_hint={x_hint}, y_hint={y_hint}, available={list(waypoints.columns)}"
        )

    possible_x = ["x", "x_m", "pos_x", "waypoint_x", "x_pos"]
    possible_y = ["y", "y_m", "pos_y", "waypoint_y", "y_pos"]
    cols_lower = {str(column).lower(): column for column in waypoints.columns}

    for x_name in possible_x:
        for y_name in possible_y:
            if x_name in cols_lower and y_name in cols_lower:
                return cols_lower[x_name], cols_lower[y_name]

    numeric_cols = list(waypoints.select_dtypes(include=[np.number]).columns)
    if f1tenth_style and len(numeric_cols) >= 3:
        # Known F1TENTH format: s, x, y, psi, kappa, vx, ax.
        return numeric_cols[1], numeric_cols[2]

    raise ValueError(
        "Could not infer waypoint x/y columns from CSV or config.\n"
        f"Available columns: {list(waypoints.columns)}"
    )


def summarize_run(telemetry: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for integrator, group in telemetry.groupby("integrator"):
        group = group.sort_values("time_s").reset_index(drop=True)
        collision = bool(pd.to_numeric(group["collision"], errors="coerce").fillna(0).max() > 0)
        termination_series = group["termination_reason"].dropna()
        termination = str(termination_series.iloc[-1]) if not termination_series.empty else "unknown"

        rows.append(
            {
                "Integrator": str(integrator).upper(),
                "Termination": termination,
                "Final time [s]": float(group["time_s"].iloc[-1]),
                "Collision": collision,
                "RMS CTE [m]": float(np.sqrt(np.mean(group["cte_m"] ** 2))),
                "Max CTE [m]": float(group["abs_cte_m"].max()),
                "Mean speed [m/s]": float(group["speed_mps"].mean()),
            }
        )

    summary = pd.DataFrame(rows)
    order = ["RK4", "EULER"]
    if not summary.empty:
        summary["order"] = summary["Integrator"].map(lambda value: order.index(value) if value in order else 999)
        summary = summary.sort_values("order").drop(columns="order").reset_index(drop=True)
    return summary


def trajectory_group(telemetry: pd.DataFrame, integrator: str) -> pd.DataFrame:
    group = telemetry[telemetry["integrator"].str.lower() == integrator].sort_values("time_s")
    if group.empty:
        raise ValueError(f"No {integrator.upper()} rows found in telemetry.")
    return group


INTEGRATORS = (("rk4", "RK4"), ("euler", "Euler"))
# Summary column, axis label and caption name for the metric panels.
METRICS = (("Final time [s]", "Final time [s]", "final time"),
           ("RMS CTE [m]", "RMS cross-track error [m]", "RMS cross-track error"),
           ("Max CTE [m]", "Peak cross-track error [m]", "peak cross-track error"),
           ("Mean speed [m/s]", "Mean speed [m/s]", "mean speed"))
LINE_STYLES = " RK4 is solid and Euler dashed."
CTE_STYLES = LINE_STYLES + " The RK4 second pass is dash-dot."
SOURCES = "Sources: runs/first_lap/telemetry.csv and examples/example_waypoints.csv."


def _passes(group: pd.DataFrame) -> list[pd.DataFrame]:
    """Split a run where progress wraps back to the start of the path (the Gym stops after two passes)."""
    wraps = np.flatnonzero(np.diff(group["progress_m"].to_numpy()) < -0.5 * group["progress_m"].max()) + 1
    return [part for part in np.split(group, wraps) if not part.empty]


def _collided(group: pd.DataFrame) -> bool:
    return bool(pd.to_numeric(group["collision"], errors="coerce").fillna(0).max() > 0)


def _end_marker(ax, x, y, collided: bool) -> None:
    """Run end: filled for the Gym's normal stop, hollow for a collision."""
    ax.plot(x, y, marker="s" if collided else "o", mfc=fs.FILL[not collided], zorder=4, **fs.MARKER)


def _draw_trajectory(ax, waypoints: pd.DataFrame, x_col: Any, y_col: Any, group: pd.DataFrame, entity: str) -> None:
    fs.line(ax, waypoints[x_col], waypoints[y_col], "path", zorder=1)
    fs.line(ax, group["x_m"], group["y_m"], entity, zorder=2)
    end = group.iloc[-1]
    _end_marker(ax, end["x_m"], end["y_m"], _collided(group))
    ax.set_xlabel("$x$ [m]")
    ax.set_ylabel("$y$ [m]")
    xs = pd.concat([waypoints[x_col], group["x_m"]])
    ys = pd.concat([waypoints[y_col], group["y_m"]])
    pad = 0.05 * max(xs.max() - xs.min(), ys.max() - ys.min())
    ax.set(xlim=(xs.min() - pad, xs.max() + pad), ylim=(ys.min() - pad, ys.max() + pad))
    ax.set_aspect("equal", adjustable="box")


def _draw_tracking_error(ax, group: pd.DataFrame, entity: str) -> None:
    for number, part in enumerate(_passes(group), start=1):
        fs.line(ax, part["progress_m"], part["abs_cte_m"], entity if number == 1 else "second_pass")
    if _collided(group):
        end = group.iloc[-1]
        _end_marker(ax, end["progress_m"], end["abs_cte_m"], True)
    ax.set_xlabel("Progress along path [m]")
    ax.set_ylabel("$|$Cross-track error$|$ [m]")


def _shared_limits(axes, rk4: pd.DataFrame, euler: pd.DataFrame) -> None:
    top = max(rk4["abs_cte_m"].max(), euler["abs_cte_m"].max()) * 1.08
    right = max(rk4["progress_m"].max(), euler["progress_m"].max()) * 1.02
    for ax in axes:
        ax.set(xlim=(0, right), ylim=(0, top))


def _handles(rk4: pd.DataFrame, euler: pd.DataFrame, cte: bool, path: bool) -> list:
    handles = [fs.handle("rk4", "RK4", marker=False), fs.handle("euler", "Euler", marker=False)]
    if path:
        handles.append(fs.handle("path", "Reference path"))
    if cte and len(_passes(rk4)) > 1:
        handles.append(fs.handle("second_pass", "RK4, second pass"))
    handles.append(Line2D([], [], marker="o", mfc=fs.FILL[True], label="Run end", **fs.MARKER))
    handles.append(Line2D([], [], marker="s", mfc=fs.FILL[False], label="Collision", **fs.MARKER))
    return handles


def facts(telemetry: pd.DataFrame) -> dict[str, Any]:
    """Values the captions state, read from the telemetry and checked before drawing."""
    rk4, euler = trajectory_group(telemetry, "rk4"), trajectory_group(telemetry, "euler")
    summary = summarize_run(telemetry).set_index("Integrator")
    assert not _collided(rk4) and _collided(euler), "caption assumes RK4 completes and Euler collides"
    for column in ("RMS CTE [m]", "Max CTE [m]"):
        assert summary.loc["RK4", column] < summary.loc["EULER", column]
    rk4_end, euler_end = rk4.iloc[-1], euler.iloc[-1]
    return {"rk4": rk4, "euler": euler, "summary": summary,
            "passes": len(_passes(rk4)), "rk4_stop": str(rk4_end["termination_reason"]).replace("_", " "),
            "rk4_time": float(rk4_end["time_s"]), "euler_time": float(euler_end["time_s"]),
            "euler_progress": float(euler_end["progress_m"])}


def _finding(f: dict[str, Any]) -> str:
    return (f"Euler collides after {f['euler_time']:.2f} s, {f['euler_progress']:.1f} m along the path; RK4 runs "
            f"to the Gym's {f['rk4_stop']} stop at {f['rk4_time']:.1f} s.")


def _summary_values(f: dict[str, Any]) -> str:
    s = f["summary"]
    parts = []
    for key, label in (("RK4", "RK4"), ("EULER", "Euler")):
        parts.append(f"{label}: final time {s.loc[key, 'Final time [s]']:.3f} s, RMS cross-track error "
                     f"{s.loc[key, 'RMS CTE [m]']:.3f} m, peak {s.loc[key, 'Max CTE [m]']:.3f} m, mean speed "
                     f"{s.loc[key, 'Mean speed [m/s]']:.3f} m/s")
    return "; ".join(parts) + "."


def _conditions(f: dict[str, Any], styles: str = "") -> str:
    return ("Simulator output, F1TENTH Gym. One closed-loop run per integrator on the example map with the same "
            f"waypoints and pure-pursuit controller; only the integrator differs.{styles} "
            f"The Gym stops a completed run after {f['passes']} passes of the path, so RK4 progress wraps once. "
            "This is an integrator sensitivity check, not a derived bicycle-model "
            "comparison; one deterministic run per integrator, so there are no error bars.")


def caption_combined(f: dict[str, Any]) -> str:
    return ("Panels (a) and (b): RK4 and Euler trajectories on the example map, with the reference path dotted. "
            "Panels (c) and (d): absolute cross-track error along the path for RK4 and Euler, on the same axes. "
            "A filled circle marks the end of a run at the Gym's normal stop; a hollow square marks a collision. "
            f"{_finding(f)} {_summary_values(f)} {_conditions(f, CTE_STYLES)} {SOURCES}")


def caption_trajectory(f: dict[str, Any]) -> str:
    return ("Panel (a): RK4 trajectory; panel (b): Euler trajectory, both on the example map with the reference "
            "path dotted and the same axes. A filled circle marks the end of the run at the Gym's normal stop; a "
            f"hollow square marks a collision. {_finding(f)} {_conditions(f, LINE_STYLES)} {SOURCES}")


def caption_tracking(f: dict[str, Any]) -> str:
    return ("Absolute cross-track error along the path for RK4 (a) and Euler (b), on the same axes. The hollow "
            f"square marks the Euler collision. {_finding(f)} {_conditions(f, CTE_STYLES)} {SOURCES}")


def caption_summary(f: dict[str, Any]) -> str:
    return ("Per-run summary metrics: (a) final time, (b) RMS cross-track error, (c) peak cross-track error and "
            "(d) mean speed, for RK4 (circles) and Euler (squares). A filled marker is a run that ended at the "
            "Gym's normal stop; a hollow marker is a run that ended in a collision. Euler ends earlier with higher "
            f"RMS and peak tracking error. {_summary_values(f)} {_conditions(f)} {SOURCES}")


def figure_combined(waypoints: pd.DataFrame, x_col: Any, y_col: Any, f: dict[str, Any]):
    fig, axes = fs.subplots(2, 2, height_in=5.8, gridspec_kw={"height_ratios": [1.5, 1]})
    for ax, (key, _) in zip(axes[0], INTEGRATORS):
        _draw_trajectory(ax, waypoints, x_col, y_col, f[key], key)
    for ax, (key, _) in zip(axes[1], INTEGRATORS):
        _draw_tracking_error(ax, f[key], key)
    _shared_limits(axes[1], f["rk4"], f["euler"])
    fs.letters(axes.flat)
    fs.legend(fig, _handles(f["rk4"], f["euler"], cte=True, path=True))
    return fig


def figure_trajectory(waypoints: pd.DataFrame, x_col: Any, y_col: Any, f: dict[str, Any]):
    fig, axes = fs.subplots(1, 2, height_in=3.4)
    for ax, (key, _) in zip(axes, INTEGRATORS):
        _draw_trajectory(ax, waypoints, x_col, y_col, f[key], key)
    fs.letters(axes)
    fs.legend(fig, _handles(f["rk4"], f["euler"], cte=False, path=True))
    return fig


def figure_tracking(f: dict[str, Any]):
    fig, axes = fs.subplots(2, 1, height_in=3.8, sharex=True)
    for ax, (key, _) in zip(axes, INTEGRATORS):
        _draw_tracking_error(ax, f[key], key)
    _shared_limits(axes, f["rk4"], f["euler"])
    axes[0].set_xlabel("")
    fs.letters(axes)
    handles = _handles(f["rk4"], f["euler"], cte=True, path=False)
    fs.legend(fig, [h for h in handles if h.get_label() != "Run end"])
    return fig


def figure_summary(f: dict[str, Any]):
    s = f["summary"]
    fig, axes = fs.subplots(1, len(METRICS), height_in=2.3)
    for ax, (column, label, _) in zip(axes, METRICS):
        for x, (key, name) in enumerate(INTEGRATORS):
            row = s.loc[name.upper()]
            ax.plot(x, row[column], marker=fs.STYLE[key]["marker"], mfc=fs.FILL[not bool(row["Collision"])],
                    zorder=3, **fs.MARKER)
        top = max(s[column])
        ax.set(xlim=(-0.6, 1.6), ylim=(0, top * 1.25), ylabel=label)
        ax.set_xticks([0, 1], [name for _, name in INTEGRATORS])
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    fs.letters(axes)
    fs.legend(fig, [Line2D([], [], marker="o", mfc=fs.FILL[True], label="RK4", **fs.MARKER),
                    Line2D([], [], marker="s", mfc=fs.FILL[True], label="Euler", **fs.MARKER),
                    Line2D([], [], marker="s", mfc=fs.FILL[False], label="Hollow: collision", **fs.MARKER)])
    return fig


def plot_integrator_comparison(
    telemetry: pd.DataFrame,
    waypoints: pd.DataFrame,
    config: dict[str, Any],
    f1tenth_style_waypoints: bool,
) -> None:
    x_col, y_col = infer_xy_columns(waypoints, config, f1tenth_style_waypoints)
    print(f"Using waypoint columns: x={x_col}, y={y_col}")
    f = facts(telemetry)
    fs.apply()
    fs.save(figure_combined(waypoints, x_col, y_col, f), COMBINED_PATH, caption_combined(f))
    fs.save(figure_trajectory(waypoints, x_col, y_col, f), TRAJECTORY_PATH, caption_trajectory(f))
    fs.save(figure_tracking(f), TRACKING_ERROR_PATH, caption_tracking(f))
    fs.save(figure_summary(f), SUMMARY_METRICS_PATH, caption_summary(f))


def load_inputs():
    """Telemetry, waypoints and their x/y columns from the committed files."""
    telemetry = load_telemetry(TELEMETRY_PATH)
    config = load_map_config(CONFIG_PATH)
    waypoints, f1tenth_style_waypoints = load_waypoints(WAYPOINTS_PATH, config)
    x_col, y_col = infer_xy_columns(waypoints, config, f1tenth_style_waypoints)
    return telemetry, waypoints, x_col, y_col


def main() -> None:
    metadata = load_metadata(METADATA_PATH)
    telemetry = load_telemetry(TELEMETRY_PATH)
    config = load_map_config(CONFIG_PATH)
    waypoints, f1tenth_style_waypoints = load_waypoints(WAYPOINTS_PATH, config)
    print(f"Loaded metadata for control={metadata.get('control', 'unknown')}")

    plot_integrator_comparison(
        telemetry=telemetry,
        waypoints=waypoints,
        config=config,
        f1tenth_style_waypoints=f1tenth_style_waypoints,
    )
    print(f"Wrote combined figure to {COMBINED_PATH}")
    print(f"Wrote trajectory figure to {TRAJECTORY_PATH}")
    print(f"Wrote tracking error figure to {TRACKING_ERROR_PATH}")
    print(f"Wrote summary metrics figure to {SUMMARY_METRICS_PATH}")


if __name__ == "__main__":
    main()
