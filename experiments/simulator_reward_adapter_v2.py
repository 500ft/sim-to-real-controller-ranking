"""Pinned, process-local bridge from the candidate simulator to common rewards.

The candidate's StepMixedReward cannot call the pinned loader's effective
MixedReward signature. This bridge replaces only that reward wrapper while
retaining the candidate's physics, observations, action wrappers, and reset.
It reports all four declared reward components for each executed transition.
"""

import hashlib
import importlib
from pathlib import Path

import gymnasium as gym
import numpy as np


SOURCE_HASHES = {
    "simulator": "d58cf97805681326d90e807af924a0d3affbeaef2b7ce070533ac88c2880382d",
    "loader_config": "2ac739a12cebbfeeb5c63ff7e530104465cefeb99693def6d6156d0d1c9f85e7",
    "loader_reward": "0dea55802bc644f4447b2e2c130193286ab6364688d316c3599aa84e60a659cf",
}
STEERING_LIMIT = 0.4189


def decode_progress(obs):
    return float(np.mod(np.arctan2(float(obs["progress_sin"][0]),
                                      float(obs["progress_cos"][0])) / (2 * np.pi), 1.0))


class TransitionRewards:
    """One reward vector per transition from the prior observation.

    A terminal observation has no outgoing reward row. The transition arriving
    there still receives its departure-row reward, matching the declared
    trajectory convention. Reset clears lap and checkpoint state.
    """

    def reset(self, progress):
        self.initial = float(progress)
        self.previous = float(progress)
        self.unwrapped = float(progress)

    def step(self, progress, target_steering):
        progress = float(progress)
        delta = progress - self.previous
        if -0.9 <= delta < -0.5:
            raise ValueError("ambiguous backward progress jump")
        if delta < -0.9:
            delta += 1.0
        old_unwrapped = self.unwrapped
        self.unwrapped += delta
        # Source checkpoints are strict: a threshold equal to the new position
        # has not been passed. Ignore thresholds at or below the reset progress.
        first = max(int(np.ceil(10 * old_unwrapped - 1e-12)),
                    int(np.floor(10 * self.initial + 1e-12)) + 1)
        last_exclusive = int(np.ceil(10 * self.unwrapped - 1e-12))
        crossings = max(0, last_exclusive - first)
        self.previous = progress
        return {
            "progress": 100.0 * max(delta, 0.0),
            "lifetime": 1.0,
            "min_act": 1.0 - (float(target_steering) / STEERING_LIMIT) ** 2,
            "checkpoint": 10.0 * crossings,
        }


class CommonRewardWrapper(gym.Wrapper):
    def __init__(self, env, reward_config):
        super().__init__(env)
        selected = reward_config["selected"]
        if selected not in ("progress", "lifetime", "min_act", "checkpoint"):
            raise ValueError(selected)
        self.selected = selected
        self.engine = TransitionRewards()

    def reset(self, seed=None, options=None):
        obs, info = self.env.reset(seed=seed, options=options)
        self.engine.reset(decode_progress(obs))
        return obs, info

    def step(self, action):
        obs, _, terminated, truncated, info = self.env.step(action)
        components = self.engine.step(decode_progress(obs), float(action[0, 0]))
        info["qualified_reward_components"] = components
        info["rewards"] = {"final_reward": components[self.selected]}
        info["collision"] = obs["collisions"][0]
        return obs, components[self.selected], terminated, truncated, info


def make_compatible_env(simulator_source, loader_source, **kwargs):
    simulator_source = Path(simulator_source).resolve()
    loader_source = Path(loader_source).resolve()
    files = {
        "simulator": simulator_source / "f110_sim_env/base_env.py",
        "loader_config": loader_source / "f110_orl_dataset/config_new.py",
        "loader_reward": loader_source / "f110_orl_dataset/fast_reward.py",
    }
    for name, path in files.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_HASHES[name]:
            raise ValueError(f"pinned {name} source hash mismatch")

    config = importlib.import_module("f110_orl_dataset.config_new")
    if Path(config.__file__).resolve() != files["loader_config"]:
        raise ValueError("loaded a different loader config")
    # Required only for importing the candidate module. The factory receives a
    # selected common-reward name, not the source's stale default dict.
    config.Config = config.RewardConfig
    candidate = importlib.import_module("f110_sim_env.base_env")
    if Path(candidate.__file__).resolve() != files["simulator"]:
        raise ValueError("loaded a different candidate simulator")
    original = candidate.MixedGymReward
    candidate.MixedGymReward = CommonRewardWrapper
    try:
        return candidate.make_base_env(reward_config={"selected": "progress"}, **kwargs)
    finally:
        candidate.MixedGymReward = original
