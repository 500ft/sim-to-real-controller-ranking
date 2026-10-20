"""Trace registered corrected-v2 real development recordings on one cohort.

Per-record values stay in a local artifact. The committed summary compares
reward definitions on identical recordings; it does not infer membership of
the benchmark's published Groundtruth aggregates.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import zarr

from experiments.common_reward_v2 import decode_progress, reward_vectors
from experiments.simulator_reward_adapter_v2 import TransitionRewards


BAD_REAL_STARTS = {161444, 283691, 82322, 202835, 152551, 268314, 155685, 161312, 278488}
REWARDS = ("progress", "lifetime", "min_act", "checkpoint")


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def discounted(vectors):
    return {name: float(np.dot(0.99 ** np.arange(len(value)), value))
            for name, value in vectors.items()}


def summarize(values):
    values = np.asarray(values, dtype=float)
    return {"count": int(len(values)), "mean": float(np.mean(values)),
            "max_abs": float(np.max(np.abs(values))),
            "nonzero_over_1e_6": int(np.count_nonzero(np.abs(values) > 1e-6))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-zip", type=Path, required=True)
    parser.add_argument("--real-root", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--centerline", type=Path, required=True)
    parser.add_argument("--private-records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((Path(__file__).parents[1] / "runs/ope_reward_adapter_qualification/protocol.json").read_text())
    parent = json.loads((Path(__file__).parents[1] / protocol["parent_protocol"]).read_text())
    if digest(args.real_zip) != parent["archive_zip_sha256"]["f110-real-stoch-v2"]:
        raise ValueError("corrected real ZIP hash mismatch")
    for filename, key in (("fast_reward.py", "fast_reward.py"),
                          ("compute_progress.py", "compute_progress.py")):
        if digest(args.loader_source / "f110_orl_dataset" / filename) != parent["upstream_reward_sources_sha256"][key]:
            raise ValueError(f"pinned {filename} hash mismatch")

    from f110_orl_dataset.compute_progress import Progress, Track
    from f110_orl_dataset.fast_reward import CheckpointReward, LifetimeReward, MinActReward, ProgressReward

    root = zarr.open(str(args.real_root), mode="r")
    step = root["timestep"][:]
    names = root["model_name"][:]
    terminal = root["compute_termination"][:]
    starts = np.r_[0, np.flatnonzero(step[1:] <= step[:-1]) + 1]
    ends = np.r_[starts[1:], len(step)]
    agents = set(json.loads((Path(__file__).parents[1] / "runs/ope_corrected_v2/eval_agents.json").read_text()))
    obs = root["observations"]
    sin_p = obs["progress_sin"][:]
    cos_p = obs["progress_cos"][:]
    x = obs["poses_x"][:]
    y = obs["poses_y"][:]
    previous = obs["previous_action_steer"][:]
    actions = root["actions"][:]
    stored = {name: root["new_rewards"][f"reward_{name}.json"][:] for name in REWARDS}
    tracker = Progress(Track(args.centerline), lookahead=200)
    private = []
    skipped_bad = 0
    reason_counts = {"first_compute_termination": 0, "horizon": 0, "recording_end": 0}
    final_transition_checkpoint = {reason: {"recordings": 0, "reward_total": 0.0}
                                   for reason in reason_counts}
    cutoff_positive = {name: 0 for name in REWARDS}
    for start, end in zip(starts, ends):
        if str(names[start]) not in agents:
            continue
        if int(start) in BAD_REAL_STARTS:
            skipped_bad += 1
            continue
        stop = min(int(end), int(start) + 250)
        hit = np.flatnonzero(terminal[start:stop])
        if len(hit):
            stop = int(start) + int(hit[0]) + 1
            reason = "first_compute_termination"
        elif stop == int(start) + 250:
            reason = "horizon"
        else:
            reason = "recording_end"
        reason_counts[reason] += 1
        if stop - start < 2:
            raise ValueError("one-row eligible recording needs separate reward handling")
        p = decode_progress(sin_p[start:stop], cos_p[start:stop])
        v2 = reward_vectors(p, actions[start:stop, 0], previous[start:stop], True)

        engine = TransitionRewards()
        engine.reset(p[0])
        aligned = {name: np.zeros(stop - start) for name in REWARDS}
        for i in range(stop - start - 1):
            values = engine.step(p[i + 1], previous[start + i] + actions[start + i, 0])
            for name in REWARDS:
                aligned[name][i] = values[name]

        poses = np.column_stack((x[start:stop], y[start:stop]))
        tracker.reset(poses[:1])
        source_p = np.array([tracker.get_progress(poses[i:i + 1])[0] for i in range(len(poses))])
        source = {
            "progress": ProgressReward()(
                np.stack((source_p, np.zeros_like(source_p)), axis=-1)[None], None, None)[0],
            "lifetime": LifetimeReward()({"poses_x": x[start:stop]}, None, None)[0],
            "min_act": MinActReward(-0.4189, 0.4189)(
                {"previous_action_steer": previous[start:stop]}, actions[start:stop], None)[0],
            "checkpoint": 10 * CheckpointReward()({"progress": source_p.copy()}, None, None)[0],
        }
        for value in source.values():
            value[-1] = 0
        stored_slice = {name: stored[name][start:stop] for name in REWARDS}
        for name in REWARDS:
            cutoff_positive[name] += int(stored_slice[name][-1] > 1e-6)
        last_crossing = float(aligned["checkpoint"][-2])
        final_transition_checkpoint[reason]["recordings"] += int(last_crossing > 0)
        final_transition_checkpoint[reason]["reward_total"] += last_crossing
        returns = {"frozen_v2": discounted(v2), "aligned_candidate": discounted(aligned),
                   "pinned_source_class": discounted(source), "stored": discounted(stored_slice)}
        private.append({"start": int(start), "end_exclusive": int(end),
                        "retained_end_exclusive": int(stop), "policy": str(names[start]),
                        "end_reason": reason,
                        "last_departure_checkpoint_reward": last_crossing,
                        "returns": returns,
                        "differences_from_aligned_candidate": {
                            variant: {name: returns[variant][name] - returns["aligned_candidate"][name]
                                      for name in REWARDS}
                            for variant in ("frozen_v2", "pinned_source_class", "stored")},
                        "last_stored_rewards": {name: float(stored_slice[name][-1]) for name in REWARDS}})
    if not private:
        raise ValueError("no eligible development recordings")
    args.private_records.parent.mkdir(parents=True, exist_ok=True)
    args.private_records.write_text(json.dumps(private, separators=(",", ":")) + "\n")
    variants = ("frozen_v2", "aligned_candidate", "pinned_source_class", "stored")
    result = {
        "protocol": "runs/ope_reward_adapter_qualification/protocol.json",
        "real_zip_sha256": digest(args.real_zip),
        "private_record_sha256": digest(args.private_records),
        "eligible_recordings": len(private), "skipped_registered_bad_recordings": skipped_bad,
        "end_reasons": reason_counts, "positive_stored_final_rows": cutoff_positive,
        "final_transition_checkpoint": final_transition_checkpoint,
        "same_cohort_return_means": {
            variant: {name: float(np.mean([row["returns"][variant][name] for row in private]))
                      for name in REWARDS} for variant in variants},
        "same_cohort_return_differences": {
            f"{left}_minus_{right}": {
                name: summarize([row["returns"][left][name] - row["returns"][right][name]
                                 for row in private]) for name in REWARDS}
            for left, right in (("frozen_v2", "aligned_candidate"),
                                ("pinned_source_class", "aligned_candidate"),
                                ("stored", "aligned_candidate"))},
        "published_groundtruth_membership": "unknown; no direct equivalence claim"
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"eligible_recordings": len(private), "end_reasons": reason_counts,
                      "private_record_sha256": result["private_record_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
