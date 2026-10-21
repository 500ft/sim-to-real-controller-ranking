"""Frozen simulation-development combinations of existing PP-correction controllers."""

from __future__ import annotations

import math
import time
from typing import Callable

import numpy as np


class CombinationController:
    """Run existing commands on one observation; only the selected command is applied.

    The supplied factories create independent controller state for each component.
    Legacy LQR/MPC factories already include a PP feedforward command.
    """

    def __init__(self, name: str, factory: Callable[[str], object], limits: dict,
                 *, blend_lqr_weight: float = 0.5, fault: str | None = None,
                 control_period_s: float = 0.01):
        self.name = name
        self.pp = factory("pure_pursuit")
        self.lqr = factory("lqr")
        self.mpc = factory("mpc")
        self.limits = limits
        self.weight = float(blend_lqr_weight)
        self.fault = fault
        self.period = float(control_period_s)
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError("Blend weight must be in [0,1]")
        self.reset()

    def reset(self) -> None:
        for item in (self.pp, self.lqr, self.mpc):
            item.reset()
        self.applied = (0.0, 0.0)
        self.call_index = 0
        self.mode = "mpc"
        self.dwell = 0
        self.valid_streak = 0
        self.last_diagnostics: dict[str, object] = {}

    def _limit(self, proposal: tuple[float, float]) -> tuple[float, float]:
        steer, speed = map(float, proposal)
        if not math.isfinite(steer) or not math.isfinite(speed):
            raise ValueError("Nonfinite command")
        bounds = self.limits
        steer = float(np.clip(steer, -bounds["command_steer_abs_rad"],
                              bounds["command_steer_abs_rad"]))
        speed = float(np.clip(speed, bounds["command_speed_min_mps"],
                              bounds["command_speed_max_mps"]))
        steer_step = bounds["command_steer_rate_abs_radps"] * self.period
        speed_step = bounds["command_speed_rate_abs_mps2"] * self.period
        return (float(np.clip(steer, self.applied[0] - steer_step, self.applied[0] + steer_step)),
                float(np.clip(speed, self.applied[1] - speed_step, self.applied[1] + speed_step)))

    def _compute(self, component: object, state: dict, path_info: dict) -> tuple[float, float]:
        result = tuple(map(float, component.command(state, path_info)))
        if len(result) != 2:
            raise ValueError("Controller must return steering and speed")
        return result

    def command(self, state: dict, path_info: dict) -> tuple[float, float]:
        self.call_index += 1
        before = self.mode
        proposed: dict[str, tuple[float, float]] = {}
        timings: dict[str, float] = {}
        need = {
            "pp": ("pp",), "pp_lqr": ("lqr",), "pp_mpc": ("mpc",),
            "lqr_active_mpc_shadow": ("lqr", "mpc"),
            "mpc_active_lqr_shadow": ("mpc", "lqr"),
            "mpc_lqr_fallback": ("mpc", "lqr"),
            "pp_blend": ("pp", "lqr", "mpc"),
        }[self.name]
        for key in need:
            start = time.perf_counter()
            proposed[key] = self._compute(getattr(self, key), state, path_info)
            timings[key] = time.perf_counter() - start
        mpc_ok = True
        if "mpc" in proposed:
            flags = self.mpc.success_flags
            mpc_ok = bool(flags and flags[-1]) and all(map(math.isfinite, proposed["mpc"]))
            # This declared fault is independent of whether the optimizer happens to succeed.
            if self.fault == "mpc_timeout" and self.call_index % 20 == 0:
                mpc_ok = False
        injected = 0.02 if self.fault == "mpc_timeout" and self.call_index % 20 == 0 and "mpc" in proposed else 0.0
        mpc_deadline = "mpc" in timings and timings["mpc"] + injected > self.period
        reason = ""
        shadow = ""
        if self.name == "pp":
            active, raw = "pp", proposed["pp"]
        elif self.name == "pp_lqr":
            active, raw = "lqr", proposed["lqr"]
        elif self.name == "pp_mpc":
            active, raw = "mpc", proposed["mpc"] if mpc_ok else self.applied
            if not mpc_ok:
                reason = "invalid_mpc_hold"
        elif self.name == "lqr_active_mpc_shadow":
            active, shadow, raw = "lqr", "mpc", proposed["lqr"]
        elif self.name == "mpc_active_lqr_shadow":
            active, shadow, raw = "mpc", "lqr", proposed["mpc"] if mpc_ok else self.applied
            if not mpc_ok:
                reason = "invalid_mpc_hold"
        elif self.name == "mpc_lqr_fallback":
            valid = mpc_ok and not mpc_deadline
            if self.mode == "mpc" and not valid:
                self.mode, self.dwell, self.valid_streak = "lqr", 5, 0
                reason = "mpc_failure_or_deadline"
            elif self.mode == "lqr":
                self.dwell = max(0, self.dwell - 1)
                self.valid_streak = self.valid_streak + 1 if valid else 0
                if self.dwell == 0 and self.valid_streak >= 3:
                    self.mode, self.valid_streak = "mpc", 0
                    reason = "mpc_recovered"
            active = self.mode
            shadow = "lqr" if active == "mpc" else "mpc"
            raw = proposed[active]
        else:
            active = "blend"
            if mpc_ok:
                base, lqr, mpc = (np.asarray(proposed[key]) for key in ("pp", "lqr", "mpc"))
                raw = tuple(base + self.weight * (lqr - base) + (1.0 - self.weight) * (mpc - base))
            else:
                raw = self.applied
                reason = "invalid_mpc_hold"
        try:
            limited = self._limit(raw)
        except ValueError:
            limited = self.applied
            reason = "nonfinite_hold"
        self.last_diagnostics = {
            "active_component": active, "shadow_component": shadow,
            "mode_before": before, "mode_after": self.mode, "switch_reason": reason,
            "proposal_pp_steer_rad": proposed.get("pp", (float("nan"), float("nan")))[0],
            "proposal_pp_speed_mps": proposed.get("pp", (float("nan"), float("nan")))[1],
            "proposal_lqr_steer_rad": proposed.get("lqr", (float("nan"), float("nan")))[0],
            "proposal_lqr_speed_mps": proposed.get("lqr", (float("nan"), float("nan")))[1],
            "proposal_mpc_steer_rad": proposed.get("mpc", (float("nan"), float("nan")))[0],
            "proposal_mpc_speed_mps": proposed.get("mpc", (float("nan"), float("nan")))[1],
            "mpc_result_valid": mpc_ok, "mpc_solve_s": self.mpc.solve_times_s[-1] if self.mpc.solve_times_s else float("nan"),
            "injected_compute_delay_s": injected, "call_index": self.call_index,
            "command_observation_time_s": state["time_s"],
            "bounded_proposal_steer_rad": limited[0], "bounded_proposal_speed_mps": limited[1],
        }
        return limited

    def on_applied(self, command: tuple[float, float]) -> None:
        self.applied = tuple(map(float, command))
        # Bypassed MPC state cannot reuse an optimizer trajectory generated for
        # another controller's plant path. The next solve starts from zero.
        if self.name in {"lqr_active_mpc_shadow", "mpc_lqr_fallback"} and self.last_diagnostics.get("active_component") != "mpc":
            self.mpc.last_solution[:] = 0.0

