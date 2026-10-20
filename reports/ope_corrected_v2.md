# Corrected v2 local qualification

The two corrected Drive objects were downloaded to a private working directory
and inspected without changing either ZIP. Their object IDs, byte counts,
SHA-256 hashes, roots, recording boundaries, terminal counts, policy coverage
and log-density presence are in the [census](../runs/ope_corrected_v2/census.json).
The earlier wrong-alias [census](../runs/ope_qualification/result.json) remains
historical. Neither archive nor any row-level derivative is committed here.

Every observed recording starts when `timestep` returns to zero. The preceding
row carries `done` or `truncated`, and each recording keeps one policy name.
This establishes recording boundaries for the registered exclusion rule; it
does not establish independent drives or paired real/simulation episodes.
The pinned source's evaluation list is copied in
[eval_agents.json](../runs/ope_corrected_v2/eval_agents.json). All listed
policies have records in both archives. Every stored two-component log-density
vector is finite and nonzero, which establishes availability only. Target
likelihood validity, action support and estimator eligibility still require
archive-level policy execution checks.

The corrected rule retains the first `compute_termination` sample in a
recording and excludes later samples from that recording. The original pinned
helper scans across recording boundaries. The [sensitivity
result](../runs/ope_corrected_v2/loader_sensitivity.json) identifies its changed
reset rows and the resulting per-agent mean changes. The private exclusion
ledger contains every row index, recording boundary and original-helper index;
its SHA-256 is `9170f8c1e778c3ba51d905a27a4f7bc04de2cf7b59a8e04501163b786999fee7`.
The exclusion is a development rule, not a determination of physical crash
truth. Original bytes remain in the private ZIPs.

The [reward protocol](../runs/ope_corrected_v2/protocol.json) and executable
[implementation](../experiments/common_reward_v2.py) were committed as
`e5e009f5b811a08395aa77b2dc610354aadfcbc9` before any reward outcome was
read. The protocol fixes source commits and hashes, nominal control step,
discount, recording starts, terminal treatment, cutoff, seeds, the four reward
formulas and whole-record aggregation. It uses the same calculation on both
archives. The [boundary tests](../experiments/test_common_reward_v2.py) cover
progress wrapping, strict checkpoints, a stationary final row, action limits
and a one-row terminal. The [per-policy means and population standard
deviations](../runs/ope_corrected_v2/reward_aggregates.json) are development
aggregates, with no inferred pairing or ranking.

The [comparison](../runs/ope_corrected_v2/reference_comparison.json) checks
those real-agent aggregates against the benchmark's pinned public `Groundtruth`
files. Lifetime agrees to floating-point precision; minimum-action differs
only at numerical precision. Progress retains a small aggregate discrepancy
after independently recomputing progress from the pinned track and poses.
Its cause is unresolved. Checkpoint differs materially: the pinned
`CheckpointReward` extends its threshold list by including the previous last
threshold again at a lap boundary. That can award the same full-lap checkpoint
twice. The [direct source-class comparison](../runs/ope_corrected_v2/checkpoint_source_comparison.json)
executes the pinned class on the same permitted recordings and records affected
cases. The registered common calculation awards it once. The difference is
reported rather than silently changing the frozen rule or tuning a ranking.
Common-reward equivalence to all four published summaries is therefore not
qualified, and M2 stays closed.

The [pinned-class trace](../runs/ope_corrected_v2/reward_trace.json) checks a
small sample of eligible real development recordings. It recomputes progress
from the pinned centerline and poses, then runs the pinned `ProgressReward` and
`MinActReward` classes. Their pre-final-row values agree with the registered
common calculation within the numerical differences recorded there. The
archive's stored progress reward stays positive on each sampled cutoff row,
while the pinned progress class appends zero. The first material per-row
stored-versus-source divergence is therefore the final cutoff row in this
sample. The public Groundtruth aggregate gap remains unexplained; the sample
cannot establish the provenance or cohort used to produce those files.

The same trace reduces the checkpoint defect to a synthetic progress sequence.
At its second full-lap crossing, the pinned class counts the duplicated
threshold twice. The registered common metric counts it once. The pinned class
also forces its last progress value to three laps; terminal zeroing hides that
last-row effect in the declared common calculation. The original source behavior
and the already frozen candidate correction remain separate. No metric was
changed after reading outcomes, and no new cohort was ranked.

The candidate `f110_sim_env` revision also fails an unmodified import with
the pinned loader: `base_env.py` imports `Config` from `config_new.py`, which
defines `RewardConfig` instead. The inspected source hashes are
`d58cf97805681326d90e807af924a0d3affbeaef2b7ce070533ac88c2880382d`
and `2ac739a12cebbfeeb5c63ff7e530104465cefeb99693def6d6156d0d1c9f85e7`,
respectively. The check used Python 3.11.15 and Gymnasium 0.29.1. No
unmodified candidate-simulator episode ran, so compatibility and historical
identity remain unestablished. The local common-reward calculation completed
in the time recorded in its aggregate JSON; this was the short runtime check
before any extended M2 work.

The [version-pinned interface probe](../runs/ope_corrected_v2/simulator_probe.json)
applies an in-process `Config` alias, the NumPy boolean alias used by the
candidate, and an explicit `RewardConfig` object. Import, construction and
reset pass. The first step fails because the candidate calls the pinned
`MixedReward` with `laser_scan`, but that class's active call signature takes
`scan` and a dictionary observation. This is a further interface mismatch;
patching only the keyword would not establish correct reward semantics. The
probe leaves the third-party source unchanged. A short simulator rollout and
the extended runtime benchmark remain unexecuted.
The later [reward bridge qualification](ope_reward_adapter_qualification.md)
preserves this failure and reports the subsequent bounded simulator smoke and
development-record trace.

## Reproduce the local checks

Keep the two ZIPs and their extracted Zarr roots outside git. Download each
object by the URL registered in the pinned loader, compare SHA-256 against the
[protocol](../runs/ope_corrected_v2/protocol.json), and inspect the ZIP roots
before running:

```bash
python3.11 -m venv /tmp/racing-v2-env
/tmp/racing-v2-env/bin/pip install -r requirements-ope-corrected-v2.txt
/tmp/racing-v2-env/bin/python -m unittest experiments.test_common_reward_v2
/tmp/racing-v2-env/bin/python experiments/census_corrected_v2.py /private/data \
  --summary /tmp/census.json --private-ledger /private/data/exclusion-ledger.json
/tmp/racing-v2-env/bin/python experiments/common_reward_v2.py /private/data \
  --out /tmp/reward_aggregates.json
python3 experiments/compare_reward_reference_v2.py /tmp/reward_aggregates.json \
  /private/pinned-f110_ope_benchmark/Groundtruth --out /tmp/reference_comparison.json
/tmp/racing-v2-env/bin/python -m experiments.compare_checkpoint_source_v2 \
  /private/data /private/pinned-f1tenth_orl_dataset/f110_orl_dataset/fast_reward.py \
  runs/ope_corrected_v2/eval_agents.json --out /tmp/checkpoint_source_comparison.json
/tmp/racing-v2-env/bin/python -m experiments.summarize_loader_sensitivity_v2 \
  /private/data /private/data/exclusion-ledger.json /tmp/reward_aggregates.json \
  runs/ope_corrected_v2/eval_agents.json --out /tmp/loader_sensitivity.json
PYTHONPATH=/private/pinned-f1tenth_orl_dataset:/private/pinned-f1tenth_gym/gym \
  /tmp/racing-v2-env/bin/python -m experiments.trace_reward_v2 \
  --real-root /private/data/f110-real-stoch-v2 \
  --loader-source /private/pinned-f1tenth_orl_dataset \
  --centerline /private/pinned-f1tenth_gym/gym/f110_gym/maps/Infsaal3/Infsaal3_centerline.csv \
  --out /tmp/reward_trace.json
PYTHONPATH=/private/pinned-f110_sim_env:/private/pinned-f1tenth_orl_dataset:/private/pinned-f1tenth_gym/gym \
  /tmp/racing-v2-env/bin/python -m experiments.probe_candidate_simulator_v2 \
  --simulator-source /private/pinned-f110_sim_env \
  --loader-source /private/pinned-f1tenth_orl_dataset \
  --out /tmp/simulator_probe.json
```

The pinned benchmark, loader and candidate simulator stay outside this
repository. The exact local output paths are examples; compare numerical fields
and hashes, since elapsed time depends on the host. ZIP reuse and derived
publication rights have not been verified. No reserved driving bags or M3 data
were opened.
