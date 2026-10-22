#!/usr/bin/env python
"""Summarize registered paired delay sensitivity; no probability model implied."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import figure_style

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_pipeline"
SCENARIOS = ("nominal", "control_delay_20ms", "control_delay_50ms")
CONTROLLERS = ("pure_pursuit", "lqr", "mpc")


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

    figure_style.apply("controller-delay-sensitivity")
    fig, axes = figure_style.subplots(1, 3, height_in=3.1, width_in=7.5, sharey=True)
    labels = ["Nominal", "20 ms", "50 ms"]
    for index, (ax, (a, b)) in enumerate(zip(axes, combinations(CONTROLLERS, 2))):
        subset = [item for item in comparisons if item["pair"] == f"{a}|{b}"]
        ax.axhspan(-near, near, color="0.88")
        figure_style.zero_line(ax)
        values = [item["delta_lap_s"] for item in subset]
        ax.plot(range(3), values, marker="o", color="black", lw=1.0, ms=3.5)
        ax.set_xticks(range(3), labels)
        figure_style.letter(ax, index)
        ax.set_xlabel("delay")
        ax.set_ylim(-0.13, 0.37)
    axes[0].set_ylabel("Gym finish difference [s]")
    figure_style.legend(fig, [Patch(facecolor="0.88", edgecolor="black", label="registered near tie")], ncol=1)
    caption = ("One example-track simulation with fixed nominal physics and source-listed command delays. "
               "Panels (a), (b), (c) show PP minus LQR, PP minus MPC, and LQR minus MPC. "
               "The shaded region is the registered ±0.1 s near-tie interval, not uncertainty. "
               "All three pairs completed in every scenario; none reversed outside that interval. "
               "Source: runs/controller_pipeline/delay_sensitivity.json. "
               "The delay values are perturbation assumptions, not an identified model distribution.")
    figure_style.save(fig, ROOT / "reports/figures/controller_delay_sensitivity.png", caption,
                      formats=("png", "svg"))
    return result


if __name__ == "__main__":
    print(json.dumps(analyze()["comparisons"], indent=2))
