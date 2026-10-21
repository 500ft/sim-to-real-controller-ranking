"""Validate and resample an ordered, closed racing line against its raster map."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml
from PIL import Image
from scipy.ndimage import distance_transform_edt


def resample_closed_line(xy: np.ndarray, spacing_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return equally spaced positions, tangent headings and signed curvature."""
    if spacing_m <= 0 or len(xy) < 4 or not np.allclose(xy[0], xy[-1], atol=1e-8):
        raise ValueError("An explicitly closed line and positive spacing are required")
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    if np.any(lengths <= 1e-8):
        raise ValueError("Only the explicit closing vertex may duplicate the first vertex")
    s = np.r_[0.0, np.cumsum(lengths)]
    count = max(4, int(round(s[-1] / spacing_m)))
    target = np.arange(count) * s[-1] / count
    points = np.column_stack([np.interp(target, s, xy[:, axis]) for axis in (0, 1)])
    delta = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
    heading = np.unwrap(np.arctan2(delta[:, 1], delta[:, 0]))
    ds = s[-1] / count
    curvature = np.arctan2(np.sin(np.roll(heading, -1) - np.roll(heading, 1)),
                           np.cos(np.roll(heading, -1) - np.roll(heading, 1))) / (2 * ds)
    return points, heading, curvature


def speed_profile(curvature: np.ndarray, spacing_m: float, lateral_mps2: float,
                  accel_mps2: float, brake_mps2: float, cap_mps: float) -> np.ndarray:
    """Closed-loop lateral, acceleration and braking bound, iterated to convergence."""
    speed = np.minimum(cap_mps, np.sqrt(lateral_mps2 / np.maximum(np.abs(curvature), 1e-9)))
    for _ in range(len(speed)):
        old = speed.copy()
        for i in range(len(speed)):
            j = (i + 1) % len(speed)
            speed[j] = min(speed[j], math.sqrt(speed[i] ** 2 + 2 * accel_mps2 * spacing_m))
        for i in range(len(speed) - 1, -1, -1):
            j = (i + 1) % len(speed)
            speed[i] = min(speed[i], math.sqrt(speed[j] ** 2 + 2 * brake_mps2 * spacing_m))
        if np.max(np.abs(speed - old)) < 1e-10:
            break
    return speed


def _intersection_count(xy: np.ndarray) -> int:
    """Count crossings between nonadjacent straight segments."""
    starts, ends = xy[:-1], xy[1:]
    n = len(starts)
    total = 0
    for i in range(n):
        a, b = starts[i], ends[i]
        c, d = starts[i + 2:], ends[i + 2:]
        if i == 0:
            c, d = c[:-1], d[:-1]
        if len(c) == 0:
            continue
        ab = b - a
        cd = d - c
        cross1 = ab[0] * (c[:, 1] - a[1]) - ab[1] * (c[:, 0] - a[0])
        cross2 = ab[0] * (d[:, 1] - a[1]) - ab[1] * (d[:, 0] - a[0])
        cross3 = cd[:, 0] * (a[1] - c[:, 1]) - cd[:, 1] * (a[0] - c[:, 0])
        cross4 = cd[:, 0] * (b[1] - c[:, 1]) - cd[:, 1] * (b[0] - c[:, 0])
        total += int(np.count_nonzero((cross1 * cross2 < 0) & (cross3 * cross4 < 0)))
    return total


def map_clearance(points: np.ndarray, heading: np.ndarray, map_yaml: Path,
                  vehicle_length_m: float, vehicle_width_m: float, margin_m: float) -> float:
    """Minimum obstacle distance for center and sampled expanded vehicle perimeter."""
    meta = yaml.safe_load(map_yaml.read_text())
    image = map_yaml.parent / meta["image"]
    raster = np.asarray(Image.open(image).convert("L").transpose(Image.FLIP_TOP_BOTTOM)) > 128
    resolution = float(meta["resolution"])
    clearance = distance_transform_edt(raster) * resolution
    origin = np.asarray(meta["origin"], dtype=float)
    c, s = math.cos(origin[2]), math.sin(origin[2])
    half_l = vehicle_length_m / 2 + margin_m
    half_w = vehicle_width_m / 2 + margin_m
    edge_step = resolution / 2
    along = np.linspace(-half_l, half_l, max(3, math.ceil(2 * half_l / edge_step) + 1))
    across = np.linspace(-half_w, half_w, max(3, math.ceil(2 * half_w / edge_step) + 1))
    offsets = [(0.0, 0.0)]
    offsets += [(u, v) for u in along for v in (-half_w, half_w)]
    offsets += [(u, v) for u in (-half_l, half_l) for v in across]
    min_clearance = float("inf")
    for (x, y), theta in zip(points, heading):
        ct, st = math.cos(theta), math.sin(theta)
        for u, v in offsets:
            wx, wy = x + u * ct - v * st, y + u * st + v * ct
            dx, dy = wx - origin[0], wy - origin[1]
            col = math.floor((dx * c + dy * s) / resolution)
            row = math.floor((-dx * s + dy * c) / resolution)
            if row < 0 or col < 0 or row >= raster.shape[0] or col >= raster.shape[1]:
                return 0.0
            min_clearance = min(min_clearance, float(clearance[row, col]))
    return min_clearance


def qualify_line(waypoints: np.ndarray, map_yaml: Path, rules: dict,
                 speed_tolerance: float = 1e-9) -> dict:
    xy = np.asarray(waypoints[:, 1:3], dtype=float)
    closure = float(np.linalg.norm(xy[0] - xy[-1]))
    if closure > rules["max_closure_gap_m"]:
        return {"eligible": False, "reason": "open line", "closure_gap_m": closure}
    if closure > 1e-8:
        xy = np.vstack([xy, xy[0]])
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    s = waypoints[:, 0]
    if np.any(np.diff(s) <= 0) or np.any(lengths <= 1e-8):
        return {"eligible": False, "reason": "unordered or duplicate interior vertices"}
    intersections = _intersection_count(xy)
    points, heading, curvature = resample_closed_line(xy, rules["resample_spacing_m"])
    spacing = float(np.sum(lengths) / len(points))
    tangent_jump = float(abs(np.arctan2(np.sin(heading[0] - heading[-1]),
                                           np.cos(heading[0] - heading[-1]))))
    speed = speed_profile(curvature, spacing, rules["lateral_accel_limit_mps2"],
                          rules["longitudinal_accel_limit_mps2"], rules["brake_limit_mps2"],
                          rules["speed_cap_mps"])
    clearance = map_clearance(points, heading, map_yaml, rules["vehicle_length_m"],
                              rules["vehicle_width_m"], rules["extra_clearance_m"])
    geometry_eligible = (intersections == 0 and tangent_jump <= rules["max_tangent_jump_rad"]
                and np.max(np.abs(curvature)) <= rules["max_curvature_1pm"] and clearance > 0)
    source_speed = waypoints[:, 5]
    source_curvature = waypoints[:, 4]
    source_lateral = float(np.max(source_speed ** 2 * np.abs(source_curvature)))
    source_acceleration = np.diff(source_speed ** 2) / (2 * np.diff(s))
    source_forward = float(np.max(source_acceleration))
    source_braking = float(-np.min(source_acceleration))
    # Text export and floating-point squaring can exceed an exact boundary by
    # a few ulps. This tolerance is numerical only; it cannot admit a physical
    # exceedance at the precision of the source waypoints.
    if speed_tolerance < 0:
        raise ValueError("Numerical speed tolerance must be nonnegative")
    source_speed_eligible = (source_lateral <= rules["lateral_accel_limit_mps2"] + speed_tolerance
                             and source_forward <= rules["longitudinal_accel_limit_mps2"] + speed_tolerance
                             and source_braking <= rules["brake_limit_mps2"] + speed_tolerance
                             and float(np.max(source_speed)) <= rules["speed_cap_mps"] + speed_tolerance)
    return {"eligible": bool(geometry_eligible and source_speed_eligible),
            "geometry_eligible": bool(geometry_eligible),
            "source_speed_profile_eligible": bool(source_speed_eligible),
            "reason": "qualified" if geometry_eligible and source_speed_eligible else "geometry or source speed limits failed",
            "closure_gap_m": closure, "length_m": float(np.sum(lengths)),
            "self_intersections": intersections, "resampled_points": len(points),
            "tangent_jump_rad": tangent_jump, "max_abs_curvature_1pm": float(np.max(np.abs(curvature))),
            "min_expanded_footprint_clearance_m": clearance,
            "source_max_lateral_accel_mps2": source_lateral,
            "source_max_forward_accel_mps2": source_forward,
            "source_max_braking_mps2": source_braking,
            "numeric_speed_tolerance": speed_tolerance,
            "profile_min_speed_mps": float(np.min(speed)), "profile_max_speed_mps": float(np.max(speed))}
