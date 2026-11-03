"""Step-hash sensitivity for the bridge benchmark's bitwise comparison."""

import unittest

import numpy as np

from experiments.benchmark_bridge_runtime_v2 import step_hash


class StepHashTest(unittest.TestCase):
    def test_hash_is_bitwise_sensitive_and_key_order_free(self):
        obs = {"b": np.array([1.0, 2.0], dtype=np.float32), "a": np.array([0.5])}
        components = {"progress": 1.0, "lifetime": 1.0, "min_act": 0.9, "checkpoint": 0.0}
        reference = step_hash(np.zeros((1, 2)), obs, components, 1.0, False, False, False)
        reordered = {"a": obs["a"], "b": obs["b"]}
        self.assertEqual(step_hash(np.zeros((1, 2)), reordered, components, 1.0, False, False, False), reference)
        nudged = {"b": np.array([1.0, np.nextafter(np.float32(2.0), np.float32(3.0))], dtype=np.float32), "a": obs["a"]}
        self.assertNotEqual(step_hash(np.zeros((1, 2)), nudged, components, 1.0, False, False, False), reference)
        self.assertNotEqual(step_hash(np.zeros((1, 2)), obs, components, 1.0, True, False, False), reference)
        self.assertNotEqual(step_hash(np.array([[1e-9, 0.0]]), obs, components, 1.0, False, False, False), reference)
        dtype_changed = {"b": obs["b"].astype(np.float64), "a": obs["a"]}
        self.assertNotEqual(step_hash(np.zeros((1, 2)), dtype_changed, components, 1.0, False, False, False), reference)


if __name__ == "__main__":
    unittest.main()
