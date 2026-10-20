"""Compare a small corrected-v2 development sample with pinned reward classes.

Keep the source checkout and Zarr archive outside git. The output contains
summary differences and a synthetic checkpoint example, never private rows.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import zarr

from experiments.common_reward_v2 import decode_progress, reward_vectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-root", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--centerline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    fast = args.loader_source / "f110_orl_dataset/fast_reward.py"
    if hashlib.sha256(fast.read_bytes()).hexdigest() != "0dea55802bc644f4447b2e2c130193286ab6364688d316c3599aa84e60a659cf":
        raise ValueError("pinned fast_reward.py hash mismatch")
    progress_file = args.loader_source / "f110_orl_dataset/compute_progress.py"
    if hashlib.sha256(progress_file.read_bytes()).hexdigest() != "03129a57adcdcb7efff3d4fc4bd10508db2bec6e8e64ca087a712cb3544cdad4":
        raise ValueError("pinned compute_progress.py hash mismatch")
    from f110_orl_dataset.compute_progress import Progress, Track
    from f110_orl_dataset.fast_reward import CheckpointReward, MinActReward, ProgressReward

    root = zarr.open(str(args.real_root), mode="r")
    step = root["timestep"][:]
    names = root["model_name"][:]
    starts = np.r_[0, np.flatnonzero(step[1:] <= step[:-1]) + 1]
    ends = np.r_[starts[1:], len(step)]
    eval_agents = set(json.loads((Path(__file__).parents[1] / "runs/ope_corrected_v2/eval_agents.json").read_text()))
    bad = {161444, 283691, 82322, 202835, 152551, 268314, 155685, 161312, 278488}
    progress_source = Progress(Track(args.centerline), lookahead=200)
    summary = {"sample_recordings": 0, "progress_source_vs_common_max_abs": 0.0,
               "progress_stored_vs_source_max_abs_before_final": 0.0,
               "progress_stored_positive_final_count": 0,
               "min_act_source_vs_common_max_abs_before_final": 0.0}
    for start, end in zip(starts, ends):
        if str(names[start]) not in eval_agents or int(start) in bad:
            continue
        stop = min(end, start + 250)
        if np.any(root["compute_termination"][start:stop]):
            continue  # This small comparison isolates the clean horizon cutoff.
        x = root["observations"]["poses_x"][start:stop]
        y = root["observations"]["poses_y"][start:stop]
        poses = np.column_stack((x, y))
        progress_source.reset(poses[:1])
        progress = np.array([progress_source.get_progress(poses[i:i+1])[0] for i in range(len(poses))])
        source_progress = ProgressReward()(np.stack((progress, np.zeros_like(progress)), axis=-1)[None], None, None)[0]
        decoded = decode_progress(root["observations"]["progress_sin"][start:stop],
                                  root["observations"]["progress_cos"][start:stop])
        action = root["actions"][start:stop]
        previous = root["observations"]["previous_action_steer"][start:stop]
        common = reward_vectors(decoded, action[:, 0], previous, True)
        source_min_act = MinActReward(-0.4189, 0.4189)(
            {"previous_action_steer": previous}, action, None)[0]
        stored_progress = root["new_rewards"]["reward_progress.json"][start:stop]
        summary["sample_recordings"] += 1
        summary["progress_source_vs_common_max_abs"] = max(summary["progress_source_vs_common_max_abs"],
                                                              float(np.max(np.abs(source_progress - common["progress"]))))
        summary["progress_stored_vs_source_max_abs_before_final"] = max(
            summary["progress_stored_vs_source_max_abs_before_final"],
            float(np.max(np.abs(stored_progress[:-1] - source_progress[:-1]))))
        summary["progress_stored_positive_final_count"] += int(stored_progress[-1] > 0 and source_progress[-1] == 0)
        summary["min_act_source_vs_common_max_abs_before_final"] = max(
            summary["min_act_source_vs_common_max_abs_before_final"],
            float(np.max(np.abs(source_min_act[:-1] - common["min_act"][:-1]))))
        if summary["sample_recordings"] == 3:
            break
    if summary["sample_recordings"] != 3:
        raise ValueError("three eligible clean-cutoff recordings were not found")

    synthetic = np.array([0.95, 0.01, 0.95, 0.01, 0.05])
    source = CheckpointReward()({"progress": synthetic.copy()}, None, None)[0]
    common = reward_vectors(synthetic, np.zeros(5), np.zeros(5), True)["checkpoint"] / 10
    summary["synthetic_checkpoint"] = {
        "progress_laps_mod_one": synthetic.tolist(),
        "upstream_checkpoint_counts_before_terminal_zero": source.tolist(),
        "common_checkpoint_counts_after_terminal_zero": common.tolist(),
        "upstream_second_full_lap_count": float(source[3]),
        "common_second_full_lap_count": float(common[3]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
