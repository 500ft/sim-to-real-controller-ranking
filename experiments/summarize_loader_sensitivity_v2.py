"""Whole-record reward sensitivity to the original global terminal helper."""

import argparse
import json
from pathlib import Path

import zarr

from experiments.common_reward_v2 import archive_aggregates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("private_data", type=Path)
    parser.add_argument("private_ledger", type=Path)
    parser.add_argument("aggregates", type=Path)
    parser.add_argument("eval_agents", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    ledger = json.loads(args.private_ledger.read_text())
    corrected = json.loads(args.aggregates.read_text())
    eval_agents = set(json.loads(args.eval_agents.read_text()))
    result = {}
    for name in ("f110-real-stoch-v2", "f110-sim-stoch-v2"):
        root = zarr.open(str(args.private_data / name), mode="r")
        changed = ledger[name]["sensitivity_changed_indices"]
        assert all(root["timestep"][index] == 0 for index in changed)
        affected = {str(root["model_name"][index]) for index in changed}
        active = [index for index in changed if str(root["model_name"][index]) in eval_agents]
        result[name] = {
            "changed_reset_rows": len(changed),
            "affected_policy_names": sorted(affected),
            "evaluation_reset_rows_changed": len(active),
            "evaluation_reward_changes": {},
        }
        if active:
            original = archive_aggregates(args.private_data / name, eval_agents, set(active))
            for policy in sorted({str(root["model_name"][index]) for index in active}):
                result[name]["evaluation_reward_changes"][policy] = {
                    reward: {
                        "corrected_recordings": corrected[name]["policies"][policy][reward]["recordings"],
                        "original_recordings": original["policies"][policy][reward]["recordings"],
                        "corrected_minus_original_mean": corrected[name]["policies"][policy][reward]["mean"]
                        - original["policies"][policy][reward]["mean"],
                    }
                    for reward in ("progress", "lifetime", "min_act", "checkpoint")
                }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
