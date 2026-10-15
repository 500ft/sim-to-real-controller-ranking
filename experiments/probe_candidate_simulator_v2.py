"""Probe the pinned candidate simulator without editing third-party sources.

Run with the pinned simulator, loader, and gym source roots on PYTHONPATH.
This checks interface compatibility only; it does not identify the benchmark's
historical simulator revision or qualify a development rollout.
"""

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "simulator": "d58cf97805681326d90e807af924a0d3affbeaef2b7ce070533ac88c2880382d",
    "loader": "2ac739a12cebbfeeb5c63ff7e530104465cefeb99693def6d6156d0d1c9f85e7",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator-source", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = {
        "simulator": args.simulator_source / "f110_sim_env/base_env.py",
        "loader": args.loader_source / "f110_orl_dataset/config_new.py",
    }
    observed = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    if observed != EXPECTED:
        raise ValueError(f"source hashes differ: {observed}")

    import numpy as np
    import f110_orl_dataset.config_new as config

    # These two aliases are local process adapters for removed or renamed APIs.
    # The source files and packages are not modified.
    config.Config = config.RewardConfig
    np.bool = np.bool_
    result = {"source_sha256": observed, "adapter": ["Config=RewardConfig", "np.bool=np.bool_", "explicit RewardConfig object"]}
    try:
        from f110_sim_env.base_env import make_base_env
        result["import"] = "passed"
        env = make_base_env(map="Infsaal3", random_start=False, pose_start=True,
                            min_vel=0, max_vel=2, eval=False,
                            reward_config=config.RewardConfig("reward_progress.json"))
        result["construction"] = "passed"
        try:
            env.reset(seed=0)
            result["reset"] = "passed"
            for _ in range(3):
                env.step(np.zeros((1, 2), dtype=np.float32))
            result["three_step_rollout"] = "passed"
        finally:
            env.close()
    except Exception as exc:
        result["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if "failure" in result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
