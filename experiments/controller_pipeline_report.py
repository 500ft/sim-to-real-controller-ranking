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


def berlin_table(files: list[str]) -> str:
    rows = ["| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for filename in files:
        path = OUT / "mapzoo_berlin" / filename
        if not path.exists():
            continue
        x = json.loads(path.read_text())
        complete = x["completed_lap"] and not x["collision"]
        lap = f"{x['lap_time_s']:.3f}" if complete else "NA"
        rows.append(f"| {NAMES[x['controller']]} | {x['run_id'].replace('_', ' ')} | {x['termination_reason']} | {lap} | "
                    f"{x['rms_reference_distance_m']:.4f} | {x['max_abs_cte_m']:.4f} | "
                    f"{x['steering_effort_rad']:.3f} | "
                    f"{1000*x['control_compute_p95_s']:.2f} / {1000*x['control_compute_max_s']:.2f} | "
                    f"{x['control_deadline_misses']} | [JSON](../runs/controller_pipeline/mapzoo_berlin/{filename}) |")
    return "\n".join(rows)


def main() -> None:
    protocol = read("protocol.json")
    delay = read("delay_sensitivity.json")
    maps = []
    for name, item in protocol["maps"].items():
        status = "geometry qualified; source speed exceeds limits" if name == "example" else item["eligibility"]
        source = f"[source](../{item['line']})" if item["line"] else "none"
        maps.append(f"| {name} | {status} | {source} |")
    maps.append("| MapZoo Berlin (public expansion) | source geometry qualified; derived target speed qualified | "
                "[source and line](../runs/controller_pipeline/mapzoo_berlin/qualification.json) |")
    map_table = "\n".join(["| Map | Line status | Ordered line |", "| --- | --- | --- |", *maps])
    baseline = [f"baseline_nominal_{name}.json" for name in NAMES]
    constrained = ["constrained60_nominal_pure_pursuit.json", "constrained_nominal_lqr.json",
                   "constrained_nominal_mpc.json", "constrained_nominal_pure_pursuit.json"]
    tuning = [f"ctune{i}_nominal_{name}.json" for name in NAMES for i in range(3)]
    evaluation = [f"ceval_nominal_{name}.json" for name in NAMES]
    caption = (ROOT / "reports/figures/controller_delay_sensitivity.caption.md").read_text().strip()
    sections = ["# Simulation controller pipeline", "",
                "The example-track legacy replay reproduces the recorded Gym finish times. "
                "Constrained target-speed lines support development runs on that map and the distinct, "
                "pinned public MapZoo Berlin map. The original installed map set supplies no second ordered line.",
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
                "The raster alone cannot resolve loop order or junction choices. No line was invented for those maps. "
                "The separately sourced MapZoo Berlin line expands the development cohort; it is not the installed Gym Berlin map.",
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
                     "became slower. These example-track tuning runs alone establish no line-optimization "
                     "or multi-track speed-improvement claim."]
    if delay:
        sections += ["", "## Delay sensitivity on the legacy line", "",
                     "![Three paired Gym finish-time differences over nominal, 20 ms and 50 ms command delays]"
                     "(figures/controller_delay_sensitivity.png)", "", caption,
                     "[Caption file](figures/controller_delay_sensitivity.caption.md) · "
                     "[SVG](figures/controller_delay_sensitivity.svg) · "
                     "[source differences](../runs/controller_pipeline/delay_sensitivity.json)."]
    berlin_dir = OUT / "mapzoo_berlin"
    if (berlin_dir / "evaluation_mpc.json").exists():
        files = [f"{phase}_{name}.json" for phase in ("baseline", "evaluation") for name in NAMES]
        sections += ["", "## Public MapZoo Berlin development track", "",
                     "[Pinned source and license](../third_party/mapzoo_berlin/SOURCE.json), "
                     "[prospective run protocol](../runs/controller_pipeline/mapzoo_berlin/expansion_protocol.json), "
                     "[line qualification](../runs/controller_pipeline/mapzoo_berlin/qualification.json) and "
                     "[frozen selection](../runs/controller_pipeline/mapzoo_berlin/frozen_selection.json) "
                     "bind the map, derived speed profile and equal-budget controller tuning. "
                     "All three controllers completed a lap without collision on the source corridor.",
                     "", berlin_table(files), "",
                     "[Synchronized simulation video](../runs/controller_pipeline/mapzoo_berlin/controller_overlay.mp4) "
                     "and [preview](../runs/controller_pipeline/mapzoo_berlin/controller_preview.png) "
                     "sample the three telemetry streams directly. The MPC frozen evaluation is slower "
                     "than its untuned baseline; every run is retained."]
        tuning_files = [f"tune{i}_{name}.json" for name in NAMES for i in range(3)]
        sections += ["", "### Registered controller tuning", "", berlin_table(tuning_files),
                     "", "Each controller received three configurations on the same offset start. "
                     "The minimum eligible independent RMS distance selected the frozen configuration, "
                     "before the zero-offset evaluation above."]
    offline = berlin_dir / "offline_frozen_choice.json"
    if offline.exists():
        selected = json.loads(offline.read_text())
        rows = ["| Candidate order | Smoothness weight | Mean tuning Gym finish [s] | All controllers completed | Source |",
                "| ---: | ---: | ---: | --- | --- |"]
        for i, (weight, item) in enumerate(selected["candidates"].items()):
            value = f"{item['mean_tuning_gym_finish_s']:.3f}" if item["mean_tuning_gym_finish_s"] is not None else "NA"
            rows.append(f"| {i} | {weight} | {value} | {'yes' if item['eligible'] else 'no'} | "
                        "[candidate](../runs/controller_pipeline/mapzoo_berlin/offline_frozen_choice.json) |")
        sections += ["", "## Frozen offline line comparison", "",
                     "The [prospective smoothing protocol](../runs/controller_pipeline/mapzoo_berlin/offline_line_protocol.json) "
                     "defines a periodic quadratic second-difference objective, then checks actual curvature, "
                     "map clearance and the speed profile on each exported line. The objective is an approximation "
                     "to smoothness, not exact minimum curvature. Every line receives the same three-setting "
                     "controller budget on a shared world start. The source line and every candidate remain in the ledger.",
                     "", *rows, "",
                     "The [selected line and controller settings](../runs/controller_pipeline/mapzoo_berlin/offline_frozen_choice.json) "
                     "were frozen before zero-offset evaluation."]
        if selected["chosen_weight"] is not None and (berlin_dir / f"offline_w{selected['chosen_weight']}_evaluation_mpc.json").exists():
            weight = selected["chosen_weight"]
            rows = ["| Controller | Source-line evaluation [s] | Selected-line evaluation [s] | Change [s] | Status |",
                    "| --- | ---: | ---: | ---: | --- |"]
            limits = ["| Controller | Selected-line max speed [m/s] | Max speed × yaw-rate proxy [m/s²] | Max absolute longitudinal acceleration [m/s²] | Deadline misses |",
                      "| --- | ---: | ---: | ---: | ---: |"]
            for name in NAMES:
                prior = json.loads((berlin_dir / f"evaluation_{name}.json").read_text())
                current = json.loads((berlin_dir / f"offline_w{weight}_evaluation_{name}.json").read_text())
                old = prior["lap_time_s"] if prior["completed_lap"] and not prior["collision"] else None
                new = current["lap_time_s"] if current["completed_lap"] and not current["collision"] else None
                rows.append(f"| {NAMES[name]} | {old:.3f} | {new:.3f} | {new-old:+.3f} | {current['termination_reason']} |"
                            if old is not None and new is not None else
                            f"| {NAMES[name]} | {old if old is not None else 'NA'} | {new if new is not None else 'NA'} | NA | {current['termination_reason']} |")
                limits.append(f"| {NAMES[name]} | {current['max_speed_mps']:.3f} | "
                              f"{current['max_abs_lat_accel_mps2']:.3f} | "
                              f"{current['max_abs_long_accel_mps2']:.3f} | "
                              f"{current['control_deadline_misses']} |")
            sections += ["", *rows, "", *limits, "",
                         "The target line passes its 4 m/s² lateral and 2 m/s² forward speed-profile limits, "
                         "but all three closed-loop runs exceed those values in the telemetry's "
                         "speed × yaw-rate proxy and longitudinal acceleration. LQR and MPC also exceed "
                         "the 8 m/s target speed cap. The lateral proxy omits lateral-velocity derivative, "
                         "so it is not a complete body acceleration measurement. The faster Gym times are "
                         "retained as constraint-failing development observations, not an accepted "
                         "speed-optimization result. "
                         "The MPC also misses its 10 ms compute deadline in the ideal-time replay."]
            for stem, alt in (("controller_offline_progress", "Frozen Berlin candidate mean and evaluation lap-time changes"),
                              ("controller_offline_overlay", "Zoomed Berlin source and selected lines with before and after controller trajectories")):
                image = ROOT / "reports/figures" / f"{stem}.png"
                if image.exists():
                    caption = image.with_name(f"{stem}.caption.md").read_text().strip()
                    sections += ["", f"![{alt}](figures/{stem}.png)", "", caption,
                                 f"[SVG](figures/{stem}.svg) · [caption](figures/{stem}.caption.md)."]
    sensitivity = OUT / "model_sensitivity" / "summary.json"
    if sensitivity.exists():
        comparison = json.loads(sensitivity.read_text())
        rows = ["| Track | Model | Pair | Gym finish difference [s] | Near tie | Reversal outside tie |",
                "| --- | --- | --- | ---: | --- | --- |"]
        for item in comparison["comparisons"]:
            delta = f"{item['delta_lap_s']:+.3f}" if item["delta_lap_s"] is not None else "NA"
            a, b = item["pair"].split("|")
            near = "yes" if item["near_tie"] else "no" if item["near_tie"] is not None else "NA"
            reversed_outside = ("yes" if item["sign_reversal_outside_tie"] else "no"
                                if item["sign_reversal_outside_tie"] is not None else "NA")
            rows.append(f"| {item['track']} | {item['model']} | {NAMES[a]} minus {NAMES[b]} | "
                        f"{delta} | {near} | {reversed_outside} |")
        indexed = {(x["track"], x["pair"], x["model"]): x for x in comparison["comparisons"]}
        max_shift = max(abs(x["delta_lap_s"] - indexed[x["track"], x["pair"], "nominal"]["delta_lap_s"])
                        for x in comparison["comparisons"] if x["delta_lap_s"] is not None)
        reversals = sum(x["sign_reversal_outside_tie"] is True for x in comparison["comparisons"])
        sections += ["", "## Paired model sensitivity", "",
                     "The [frozen model set](../runs/controller_pipeline/model_sensitivity_protocol.json) "
                     "uses paired stiffness fits from prior synthetic identification. These are labeled "
                     "simulation assumptions, not a measured joint uncertainty distribution. The noise "
                     "and quantization labels describe the earlier fit conditions; this replay changes "
                     "stiffness only and injects no observation noise. Each controller "
                     "pair shares the map, line, start, seed and model; collisions have no invented lap time.",
                     "", *rows, "",
                     f"The largest signed-pair change from nominal is {max_shift:.3f} s; "
                     f"{reversals} registered comparisons reverse outside the near-tie region. "
                     "Gym finish is resolved on the 2 ms integration grid, so these small changes "
                     "do not establish general robustness. "
                     "[Source differences](../runs/controller_pipeline/model_sensitivity/summary.json)."]
        image = ROOT / "reports/figures/controller_model_dispersion.png"
        if image.exists():
            caption = image.with_name("controller_model_dispersion.caption.md").read_text().strip()
            sections += ["", "![Paired finish differences over four simulator stiffness variants on two development tracks]"
                         "(figures/controller_model_dispersion.png)", "", caption,
                         "[SVG](figures/controller_model_dispersion.svg) · "
                         "[caption](figures/controller_model_dispersion.caption.md)."]
    sections += ["", "## Reproduce", "", "Use the repository's Python 3.9 Gym environment from `environment.yml`. "
                 "The commands below read checked-in example and licensed public MapZoo assets; no driving archive is accessed.",
                 "", "```bash", "export PYTHONPATH=gym:.", "python -m unittest roboracer.test_reference_line -v",
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
                 "python -m experiments.prepare_mapzoo_berlin",
                 "python -m experiments.run_mapzoo_berlin baseline",
                 "python -m experiments.run_mapzoo_berlin tune",
                 "python -m experiments.run_mapzoo_berlin freeze",
                 "python -m experiments.run_mapzoo_berlin evaluate",
                 "python experiments/controller_video.py --track mapzoo_berlin",
                 "python -m experiments.mapzoo_offline_line prepare",
                 "python -m experiments.mapzoo_offline_line tune",
                 "python -m experiments.mapzoo_offline_line freeze",
                 "python -m experiments.mapzoo_offline_line evaluate",
                 "python -m experiments.controller_model_sensitivity pilot",
                 "python -m experiments.controller_model_sensitivity nominal",
                 "python -m experiments.controller_model_sensitivity variants",
                 "python -m experiments.controller_model_sensitivity analyze",
                 "python experiments/controller_multitrack_figures.py",
                 "python experiments/controller_pipeline_report.py", "```", "",
                 "Run order matters: the frozen protocol and line artifact must exist before simulation, "
                 "and selection must be frozen before evaluation. Video and plot generators read committed telemetry/JSON. "
                 "Per-run compressed telemetry, source hashes and full metrics are in "
                 "[runs/controller_pipeline](../runs/controller_pipeline/protocol.json).",
                 "", "## Remaining gate", "", "The original five map exclusions remain. A measured joint "
                 "vehicle-model region and compute-delay-aware execution are absent, so the paired variants "
                 "are development sensitivity only. The paper's M2, M3 and reserved cases remain closed."]
    REPORT.write_text("\n".join(sections) + "\n")
    print(REPORT)


if __name__ == "__main__":
    main()
