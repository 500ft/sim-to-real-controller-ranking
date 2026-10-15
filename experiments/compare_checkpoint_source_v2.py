"""Execute the pinned checkpoint class on permitted evaluation recordings."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import zarr

from experiments.common_reward_v2 import decode_progress, reward_vectors


SOURCE_SHA256 = "0dea55802bc644f4447b2e2c130193286ab6364688d316c3599aa84e60a659cf"


def load_pinned_class(path):
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256
    module = ast.parse(source)
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "CheckpointReward")
    namespace = {"np": np}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["CheckpointReward"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("private_data", type=Path)
    parser.add_argument("pinned_fast_reward", type=Path)
    parser.add_argument("eval_agents", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    upstream_class = load_pinned_class(args.pinned_fast_reward)
    agents = set(json.loads(args.eval_agents.read_text()))
    bad_real = {161444, 283691, 82322, 202835, 152551, 268314, 155685, 161312, 278488}
    result = {}
    for name in ("f110-real-stoch-v2", "f110-sim-stoch-v2"):
        root = zarr.open(str(args.private_data / name), mode="r")
        timestep = root["timestep"][:]
        starts = np.r_[0, np.flatnonzero(timestep[1:] <= timestep[:-1]) + 1]
        ends = np.r_[starts[1:], len(timestep)]
        terminal = root["compute_termination"][:]
        names = root["model_name"][:]
        sin_progress = root["observations"]["progress_sin"][:]
        cos_progress = root["observations"]["progress_cos"][:]
        compared = changed = 0
        max_row_delta = 0.0
        for start, end in zip(starts, ends):
            if str(names[start]) not in agents or (name == "f110-real-stoch-v2" and int(start) in bad_real):
                continue
            first = np.flatnonzero(terminal[start:end])
            stop = min(end, start + 250, start + int(first[0]) + 1 if len(first) else end)
            progress = decode_progress(sin_progress[start:stop], cos_progress[start:stop])
            ours = reward_vectors(progress, np.zeros(len(progress)), np.zeros(len(progress)), True)["checkpoint"]
            upstream = 10 * upstream_class()({"progress": progress.copy()}, None, None).reshape(-1)
            upstream[-1] = 0.0
            delta = np.abs(ours - upstream)
            compared += 1
            changed += bool(np.any(delta > 1e-8))
            max_row_delta = max(max_row_delta, float(np.max(delta)))
        result[name] = {
            "recordings_compared": compared,
            "recordings_with_different_checkpoint_rows": changed,
            "maximum_absolute_row_reward_difference": max_row_delta,
        }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
