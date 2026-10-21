"""Retain every control tick publicly and keep full 2 ms integration traces local."""

from __future__ import annotations

import gzip
import io
import json
import shutil
from pathlib import Path

import pandas as pd

from experiments.controller_combinations import OUT, PROTOCOL, ROOT, read, sha


def compact() -> None:
    protocol = read(PROTOCOL)
    local = OUT / "full"
    local.mkdir(parents=True, exist_ok=True)
    for track in protocol["tracks"]:
        for timing, scenarios in protocol["timing_modes"].items():
            for scenario in scenarios:
                for name in protocol["architecture_order"]:
                    stem = f"{track}_{scenario}_{timing}_{name}"
                    result_path = OUT / f"{stem}.json"
                    result = read(result_path)
                    if result.get("telemetry_sampling") == "every control tick plus terminal integration step":
                        continue
                    full = ROOT / result["telemetry"]
                    if sha(full) != result["telemetry_sha256"]:
                        raise ValueError(f"Changed full integration trace: {full}")
                    full_hash = sha(full)
                    frame = pd.read_csv(full)
                    sampled = frame[(frame["step"] - 1) % frame["hold_steps"] == 0]
                    sampled = pd.concat([sampled, frame.iloc[[-1]]]).drop_duplicates("step")
                    path = OUT / f"{stem}_control.csv.gz"
                    with path.open("wb") as raw:
                        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                                sampled.to_csv(text, index=False)
                    shutil.move(str(full), str(local / full.name))
                    result.update({"telemetry": str(path.relative_to(ROOT)),
                                   "telemetry_sha256": sha(path),
                                   "telemetry_rows": len(sampled),
                                   "telemetry_sampling": "every control tick plus terminal integration step",
                                   "full_integration_telemetry_sha256": full_hash,
                                   "full_integration_telemetry_local": str((local / full.name).relative_to(ROOT))})
                    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
                    print(stem, len(frame), "integration rows ->", len(sampled), "public control rows", flush=True)


if __name__ == "__main__":
    compact()
