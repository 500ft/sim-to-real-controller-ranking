# Development reward interface qualification

The [pinned candidate wrapper](../runs/ope_reward_adapter_qualification/source_call_witness.json)
cannot execute the pinned loader reward as written. `make_base_env` builds
`MixedGymReward`, which builds `StepMixedReward`. The latter flattens an
observation, adds a time axis, and calls `MixedReward` with `laser_scan`.
`fast_reward.py` defines `MixedReward.__call__` twice. Python retains the later
dict-observation signature, which accepts `scan` and rejects that keyword.
The [synthetic witness](../experiments/reproduce_mixed_reward_call_v2.py)
reproduces the error. Even a keyword substitution would leave a flat-array
input where the live method expects a dict. For a two-observation progress
pair, `ProgressReward` returns the forward difference followed by zero;
`StepMixedReward` selects the zero column. The original failed
[probe](../runs/ope_corrected_v2/simulator_probe.json) remains unchanged.

The [local bridge](../experiments/simulator_reward_adapter_v2.py) verifies
the source file hashes and replaces only the broken reward wrapper during
candidate environment construction. It retains the candidate physics,
observations, action wrappers and reset. Its selected scalar reward is progress;
the per-step info also exposes lifetime, minimum-action and checkpoint
contributions. Progress and checkpoints are assigned to the transition's
departure observation. The physical steering target sets minimum-action
reward, while a separate recorded delta command remains available in the
environment info. Reset clears progress and lap state. A terminal observation
has no outgoing reward row. This convention is registered in the
[prospective protocol](../runs/ope_reward_adapter_qualification/protocol.json)
and checked against hand-calculated synthetic cases, including wraps, strict
thresholds, reset, terminal, horizon and physical steering. The
[pinned action-wrapper witness](../runs/ope_reward_adapter_qualification/action_mapping.json)
checks a nonzero normalized steering/speed command against its registered
delta and physical targets.

The [public-start smoke result](../runs/ope_reward_adapter_qualification/smoke.json)
records the exact number of executed control steps, its collision termination,
the public map hash and the private step-record hash. Each returned component
agreed with a separate step calculation using progress, action and threshold
values. The step records, poses and per-step contributions stay outside git.
The fixed straight command collides on the candidate map; it is an interface
check, not a lap or controller evaluation. The source gym uses RK4 and its
candidate wrapper skips physics frames to the registered control interval.
The wrapper's reset path drops the supplied seed before the base environment;
fixed pose, velocity and action remove the intended stochastic inputs for this
smoke, but the seed propagation defect remains a simulator limitation.

The [development trace](../runs/ope_reward_adapter_qualification/development_trace.json)
covers every eligible corrected real evaluation-agent recording under the
previously registered exclusion and cutoff. It verifies the ZIP and reward
source hashes. For each recording it keeps frozen-v2, departure-aligned,
pinned-source-class and stored reward returns, their differences, terminal
reason and final stored values in a private ledger. The public result gives
cohort counts, cutoff behavior and distribution summaries. The frozen-v2
checkpoint calculation places a crossing on the arrival row, while its
progress calculation uses the departure row. The bridge resolves this
alignment for the candidate metric. Stored horizon-end rewards and the
source-class duplicate full-lap checkpoint remain separate explanations.
The comparison uses the same local recording set for each variant and does
not select a metric by closeness to a published total.

The public Groundtruth files contain per-policy aggregates without an
identifiable per-record membership or exact generating revision. Their
remaining difference cannot be assigned to one cause from these files.
Historical simulator identity, corrected-ZIP reuse terms, policy execution on
archived observations and independent session groups remain open. M2 ranking
and M3 were not run. A successful local reward bridge establishes candidate
compatibility on these tests only.

Unsent author question: Which exact `f110_sim_env` revision, real-v2 ZIP object,
loader revision and `compute_reward_from_ds.py` settings generated the published
Groundtruth JSONs, including the eligible recording starts and terminal/cutoff
rule? Do the corrected real-v2 and sim-v2 Drive ZIP terms permit local analysis
and publication of derived per-policy aggregates? No message was sent.

## Reproduce

Use the pins in the protocol and keep the ZIP, extracted archive and step/record
ledgers outside git. With the pinned loader, candidate simulator and gym roots
on `PYTHONPATH`, run:

```bash
python -m unittest experiments.test_common_reward_v2 experiments.test_simulator_reward_adapter_v2
python -m experiments.reproduce_mixed_reward_call_v2 \
  --loader-source /private/pinned-loader --out /tmp/source_call_witness.json
python -m experiments.reproduce_action_mapping_v2 \
  --simulator-source /private/pinned-simulator --loader-source /private/pinned-loader \
  --out /tmp/action_mapping.json
python -m experiments.smoke_simulator_reward_adapter_v2 \
  --simulator-source /private/pinned-simulator --loader-source /private/pinned-loader \
  --gym-source /private/pinned-gym --private-steps /private/adapter-smoke.json \
  --out /tmp/smoke.json
python -m experiments.trace_all_development_rewards_v2 \
  --real-zip /private/data/f110-real-stoch-v2.zip \
  --real-root /private/data/f110-real-stoch-v2 \
  --loader-source /private/pinned-loader \
  --centerline /private/pinned-gym/gym/f110_gym/maps/Infsaal3/Infsaal3_centerline.csv \
  --private-records /private/adapter-reward-records.json \
  --out /tmp/development_trace.json
```

The source-call witness retains an expected failure as a passing diagnostic.
The original pinned simulator probe still exits with its recorded error.
