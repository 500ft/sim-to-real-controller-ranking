"""Independent arithmetic boundary cases for the registered reward definitions."""

import unittest

import numpy as np

from experiments.common_reward_v2 import decode_progress, reward_vectors


class CommonRewardCases(unittest.TestCase):
    def test_progress_wrap_and_terminal(self):
        result = reward_vectors(np.array([0.95, 0.02, 0.04]), np.zeros(3), np.zeros(3), True)
        np.testing.assert_allclose(result["progress"], [7.0, 2.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result["lifetime"], [1.0, 1.0, 0.0])

    def test_stationary_checkpoint_and_strict_crossing(self):
        result = reward_vectors(np.array([0.05, 0.10, 0.10001, 0.10001]), np.zeros(4), np.zeros(4), False)
        np.testing.assert_array_equal(result["checkpoint"], [0, 0, 10, 0])

    def test_action_bounds_and_progress_decode(self):
        result = reward_vectors(np.array([0.2, 0.2]), np.array([0.0, 0.4189]), np.zeros(2), False)
        np.testing.assert_allclose(result["min_act"], [1.0, 0.0])
        np.testing.assert_allclose(decode_progress(np.sin(2 * np.pi * np.array([0.2, 0.8])),
                                                   np.cos(2 * np.pi * np.array([0.2, 0.8]))), [0.2, 0.8])


if __name__ == "__main__":
    unittest.main()
