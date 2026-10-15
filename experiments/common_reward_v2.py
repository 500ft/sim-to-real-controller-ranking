"""Registered common development rewards for the corrected v2 recordings.

Only derived per-policy aggregates are written to git. Original ZIPs and the
row-level exclusion ledger stay outside the repository.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import zarr


DISCOUNT = 0.99
HORIZON = 250
STEERING_LIMIT = 0.4189


def decode_progress(sin_value, cos_value):
    return np.mod(np.arctan2(sin_value, cos_value) / (2 * np.pi), 1.0)


def reward_vectors(progress, delta_steer, previous_steer, terminal):
    n = len(progress)
    assert n and len(delta_steer) == n and len(previous_steer) == n
    progress = np.asarray(progress, dtype=float)
    step = np.diff(progress)
    step[step < -0.9] += 1.0
    forward = np.r_[100 * np.maximum(step, 0.0), 0.0]
    lifetime = np.ones(n)
    min_act = 1 - ((previous_steer + delta_steer) / STEERING_LIMIT) ** 2

    # A crossing is strict, as in the pinned source. Do not force a final
    # progress value of three laps, which creates checkpoints while stationary.
    unwrapped = progress.copy()
    for i in range(1, n):
        if progress[i] - progress[i - 1] < -0.5:
            unwrapped[i:] += 1.0
    checkpoint = np.zeros(n)
    for i in range(1, n):
        left = int(np.ceil(10 * unwrapped[i - 1] - 1e-12)) - 1
        right = int(np.ceil(10 * unwrapped[i] - 1e-12)) - 1
        checkpoint[i] = 10 * max(0, right - left)
    vectors = {
        "progress": forward,
        "lifetime": lifetime,
        "min_act": min_act,
        "checkpoint": checkpoint,
    }
    if terminal:
        for value in vectors.values():
            value[-1] = 0.0
    return vectors


def archive_aggregates(path, eval_agents, bad_starts=()):
    root = zarr.open(str(path), mode="r")
    step = root["timestep"][:]
    names = root["model_name"][:]
    terminal = root["compute_termination"][:].astype(bool)
    sin_progress = root["observations"]["progress_sin"][:]
    cos_progress = root["observations"]["progress_cos"][:]
    action = root["actions"][:, 0]
    previous = root["observations"]["previous_action_steer"][:]
    starts = np.r_[0, np.flatnonzero(step[1:] <= step[:-1]) + 1]
    ends = np.r_[starts[1:], len(step)]
    by_policy = {}
    skipped_bad = 0
    for start, end in zip(starts, ends):
        name = str(names[start])
        if name not in eval_agents:
            continue
        if int(start) in bad_starts:
            skipped_bad += 1
            continue
        first_terminal = np.flatnonzero(terminal[start:end])
        stop = min(end, start + HORIZON)
        has_terminal = bool(len(first_terminal) and start + first_terminal[0] < stop)
        if has_terminal:
            stop = start + int(first_terminal[0]) + 1
        if stop <= start:
            continue
        # set_terminals=True makes timeouts terminal too.
        ended = has_terminal or stop == end or stop == start + HORIZON
        progress = decode_progress(sin_progress[start:stop], cos_progress[start:stop])
        rewards = reward_vectors(progress, action[start:stop], previous[start:stop], ended)
        weights = DISCOUNT ** np.arange(stop - start)
        by_policy.setdefault(name, {key: [] for key in rewards})
        for key, value in rewards.items():
            by_policy[name][key].append(float(np.dot(weights, value)))
    return {
        "recordings_seen": len(starts),
        "registered_bad_recordings_excluded": skipped_bad,
        "policies": {
            name: {
                key: {"recordings": len(values), "mean": float(np.mean(values)), "std_population": float(np.std(values))}
                for key, values in reward_values.items()
            }
            for name, reward_values in sorted(by_policy.items())
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("private_data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--eval-agents", type=Path, default=Path("runs/ope_corrected_v2/eval_agents.json"))
    args = parser.parse_args()
    eval_agents = set(json.loads(args.eval_agents.read_text()))
    bad_real = {161444, 283691, 82322, 202835, 152551, 268314, 155685, 161312, 278488}
    output = {}
    start = perf_counter()
    for name in ("f110-real-stoch-v2", "f110-sim-stoch-v2"):
        output[name] = archive_aggregates(args.private_data / name, eval_agents, bad_real if "real" in name else ())
        assert set(output[name]["policies"]) == eval_agents
    output["runtime_seconds"] = perf_counter() - start
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
