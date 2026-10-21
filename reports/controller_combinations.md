# Controller combinations on two development tracks

This is a simulation-development comparison on the checked-in example and licensed MapZoo Berlin lines. Legacy `lqr` and `mpc` in the earlier pipeline already meant PP plus bounded LQR or MPC correction; the labels below make that architecture explicit. No real-data or physical-platform ranking follows from these runs.

[Registered protocol](../runs/controller_combinations/protocol.json) · [frozen blend choice](../runs/controller_combinations/frozen_blend.json) · [machine-readable ranking and pairwise differences](../runs/controller_combinations/ranking.json)

## Frozen candidates and exclusions

PP, PP plus LQR correction, and PP plus MPC correction are the three active baselines. The two pure-shadow wrappers apply only the named active controller; the shadow receives the same observation and its bypassed state is synchronized to the applied command. Their shadow proposals are diagnostics, not counterfactual lap times. The fallback switches from MPC to LQR after registered solver, finite-output, command-domain or timing failure, with five control ticks of dwell and three valid MPC ticks for recovery. The blend adds weighted bounded corrections to one PP base, subtracting each correction controller's own PP feedforward first. The LQR-primary selective MPC takeover was excluded before outcomes because no distinct justified trigger was available.

The seven candidates share the frozen per-track source-line controller settings. Only the blend added a three-weight offline search on the prior tuning start, then froze its choice before evaluation. Those tuning records, including constraint failures, remain in [the run directory](../runs/controller_combinations/frozen_blend.json). The faster Berlin line from the earlier pipeline remains excluded because its closed-loop motion limits failed.

## Overall development ordering

The preregistered order first requires every case to finish without collision, pass shared motion limits, and meet the measured compute deadline in timing-aware runs. It then compares noncompletions, motion-limit failures, deadline misses, worst completed Gym finish and mean tracking distance. A noncompletion receives no finite lap time. Each track/scenario/timing case has equal count weight; the worst finish is a separate lexicographic criterion.

**No candidate qualifies as an overall winner** under the registered motion and timing requirements. The conditional development order begins with **PP + LQR correction** and ends with **PP + LQR active; PP + MPC shadow**. This is an ordering of measured candidates under failed requirements, not a recommended vehicle controller.

Every run exceeded the 4 m/s² lateral speed-times-yaw-rate proxy target and the 2 m/s² forward-acceleration target: even the lowest run peak was 8.03 m/s² laterally and 4.95 m/s² forward. The lateral proxy omits lateral-velocity derivative; it is a registered screening signal, not a full tire-force measurement.

| Conditional order | Architecture | Completed / attempted | Motion-failed runs | Deadline-aware misses | Mean completed Gym finish [s] | Mean completed RMS distance [m] | Max whole-call compute [ms] |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | PP + LQR correction | 14 / 14 | 14 | 1 | 42.933 | 0.1087 | 18.41 |
| 2 | PP | 14 / 14 | 14 | 1 | 46.756 | 0.0656 | 17.32 |
| 3 | PP + MPC correction | 14 / 14 | 14 | 444 | 43.260 | 0.1080 | 45.75 |
| 4 | PP + MPC primary; PP + LQR fallback | 14 / 14 | 14 | 446 | 43.941 | 0.1046 | 47.61 |
| 5 | PP + weighted LQR/MPC corrections | 14 / 14 | 14 | 456 | 43.558 | 0.0762 | 58.86 |
| 6 | PP + MPC active; PP + LQR shadow | 14 / 14 | 14 | 458 | 43.283 | 0.1080 | 42.51 |
| 7 | PP + LQR active; PP + MPC shadow | 14 / 14 | 14 | 465 | 42.934 | 0.1087 | 67.07 |

The first two candidates have the same completed, motion-failed and deadline-miss counts; the conditional leader is decided by the next registered worst-finish comparison. The last candidate has the most deadline-aware misses. Host wall-clock tails are variable, so the compute ordering is a development observation rather than target-hardware timing evidence.

Completed-time and tracking averages include only completed cases, so compare them alongside coverage. The 0.1 s near-tie rule and 2 ms Gym integration grid bound interpretation of small finish differences; [pairwise differences](../runs/controller_combinations/ranking.json) retain each common case.

## Criterion-specific order

| Criterion | Best measured candidate | Worst measured candidate | Scope |
| --- | --- | --- | --- |
| completion and constraints | PP, PP + LQR correction | PP + LQR active; PP + MPC shadow | Equal coverage; motion failures and deadline counts break ties. |
| finish time | PP + LQR correction, PP + LQR active; PP + MPC shadow | PP | Completed cases only; 0.1 s near-tie band. |
| tracking | PP | PP + LQR correction | Mean completed RMS reference distance. |
| compute deadlines | PP, PP + LQR correction | PP + LQR active; PP + MPC shadow | Measured deadline counts; maximum is host-dependent. |
| disturbance robustness | All seven tied | All seven tied | Non-nominal completion count only; all candidates tied. |

### Fault-case trade-off

| Track | Timing | PP + MPC Gym finish [s] | MPC→LQR fallback Gym finish [s] | Fallback switches |
| --- | --- | ---: | ---: | ---: |
| example | ideal | [46.906](../runs/controller_combinations/example_mpc_timeout_ideal_pp_mpc.json) | [44.898](../runs/controller_combinations/example_mpc_timeout_ideal_mpc_lqr_fallback.json) | 268 |
| example | deadline aware | [47.080](../runs/controller_combinations/example_mpc_timeout_deadline_aware_pp_mpc.json) | [44.948](../runs/controller_combinations/example_mpc_timeout_deadline_aware_mpc_lqr_fallback.json) | 238 |
| mapzoo_berlin | ideal | [42.776](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_ideal_pp_mpc.json) | [42.000](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_ideal_mpc_lqr_fallback.json) | 411 |
| mapzoo_berlin | deadline aware | [42.760](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_pp_mpc.json) | [42.160](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_mpc_lqr_fallback.json) | 376 |

The fallback improves the injected-fault finish relative to PP + MPC in these runs, but it is slower on Berlin without the injected fault. Every listed fault run fails the shared motion target.

## Execution and interpretation

The ledger contains 98 executed full-horizon runs, 14 common cases per architecture on two tracks. Ideal simulated-time and measured deadline-aware runs are separate; late commands wait for a later control tick. The injected MPC timeout and actuator delay are deterministic development assumptions, not measured hardware latency. Whole-call timing includes shadow computation and is host-dependent. Stiffness variants retain paired front/rear values from earlier synthetic identification, not an identified vehicle uncertainty distribution. No grip range was qualified. Repeated deterministic cases are neither independent vehicles nor real-platform transfer evidence.

Each [run JSON](../runs/controller_combinations/ranking.json) links a compressed control-tick trace and its SHA-256. The final terminal integration row is retained. Full 2 ms integration traces and their hashes were kept locally outside git after extracting compact telemetry; the runner regenerates them. Earlier source errors and exploratory runs remain in [history](../runs/controller_combinations/history/pre_sync/README.md), and the first full cohort's failed actuator-rate check is [retained](../runs/controller_combinations/history/rate_limit_failure/README.md).

The synchronized videos show real sampled simulator positions, applied steering, active and shadow identities, switches and terminal status. They do not infer a shadow controller's hypothetical trajectory.

- [Example timeout comparison video](../runs/controller_combinations/example_mpc_timeout_deadline_aware_comparison.mp4) and [preview](../runs/controller_combinations/example_mpc_timeout_deadline_aware_preview.png)
- [MapZoo Berlin timeout comparison video](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_comparison.mp4) and [preview](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_preview.png)

## Reproduce

Use the Python 3.9 Gym environment specified by the parent [pipeline report](controller_pipeline.md). The commands use only checked-in and pinned public simulation assets.

```bash
export PYTHONPATH=gym:.
python -m unittest roboracer.test_controller_combinations -v
python -m experiments.controller_combinations pilot
python -m experiments.controller_combinations tune
python -m experiments.controller_combinations freeze
# Commit frozen_blend.json before evaluation.
python -m experiments.controller_combinations evaluate
python -m experiments.controller_combination_publish
python -m experiments.controller_combination_ranking
python -m experiments.controller_combination_video example mpc_timeout deadline_aware
python -m experiments.controller_combination_video mapzoo_berlin mpc_timeout deadline_aware
python -m unittest experiments.test_controller_combination_results -v
```

The paper's M1/M2/M3/M5 qualification gates and reserved groups remain unchanged.
