"""Run the preregistered public-start simulator smoke, with local step evidence."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.simulator_reward_adapter_v2 import decode_progress, make_compatible_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator-source", type=Path, required=True)
    parser.add_argument("--loader-source", type=Path, required=True)
    parser.add_argument("--gym-source", type=Path, required=True)
    parser.add_argument("--private-steps", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((Path(__file__).parents[1] / "runs/ope_reward_adapter_qualification/protocol.json").read_text())
    smoke = protocol["smoke_rollout"]
    centerline_path = args.gym_source / "gym/f110_gym/maps/Infsaal3/Infsaal3_centerline.csv"
    centerline = np.loadtxt(centerline_path, delimiter=",")
    x, y = centerline[0, :2]
    dx, dy = centerline[1, :2] - centerline[0, :2]
    pose = np.array([[x, y, np.arctan2(dy, dx)]])
    env = make_compatible_env(args.simulator_source, args.loader_source, map=smoke["map"],
                              random_start=False, pose_start=True, min_vel=0, max_vel=2, eval=False)
    rows = []
    try:
        obs, _ = env.reset(seed=smoke["seed"], options={"poses": pose, "velocity": 0.5})
        previous_progress = decode_progress(obs)
        unwrapped = previous_progress
        initial = previous_progress
        for step in range(smoke["maximum_control_steps"]):
            action = np.asarray([smoke["normalized_action_each_step"]], dtype=np.float32)
            obs, selected_reward, done, truncated, info = env.step(action)
            progress = decode_progress(obs)
            delta = progress - previous_progress
            if delta < -0.9:
                delta += 1
            if -0.9 <= delta < -0.5:
                raise ValueError("ambiguous backward progress jump")
            prior_unwrapped = unwrapped
            unwrapped += delta
            thresholds = np.arange(1, int(np.ceil(10 * unwrapped)) + 1) / 10
            independently_crossed = sum(initial < t and prior_unwrapped <= t < unwrapped for t in thresholds)
            physical = np.asarray(info["action_raw"])[0]
            reported = info["qualified_reward_components"]
            expected = {
                "progress": 100 * max(delta, 0),
                "lifetime": 1.0,
                "min_act": 1 - (float(physical[0]) / 0.4189) ** 2,
                "checkpoint": 10 * independently_crossed,
            }
            for name in smoke["reward_definitions"]:
                if not np.isclose(reported[name], expected[name], atol=1e-6, rtol=0):
                    raise AssertionError(f"step {step}: {name} differs from independent calculation")
            if not np.isclose(selected_reward, reported["progress"], atol=1e-12):
                raise AssertionError("selected reward differs from progress component")
            rows.append({"step": step, "progress_before": previous_progress, "progress_after": progress,
                         "normalized_action": action[0].tolist(),
                         "delta_action": np.asarray(info["action_delta"])[0].tolist(),
                         "physical_action": physical.tolist(), "components": reported,
                         "terminated": bool(done), "truncated": bool(truncated),
                         "collision": bool(info["collision"]),
                         "pose_x": float(np.asarray(info["observations"]["poses_x"])[0]),
                         "pose_y": float(np.asarray(info["observations"]["poses_y"])[0])})
            previous_progress = progress
            if done or truncated:
                break
    finally:
        env.close()
    args.private_steps.parent.mkdir(parents=True, exist_ok=True)
    args.private_steps.write_text(json.dumps(rows, separators=(",", ":")) + "\n")
    summary = {
        "protocol": "runs/ope_reward_adapter_qualification/protocol.json",
        "public_centerline_sha256": hashlib.sha256(centerline_path.read_bytes()).hexdigest(),
        "executed_control_steps": len(rows),
        "terminated": rows[-1]["terminated"], "truncated": rows[-1]["truncated"],
        "collision_on_final_step": rows[-1]["collision"],
        "first_progress_fraction": rows[0]["progress_before"],
        "last_progress_fraction": rows[-1]["progress_after"],
        "reward_sums": {name: float(sum(row["components"][name] for row in rows))
                        for name in smoke["reward_definitions"]},
        "private_steps_sha256": hashlib.sha256(args.private_steps.read_bytes()).hexdigest(),
        "independent_step_alignment": "passed for all executed steps and four reward components",
        "physics_scope": "pinned candidate simulator and gym; fixed public start, velocity and zero normalized actions; historical simulator identity unknown"
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
