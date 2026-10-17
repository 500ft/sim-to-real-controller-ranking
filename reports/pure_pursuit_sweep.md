# Pure Pursuit Sweep

## Objective

Tune pure pursuit over lookahead and velocity gain before comparing against LQR and MPC.

## Setup

- Integrator: RK4
- Integration timestep: `0.002 s`
- Controller update rate: `100 Hz`
- Command hold: zero-order hold between controller updates
- Track: `examples/example_map`
- Lookahead values: `[0.4, 0.6, 0.8, 1.0, 1.2, 1.5]`
- Velocity gains: `[0.8, 1.0, 1.2, 1.375, 1.6]`

## Recommended Baseline

Recommended baseline: **lookahead = 1.200 m, vgain = 1.200**.

Reason: this run completed without collision and had the lowest weighted score among stable candidates.

| Metric | Value |
| --- | ---: |
| Lap time | 38.042 s |
| RMS CTE | 0.157892 m |
| Max CTE | 0.403062 m |
| Steering effort | 8.19853 rad |
| Weighted score | 0.668584 |

## Top Completed Runs

| lookahead_m | vgain | lap_time_s | rms_cte_m | max_abs_cte_m | steering_effort_rad | weighted_score | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.2 | 1.2 | 38.042 | 0.157892 | 0.403062 | 8.19853 | 0.668584 | stable |
| 1.5 | 1.2 | 38.216 | 0.206472 | 0.487029 | 6.99299 | 0.677879 | stable |
| 1 | 1.2 | 37.928 | 0.127334 | 0.36798 | 10.4543 | 0.742044 | stable |
| 1.2 | 1.375 | 33.504 | 0.205956 | 0.510443 | 11.7676 | 0.921946 | stable |
| 0.8 | 1.2 | 37.82 | 0.0986543 | 0.36798 | 17.4812 | 1.06471 | stable |
| 1 | 1.375 | 33.374 | 0.165826 | 0.414591 | 17.0947 | 1.12421 | stable |
| 0.6 | 1 | 44.986 | 0.0559593 | 0.36798 | 21.5057 | 1.22324 | stable |
| 0.8 | 1.375 | 33.244 | 0.126354 | 0.367979 | 27.1321 | 1.57495 | stable |

## Classification Rules

Priority order: collision, incomplete, corner cutting, oscillatory, stable.

- Corner cutting threshold: max CTE > `0.800 m`
- Oscillatory threshold: steering effort above the completed-run 75th percentile
- Weighted score: `rms_cte + 0.25 * max_cte + 0.05 * steering_effort`

These thresholds are map-specific heuristics intended to select a controller baseline, not universal stability criteria.

## Figures

![RMS CTE heatmap](figures/pure_pursuit_sweep_rms_cte_heatmap.png)

Simulator output, F1TENTH Gym, pure pursuit. Among completed laps, RMS cross-track error grows with lookahead and velocity gain. Each cell is one run, coloured and labelled by its RMS cross-track error [m]; the colour bar gives the scale. Hatched cells did not complete a lap (diagonal: no lap within the time limit; crossed: collision), so their RMS covers the partial run. The black box marks the selected baseline (1.2 m lookahead, gain 1.2). n = 30 closed-loop runs, one per setting; integration step 2 ms, control 100 Hz. Sources: runs/pure_pursuit_sweep/results.csv and runs/pure_pursuit_sweep/metadata.json.
[Caption file](figures/pure_pursuit_sweep_rms_cte_heatmap.caption.md).

![Lap time heatmap](figures/pure_pursuit_sweep_lap_time_heatmap.png)

Simulator output, F1TENTH Gym, pure pursuit. Completed laps get faster as velocity gain rises (28.9 to 45.0 s). Each cell is one run, coloured and labelled by its lap time [s]; the colour bar gives the scale. 19 runs did not complete a lap and have no lap time: their cells are white and hatched (diagonal: no lap within the time limit; crossed: collision). The black box marks the selected baseline (1.2 m lookahead, gain 1.2). n = 30 closed-loop runs, one per setting; integration step 2 ms, control 100 Hz. Sources: runs/pure_pursuit_sweep/results.csv and runs/pure_pursuit_sweep/metadata.json.
[Caption file](figures/pure_pursuit_sweep_lap_time_heatmap.caption.md).

![Sweep regions](figures/pure_pursuit_sweep_regions.png)

Simulator output, F1TENTH Gym, pure pursuit. 11 of 30 settings complete a lap; the selected baseline (1.2 m lookahead, gain 1.2, large ring) is stable. Each marker is one setting, its shape giving the run class from experiments/pure_pursuit_sweep.py; filled markers completed a lap and hollow markers did not. Counts: stable 8, oscillatory 3, no lap within time limit 9, collision 10. n = 30 closed-loop runs, one per setting; integration step 2 ms, control 100 Hz. Sources: runs/pure_pursuit_sweep/results.csv and runs/pure_pursuit_sweep/metadata.json.
[Caption file](figures/pure_pursuit_sweep_regions.caption.md).

## Outputs

- `runs/pure_pursuit_sweep/results.csv`
- `runs/pure_pursuit_sweep/metadata.json`
