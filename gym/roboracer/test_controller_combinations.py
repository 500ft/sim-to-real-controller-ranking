"""Known-answer behavior for combination selection and delayed application."""

import unittest

import numpy as np

from roboracer.controller_combinations import CombinationController


LIMITS = {"command_steer_abs_rad": 0.4189, "command_speed_min_mps": 0.0,
          "command_speed_max_mps": 8.0, "command_steer_rate_abs_radps": 3.2,
          "command_speed_rate_abs_mps2": 9.51}
STATE = {"time_s": 0.0}


class Fake:
    def __init__(self, name, action, valid=True):
        self.name, self.action, self.valid = name, action, valid
        self.calls = 0
        self.success_flags = []
        self.solve_times_s = []
        self.last_solution = np.ones((2, 2))

    def reset(self):
        self.calls = 0
        self.success_flags = []
        self.solve_times_s = []

    def command(self, state, path_info):
        self.calls += 1
        if self.name == "mpc":
            self.success_flags.append(self.valid)
            self.solve_times_s.append(0.001)
        return self.action


def factory(actions, valid=True):
    return lambda name: Fake(name, actions[name], valid)


class CombinationTests(unittest.TestCase):
    def test_shadow_cannot_change_active_proposal(self):
        actions = {"pure_pursuit": (0.0, 2.0), "lqr": (0.02, 2.0), "mpc": (0.4, 8.0)}
        one = CombinationController("pp_lqr", factory(actions), LIMITS)
        shadow = CombinationController("lqr_active_mpc_shadow", factory(actions), LIMITS)
        for i in range(8):
            self.assertEqual(one.command({"time_s": i * .01}, {}), shadow.command({"time_s": i * .01}, {}))
            command = (one.last_diagnostics["bounded_proposal_steer_rad"],
                       one.last_diagnostics["bounded_proposal_speed_mps"])
            one.on_applied(command)
            shadow.on_applied(command)
        self.assertEqual(shadow.mpc.calls, 8)
        self.assertEqual(one.mpc.calls, 0)

    def test_blend_uses_one_pp_base_and_bounds_rate(self):
        actions = {"pure_pursuit": (0.1, 3.0), "lqr": (0.2, 4.0), "mpc": (0.3, 5.0)}
        blend = CombinationController("pp_blend", factory(actions), LIMITS, blend_lqr_weight=0.25)
        out = blend.command(STATE, {})
        self.assertAlmostEqual(blend.last_diagnostics["proposal_pp_steer_rad"], 0.1)
        self.assertAlmostEqual(blend.last_diagnostics["bounded_proposal_steer_rad"], 0.032)
        self.assertEqual(out, (0.032, 0.0951))
        blend.on_applied(out)
        # Unbounded raw blend is 0.275 rad, 4.75 m/s, not PP plus both full commands.
        self.assertEqual(blend._limit((0.275, 4.75)), (0.064, 0.1902))

    def test_failed_mpc_falls_back_and_dwell_prevents_chatter(self):
        actions = {"pure_pursuit": (0.0, 1.0), "lqr": (0.01, 1.0), "mpc": (0.02, 1.0)}
        combo = CombinationController("mpc_lqr_fallback", factory(actions, valid=False), LIMITS)
        combo.command(STATE, {})
        self.assertEqual(combo.last_diagnostics["active_component"], "lqr")
        self.assertEqual(combo.last_diagnostics["switch_reason"], "mpc_failure_or_deadline")
        combo.mpc.valid = True
        for i in range(4):
            combo.command({"time_s": (i + 1) * .01}, {})
            self.assertEqual(combo.last_diagnostics["active_component"], "lqr")
        combo.command({"time_s": .05}, {})
        self.assertEqual(combo.last_diagnostics["active_component"], "mpc")

    def test_rejected_mpc_output_is_not_applied(self):
        actions = {"pure_pursuit": (0.0, 1.0), "lqr": (0.01, 1.0), "mpc": (float("nan"), 1.0)}
        combo = CombinationController("pp_mpc", factory(actions), LIMITS)
        self.assertEqual(combo.command(STATE, {}), (0.0, 0.0))
        self.assertEqual(combo.last_diagnostics["switch_reason"], "invalid_mpc_hold")

    def test_registered_timeout_fault_is_rejected_on_twentieth_call(self):
        actions = {"pure_pursuit": (0.0, 1.0), "lqr": (0.01, 1.0), "mpc": (0.02, 1.0)}
        combo = CombinationController("mpc_lqr_fallback", factory(actions), LIMITS,
                                      fault="Reject every twentieth MPC result")
        for index in range(1, 21):
            combo.command({"time_s": index * .01}, {})
        self.assertEqual(combo.last_diagnostics["active_component"], "lqr")
        self.assertEqual(combo.last_diagnostics["switch_reason"], "mpc_failure_or_deadline")
        self.assertEqual(combo.last_diagnostics["injected_compute_delay_s"], .02)


if __name__ == "__main__":
    unittest.main()
