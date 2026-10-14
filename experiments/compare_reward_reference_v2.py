"""Compare frozen real-v2 reward aggregates to the pinned public Groundtruth."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("aggregates", type=Path)
    parser.add_argument("groundtruth_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    local = json.loads(args.aggregates.read_text())["f110-real-stoch-v2"]["policies"]
    comparison = {}
    for reward in ("progress", "lifetime", "min_act", "checkpoint"):
        source = args.groundtruth_dir / f"gt_reward_{reward}.json"
        published = json.loads(source.read_text())
        assert set(published) == set(local)
        errors = {
            name: {
                "mean": local[name][reward]["mean"] - reference["mean"],
                "std_population": local[name][reward]["std_population"] - reference["std"],
            }
            for name, reference in published.items()
        }
        comparison[reward] = {
            "published_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "agents": len(errors),
            "maximum_absolute_mean_difference": max(abs(item["mean"]) for item in errors.values()),
            "maximum_absolute_std_difference": max(abs(item["std_population"]) for item in errors.values()),
            "per_agent_differences": dict(sorted(errors.items())),
        }
    args.out.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
