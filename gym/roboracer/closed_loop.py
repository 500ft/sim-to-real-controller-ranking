"""Closed-loop F1TENTH Gym runner shared by controller experiments."""

from __future__ import annotations

import math
import time
from argparse import Namespace
from typing import Protocol

import gym
import numpy as np
import pandas as pd

from f110_gym.envs.base_classes import Integrator
from roboracer.numerics import rmse, wrap_angle
from roboracer.track import nearest_waypoint_metrics, scalar


WHEELBASE_M = 0.15875 + 0.17145


class Controller(Protocol):
    name: str

    def reset(self) -> None:
        ...

    def command(self, state: dict[str, float], path_info: dict[str, float]) -> tuple[float, float]:
        ...


def waypoint_xy(waypoints: np.ndarray, conf: Namespace) -> np.ndarray:
    return waypoints[:, [conf.wpt_xind, conf.wpt_yind]]


def project_to_path(x: float, y: float, waypoints: np.ndarray, conf: Namespace) -> dict[str, float]:
    point = np.array([x, y], dtype=float)
    xy = waypoint_xy(waypoints, conf)
    progress = waypoints[:, 0]

    starts = xy[:-1]
    ends = xy[1:]
    segments = ends - starts
    seg_len_sq = np.sum(segments * segments, axis=1)
    valid = seg_len_sq > 0.0
    if not np.any(valid):
        raise ValueError("Waypoint path has no valid segments.")

    t = np.zeros(len(segments))
    t[valid] = np.clip(np.sum((point - starts[valid]) * segments[valid], axis=1) / seg_len_sq[valid], 0.0, 1.0)
    projections = starts + (t * segments.T).T
    deltas = point - projections
    dists = np.linalg.norm(deltas, axis=1)
    dists[~valid] = np.inf

    idx = int(np.argmin(dists))
    seg = segments[idx]
    seg_len = float(np.sqrt(seg_len_sq[idx]))
    heading = float(math.atan2(seg[1], seg[0]))
    cross = float(seg[0] * (point[1] - starts[idx, 1]) - seg[1] * (point[0] - starts[idx, 0]))
    cte = cross / seg_len
    progress_m = float(progress[idx] + float(t[idx]) * (progress[idx + 1] - progress[idx]))

    prev_idx = max(0, idx - 1)
    next_idx = min(len(segments) - 1, idx + 1)
    prev_heading = math.atan2(segments[prev_idx, 1], segments[prev_idx, 0])
    next_heading = math.atan2(segments[next_idx, 1], segments[next_idx, 0])
    ds = max(float(progress[min(len(progress) - 1, next_idx + 1)] - progress[prev_idx]), 1e-6)
    curvature = float(wrap_angle(next_heading - prev_heading) / ds)

    return {
        "nearest_waypoint_index": float(idx),
        "progress_m": progress_m,
        "cte_m": float(cte),
        "abs_cte_m": abs(float(cte)),
        "path_heading_rad": heading,
        "path_curvature_1pm": curvature,
        "reference_x_m": float(projections[idx, 0]),
        "reference_y_m": float(projections[idx, 1]),
    }


def initial_pose(conf: Namespace, waypoints: np.ndarray, offset_m: float = 0.0) -> np.ndarray:
    pose = np.array([conf.sx, conf.sy, conf.stheta], dtype=float)
    if abs(offset_m) <= 0.0:
        return pose
    info = project_to_path(float(pose[0]), float(pose[1]), waypoints, conf)
    normal = np.array([-math.sin(info["path_heading_rad"]), math.cos(info["path_heading_rad"])], dtype=float)
    pose[:2] += offset_m * normal
    return pose


def normalize_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in frame.columns:
        if column not in {"run_id", "controller", "termination_reason", "classification"}:
            frame[column] = pd.to_numeric(frame[column], errors="ignore")
    return frame


def summarize_run(frame: pd.DataFrame) -> dict[str, object]:
    command_steer = frame["command_steer_rad"].to_numpy(dtype=float)
    steer = frame["steer_rad"].to_numpy(dtype=float)
    steering_effort = float(np.sum(np.abs(np.diff(command_steer)))) if len(command_steer) > 1 else 0.0

    lat_accel = frame["accel_y_mps2"].to_numpy(dtype=float)
    long_accel = frame["accel_x_mps2"].to_numpy(dtype=float)
    time_s = frame["time_s"].to_numpy(dtype=float)
    if lat_accel.size > 1:
        dt = np.diff(time_s)
        dt[dt <= 0.0] = np.nan
        lat_jerk = np.diff(lat_accel) / dt
        lat_jerk = lat_jerk[np.isfinite(lat_jerk)]
    else:
        lat_jerk = np.empty(0, dtype=float)
    rms_lat_jerk = rmse(lat_jerk) if lat_jerk.size else 0.0
    max_abs_lat_jerk = float(np.max(np.abs(lat_jerk))) if lat_jerk.size else 0.0

    return {
        "run_id": str(frame["run_id"].iloc[0]),
        "controller": str(frame["controller"].iloc[0]),
        "integration_dt_s": float(frame["integration_dt_s"].iloc[0]),
        "control_rate_hz": float(frame["control_rate_hz"].iloc[0]),
        "control_period_s": float(frame["control_period_s"].iloc[0]),
        "completed_lap": bool(frame["completed_lap"].max()),
        "collision": bool(frame["collision"].max()),
        "final_time_s": float(frame["time_s"].iloc[-1]),
        "lap_time_s": float(frame["lap_time_s"].iloc[-1]),
        "final_progress_m": float(frame["progress_m"].max()),
        "mean_speed_mps": float(frame["speed_mps"].mean()),
        "max_speed_mps": float(frame["speed_mps"].max()),
        "rms_cte_m": rmse(frame["cte_m"]),
        "max_abs_cte_m": float(frame["abs_cte_m"].max()),
        "mean_abs_steer_rad": float(np.mean(np.abs(steer))),
        "max_abs_steer_rad": float(np.max(np.abs(steer))),
        "mean_abs_command_steer_rad": float(np.mean(np.abs(command_steer))),
        "max_abs_command_steer_rad": float(np.max(np.abs(command_steer))),
        "steering_effort_rad": steering_effort,
        "mean_abs_lat_accel_mps2": float(np.mean(np.abs(lat_accel))),
        "max_abs_lat_accel_mps2": float(np.max(np.abs(lat_accel))),
        "max_abs_long_accel_mps2": float(np.max(np.abs(long_accel))),
        "rms_lat_jerk_mps3": rms_lat_jerk,
        "max_abs_lat_jerk_mps3": max_abs_lat_jerk,
        "termination_reason": str(frame["termination_reason"].iloc[-1]),
    }


def run_closed_loop(
    controller: Controller,
    conf: Namespace,
    waypoints: np.ndarray,
    *,
    integration_dt: float = 0.002,
    control_rate_hz: float = 100.0,
    integrator=Integrator.RK4,
    max_sim_time_s: float = 45.0,
    init_lateral_offset_m: float = 0.0,
    control_delay_steps: int = 0,
    seed: int = 12345,
    vehicle_params: dict[str, float] | None = None,
    run_id: str | None = None,
    timing_mode: str = "legacy",
    command_delay_s: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if control_rate_hz <= 0.0:
        raise ValueError("control_rate_hz must be positive.")
    hold_steps = max(1, int(round(1.0 / (control_rate_hz * integration_dt))))
    actual_control_period = hold_steps * integration_dt
    max_steps = math.ceil(max_sim_time_s / integration_dt)
    run_id = run_id or controller.name
    if timing_mode not in {"legacy", "ideal", "deadline_aware"}:
        raise ValueError("Unknown timing mode")
    if command_delay_s < 0.0:
        raise ValueError("Negative command delay")

    env_kwargs = dict(
        map=conf.map_path,
        map_ext=conf.map_ext,
        num_agents=1,
        timestep=integration_dt,
        integrator=integrator,
        seed=seed,
    )
    if vehicle_params is not None:
        env_kwargs["params"] = dict(vehicle_params)
    env = gym.make(
        "f110_gym:f110-v0",
        **env_kwargs,
    )

    controller.reset()
    obs, _, _, info = env.reset(np.array([initial_pose(conf, waypoints, init_lateral_offset_m)]))
    previous_speed = scalar(obs, "linear_vels_x")
    command_steer = 0.0
    command_speed = 0.0
    command_queue: list[tuple[float, float, float]] = []
    pending: tuple[int, float, float, float] | None = None
    generated_time_s = float("nan")
    applied_time_s = float("nan")
    control_compute_s = float("nan")
    mpc_solve_s = float("nan")
    mpc_success: bool | None = None
    termination_reason = "max_steps"
    rows: list[dict[str, object]] = []

    try:
        for step in range(max_steps):
            x = scalar(obs, "poses_x")
            y = scalar(obs, "poses_y")
            theta = scalar(obs, "poses_theta")
            path_info = project_to_path(x, y, waypoints, conf)
            path_info["heading_error_rad"] = float(wrap_angle(theta - path_info["path_heading_rad"]))
            state = {
                "x_m": x,
                "y_m": y,
                "theta_rad": theta,
                "speed_mps": scalar(obs, "linear_vels_x"),
                "steer_rad": float(env.sim.agents[0].state[2]),
                "yaw_rate_radps": scalar(obs, "ang_vels_z"),
                "slip_angle_rad": float(env.sim.agents[0].state[6]),
                "time_s": step * integration_dt,
            }

            if step % hold_steps == 0:
                if timing_mode != "legacy" and pending is not None and step >= pending[0]:
                    _, command_steer, command_speed, applied_time_s = pending
                    pending = None
                    notify = getattr(controller, "on_applied", None)
                    if callable(notify):
                        notify((command_steer, command_speed))
                if timing_mode == "legacy" or pending is None:
                    call_start = time.perf_counter()
                    new_command = controller.command(state, path_info)
                    control_compute_s = time.perf_counter() - call_start
                    generated_time_s = step * integration_dt
                    solve_times = getattr(controller, "solve_times_s", [])
                    success_flags = getattr(controller, "success_flags", [])
                    mpc_solve_s = float(solve_times[-1]) if solve_times else float("nan")
                    mpc_success = bool(success_flags[-1]) if success_flags else None
                    if timing_mode == "legacy":
                        command_queue.append((float(new_command[0]), float(new_command[1]), generated_time_s))
                        if len(command_queue) > control_delay_steps:
                            command_steer, command_speed, applied_time_s = command_queue.pop(0)
                    else:
                        extra = float(getattr(controller, "last_diagnostics", {}).get("injected_compute_delay_s", 0.0))
                        delay = command_delay_s + (control_compute_s + extra if timing_mode == "deadline_aware" else 0.0)
                        ticks = max(1 if timing_mode == "deadline_aware" else 0,
                                    int(math.ceil(delay / actual_control_period - 1e-12)))
                        if ticks == 0:
                            command_steer, command_speed, applied_time_s = (
                                float(new_command[0]), float(new_command[1]), generated_time_s)
                            notify = getattr(controller, "on_applied", None)
                            if callable(notify):
                                notify((command_steer, command_speed))
                        else:
                            pending = (step + ticks * hold_steps, float(new_command[0]),
                                       float(new_command[1]), generated_time_s)
                else:
                    control_compute_s = float("nan")

            obs, step_reward, done, info = env.step(np.array([[command_steer, command_speed]], dtype=float))
            step_dt = float(step_reward)
            speed = scalar(obs, "linear_vels_x")
            yaw_rate = scalar(obs, "ang_vels_z")
            accel_x = (speed - previous_speed) / step_dt
            accel_y = speed * yaw_rate
            previous_speed = speed

            x = scalar(obs, "poses_x")
            y = scalar(obs, "poses_y")
            theta = scalar(obs, "poses_theta")
            nearest_idx, progress_m, cte_m, abs_cte_m = nearest_waypoint_metrics(x, y, waypoints, conf)
            reference = project_to_path(x, y, waypoints, conf)
            collision = bool(scalar(obs, "collisions"))
            completed_lap = bool(np.asarray(info.get("checkpoint_done", [False]))[0])

            if completed_lap:
                termination_reason = "completed_lap"
            elif collision:
                termination_reason = "collision"
            elif step == max_steps - 1:
                termination_reason = "max_steps"
            else:
                termination_reason = ""

            rows.append(
                {
                    "run_id": run_id,
                    "controller": controller.name,
                    "integration_dt_s": f"{integration_dt:.6f}",
                    "control_rate_hz": f"{control_rate_hz:.3f}",
                    "control_period_s": f"{actual_control_period:.6f}",
                    "hold_steps": hold_steps,
                    "control_delay_steps": control_delay_steps,
                    "timing_mode": timing_mode,
                    "command_delay_s": command_delay_s,
                    "seed": seed,
                    "init_lateral_offset_m": f"{init_lateral_offset_m:.6f}",
                    "step": step + 1,
                    "time_s": f"{(step + 1) * step_dt:.6f}",
                    "x_m": f"{x:.9f}",
                    "y_m": f"{y:.9f}",
                    "theta_rad": f"{theta:.9f}",
                    "speed_mps": f"{speed:.9f}",
                    "steer_rad": f"{float(env.sim.agents[0].state[2]):.9f}",
                    "command_speed_mps": f"{command_speed:.9f}",
                    "command_steer_rad": f"{command_steer:.9f}",
                    "command_generated_at_s": generated_time_s,
                    "command_applied_at_s": applied_time_s,
                    "command_age_s": (step * integration_dt - applied_time_s) if math.isfinite(applied_time_s) else float("nan"),
                    "control_compute_s": control_compute_s if step % hold_steps == 0 else float("nan"),
                    "mpc_solve_s": mpc_solve_s if step % hold_steps == 0 else float("nan"),
                    "mpc_success": mpc_success if step % hold_steps == 0 else None,
                    "yaw_rate_radps": f"{yaw_rate:.9f}",
                    "slip_angle_rad": f"{float(env.sim.agents[0].state[6]):.9f}",
                    "accel_x_mps2": f"{accel_x:.9f}",
                    "accel_y_mps2": f"{accel_y:.9f}",
                    "nearest_waypoint_index": nearest_idx,
                    "progress_m": f"{progress_m:.9f}",
                    "cte_m": f"{cte_m:.9f}",
                    "abs_cte_m": f"{abs_cte_m:.9f}",
                    "reference_x_m": f"{reference['reference_x_m']:.9f}",
                    "reference_y_m": f"{reference['reference_y_m']:.9f}",
                    "lap_time_s": f"{float(obs['lap_times'][0]):.6f}",
                    "lap_count": f"{float(obs['lap_counts'][0]):.0f}",
                    "collision": int(collision),
                    "completed_lap": int(completed_lap),
                    "termination_reason": termination_reason,
                }
            )
            if timing_mode != "legacy":
                rows[-1].update(getattr(controller, "last_diagnostics", {}))

            if done or termination_reason in {"completed_lap", "collision"}:
                break
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    if not rows:
        raise RuntimeError(f"Controller {controller.name} produced no rows.")
    if not rows[-1]["termination_reason"]:
        rows[-1]["termination_reason"] = termination_reason
    final_reason = rows[-1]["termination_reason"]
    for row in rows:
        row["termination_reason"] = final_reason

    frame = normalize_rows(rows)
    return frame, summarize_run(frame)


def race_and_report(
    controller: Controller,
    conf: Namespace,
    waypoints: np.ndarray,
    *,
    return_trace: bool = False,
    **kwargs: object,
) -> dict[str, object] | tuple[dict[str, object], pd.DataFrame]:
    """Race a controller closed-loop and return its summary metrics in one call.

    Convenience wrapper over :func:`run_closed_loop` for callers that only need
    the per-race metrics (lap time, RMS/max CTE, steering effort, lateral
    accel/jerk, ...). Accepts the same keyword arguments as ``run_closed_loop``.
    Set ``return_trace=True`` to also get the per-step telemetry frame.
    """
    trace, summary = run_closed_loop(controller, conf, waypoints, **kwargs)
    if return_trace:
        return summary, trace
    return summary
