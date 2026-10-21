#!/usr/bin/env python
"""Summarize registered paired delay sensitivity; no probability model implied."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_pipeline"
SCENARIOS = ("nominal", "control_delay_20ms", "control_delay_50ms")
CONTROLLERS = ("pure_pursuit", "lqr", "mpc")
NAMES = {"pure_pursuit": "PP", "lqr": "LQR", "mpc": "MPC"}
COLORS = {"pure_pursuit": "#0072B2", "lqr": "#D55E00", "mpc": "#009E73"}


def analyze() -> dict:
    protocol = json.loads((OUT / "protocol.json").read_text())
    near = float(protocol["dispersion_sandbox"]["near_tie_s"])
    runs = {}
    for scenario in SCENARIOS:
        for name in CONTROLLERS:
            path = OUT / f"baseline_{scenario}_{name}.json"
            runs[(scenario, name)] = json.loads(path.read_text())
            assert runs[(scenario, name)]["scenario"] == scenario
            assert runs[(scenario, name)]["initial_offset_m"] == 0
            trace = pd.read_csv(OUT / f"baseline_{scenario}_{name}.csv.gz", usecols=["time_s"])
            assert len(trace) == runs[(scenario, name)]["n_steps"]
    comparisons = []
    for a, b in combinations(CONTROLLERS, 2):
        nominal = runs[("nominal", a)]["lap_time_s"] - runs[("nominal", b)]["lap_time_s"]
        for scenario in SCENARIOS:
            ra, rb = runs[(scenario, a)], runs[(scenario, b)]
            complete = all(r["completed_lap"] and not r["collision"] for r in (ra, rb))
            delta = float(ra["lap_time_s"] - rb["lap_time_s"]) if complete else None
            comparisons.append({"pair": f"{a}|{b}", "scenario": scenario,
                                "delta_lap_s": delta,
                                "a_status": ra["termination_reason"], "b_status": rb["termination_reason"],
                                "near_tie": (abs(delta) <= near) if delta is not None else None,
                                "sign_reversal_outside_tie": bool(abs(nominal) > near and abs(delta) > near
                                                              and np.sign(nominal) != np.sign(delta)) if delta is not None else None})
    result = {"scope": "one example track, fixed nominal physics, source-listed command delays only",
              "seed_provenance": "F110Env default 12345 in pinned checked-in source; legacy baseline traces omit explicit seed column",
              "distribution_claim": "none; delay values are sensitivity assumptions, not an identified joint region",
              "near_tie_s": near, "runs": {f"{s}|{n}": {"status": r["termination_reason"],
                                              "lap_time_s": r["lap_time_s"] if r["completed_lap"] and not r["collision"] else None,
                                              "n_steps": r["n_steps"]}
                                          for (s, n), r in runs.items()},
              "comparisons": comparisons}
    (OUT / "delay_sensitivity.json").write_text(json.dumps(result, indent=2) + "\n")

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5), sharey=True, constrained_layout=True)
    labels = ["Nominal", "20 ms", "50 ms"]
    for ax, (a, b) in zip(axes, combinations(CONTROLLERS, 2)):
        subset = [item for item in comparisons if item["pair"] == f"{a}|{b}"]
        ax.axhspan(-near, near, color="#E7E7E7", label="registered near tie")
        ax.axhline(0, color="black", lw=0.8)
        values = [item["delta_lap_s"] for item in subset]
        ax.plot(range(3), values, marker="o", color=COLORS[a], lw=1.7)
        ax.set_xticks(range(3), labels)
        ax.set_title(f"{NAMES[a]} − {NAMES[b]}")
        ax.grid(axis="y", alpha=0.2)
        ax.set_xlabel("command delay assumption")
    axes[0].set_ylabel("Gym finish-time difference [s]")
    fig.suptitle("Paired controller timing sensitivity | example simulation")
    fig.savefig(OUT / "delay_sensitivity.png", dpi=180)
    fig.savefig(OUT / "delay_sensitivity.svg")
    plt.close(fig)
    return result


if __name__ == "__main__":
    print(json.dumps(analyze()["comparisons"], indent=2))
