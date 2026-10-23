"""Reconcile real-v2 per-agent reward aggregates with the pinned Groundtruth.

Every registered variant runs on the same eligible development recordings.
Per-recording returns stay outside git. The committed result holds per-agent
aggregates, differences from the published files and match flags. Nothing
here ranks a controller.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import zarr

from experiments.common_reward_v2 import DISCOUNT, HORIZON, decode_progress, reward_vectors
from experiments.simulator_reward_adapter_v2 import STEERING_LIMIT, TransitionRewards


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "runs/ope_groundtruth_reconciliation/protocol.json"
REWARDS = ("progress", "lifetime", "min_act", "checkpoint")
LOADERS = ("corrected", "original")
FINAL_ROWS = ("zero", "keep")
SOURCES = ("frozen_v2", "departure_aligned", "pinned_source_class", "stored_new_rewards")


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def excluded_masks(terminal, starts, ends):
    """Rows excluded by the corrected rule and by the original pinned helper."""
    terminal = np.asarray(terminal, dtype=bool)
    corrected = np.zeros(len(terminal), dtype=bool)
    original = np.zeros(len(terminal), dtype=bool)
    for start, end in zip(starts, ends):
        hit = np.flatnonzero(terminal[start:end])
        if len(hit):
            corrected[start + hit[0] + 1:end] = True
    # The pinned helper ignores recording boundaries and never touches the last row.
    changes = np.r_[0, np.flatnonzero(np.diff(terminal.astype(np.int8)) != 0) + 1, len(terminal) - 1]
    for left, right in zip(changes[:-1], changes[1:]):
        if terminal[left]:
            original[left + 1:right] = True
    return {"corrected": corrected, "original": original}


def retained_window(start, end, excluded):
    """First HORIZON contiguous retained rows of one recording, or None."""
    rows = np.flatnonzero(~excluded[start:end]) + start
    if not len(rows):
        return None
    if np.any(np.diff(rows) != 1):
        raise ValueError("retained rows of one recording are not contiguous")
    return int(rows[0]), int(min(rows[-1] + 1, rows[0] + HORIZON))


def departure_vectors(progress, target_steering):
    """Bridge rewards per departure row; the last observation has no transition."""
    engine = TransitionRewards()
    engine.reset(progress[0])
    vectors = {name: np.zeros(len(progress)) for name in REWARDS}
    for i in range(len(progress) - 1):
        values = engine.step(progress[i + 1], target_steering[i])
        for name in REWARDS:
            vectors[name][i] = values[name]
    return vectors


def pinned_vectors(pinned, source_progress, previous, actions):
    progress = np.asarray(source_progress, dtype=float)
    return {
        "progress": np.asarray(pinned["progress"](
            np.stack((progress, np.zeros_like(progress)), axis=-1)[None], None, None)[0], dtype=float),
        "lifetime": np.asarray(pinned["lifetime"]({"poses_x": progress}, None, None)[0], dtype=float),
        "min_act": np.asarray(pinned["min_act"](
            {"previous_action_steer": np.asarray(previous, dtype=float)},
            np.asarray(actions, dtype=float), None)[0], dtype=float),
        "checkpoint": 10.0 * np.asarray(pinned["checkpoint"]({"progress": progress.copy()}, None, None)[0], dtype=float),
    }


def recording_variants(window, lookahead, data, pinned=None):
    """Discounted returns for one recording under every final-row and source variant.

    data holds per-row arrays over the window plus one lookahead row when
    ``lookahead`` is true: sin, cos, action (rows, 2), previous, stored (dict)
    and, when ``pinned`` is given, source_progress from the pinned tracker.
    """
    start, stop = window
    n = stop - start
    m = n + int(lookahead)
    weights = DISCOUNT ** np.arange(n)
    returns = {}
    for final_row in FINAL_ROWS:
        rows = n if final_row == "zero" else m
        terminal = final_row == "zero"
        sin, cos = data["sin"][:rows], data["cos"][:rows]
        action, previous = data["action"][:rows], data["previous"][:rows]
        vectors = {
            "frozen_v2": reward_vectors(decode_progress(sin, cos), action[:, 0], previous, terminal),
            "departure_aligned": departure_vectors(
                np.asarray(decode_progress(sin, cos), dtype=float), previous + action[:, 0]),
            "stored_new_rewards": {name: np.asarray(data["stored"][name][:rows], dtype=float).copy()
                                   for name in REWARDS},
        }
        if pinned is not None:
            vectors["pinned_source_class"] = pinned_vectors(pinned, data["source_progress"][:rows], previous, action)
        for source, value in vectors.items():
            value = {name: np.asarray(value[name], dtype=float)[:n].copy() for name in REWARDS}
            if terminal:
                for name in REWARDS:
                    value[name][-1] = 0.0
            elif source == "departure_aligned" and not lookahead:
                # The bridge gives a final observation no outgoing row; the
                # keep variant retains the row's own lifetime and action values.
                value["lifetime"][-1] = 1.0
                value["min_act"][-1] = 1.0 - ((previous[n - 1] + action[n - 1, 0]) / STEERING_LIMIT) ** 2
            returns[f"{final_row}/{source}"] = {name: float(np.dot(weights, value[name])) for name in REWARDS}
    return returns


def aggregate(records, key, agents):
    out = {}
    for agent in agents:
        values = {name: np.array([row["returns"][key][name] for row in records if row["policy"] == agent])
                  for name in REWARDS}
        out[agent] = {name: {"recordings": int(len(value)), "mean": float(np.mean(value)),
                             "std_population": float(np.std(value))} for name, value in values.items()}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-zip", type=Path, required=True)
    parser.add_argument("--real-root", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--centerline", type=Path, required=True)
    parser.add_argument("--groundtruth-dir", type=Path, required=True)
    parser.add_argument("--private-records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    if digest(args.real_zip) != protocol["archive"]["zip_sha256"]:
        raise ValueError("corrected real ZIP hash mismatch")
    for name, expected in protocol["source_sha256"].items():
        path = args.centerline if name.endswith(".csv") else args.loader_source / name
        if digest(path) != expected:
            raise ValueError(f"pinned source hash mismatch: {name}")
    published = {}
    for name in REWARDS:
        path = args.groundtruth_dir / f"gt_reward_{name}.json"
        if digest(path) != protocol["published_groundtruth"]["sha256"][name]:
            raise ValueError(f"published Groundtruth hash mismatch: {name}")
        published[name] = json.loads(path.read_text())

    from f110_orl_dataset.compute_progress import Progress, Track
    from f110_orl_dataset.fast_reward import CheckpointReward, LifetimeReward, MinActReward, ProgressReward
    pinned = {"progress": ProgressReward(), "lifetime": LifetimeReward(),
              "min_act": MinActReward(-STEERING_LIMIT, STEERING_LIMIT), "checkpoint": CheckpointReward()}
    tracker = Progress(Track(args.centerline), lookahead=200)

    agents = json.loads((ROOT / protocol["selection"]["agents"]).read_text())
    bad = set(protocol["selection"]["excluded_recording_starts"])
    root = zarr.open(str(args.real_root), mode="r")
    step = root["timestep"][:]
    names = root["model_name"][:]
    terminal = root["compute_termination"][:].astype(bool)
    obs = root["observations"]
    sin, cos = obs["progress_sin"][:], obs["progress_cos"][:]
    x, y = obs["poses_x"][:], obs["poses_y"][:]
    previous = obs["previous_action_steer"][:]
    actions = root["actions"][:]
    stored = {name: root["new_rewards"][f"reward_{name}.json"][:] for name in REWARDS}
    starts = np.r_[0, np.flatnonzero(step[1:] <= step[:-1]) + 1]
    ends = np.r_[starts[1:], len(step)]
    masks = excluded_masks(terminal, starts, ends)

    records = []
    counts = {loader: {"eligible": 0, "dropped_by_loader": 0} for loader in LOADERS}
    skipped_bad = 0
    for start, end in zip(starts, ends):
        if str(names[start]) not in agents:
            continue
        if int(start) in bad:
            skipped_bad += 1
            continue
        record = {"start": int(start), "end_exclusive": int(end), "policy": str(names[start]),
                  "retained_end_exclusive": {}, "returns": {}}
        for loader in LOADERS:
            window = retained_window(int(start), int(end), masks[loader])
            if window is None:
                counts[loader]["dropped_by_loader"] += 1
                continue
            counts[loader]["eligible"] += 1
            a, b = window
            lookahead = b < int(end)
            m = b - a + int(lookahead)
            poses = np.column_stack((x[a:a + m], y[a:a + m])).astype(float)
            tracker.reset(poses[:1])
            source_progress = np.array([tracker.get_progress(poses[i:i + 1])[0] for i in range(m)])
            data = {"sin": sin[a:a + m], "cos": cos[a:a + m], "action": actions[a:a + m],
                    "previous": previous[a:a + m], "source_progress": source_progress,
                    "stored": {name: stored[name][a:a + m] for name in REWARDS}}
            record["retained_end_exclusive"][loader] = b
            for key, value in recording_variants(window, lookahead, data, pinned).items():
                record["returns"][f"{loader}/{key}"] = value
        records.append(record)
    if not records:
        raise ValueError("no eligible development recordings")
    args.private_records.parent.mkdir(parents=True, exist_ok=True)
    args.private_records.write_text(json.dumps(records, separators=(",", ":")) + "\n")

    variants = [f"{loader}/{final_row}/{source}"
                for loader, final_row, source in itertools.product(LOADERS, FINAL_ROWS, SOURCES)]
    aggregates = {key: aggregate([r for r in records if key in r["returns"]], key, agents) for key in variants}

    frozen = json.loads((ROOT / "runs/ope_corrected_v2/reward_aggregates.json").read_text())["f110-real-stoch-v2"]["policies"]
    self_check = max(abs(aggregates["corrected/zero/frozen_v2"][agent][name][field] - frozen[agent][name][field])
                     for agent in agents for name in REWARDS for field in ("mean", "std_population"))
    if self_check > 1e-9:
        raise ValueError(f"frozen variant does not reproduce reward_aggregates.json: {self_check}")

    tolerance = protocol["comparison"]
    result_variants = {}
    for key in variants:
        per_agent = {}
        for agent in agents:
            per_agent[agent] = {}
            for name in REWARDS:
                local = aggregates[key][agent][name]
                reference = published[name][agent]
                mean_difference = local["mean"] - reference["mean"]
                std_difference = local["std_population"] - reference["std"]
                per_agent[agent][name] = {
                    "recordings": local["recordings"], "mean": local["mean"], "std_population": local["std_population"],
                    "mean_difference": mean_difference, "std_difference": std_difference,
                    "match": bool(abs(mean_difference) <= tolerance["mean_abs_tolerance"]
                                  and abs(std_difference) <= tolerance["std_abs_tolerance"])}
        result_variants[key] = {
            "matching_agents": {name: sum(per_agent[agent][name]["match"] for agent in agents) for name in REWARDS},
            "max_abs_mean_difference": {name: max(abs(per_agent[agent][name]["mean_difference"]) for agent in agents)
                                        for name in REWARDS},
            "max_abs_std_difference": {name: max(abs(per_agent[agent][name]["std_difference"]) for agent in agents)
                                       for name in REWARDS},
            "per_agent": dict(sorted(per_agent.items())),
        }
    best = {}
    for name in REWARDS:
        top = max(result_variants[key]["matching_agents"][name] for key in variants)
        winners = [key for key in variants if result_variants[key]["matching_agents"][name] == top]
        best[name] = {"matching_agents": top, "variants": winners,
                      "failing_agents": sorted(agent for agent in agents
                                               if not result_variants[winners[0]]["per_agent"][agent][name]["match"])}
    complete = [key for key in variants
                if all(result_variants[key]["matching_agents"][name] == len(agents) for name in REWARDS)]
    loader_inert = all(
        aggregates[f"corrected/{suffix}"] == aggregates[f"original/{suffix}"]
        for suffix in (f"{final_row}/{source}" for final_row in FINAL_ROWS for source in SOURCES))
    result = {
        "protocol": PROTOCOL,
        "real_zip_sha256": digest(args.real_zip),
        "published_groundtruth_sha256": protocol["published_groundtruth"]["sha256"],
        "private_record_sha256": digest(args.private_records),
        "agents": len(agents),
        "skipped_registered_bad_recordings": skipped_bad,
        "recordings_by_loader": counts,
        "frozen_self_check_max_abs_difference": self_check,
        "tolerance": tolerance,
        "loader_axis_inert_for_evaluation_agents": loader_inert,
        "variants_matching_all_agents_on_all_rewards": complete,
        "best_variant_by_reward": best,
        "variants": result_variants,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"complete": complete, "best": {name: (best[name]["matching_agents"], best[name]["variants"][0])
                                                      for name in REWARDS},
                      "loader_inert": loader_inert, "self_check": self_check}, sort_keys=True))


if __name__ == "__main__":
    main()
