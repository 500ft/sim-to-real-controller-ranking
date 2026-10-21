# Simulation controller pipeline

The example-track legacy replay reproduces the recorded Gym finish times. A separate constrained target-speed line supports development runs on that same map. The installed map set supplies no other ordered line, so multi-track coverage and the offline line-improvement gate remain open.

## Source and method

[Frozen protocol](../runs/controller_pipeline/protocol.json), [constrained-line protocol](../runs/controller_pipeline/constrained_run_protocol.json), [tuning protocol](../runs/controller_pipeline/tuning_constrained_protocol.json), [line qualification](../runs/controller_pipeline/line_qualification.json) and [map inventory](../runs/controller_pipeline/protocol.json) bind source files, settings and selection rules. The old claimed simulator revision could not be retrieved. Checked-in simulator and example bytes match the separately verified MIT upstream candidate in the protocol. This reproduces the checked-in setup, without establishing the historical Git revision. All traces are simulator output.

The planner reads the native semicolon waypoint columns. Geometry checks cover closure, ordering, self-intersection, tangent/curvature and the sampled expanded vehicle perimeter against the map raster using its declared origin and resolution. The source geometry passes. Its speed schedule exceeds the registered lateral and forward target limits. The derived arc-length line meets those target profile limits; actual vehicle acceleration and controller timing are reported separately. The derived line is a speed-profile replacement on the same geometry, not a new track.

The [initial geometry-only qualification](../runs/controller_pipeline/line_qualification_initial.json) omitted the source-speed check. The corrected result retains that record. Three exploratory legacy-line LQR tuning runs ([candidate 0](../runs/controller_pipeline/tune0_nominal_lqr.json), [1](../runs/controller_pipeline/tune1_nominal_lqr.json), [2](../runs/controller_pipeline/tune2_nominal_lqr.json)) were stopped at that finding and excluded from the constrained cohort.

Gym's finish rule requires later checkpoint visits. A first forward geometric crossing occurs earlier than the reported Gym finish; both are retained in each run JSON. The source Gym code requires four near-start toggles and the completed legacy traces show lap_count 2 at termination. The tables below use Gym finish time, not a one-circuit crossing time.

## Map coverage

| Map | Line status | Ordered line |
| --- | --- | --- |
| berlin | excluded: no ordered source line; map raster alone does not select a unique closed loop | none |
| example | geometry qualified; source speed exceeds limits | [source](../examples/example_waypoints.csv) |
| levine | excluded: no ordered source line; map raster alone does not select a unique closed loop | none |
| skirk | excluded: no ordered source line; map raster alone does not select a unique closed loop | none |
| stata_basement | excluded: no ordered source line; map raster alone does not select a unique closed loop | none |
| vegas | excluded: no ordered source line; map raster alone does not select a unique closed loop | none |

Five installed maps lack a qualified ordered line. Levine's YAML also names a missing PNG. The raster alone cannot resolve loop order or junction choices. No line was invented for those maps.

## Legacy source-line replay

| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PP | baseline pure pursuit | completed_lap | 38.042 | 0.1579 | 0.4031 | 8.199 | 0.16 / 6.21 | 0 | [JSON](../runs/controller_pipeline/baseline_nominal_pure_pursuit.json) |
| LQR | baseline lqr | completed_lap | 38.064 | 0.1786 | 0.4977 | 8.988 | 0.25 / 6.21 | 0 | [JSON](../runs/controller_pipeline/baseline_nominal_lqr.json) |
| MPC | baseline mpc | completed_lap | 37.860 | 0.1692 | 0.4767 | 8.677 | 2.86 / 27.44 | 22 | [JSON](../runs/controller_pipeline/baseline_nominal_mpc.json) |

The [synchronized video](../runs/controller_pipeline/example_controller_overlay.mp4) uses each 2 ms telemetry stream directly. [Preview](../runs/controller_pipeline/example_controller_preview.png). Its colors and marker shapes distinguish controllers; time, map axes and terminal states remain visible.

## Constrained target-speed line

| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PP | constrained60 pure pursuit | completed_lap | 49.286 | 0.0843 | 0.3680 | 12.270 | 0.15 / 8.55 | 0 | [JSON](../runs/controller_pipeline/constrained60_nominal_pure_pursuit.json) |
| LQR | constrained lqr | completed_lap | 43.492 | 0.1220 | 0.4127 | 10.916 | 0.23 / 11.47 | 1 | [JSON](../runs/controller_pipeline/constrained_nominal_lqr.json) |
| MPC | constrained mpc | completed_lap | 43.124 | 0.1208 | 0.3906 | 11.073 | 2.00 / 27.72 | 10 | [JSON](../runs/controller_pipeline/constrained_nominal_mpc.json) |
| PP | constrained pure pursuit | max_steps | NA | 0.0856 | 0.3680 | 11.303 | 0.15 / 17.69 | 1 | [JSON](../runs/controller_pipeline/constrained_nominal_pure_pursuit.json) |

The original 45 s PP run was truncated. Its [registered horizon amendment](../runs/controller_pipeline/constrained60_amendment.json) kept the completed LQR/MPC traces and reran PP to a 60 s upper horizon. Source target-speed limits do not certify closed-loop acceleration or real-time MPC execution.

## Equal-budget offline tuning

| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PP | ctune0 pure pursuit | completed_lap | 49.240 | 0.0828 | 0.6180 | 14.022 | 0.14 / 5.97 | 0 | [JSON](../runs/controller_pipeline/ctune0_nominal_pure_pursuit.json) |
| PP | ctune1 pure pursuit | completed_lap | 49.292 | 0.0966 | 0.6180 | 12.652 | 0.15 / 10.17 | 1 | [JSON](../runs/controller_pipeline/ctune1_nominal_pure_pursuit.json) |
| PP | ctune2 pure pursuit | completed_lap | 49.372 | 0.1205 | 0.6180 | 11.152 | 0.16 / 7.21 | 0 | [JSON](../runs/controller_pipeline/ctune2_nominal_pure_pursuit.json) |
| LQR | ctune0 lqr | completed_lap | 43.486 | 0.1300 | 0.6180 | 11.089 | 0.22 / 5.84 | 0 | [JSON](../runs/controller_pipeline/ctune0_nominal_lqr.json) |
| LQR | ctune1 lqr | completed_lap | 43.504 | 0.1338 | 0.6180 | 11.334 | 0.24 / 14.19 | 1 | [JSON](../runs/controller_pipeline/ctune1_nominal_lqr.json) |
| LQR | ctune2 lqr | completed_lap | 43.538 | 0.1414 | 0.6180 | 11.681 | 0.23 / 10.64 | 1 | [JSON](../runs/controller_pipeline/ctune2_nominal_lqr.json) |
| MPC | ctune0 mpc | completed_lap | 43.242 | 0.1301 | 0.6180 | 11.338 | 1.94 / 21.79 | 9 | [JSON](../runs/controller_pipeline/ctune0_nominal_mpc.json) |
| MPC | ctune1 mpc | completed_lap | 43.170 | 0.1314 | 0.6180 | 11.382 | 2.58 / 31.98 | 23 | [JSON](../runs/controller_pipeline/ctune1_nominal_mpc.json) |
| MPC | ctune2 mpc | completed_lap | 43.132 | 0.1323 | 0.6180 | 11.406 | 2.86 / 34.86 | 21 | [JSON](../runs/controller_pipeline/ctune2_nominal_mpc.json) |

Selections were frozen in [frozen_constrained_selection.json](../runs/controller_pipeline/frozen_constrained_selection.json) before zero-offset evaluation.

## Frozen zero-offset evaluation

| Controller | Run | Status | Gym finish [s] | RMS distance [m] | Max CTE [m] | Steering effort [rad] | p95 / max compute [ms] | Deadline misses | Source |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PP | ceval pure pursuit | completed_lap | 49.230 | 0.0688 | 0.3680 | 13.338 | 0.15 / 8.23 | 0 | [JSON](../runs/controller_pipeline/ceval_nominal_pure_pursuit.json) |
| LQR | ceval lqr | completed_lap | 43.474 | 0.1179 | 0.4122 | 10.669 | 0.24 / 9.96 | 0 | [JSON](../runs/controller_pipeline/ceval_nominal_lqr.json) |
| MPC | ceval mpc | completed_lap | 43.238 | 0.1192 | 0.3694 | 11.067 | 1.91 / 44.45 | 11 | [JSON](../runs/controller_pipeline/ceval_nominal_mpc.json) |

## Same-track controller-tuning comparison

| Controller | Prior constrained Gym finish [s] | Frozen evaluation [s] | Change [s] | RMS distance change [m] |
| --- | ---: | ---: | ---: | ---: |
| PP | 49.286 | 49.230 | -0.056 | -0.0156 |
| LQR | 43.492 | 43.474 | -0.018 | -0.0041 |
| MPC | 43.124 | 43.238 | +0.114 | -0.0016 |

The frozen search minimized tracking distance on offset starts, not lap time. The zero-offset evaluation reduced RMS distance for each controller; MPC's Gym finish became slower. This is one-track offline controller tuning, with no line optimization or multi-track speed-improvement claim.

## Delay sensitivity on the legacy line

![Three paired Gym finish-time differences over nominal, 20 ms and 50 ms command delays](figures/controller_delay_sensitivity.png)

One example-track simulation with fixed nominal physics and source-listed command delays. Panels (a), (b), (c) show PP minus LQR, PP minus MPC, and LQR minus MPC. The shaded region is the registered ±0.1 s near-tie interval, not uncertainty. All three pairs completed in every scenario; none reversed outside that interval. Source: runs/controller_pipeline/delay_sensitivity.json. The delay values are perturbation assumptions, not an identified model distribution.
[Caption file](figures/controller_delay_sensitivity.caption.md) · [SVG](figures/controller_delay_sensitivity.svg) · [source differences](../runs/controller_pipeline/delay_sensitivity.json).

## Reproduce

Use the repository's Python 3.9 Gym environment from `environment.yml`. The commands below read only checked-in example assets; no driving archive is accessed.

```bash
export PYTHONPATH=gym
python -m unittest roboracer.test_reference_line -v
python experiments/controller_pipeline.py qualify
python experiments/controller_pipeline.py baseline
python experiments/controller_pipeline.py constrained_baseline
python experiments/controller_pipeline.py constrained60_pp
python experiments/controller_pipeline.py sensitivity
python experiments/controller_dispersion.py
python experiments/controller_pipeline.py tune_constrained
python experiments/controller_pipeline.py freeze_constrained
python experiments/controller_pipeline.py evaluate_constrained
python experiments/controller_video.py
python experiments/controller_pipeline_report.py
```

Run order matters: the frozen protocol and line artifact must exist before simulation, and selection must be frozen before evaluation. Video and plot generators read committed telemetry/JSON. Per-run compressed telemetry, source hashes and full metrics are in [runs/controller_pipeline](../runs/controller_pipeline/protocol.json).

## Remaining gate

A multi-track comparison needs a permitted, ordered line for another installed map and the same qualification on it. An identified joint vehicle-model region is absent, so the delay figure is a sensitivity check only. The registered multi-track feasibility condition for offline line optimization has not been met. The paper's M2, M3 and reserved cases remain closed.
