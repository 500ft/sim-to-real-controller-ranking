# Groundtruth aggregate reconciliation

One registered variant reproduces every published Groundtruth aggregate.
Under `zero/pinned_source_class_gym_track`, all 15 evaluation agents match the
published mean and population standard deviation for all four rewards within
the registered 1e-4 tolerance. Progress and checkpoint agree to 1.4e-14 and
7.1e-15, lifetime to 1.4e-14, and minimum action to 3.3e-6. The
[result](../runs/ope_groundtruth_reconciliation/result.json) owns every
number; the [protocol](../runs/ope_groundtruth_reconciliation/protocol.json)
fixed the variants, tolerance and expectations before the run.

The matching variant is the inspected published path: the 825 eligible
corrected real-v2 development recordings, the first 250 rows, the final
retained row set to zero, the pinned `ProgressReward`, `LifetimeReward`,
`MinActReward` and `CheckpointReward` classes with their duplicated full-lap
threshold, and progress computed by the pinned `Progress` tracker from poses
on the gym `Track` centerline. That centerline is not the 2,203-point CSV. The
gym's `Raceline.from_centerline_file` closes the loop and resamples the CSV
with a cubic spline at 0.1 m into 221 float32 points. The earlier
[trace](ope_corrected_v2.md) and [development trace](ope_reward_adapter_qualification.md)
loaded the CSV directly, which is why their progress residual of up to 0.0085
never closed. Every other progress source in this run, decoded `progress_sin`
and `progress_cos`, the CSV tracker and the stored `new_rewards` rows, leaves
that same residual.

| Loader | Final row | Reward source | progress | lifetime | min_act | checkpoint |
| --- | --- | --- | --- | --- | --- | --- |
| corrected or original | zero | frozen_v2 | 0 (8.5e-3) | 15 (1.4e-14) | 15 (3.3e-6) | 0 (1.39) |
| corrected or original | zero | departure_aligned | 0 (8.5e-3) | 15 (1.4e-14) | 15 (3.3e-6) | 0 (0.92) |
| corrected or original | zero | pinned_source_class | 0 (8.5e-3) | 15 (1.4e-14) | 15 (3.3e-6) | 0 (0.37) |
| corrected or original | zero | pinned_source_class_gym_track | 15 (1.4e-14) | 15 (1.4e-14) | 15 (3.3e-6) | 15 (7.1e-15) |
| corrected or original | zero | stored_new_rewards | 0 (8.5e-3) | 15 (1.4e-14) | 15 (1.4e-14) | 0 (0.37) |
| corrected or original | keep | any | 0 | 0 or 1 | 0 or 1 | 0 or 1 |

Cells give the number of agents matching out of 15 and, in brackets, the
largest absolute mean difference. The result file holds the per-agent and
per-variant values. The loader axis is inert on this cohort: the corrected and
original helpers retain the same 825 recordings and give identical aggregates,
as the [loader sensitivity](../runs/ope_corrected_v2/loader_sensitivity.json)
predicted. Keeping the final row fails every reward, so the published files
zero the termination row. The stored `new_rewards` rows reproduce minimum
action exactly while the pinned class in float64 leaves 3.3e-6; the two differ
in arithmetic precision only.

The `zero/frozen_v2` variant reproduced the committed
[reward aggregates](../runs/ope_corrected_v2/reward_aggregates.json) exactly
before any comparison was read. The gym-track variant was registered as an
amendment after the first sixteen variants had run and before any gym-track
outcome was computed; the protocol records that order.

## What this does and does not establish

The published per-agent aggregates are now reproduced from the corrected
real-v2 archive with the pinned loader, gym and benchmark sources. This
identifies the cohort, cutoff, terminal handling and reward calculation behind
the Groundtruth files at the aggregate level. It does not establish per-record
equivalence, the author's exact generating revision, or any ZIP reuse term.
Agreement to 1e-14 across 120 published values is strong evidence that the
per-record calculation is the same, but only a membership list from the author
would confirm it.

The frozen common calculation differs from the published definition on two
known points: it decodes the archive's stored progress instead of recomputing
progress on the resampled centerline, and it counts a full-lap checkpoint
once. Which definition the development comparison should use is a choice for
the owner, recorded in the open questions. Nothing from this run enters a
controller ranking. A membership list or revision from the author that
contradicts the identified cohort, or a Groundtruth file with a different hash,
would change this conclusion.

## Reproduce

Use Python 3.11 with `requirements-ope-corrected-v2.txt`, the pinned loader,
gym and benchmark checkouts on the path, and the corrected ZIP and extracted
root outside git:

```bash
python -m unittest experiments.test_reconcile_groundtruth_v2
python -m experiments.reconcile_groundtruth_v2 \
  --real-zip /private/data/f110-real-stoch-v2.zip \
  --real-root /private/data/f110-real-stoch-v2 \
  --loader-source /private/pinned-loader \
  --centerline /private/pinned-gym/gym/f110_gym/maps/Infsaal3/Infsaal3_centerline.csv \
  --groundtruth-dir /private/pinned-benchmark/Groundtruth \
  --private-records /private/groundtruth-reconciliation.json \
  --out /tmp/result.json
```

The script checks the ZIP, loader, centerline and Groundtruth hashes before
reading rows, and refuses to compare if the frozen variant does not reproduce
the committed aggregates. The run took 78 s on the development machine.
