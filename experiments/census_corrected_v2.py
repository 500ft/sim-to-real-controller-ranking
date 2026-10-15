"""Structural census of the two pinned Drive ZIPs. Does not read reward values."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import zarr


OBJECTS = {
    "f110-real-stoch-v2": "1ryaq4F3hHIo_klvlj0KlkDBZ9Zd5qI0Q",
    "f110-sim-stoch-v2": "14GnCIa9Bz4ZiOaPjFEnPZLXJIZzamKix",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def census(root, name, archive):
    data = zarr.open(str(root / name), mode="r")
    timestep = data["timestep"][:]
    names = data["model_name"][:]
    done = data["done"][:].astype(bool)
    truncated = data["truncated"][:].astype(bool)
    computed = data["compute_termination"][:].astype(bool)
    log_prob = data["log_prob"][:]
    starts = np.r_[0, np.flatnonzero(timestep[1:] <= timestep[:-1]) + 1]
    ends = np.r_[starts[1:], len(timestep)]
    assert np.all(timestep[starts] == 0)
    assert np.all((done | truncated)[ends - 1])
    assert all(np.all(names[start:end] == names[start]) for start, end in zip(starts, ends))
    assert log_prob.shape == (len(timestep), 1, 2)

    # The original pinned helper scans the full array. The candidate correction
    # stops at each established recording boundary and includes the final row.
    corrected = []
    original = []
    for start, end in zip(starts, ends):
        terminal = computed[start:end]
        first = np.flatnonzero(terminal)
        if len(first):
            assert np.all(terminal[first[0]:]), "nonmonotone terminal run within recording"
            corrected.extend(range(start + int(first[0]) + 1, end))
    changes = np.flatnonzero(np.diff(computed) != 0) + 1
    changes = np.r_[0, changes, len(computed) - 1]
    for start, end in zip(changes[:-1], changes[1:]):
        if computed[start]:
            original.extend(range(start + 1, end))
    corrected = np.array(corrected, dtype=np.int64)
    original = np.array(original, dtype=np.int64)
    changed = np.setxor1d(corrected, original)
    ledger = {
        "archive": name,
        "source_object_id": OBJECTS[name],
        "archive_sha256": sha256(archive),
        "recording_starts": starts.tolist(),
        "recording_ends_exclusive": ends.tolist(),
        "corrected_excluded_indices": corrected.tolist(),
        "original_pinned_excluded_indices": original.tolist(),
        "sensitivity_changed_indices": changed.tolist(),
    }
    finite = np.isfinite(log_prob).all(axis=(1, 2))
    policy = {}
    for policy_name in np.unique(names):
        mask = names == policy_name
        segment_mask = names[starts] == policy_name
        policy[str(policy_name)] = {
            "recordings": int(segment_mask.sum()),
            "rows": int(mask.sum()),
            "finite_joint_log_density_rows": int(np.count_nonzero(finite & mask)),
            "nonzero_log_density_rows": int(np.count_nonzero(np.any(log_prob[mask] != 0, axis=(1, 2)))),
            "corrected_exclusions": int(np.count_nonzero(mask[corrected])),
        }
    summary = {
        "source_object_id": OBJECTS[name],
        "zip_filename": archive.name,
        "zip_size_bytes": archive.stat().st_size,
        "zip_sha256": ledger["archive_sha256"],
        "zarr_root": name,
        "rows": len(timestep),
        "recordings": len(starts),
        "recording_boundary_rule": "timestep resets to zero; each prior row has done or truncated",
        "length_min_max": [int(np.min(ends - starts)), int(np.max(ends - starts))],
        "done_rows": int(done.sum()),
        "truncated_rows": int(truncated.sum()),
        "compute_termination_rows": int(computed.sum()),
        "compute_termination_at_record_end": int(computed[ends - 1].sum()),
        "corrected_excluded_rows": len(corrected),
        "original_pinned_excluded_rows": len(original),
        "sensitivity_changed_rows": len(changed),
        "sensitivity_changed_index_sha256": hashlib.sha256(changed.astype("<i8").tobytes()).hexdigest(),
        "log_prob_shape": list(log_prob.shape),
        "finite_log_density_rows": int(finite.sum()),
        "policies": policy,
        "new_rewards_present": "new_rewards" in data,
    }
    return summary, ledger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("private_data", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--private-ledger", type=Path, required=True)
    args = parser.parse_args()
    summaries, ledgers = {}, {}
    for name in OBJECTS:
        summaries[name], ledgers[name] = census(args.private_data, name, args.private_data / f"{name}.zip")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.private_ledger.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n")
    args.private_ledger.write_text(json.dumps(ledgers, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
