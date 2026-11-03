"""Runtime, memory, determinism and checkpoint benchmark of the reward bridge.

Executes the registered modes, seeds and repeats from one recorded real start
pose. Per-step records stay outside git. The public result characterizes the
bridge; no reward here enters a ranking.
"""

import argparse
import copy
import hashlib
import json
import pickle
import platform
import resource
import time
from pathlib import Path

import numpy as np
import zarr

from experiments.simulator_reward_adapter_v2 import decode_progress, make_compatible_env
from experiments.trace_all_development_rewards_v2 import BAD_REAL_STARTS, digest


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "runs/bridge_runtime_benchmark/protocol.json"
REWARDS = ("progress", "lifetime", "min_act", "checkpoint")


def step_hash(action, obs, components, selected, terminated, truncated, collision):
    sha = hashlib.sha256()
    sha.update(np.ascontiguousarray(action, dtype=np.float64).tobytes())
    for key in sorted(obs):
        value = np.ascontiguousarray(obs[key])
        sha.update(key.encode())
        sha.update(str(value.dtype).encode())
        sha.update(value.tobytes())
    for name in REWARDS:
        sha.update(np.float64(components[name]).tobytes())
    sha.update(np.float64(selected).tobytes())
    sha.update(bytes([int(terminated), int(truncated), int(collision)]))
    return sha.hexdigest()


def registered_start(real_root, agents):
    root = zarr.open(str(real_root), mode="r")
    step = root["timestep"][:]
    names = root["model_name"][:]
    starts = np.r_[0, np.flatnonzero(step[1:] <= step[:-1]) + 1]
    row = next(int(s) for s in starts if str(names[s]) in agents and int(s) not in BAD_REAL_STARTS)
    obs = root["observations"]
    pose = [float(obs["poses_x"][row]), float(obs["poses_y"][row]),
            float(np.arctan2(obs["theta_sin"][row], obs["theta_cos"][row]))]
    velocity = float(obs["previous_action_speed"][row])
    return row, pose, velocity, float(obs["linear_vels_x"][row])


def delta_wrapper(env):
    current = env
    while not type(current).__name__ == "AccelerationAndDeltaSteeringWrapper":
        current = current.env
    return current


def execute(env, obs, actions, first_step, max_steps, ledger, label):
    """Run control steps first_step..max_steps-1; return per-step records."""
    records = []
    started = time.perf_counter()
    for step in range(first_step, max_steps):
        action = np.asarray([actions(step)], dtype=np.float32)
        step_started = time.perf_counter()
        obs, selected, terminated, truncated, info = env.step(action)
        step_seconds = time.perf_counter() - step_started
        components = info["qualified_reward_components"]
        collision = bool(info["collision"])
        record = {"run": label, "step": step, "action": action[0].tolist(),
                  "hash": step_hash(action, obs, components, selected, terminated, truncated, collision),
                  "pose": [float(np.asarray(info["observations"]["poses_x"])[0]),
                           float(np.asarray(info["observations"]["poses_y"])[0])],
                  "progress_after": decode_progress(obs), "step_seconds": step_seconds,
                  "components": {name: float(components[name]) for name in REWARDS},
                  "terminated": bool(terminated), "truncated": bool(truncated), "collision": collision}
        records.append(record)
        ledger.write(json.dumps(record, separators=(",", ":")) + "\n")
        if terminated or truncated:
            break
    elapsed = time.perf_counter() - started
    return records, elapsed


BINS = ((0, 50), (50, 100), (100, 150), (150, 250))


def binned_step_seconds(records):
    out = {}
    for low, high in BINS:
        values = [r["step_seconds"] for r in records if low <= r["step"] < high]
        out[f"{low}-{high - 1}"] = {"steps": len(values), "mean_seconds": float(np.mean(values)) if values else None}
    return out


def summarize(records, elapsed, label, mode, seed, repeat, start_velocity, rng_note):
    return {"label": label, "mode": mode, "seed": seed, "repeat": repeat,
            "step_seconds_by_index": binned_step_seconds(records),
            "executed_steps": len(records), "elapsed_seconds": elapsed,
            "steps_per_second": len(records) / elapsed if elapsed else None,
            "terminated": records[-1]["terminated"], "truncated": records[-1]["truncated"],
            "collision_on_final_step": records[-1]["collision"],
            "last_progress_fraction": records[-1]["progress_after"],
            "reward_sums": {name: float(sum(r["components"][name] for r in records)) for name in REWARDS},
            "trajectory_sha256": hashlib.sha256("".join(r["hash"] for r in records).encode()).hexdigest(),
            "start_velocity_in_wrapper": start_velocity, "global_numpy_rng_at_reset": rng_note}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator-source", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--real-zip", type=Path, required=True)
    parser.add_argument("--real-root", type=Path, required=True)
    parser.add_argument("--private-steps", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    if digest(args.real_zip) != protocol["start"]["archive_zip_sha256"]:
        raise ValueError("corrected real ZIP hash mismatch")
    agents = set(json.loads((ROOT / "runs/ope_corrected_v2/eval_agents.json").read_text()))
    row, pose, velocity, measured = registered_start(args.real_root, agents)
    pose_array = np.asarray([pose], dtype=float)
    max_steps = protocol["maximum_control_steps"]
    fresh_12345 = np.random.RandomState(12345).get_state()

    def rng_note_for(before, after):
        return {"changed": not (np.array_equal(before[1], after[1]) and before[2] == after[2]),
                "equals_fresh_config_seed_state": bool(np.array_equal(after[1], fresh_12345[1]) and after[2] == fresh_12345[2])}

    runs, construction, checkpoints, drawn = [], {}, [], {}
    checkpoint_steps = {check["run"]: check["step"] for check in protocol["checkpoint"]["checks"]}
    args.private_steps.parent.mkdir(parents=True, exist_ok=True)
    with args.private_steps.open("w") as ledger:
        ledger.write(json.dumps({"start_row": row, "pose": pose, "velocity": velocity,
                                 "measured_linear_vels_x": measured}) + "\n")
        memory_after_construction = None
        for mode in protocol["modes"]:
            started = time.perf_counter()
            env = make_compatible_env(args.simulator_source, args.loader_source, map="Infsaal3",
                                      random_start=False, pose_start=True, min_vel=0, max_vel=2, eval=False)
            construction[mode] = time.perf_counter() - started
            if memory_after_construction is None:
                memory_after_construction = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            try:
                for seed in protocol["seeds"]:
                    for repeat in range(protocol["runs_per_seed"]):
                        label = f"{mode}/seed{seed}/run{repeat + 1}"
                        options = {"poses": pose_array.copy()}
                        if mode != "env_velocity":
                            options["velocity"] = velocity
                        rng = np.random.default_rng(seed) if mode == "seeded_actions" else None
                        actions = (lambda step, rng=rng: rng.uniform(-1.0, 1.0, size=2)) if rng is not None \
                            else (lambda step: np.zeros(2))
                        before = np.random.get_state()
                        obs, _ = env.reset(seed=seed, options=options)
                        rng_note = rng_note_for(before, np.random.get_state())
                        start_velocity = float(delta_wrapper(env).current_velocity)
                        drawn.setdefault(mode, {}).setdefault(str(seed), []).append(start_velocity)
                        if label not in checkpoint_steps:
                            records, elapsed = execute(env, obs, actions, 0, max_steps, ledger, label)
                            runs.append(summarize(records, elapsed, label, mode, seed, repeat, start_velocity, rng_note))
                            continue
                        split = checkpoint_steps[label]
                        prefix, elapsed_prefix = execute(env, obs, actions, 0, split, ledger, label)
                        if len(prefix) < split:
                            raise ValueError("checkpoint run ended before the registered checkpoint step")
                        errors, method, blob = {}, None, None
                        saved = time.perf_counter()
                        try:
                            blob = pickle.dumps((env, rng))
                            method = "pickle"
                        except Exception as exc:
                            errors["pickle"] = f"{type(exc).__name__}: {exc}"
                            try:
                                restored_pair = copy.deepcopy((env, rng))
                                method = "deepcopy"
                            except Exception as exc2:
                                errors["deepcopy"] = f"{type(exc2).__name__}: {exc2}"
                                method = "prefix_replay"
                        save_seconds = time.perf_counter() - saved
                        tail, elapsed_tail = execute(env, obs, actions, split, max_steps, ledger, label)
                        records = prefix + tail
                        runs.append(summarize(records, elapsed_prefix + elapsed_tail, label, mode, seed, repeat,
                                              start_velocity, rng_note))
                        restored_at = time.perf_counter()
                        if method == "pickle":
                            env2, rng2 = pickle.loads(blob)
                        elif method == "deepcopy":
                            env2, rng2 = restored_pair
                        else:
                            env2 = make_compatible_env(args.simulator_source, args.loader_source, map="Infsaal3",
                                                       random_start=False, pose_start=True, min_vel=0, max_vel=2,
                                                       eval=False)
                            rng2 = np.random.default_rng(seed)
                            replay_obs, _ = env2.reset(seed=seed, options={"poses": pose_array.copy(), "velocity": velocity})
                            execute(env2, replay_obs, lambda step, rng=rng2: rng.uniform(-1.0, 1.0, size=2),
                                    0, split, ledger, label + "/replay-prefix")
                        restore_seconds = time.perf_counter() - restored_at
                        actions2 = lambda step, rng=rng2: rng.uniform(-1.0, 1.0, size=2)
                        restarted, elapsed_restart = execute(env2, None, actions2, split, max_steps, ledger,
                                                             label + "/restart")
                        checkpoints.append({
                            "run": label, "step": split, "method": method, "errors": errors,
                            "checkpoint_bytes": len(blob) if blob is not None else None,
                            "save_seconds": save_seconds, "restore_seconds": restore_seconds,
                            "steps_compared": min(len(tail), len(restarted)),
                            "uninterrupted_steps_after_checkpoint": len(tail),
                            "restarted_steps_after_checkpoint": len(restarted),
                            "identical_after_restart": [r["hash"] for r in tail] == [r["hash"] for r in restarted],
                        })
                        if method != "prefix_replay":
                            env2.close()
            finally:
                env.close()
        memory_final = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    by_mode = {}
    for mode in protocol["modes"]:
        rates = [r["steps_per_second"] for r in runs if r["mode"] == mode]
        same_seed = {}
        for seed in protocol["seeds"]:
            pair = [r for r in runs if r["mode"] == mode and r["seed"] == seed]
            same_seed[str(seed)] = (len(pair) == 2 and pair[0]["trajectory_sha256"] == pair[1]["trajectory_sha256"]
                                    and pair[0]["executed_steps"] == pair[1]["executed_steps"])
        mode_records = [r for r in runs if r["mode"] == mode]
        step_bins = {}
        for label_bin in (f"{low}-{high - 1}" for low, high in BINS):
            total = sum(r["step_seconds_by_index"][label_bin]["steps"] for r in mode_records)
            weighted = sum(r["step_seconds_by_index"][label_bin]["steps"] * r["step_seconds_by_index"][label_bin]["mean_seconds"]
                           for r in mode_records if r["step_seconds_by_index"][label_bin]["steps"])
            step_bins[label_bin] = {"steps": int(total), "mean_seconds": float(weighted / total) if total else None}
        by_mode[mode] = {
            "runs": len(rates), "executed_steps_total": int(sum(r["executed_steps"] for r in runs if r["mode"] == mode)),
            "step_seconds_by_index": step_bins,
            "steps_per_second": {"min": float(min(rates)), "median": float(np.median(rates)), "max": float(max(rates))},
            "same_seed_bitwise_identical": same_seed,
            "all_same_seed_pairs_identical": all(same_seed.values()),
            "distinct_trajectories_across_seeds_first_run": len({r["trajectory_sha256"] for r in runs
                                                                 if r["mode"] == mode and r["repeat"] == 0}),
            "start_velocity_in_wrapper_by_seed": drawn[mode],
            "global_numpy_rng_changed_by_any_reset": any(r["global_numpy_rng_at_reset"]["changed"]
                                                         for r in runs if r["mode"] == mode),
            "global_numpy_rng_reseeded_to_config_seed_by_any_reset": any(
                r["global_numpy_rng_at_reset"]["equals_fresh_config_seed_state"] for r in runs if r["mode"] == mode),
        }
    env_velocity = by_mode["env_velocity"]
    seed_inert = (by_mode["fixed"]["distinct_trajectories_across_seeds_first_run"] == 1
                  and not env_velocity["all_same_seed_pairs_identical"]
                  and not env_velocity["global_numpy_rng_reseeded_to_config_seed_by_any_reset"])
    result = {
        "protocol": PROTOCOL,
        "candidate_simulator_commit": protocol["candidate_simulator_commit"],
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                     "python": platform.python_version(), "numpy": np.__version__},
        "start": {"row": row, "pose_velocity_sha256": hashlib.sha256(json.dumps([*pose, velocity]).encode()).hexdigest(),
                  "velocity_rule": "previous_action_speed at the start row"},
        "environment_construction_seconds": construction,
        "memory": {"ru_maxrss_after_first_construction": memory_after_construction,
                   "ru_maxrss_final": memory_final,
                   "unit": "bytes on Darwin, kilobytes on Linux"},
        "modes": by_mode,
        "checkpoints": checkpoints,
        "seed_propagation_defect_present": seed_inert,
        "seed_propagation_evidence": "reset seed inert in fixed mode, env_velocity repeats differ, and no reset reseeded the global generator to the config seed; see protocol.seed_propagation_hypothesis",
        "runs": runs,
        "private_steps_sha256": digest(args.private_steps),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"modes": {m: (v["steps_per_second"], v["all_same_seed_pairs_identical"],
                                    v["distinct_trajectories_across_seeds_first_run"]) for m, v in by_mode.items()},
                      "checkpoints": [{k: c[k] for k in ("run", "method", "identical_after_restart", "steps_compared", "errors")}
                                      for c in checkpoints],
                      "seed_defect": seed_inert, "memory": result["memory"]}, sort_keys=True))


if __name__ == "__main__":
    main()
