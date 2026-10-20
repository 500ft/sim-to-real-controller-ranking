"""Synthetic action mapping through the pinned candidate's actual wrappers."""

import argparse
import hashlib
import json
from pathlib import Path

import gymnasium as gym
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator-source", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.simulator_source / "f110_sim_env/base_env.py"
    config_file = args.loader_source / "f110_orl_dataset/config_new.py"
    if hashlib.sha256(source.read_bytes()).hexdigest() != "d58cf97805681326d90e807af924a0d3affbeaef2b7ce070533ac88c2880382d":
        raise ValueError("candidate simulator source hash mismatch")
    if hashlib.sha256(config_file.read_bytes()).hexdigest() != "2ac739a12cebbfeeb5c63ff7e530104465cefeb99693def6d6156d0d1c9f85e7":
        raise ValueError("loader config source hash mismatch")
    import f110_orl_dataset.config_new as config
    config.Config = config.RewardConfig
    from f110_sim_env.base_env import AccelerationAndDeltaSteeringWrapper, RescaleAction2

    class PhysicalActionSpace(gym.Env):
        action_space = gym.spaces.Box(low=np.array([[-0.4189, 0.0]], dtype=np.float32),
                                      high=np.array([[0.4189, 2.0]], dtype=np.float32))

    protocol = json.loads((Path(__file__).parents[1] / "runs/ope_reward_adapter_qualification/protocol.json").read_text())
    fixture = protocol["synthetic_trajectories"]["source_action_mapping"]
    physical = PhysicalActionSpace()
    delta = AccelerationAndDeltaSteeringWrapper(
        physical, max_acceleration=0.05, max_delta_steering=0.05,
        min_velocity=0.0, max_velocity=2.0,
        min_steering=-0.4189, max_steering=0.4189,
        inital_velocity=fixture["initial_target_speed_m_per_s"])
    delta.current_steering = fixture["initial_target_steering_rad"]
    delta.current_velocity = fixture["initial_target_speed_m_per_s"]
    normalized = RescaleAction2(delta, -1.0, 1.0)
    command = np.asarray([fixture["normalized_input"]], dtype=np.float32)
    delta_action = normalized.action(command)
    target = delta.action(delta_action)
    np.testing.assert_allclose(delta_action[0],
                               [fixture["expected_delta_steering_rad"], fixture["expected_delta_speed_m_per_s"]], atol=1e-7)
    np.testing.assert_allclose(target[0], fixture["expected_physical_target"], atol=1e-7)
    result = {"normalized_input": command[0].tolist(), "delta_action": delta_action[0].tolist(),
              "physical_target": target[0].tolist(), "fixture_agreement": "passed"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
