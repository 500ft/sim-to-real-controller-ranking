#!/usr/bin/env python
"""Build the readable controller result from committed JSON sources."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_pipeline"
REPORT = ROOT / "reports/controller_pipeline.md"
NAMES = {"pure_pursuit": "PP", "lqr": "LQR", "mpc": "MPC"}


def read(name: str):
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else None


def run_table(files: list[str]) -> str:
    rows = ["| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for filename in files:
        x = read(filename)
        if x is None:
            continue
        complete = x["completed_lap"] and not x["collision"]
        label = NAMES[x["controller"]]
        run = x["run_id"].replace("_nominal_", " ").replace("_", " ")
        lap = f"{x['lap_time_s']:.3f}" if complete else "NA"
        rows.append(f"| {label} | {run} | {x['termination_reason']} | {lap} | "
                    f"{x['rms_reference_distance_m']:.4f} | {x['max_abs_cte_m']:.4f} | "
                    f"{x['steering_effort_rad']:.3f} | "
                    f"{1000*x['control_compute_p95_s']:.2f} / {1000*x['control_compute_max_s']:.2f} | "
                    f"{x['control_deadline_misses']} | [JSON](../runs/controller_pipeline/{filename}) |")
    return "\n".join(rows)


def main() -> None:
    protocol = read("protocol.json")
    delay = read("delay_sensitivity.json")
    maps = []
    for name, item in protocol["maps"].items():
        status = "geometry qualified; source speed exceeds limits" if name == "example" else item["eligibility"]
        source = f"[source](../{item['line']})" if item["line"] else "none"
        maps.append(f"| {name} | {status} | {source} |")
    map_table = "\n".join(["| Map | Line status | Ordered line |", "| --- | --- | --- |", *maps])
    baseline = [f"baseline_nominal_{name}.json" for name in NAMES]
    constrained = ["constrained60_nominal_pure_pursuit.json", "constrained_nominal_lqr.json",
                   "constrained_nominal_mpc.json", "constrained_nominal_pure_pursuit.json"]
    tuning = [f"ctune{i}_nominal_{name}.json" for name in NAMES for i in range(3)]
    evaluation = [f"ceval_nominal_{name}.json" for name in NAMES]
    caption = (ROOT / "reports/figures/controller_delay_sensitivity.caption.md").read_text().strip()
    sections = ["# Simulation controller pipeline", "",
                "The example-track legacy replay reproduces the recorded Gym finish times. "
                "A separate constrained target-speed line supports development runs on that same map. "
                "The installed map set supplies no other ordered line, so multi-track coverage and the offline line-improvement gate remain open.",
                "", "## Source and method", "",
                "[Frozen protocol](../runs/controller_pipeline/protocol.json), "
                "[constrained-line protocol](../runs/controller_pipeline/constrained_run_protocol.json), "
                "[tuning protocol](../runs/controller_pipeline/tuning_constrained_protocol.json), "
                "[line qualification](../runs/controller_pipeline/line_qualification.json) and "
                "[map inventory](../runs/controller_pipeline/protocol.json) bind source files, settings and selection rules. "
                "The old claimed simulator revision could not be retrieved. Checked-in simulator and example bytes match "
                "the separately verified MIT upstream candidate in the protocol. This reproduces the checked-in setup, "
                "without establishing the historical Git revision. All traces are simulator output.",
                "", "The planner reads the native semicolon waypoint columns. Geometry checks cover closure, ordering, "
                "self-intersection, tangent/curvature and the sampled expanded vehicle perimeter against the map raster "
                "using its declared origin and resolution. The source geometry passes. Its speed schedule exceeds "
                "the registered lateral and forward target limits. The derived arc-length line meets those target "
                "profile limits; actual vehicle acceleration and controller timing are reported separately. "
                "The derived line is a speed-profile replacement on the same geometry, not a new track.",
                "", "The [initial geometry-only qualification]"
                "(../runs/controller_pipeline/line_qualification_initial.json) omitted the source-speed check. "
                "The corrected result retains that record. Three exploratory legacy-line LQR tuning runs "
                "([candidate 0](../runs/controller_pipeline/tune0_nominal_lqr.json), "
                "[1](../runs/controller_pipeline/tune1_nominal_lqr.json), "
                "[2](../runs/controller_pipeline/tune2_nominal_lqr.json)) were stopped at that finding "
                "and excluded from the constrained cohort.",
                "", "Gym's finish rule requires later checkpoint visits. A first forward geometric crossing occurs "
                "earlier than the reported Gym finish; both are retained in each run JSON. The source Gym code "
                "requires four near-start toggles and the completed legacy traces show lap_count 2 at termination. "
                "The tables below use Gym finish time, not a one-circuit crossing time.",
                "", "## Map coverage", "", map_table,
                "", "Five installed maps lack a qualified ordered line. Levine's YAML also names a missing PNG. "
                "The raster alone cannot resolve loop order or junction choices. No line was invented for those maps.",
                "", "## Legacy source-line replay", "", run_table(baseline),
                "", "The [synchronized video](../runs/controller_pipeline/example_controller_overlay.mp4) "
                "uses each 2 ms telemetry stream directly. "
                "[Preview](../runs/controller_pipeline/example_controller_preview.png). "
                "Its colors and marker shapes distinguish controllers; time, map axes and terminal states remain visible.",
                "", "## Constrained target-speed line", "", run_table(constrained),
                "", "The original 45 s PP run was truncated. Its [registered horizon amendment]"
                "(../runs/controller_pipeline/constrained60_amendment.json) kept the completed LQR/MPC traces "
                "and reran PP to a 60 s upper horizon. Source target-speed limits do not certify closed-loop "
                "acceleration or real-time MPC execution."]
    if any(read(file) for file in tuning):
        sections += ["", "## Equal-budget offline tuning", "", run_table(tuning)]
        frozen = read("frozen_constrained_selection.json")
        if frozen:
            sections += ["", "Selections were frozen in "
                         "[frozen_constrained_selection.json](../runs/controller_pipeline/frozen_constrained_selection.json) "
                         "before zero-offset evaluation."]
    if any(read(file) for file in evaluation):
        sections += ["", "## Frozen zero-offset evaluation", "", run_table(evaluation)]
        comparison = ["| Controller | Prior constrained Gym finish [s] | Frozen evaluation [s] | Change [s] | RMS distance change [m] |",
                      "| --- | ---: | ---: | ---: | ---: |"]
        for name in NAMES:
            prior_file = ("constrained60_nominal_pure_pursuit.json" if name == "pure_pursuit"
                          else f"constrained_nominal_{name}.json")
            prior, current = read(prior_file), read(f"ceval_nominal_{name}.json")
            comparison.append(f"| {NAMES[name]} | {prior['lap_time_s']:.3f} | {current['lap_time_s']:.3f} | "
                              f"{current['lap_time_s']-prior['lap_time_s']:+.3f} | "
                              f"{current['rms_reference_distance_m']-prior['rms_reference_distance_m']:+.4f} |")
        sections += ["", "## Same-track controller-tuning comparison", "", *comparison,
                     "", "The frozen search minimized tracking distance on offset starts, not lap time. "
                     "The zero-offset evaluation reduced RMS distance for each controller; MPC's Gym finish "
                     "became slower. This is one-track offline controller tuning, with no line optimization "
                     "or multi-track speed-improvement claim."]
    if delay:
        sections += ["", "## Delay sensitivity on the legacy line", "",
                     "![Three paired Gym finish-time differences over nominal, 20 ms and 50 ms command delays]"
                     "(figures/controller_delay_sensitivity.png)", "", caption,
                     "[Caption file](figures/controller_delay_sensitivity.caption.md) · "
                     "[SVG](figures/controller_delay_sensitivity.svg) · "
                     "[source differences](../runs/controller_pipeline/delay_sensitivity.json)."]
    sections += ["", "## Reproduce", "", "Use the repository's Python 3.9 Gym environment from `environment.yml`. "
                 "The commands below read only checked-in example assets; no driving archive is accessed.",
                 "", "```bash", "export PYTHONPATH=gym", "python -m unittest roboracer.test_reference_line -v",
                 "python experiments/controller_pipeline.py qualify",
                 "python experiments/controller_pipeline.py baseline",
                 "python experiments/controller_pipeline.py constrained_baseline",
                 "python experiments/controller_pipeline.py constrained60_pp",
                 "python experiments/controller_pipeline.py sensitivity",
                 "python experiments/controller_dispersion.py",
                 "python experiments/controller_pipeline.py tune_constrained",
                 "python experiments/controller_pipeline.py freeze_constrained",
                 "python experiments/controller_pipeline.py evaluate_constrained",
                 "python experiments/controller_video.py",
                 "python experiments/controller_pipeline_report.py", "```", "",
                 "Run order matters: the frozen protocol and line artifact must exist before simulation, "
                 "and selection must be frozen before evaluation. Video and plot generators read committed telemetry/JSON. "
                 "Per-run compressed telemetry, source hashes and full metrics are in "
                 "[runs/controller_pipeline](../runs/controller_pipeline/protocol.json).",
                 "", "## Remaining gate", "", "A multi-track comparison needs a permitted, ordered line for "
                 "another installed map and the same qualification on it. An identified joint vehicle-model region "
                 "is absent, so the delay figure is a sensitivity check only. The registered multi-track feasibility "
                 "condition for offline line optimization has not been met. The paper's M2, M3 and reserved cases remain closed."]
    REPORT.write_text("\n".join(sections) + "\n")
    print(REPORT)


if __name__ == "__main__":
    main()
