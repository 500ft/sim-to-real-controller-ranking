"""Check pinned policies on declared synthetic scalar, batch and reset cases."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from experiments.policy_density_v2 import independent_density


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((ROOT / "runs/ope_policy_interface_qualification/protocol.json").read_text())
    root = args.agents_source.resolve()
    for name, expected in protocol["source_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"source hash mismatch: {name}")
    sys.path.insert(0, str(root))
    from f110_agents.agent import Agent

    scans = np.full((4, 54), .8)
    scans[1, :20] = .1
    scans[2, 30:] = .2
    scans[3, 20:28] = .1
    obs = {
        "poses_x": np.array([0., 1., -1., 2.]),
        "poses_y": np.array([0., .5, 1., -1.]),
        "theta_sin": np.sin([-.6, 0., .5, 1.2]),
        "theta_cos": np.cos([-.6, 0., .5, 1.2]),
        "previous_action_steer": np.array([-.1, 0., .1, -.2]),
        "previous_action_speed": np.array([.6, 1., 2., 4.8]),
        "lidar_occupancy": scans
    }
    permutation = np.array([3, 1, 0, 2])
    result = {}
    for name, spec in protocol["configs"].items():
        agent = Agent().load(name=name, no_print=True)
        agent.reset()
        _, batch, _ = agent({k: v.copy() for k, v in obs.items()}, deterministic=True)
        singles = np.concatenate([
            agent({k: v[i:i+1].copy() for k, v in obs.items()}, deterministic=True)[1]
            for i in range(4)
        ])
        agent.reset()
        _, reset, _ = agent({k: v.copy() for k, v in obs.items()}, deterministic=True)
        _, permuted, _ = agent({k: v[permutation].copy() for k, v in obs.items()}, deterministic=True)
        np.random.seed(0)
        _, _, source_log = agent({k: v.copy() for k, v in obs.items()}, actions=batch.copy())
        previous = np.column_stack((obs["previous_action_steer"], obs["previous_action_speed"]))
        if spec["class"] == "FTGAgent":
            previous[:, 1] = np.clip(previous[:, 1], 0, spec["parameters"]["max_speed"])
        independent, support, _, _ = independent_density(
            batch, batch, previous, spec["parameters"]["max_delta"], spec["parameters"]["max_speed"],
            spec["parameters"]["std_vel"], spec["parameters"]["std_steer"])
        errors = {
            "scalar_batch": float(np.max(abs(batch - singles))),
            "reset": float(np.max(abs(batch - reset))),
            "permutation": float(np.max(abs(batch[permutation] - permuted))),
            "independent_density": float(np.max(abs(source_log - independent))),
        }
        result[name] = {"family": spec["class"], "max_abs_error": errors,
                        "support_all": bool(support.all()),
                        "pass": bool(support.all() and all(v <= 1e-6 for v in errors.values()))}
    output = {"protocol": "runs/ope_policy_interface_qualification/protocol.json",
              "cases_per_policy": 4, "policy_count": len(result),
              "all_pass": all(p["pass"] for p in result.values()), "per_policy": result}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"policy_count": len(result), "all_pass": output["all_pass"]}))


if __name__ == "__main__":
    main()
