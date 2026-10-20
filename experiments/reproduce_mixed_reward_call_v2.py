"""Minimal public witness for the pinned nested reward-call incompatibility."""

import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path

import gymnasium as gym
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.loader_source / "f110_orl_dataset/fast_reward.py"
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    if sha != "0dea55802bc644f4447b2e2c130193286ab6364688d316c3599aa84e60a659cf":
        raise ValueError("fast_reward.py hash differs")
    tree = ast.parse(source.read_text())
    mixed_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MixedReward")
    definitions = [node for node in mixed_class.body if isinstance(node, ast.FunctionDef) and node.name == "__call__"]
    from f110_orl_dataset.config_new import RewardConfig
    from f110_orl_dataset.fast_reward import MixedReward, ProgressReward, StepMixedReward

    class TinyEnv:
        action_space = gym.spaces.Box(low=np.array([[-0.4189, 0.0]]),
                                      high=np.array([[0.4189, 2.0]]), dtype=np.float32)

    wrapper = StepMixedReward(TinyEnv(), RewardConfig("reward_progress.json"))
    wrapper.reset()
    flat_obs = np.zeros((1, 11))
    action = np.zeros((1, 2))
    try:
        wrapper(flat_obs, action, np.array([False]), np.array([False]))
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
    else:
        raise AssertionError("pinned call unexpectedly succeeded")

    progress_pair = np.array([0.2, 0.3])
    source_progress = ProgressReward()({"progress": progress_pair}, None, None)[0].tolist()
    result = {
        "fast_reward_sha256": sha,
        "mixed_reward_call_definition_lines": [node.lineno for node in definitions],
        "effective_mixed_reward_signature": str(inspect.signature(MixedReward.__call__)),
        "step_mixed_reward_signature": str(inspect.signature(StepMixedReward.__call__)),
        "flat_observation_shape": list(flat_obs.shape),
        "nested_call_failure": failure,
        "synthetic_progress_pair": progress_pair.tolist(),
        "source_progress_vector": source_progress,
        "step_wrapper_selected_column": 1,
        "selected_progress_value_if_keyword_and_layout_were_repaired": source_progress[1],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
