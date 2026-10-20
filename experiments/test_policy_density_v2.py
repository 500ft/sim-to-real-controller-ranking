import math
import unittest

import numpy as np
from scipy.integrate import quad

from experiments.policy_density_v2 import independent_density, target_from_delta


class DensityCases(unittest.TestCase):
    def test_interior_tail_and_normalization(self):
        previous = np.array([[0., 1.], [0., 1.]])
        mean = np.array([[0.02, -0.03], [0.02, -0.03]])
        action = np.array([[0.01, 0.04], [-0.28, 0.29]])
        density, support, lower, upper = independent_density(
            action, mean, previous, .3, 5., .1, .03)
        self.assertTrue(support.all())
        self.assertEqual(density.shape, (2, 2))
        for coordinate, component, sigma in ((0, 1, .03), (1, 0, .1)):
            lo, hi = lower[0, coordinate], upper[0, coordinate]
            mu = mean[0, coordinate]
            norm, _ = quad(lambda x: math.exp(-.5*((x-mu)/sigma)**2) /
                           (sigma*math.sqrt(2*math.pi)), lo, hi)
            def independently(x):
                return math.log(math.exp(-.5*((x-mu)/sigma)**2) /
                                (sigma*math.sqrt(2*math.pi)*norm))
            self.assertAlmostEqual(density[0, component], independently(action[0, coordinate]), places=9)
            integral, _ = quad(lambda x: math.exp(independently(x)), lo, hi)
            self.assertAlmostEqual(integral, 1., places=9)
        self.assertLess(density[1, 1], density[0, 1])

    def test_boundaries_swap_and_action_frame(self):
        previous = np.array([[.1, 1.]])
        mean = np.array([[.02, .04]])
        for action in (np.array([[-.3, -.3]]), np.array([[.3, .3]])):
            density, support, _, _ = independent_density(action, mean, previous, .3, 5., .1, .03)
            self.assertTrue(np.isfinite(density).all())
            self.assertTrue(support.all())
        outside, support, _, _ = independent_density(
            np.array([[.31, .04]]), mean, previous, .3, 5., .1, .03)
        self.assertFalse(support[0, 1])
        self.assertTrue(np.isneginf(outside[0, 1]))
        actual, _, _, _ = independent_density(np.array([[.01, .04]]), mean, previous, .3, 5., .1, .03)
        swapped, _, _, _ = independent_density(np.array([[.04, .01]]), mean, previous, .3, 5., .1, .03)
        self.assertGreater(abs(actual[0, 0] - swapped[0, 0]), .01)
        np.testing.assert_allclose(target_from_delta(previous, np.array([[.01, .04]])), [[.11, 1.04]])

    def test_zero_width_speed_and_batch_permutation(self):
        previous = np.array([[0., .2], [.1, 1.]])
        action = np.array([[0., .3], [.01, .04]])
        mean = np.array([[0., .3], [.02, .03]])
        density, support, _, _ = independent_density(action, mean, previous, .3, 5., .1, .03)
        self.assertEqual(density[0, 0], 0.)
        self.assertTrue(support.all())
        permuted, _, _, _ = independent_density(action[::-1], mean[::-1], previous[::-1], .3, 5., .1, .03)
        np.testing.assert_allclose(density, permuted[::-1])
        self.assertTrue(np.isneginf(independent_density(
            np.array([[0., .299]]), mean[:1], previous[:1], .3, 5., .1, .03)[0][0, 0]))


if __name__ == "__main__":
    unittest.main()
