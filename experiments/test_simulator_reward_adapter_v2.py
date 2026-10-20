"""Registered, hand-calculated transition cases for the common reward bridge."""

import json
import unittest
from pathlib import Path

import gymnasium as gym
import numpy as np

from experiments.simulator_reward_adapter_v2 import CommonRewardWrapper, TransitionRewards


FIXTURE = json.loads((Path(__file__).parents[1] / "runs/ope_reward_adapter_qualification/protocol.json").read_text())[
    "synthetic_trajectories"
]


def run_progress(progress):
    engine = TransitionRewards()
    engine.reset(progress[0])
    return [engine.step(value, 0.0) for value in progress[1:]]


class AdapterRewardTest(unittest.TestCase):
    def test_nonzero_progress_and_strict_checkpoint(self):
        case = FIXTURE["nonzero_progress"]
        result = run_progress(case["progress_fraction"])
        self.assertEqual(len(result) + 1, len(case["expected_departure_progress_reward"]))
        for reward, expected in zip(result, case["expected_departure_progress_reward"]):
            self.assertAlmostEqual(reward["progress"], expected)
        self.assertEqual([reward["checkpoint"] for reward in result] + [0.0],
                         case["expected_departure_checkpoint_reward"])

    def test_two_laps_no_duplicate_threshold(self):
        case = FIXTURE["two_lap_wrap"]
        result = run_progress(case["progress_fraction"])
        for reward, expected in zip(result, case["expected_departure_progress_reward"]):
            self.assertAlmostEqual(reward["progress"], expected)
        self.assertEqual([reward["checkpoint"] for reward in result] + [0.0],
                         case["expected_departure_checkpoint_reward"])

    def test_reset_does_not_bridge_segments(self):
        case = FIXTURE["reset_segments"]
        engine = TransitionRewards()
        for segment, expected in zip(case["progress_fraction_by_segment"],
                                     case["expected_departure_progress_reward_by_segment"]):
            engine.reset(segment[0])
            self.assertAlmostEqual(engine.step(segment[1], 0.0)["progress"], expected[0])

    def test_terminal_and_horizon_alignment(self):
        # An n-step rollout has n+1 observations. The final observation has no
        # outgoing reward; the transition arriving there still earns a reward.
        result = run_progress(FIXTURE["terminal"]["progress_fraction"])
        self.assertEqual([r["lifetime"] for r in result] + [0.0],
                         FIXTURE["terminal"]["expected_lifetime_reward"])
        engine = TransitionRewards()
        engine.reset(0.2)
        constant = [engine.step(0.2, 0.0) for _ in range(250)]
        self.assertEqual(len(constant), 250)
        self.assertEqual(sum(r["lifetime"] for r in constant), 250)
        self.assertEqual(sum(r["progress"] for r in constant), 0)
        self.assertEqual(sum(r["checkpoint"] for r in constant), 0)

    def test_physical_steering_target(self):
        case = FIXTURE["steering"]
        engine = TransitionRewards()
        engine.reset(0.2)
        for previous, delta, target in zip(case["previous_steering_rad"],
                                           case["delta_steering_rad"],
                                           case["expected_target_steering_rad"]):
            self.assertAlmostEqual(previous + delta, target)
            observed = engine.step(0.2, target)["min_act"]
            self.assertAlmostEqual(observed, 1 - (target / case["steering_limit_rad"]) ** 2)

    def test_ambiguous_backward_jump_is_rejected(self):
        engine = TransitionRewards()
        engine.reset(0.8)
        with self.assertRaises(ValueError):
            engine.step(0.1, 0.0)

    def test_wrapper_terminal_transition_and_reset(self):
        class TinyEnv(gym.Env):
            def __init__(self):
                self.start = 0.95
                self.next_progress = 0.01

            def observation(self, progress):
                return {"progress_sin": np.array([np.sin(2 * np.pi * progress)]),
                        "progress_cos": np.array([np.cos(2 * np.pi * progress)]),
                        "collisions": np.array([False])}

            def reset(self, seed=None, options=None):
                return self.observation(self.start), {}

            def step(self, action):
                return self.observation(self.next_progress), 0.0, True, False, {}

        base = TinyEnv()
        wrapped = CommonRewardWrapper(base, {"selected": "progress"})
        wrapped.reset(seed=0)
        _, reward, terminated, truncated, info = wrapped.step(np.array([[0.1, 0.5]]))
        self.assertAlmostEqual(reward, 6.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["qualified_reward_components"]["checkpoint"], 10.0)
        self.assertAlmostEqual(info["qualified_reward_components"]["min_act"],
                               1 - (0.1 / 0.4189) ** 2)
        base.start, base.next_progress = 0.3, 0.35
        wrapped.reset(seed=0)
        _, reward, _, _, info = wrapped.step(np.array([[0.0, 0.5]]))
        self.assertAlmostEqual(reward, 5.0)
        self.assertEqual(info["qualified_reward_components"]["checkpoint"], 0.0)


if __name__ == "__main__":
    unittest.main()
