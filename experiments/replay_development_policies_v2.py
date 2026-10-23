"""Replay pinned policy likelihoods on corrected real-v2 development records."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import zarr

from experiments.policy_density_v2 import independent_density, target_from_delta


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-zip", type=Path, required=True)
    parser.add_argument("--real-root", type=Path, required=True)
    parser.add_argument("--agents-source", type=Path, required=True)
    parser.add_argument("--private-rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=ROOT / "runs/ope_policy_interface_qualification/protocol.json",
                        help="registered protocol; the default is the real-v2 replay, the sim-v2 replay passes its own")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    protocol_path = str(args.protocol.resolve().relative_to(ROOT))
    agents_root = args.agents_source.resolve()
    import subprocess
    revision = subprocess.check_output(["git", "-C", str(agents_root), "rev-parse", "HEAD"], text=True).strip()
    if revision != protocol["agents_revision"]:
        raise ValueError("agents revision mismatch")
    if digest(args.real_zip) != protocol["archive"]["zip_sha256"]:
        raise ValueError("real ZIP hash mismatch")
    for name, expected in protocol["source_sha256"].items():
        if digest(agents_root / name) != expected:
            raise ValueError(f"agent source hash mismatch: {name}")
    for name, spec in protocol["configs"].items():
        if digest(agents_root / "agent_configs" / (name + ".json")) != spec["sha256"]:
            raise ValueError(f"agent config hash mismatch: {name}")
    sys.path.insert(0, str(agents_root))
    from f110_agents.agent import Agent

    root = zarr.open(str(args.real_root), mode="r")
    steps = root["timestep"][:]
    names = root["model_name"][:]
    termination = root["compute_termination"][:]
    done = root["done"][:]
    truncated = root["truncated"][:]
    actions = root["actions"][:]
    raw_actions = root["raw_actions"][:]
    recorded_log = root["log_prob"][:, 0, :]
    obs_root = root["observations"]
    keys = protocol["observations"]["fields"]
    observations = {key: obs_root[key][:] for key in keys}
    starts = np.r_[0, np.flatnonzero(steps[1:] <= steps[:-1]) + 1]
    ends = np.r_[starts[1:], len(steps)]
    selected = set(protocol["configs"])
    bad = set(protocol["selection"]["excluded_recording_starts"])
    counts = Counter()
    by_policy = defaultdict(lambda: Counter())
    maxima = defaultdict(lambda: defaultdict(float))
    errors = Counter()
    args.private_rows.parent.mkdir(parents=True, exist_ok=True)
    with args.private_rows.open("w") as output:
        for start, end in zip(starts, ends):
            name = str(names[start])
            if name not in selected:
                continue
            counts["attempted_recordings"] += 1
            if int(start) in bad:
                counts["excluded_recordings"] += 1
                by_policy[name]["excluded_recordings"] += 1
                continue
            counts["eligible_recordings"] += 1
            by_policy[name]["eligible_recordings"] += 1
            stop = min(int(end), int(start) + 250)
            hit = np.flatnonzero(termination[start:stop])
            if len(hit):
                stop = int(start) + int(hit[0]) + 1
            idx = slice(int(start), stop)
            current = {key: value[idx].copy() for key, value in observations.items()}
            recorded_delta = actions[idx]
            previous = np.column_stack((current["previous_action_steer"], current["previous_action_speed"]))
            spec = protocol["configs"][name]
            agent = Agent().load(name=name, no_print=True)
            agent.reset()
            try:
                np.random.seed(0)  # Source likelihood call samples internally; sampled actions are discarded.
                _, deterministic_mean, _ = agent(current, deterministic=True)
                _, _, source_log = agent(current, actions=recorded_delta)
                effective_previous = previous.copy()
                if spec["class"] == "FTGAgent":
                    effective_previous[:, 1] = np.clip(effective_previous[:, 1], 0, spec["parameters"]["max_speed"])
                independent, support, lower, upper = independent_density(
                    recorded_delta, deterministic_mean, effective_previous,
                    spec["parameters"]["max_delta"], spec["parameters"]["max_speed"],
                    spec["parameters"]["std_vel"], spec["parameters"]["std_steer"])
                source_log = np.asarray(source_log)
                if source_log.shape != independent.shape:
                    raise ValueError(f"density shape {source_log.shape}, expected {independent.shape}")
                target = target_from_delta(previous, recorded_delta)
                source_difference = abs(source_log - recorded_log[idx])
                independent_difference = abs(independent - source_log)
                target_difference = abs(target - raw_actions[idx])
                finite = np.isfinite(source_log) & np.isfinite(independent) & np.isfinite(recorded_log[idx])
                acceptable = protocol["comparison"]
                for j, row in enumerate(range(int(start), stop)):
                    ok = bool(finite[j].all() and support[j].all())
                    obs_gap = float(np.max(source_difference[j])) if finite[j].all() else float("inf")
                    independent_gap = float(np.max(independent_difference[j])) if finite[j].all() else float("inf")
                    target_gap = float(np.max(target_difference[j]))
                    target_mismatch = target_gap > acceptable["deterministic_mean_abs_tolerance"]
                    zero_raw = bool(np.all(raw_actions[row] == 0))
                    by_policy[name]["rows"] += 1
                    counts["executed_rows"] += 1
                    counts["unsupported_rows"] += int(not support[j].all())
                    counts["nonfinite_rows"] += int(not finite[j].all())
                    counts["source_density_mismatch_rows"] += int(obs_gap > acceptable["stored_log_density_abs_tolerance"])
                    counts["independent_density_mismatch_rows"] += int(independent_gap > acceptable["density_formula_abs_tolerance"])
                    counts["target_mismatch_rows"] += int(target_mismatch)
                    counts["target_mismatch_done_zero_final_rows"] += int(
                        target_mismatch and bool(done[row]) and bool(termination[row])
                        and not bool(truncated[row]) and zero_raw and row == stop-1)
                    by_policy[name]["unsupported_rows"] += int(not support[j].all())
                    by_policy[name]["nonfinite_rows"] += int(not finite[j].all())
                    by_policy[name]["source_density_mismatch_rows"] += int(obs_gap > acceptable["stored_log_density_abs_tolerance"])
                    by_policy[name]["independent_density_mismatch_rows"] += int(independent_gap > acceptable["density_formula_abs_tolerance"])
                    by_policy[name]["target_mismatch_rows"] += int(target_mismatch)
                    for label, value in (("source_density", obs_gap), ("independent_density", independent_gap),
                                         ("target", target_gap)):
                        maxima[name][label] = max(maxima[name][label], value)
                    output.write(json.dumps({
                        "row": row, "recording_start": int(start), "policy": name,
                        "terminal_row": row == stop-1, "done": bool(done[row]),
                        "compute_termination": bool(termination[row]),
                        "truncated": bool(truncated[row]), "raw_target_zero": zero_raw,
                        "action_delta": recorded_delta[j].tolist(), "deterministic_mean": deterministic_mean[j].tolist(),
                        "previous_target": previous[j].tolist(), "raw_target": raw_actions[row].tolist(),
                        "lower": lower[j].tolist(), "upper": upper[j].tolist(),
                        "support_speed_steering": support[j].tolist(),
                        "recorded_log_speed_steering": recorded_log[row].tolist(),
                        "source_log_speed_steering": source_log[j].tolist(),
                        "independent_log_speed_steering": independent[j].tolist(),
                        "source_density_abs_error": obs_gap,
                        "independent_density_abs_error": independent_gap,
                        "target_abs_error": target_gap, "finite_and_supported": ok
                    }, separators=(",", ":"), allow_nan=True) + "\n")
                counts["executed_recordings"] += 1
                by_policy[name]["executed_recordings"] += 1
            except Exception as exc:
                counts["failed_recordings"] += 1
                by_policy[name]["failed_recordings"] += 1
                errors[f"{type(exc).__name__}: {exc}"] += 1
                output.write(json.dumps({"recording_start": int(start), "policy": name,
                                         "exception": f"{type(exc).__name__}: {exc}"}) + "\n")
    result = {
        "protocol": protocol_path,
        "archive_drive_object_id": protocol["archive"]["drive_object_id"],
        "archive_sha256": digest(args.real_zip),
        "agents_revision": revision,
        "private_rows_sha256": digest(args.private_rows),
        "counts": dict(counts), "exceptions": dict(errors),
        "policy_coverage": {name: {"family": protocol["configs"][name]["class"],
                                   "counts": dict(by_policy[name]), "max_abs_error": dict(maxima[name])}
                            for name in protocol["configs"]},
        "comparison_rule": protocol["comparison"],
        "exact_stochastic_draw_replay": "unavailable: original RNG state or innovation not archived",
        "unreconstructible_exact_draw_recordings": counts["eligible_recordings"],
        "unreconstructible_exact_draw_rows": counts["executed_rows"],
        "gate": "pass" if counts["executed_recordings"] == counts["eligible_recordings"]
                         and not any(counts[k] for k in ("unsupported_rows", "nonfinite_rows",
                             "source_density_mismatch_rows", "independent_density_mismatch_rows",
                             "target_mismatch_rows")) else "failed"
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"counts": result["counts"], "gate": result["gate"],
                      "exceptions": result["exceptions"]}, sort_keys=True))


if __name__ == "__main__":
    main()
