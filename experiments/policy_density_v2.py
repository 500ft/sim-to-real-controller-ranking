"""Independent density and action-frame calculations for the pinned FTG/PP policies."""

import math

import numpy as np
from scipy.special import log_ndtr


def log_normal_interval(lower, upper):
    """Log(Phi(upper)-Phi(lower)), stable in either tail."""
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    left = upper <= 0
    a = np.where(left, lower, -upper)
    b = np.where(left, upper, -lower)
    # On the right tail, Phi(upper)-Phi(lower) is Phi(-lower)-Phi(-upper).
    hi = np.where(left, b, b)
    lo = np.where(left, a, a)
    log_hi = log_ndtr(hi)
    log_lo = log_ndtr(lo)
    return log_hi + np.log(-np.expm1(log_lo - log_hi))


def independent_density(action, mean, previous, max_delta, max_speed, std_speed, std_steer):
    """Log densities in [speed, steering] order for delta [steering, speed].

    A zero-width speed interval is a point mass, matching the pinned policy's
    zero log-density convention. Steering remains continuous.
    """
    action = np.asarray(action, dtype=float)
    mean = np.asarray(mean, dtype=float)
    previous = np.asarray(previous, dtype=float)
    speed_lo = np.minimum(np.maximum(0.5 - previous[:, 1], -max_delta), max_delta)
    speed_hi = np.minimum(max_delta, max_speed - previous[:, 1])
    steer_lo = -np.minimum(max_delta, 0.4189 + previous[:, 0])
    steer_hi = np.minimum(max_delta, 0.4189 - previous[:, 0])
    lower = np.column_stack((steer_lo, speed_lo))
    upper = np.column_stack((steer_hi, speed_hi))
    if np.any(upper < lower - 1e-12):
        raise ValueError("invalid action interval at archived previous action")
    point_speed = np.isclose(speed_lo, speed_hi, atol=1e-6, rtol=1e-5)
    support = (action >= lower - 1e-6) & (action <= upper + 1e-6)
    scale = np.array([std_steer, std_speed])
    z = (action - mean) / scale
    lo_z = (lower - mean) / scale
    hi_z = (upper - mean) / scale
    with np.errstate(divide="ignore", invalid="ignore"):
        normalizer = log_normal_interval(lo_z, hi_z)
        ordered = -.5 * z*z - np.log(scale * math.sqrt(2*math.pi)) - normalizer
    ordered[point_speed, 1] = 0.0
    support[point_speed, 1] = abs(action[point_speed, 1] - speed_lo[point_speed]) <= 1e-6
    ordered[~support] = -np.inf
    return ordered[:, ::-1], support[:, ::-1], lower, upper


def target_from_delta(previous, delta):
    """Collection path clips speed after adding the delta, in [steering,speed]."""
    raw = np.asarray(previous) + np.asarray(delta)
    raw[:, 1] = np.clip(raw[:, 1], 0.5, 7.0)
    return raw
