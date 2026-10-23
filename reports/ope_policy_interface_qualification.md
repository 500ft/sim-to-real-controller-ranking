# Development policy-interface qualification

The [registered replay](../runs/ope_policy_interface_qualification/result.json)
executed the pinned FTG and PP policies on every eligible corrected real-v2
evaluation-agent development recording. It checked the source-reported and
independently computed log densities of each archived delta action in
**[speed, steering]** order. Every retained row had finite densities and action
support; both density comparisons met the frozen rule. The exact stochastic
draw cannot be reproduced because the archive has no original random state or
innovation.

The action-frame check failed. The result identifies terminal rows where
`raw_actions` is `[0, 0]` while `previous_action + actions` gives a different
physical target. Every such mismatch has `done` and `compute_termination`
true, `truncated` false, and is the last retained row of its recording.
The original and flagged rows remain in the private ledger. A zero target may
represent a safety or recording convention; the archive and inspected source do
not establish which command was executed. We did not relax the registered
tolerance or remove those rows after seeing this result. The M1 action gate
remains open.

The [protocol](../runs/ope_policy_interface_qualification/protocol.json) was
committed before archive replay. It binds the Drive object, ZIP hash, agents
revision and each evaluation configuration. Configuration classes establish
family membership; names alone were not used. The policy code consumes
archive-normalized lidar with its stored batch layout, physical previous
steering and speed, and pose and heading fields. It emits steering/speed
deltas. The archive also stores absolute target commands. The collection path
adds the delta to the previous target and clips speed. Likelihoods refer to
the delta coordinates, and the two component logs sum only under the source's
conditional independent truncated-normal model. No density was transferred
to absolute-target coordinates.

The [synthetic result](../runs/ope_policy_interface_qualification/synthetic.json)
tests all pinned controllers against scalar, batch, permuted and reset calls,
including the corrected PP batch implementation. Separate
[density cases](../experiments/test_policy_density_v2.py) check interior and
tail values, normalization by quadrature, support boundaries, component
order, zero-width speed support and delta-to-target conversion. The archive
replay makes a fresh policy instance and resets it at each recording. The
source density call samples internally even when a logged action is supplied;
those newly sampled actions are discarded. Its log density is evaluated at
the archived action. This does not reconstruct the original draw.

All replayed rows are development observations under the prior split and
exclusion. Recordings and time steps are reported separately in the
[result](../runs/ope_policy_interface_qualification/result.json); repeated
observations are not treated as independent cars or episodes. The private
JSONL retains per-row source and independent densities, action bounds,
support, target differences and flags. Its SHA-256 is in the public result.
Raw and processed third-party data remain outside git. The original reward
and loader failures remain in their historical reports.

Unsent author question: In corrected real-stoch-v2, what does a
`raw_actions=[0,0]` value on a final `done=true` and
`compute_termination=true` row represent? Was the corresponding
`actions` delta executed before the crash or intervention, and does its
stored `log_prob` describe that executed command? Please identify any
terminal-row action convention and whether those rows enter the published
Groundtruth cohort. The [reward report](ope_reward_adapter_qualification.md)
holds the separate unresolved simulator, cohort and corrected-ZIP terms
questions. No message was sent.

## Simulation archive replay

The same replay on the corrected sim-v2 archive passes the registered gate.
The [sim result](../runs/ope_policy_interface_qualification_sim/result.json)
covers all 825 evaluation-agent recordings and 167,647 retained rows under the
[sim protocol](../runs/ope_policy_interface_qualification_sim/protocol.json),
which copies the real-v2 tolerances, configurations, source hashes and
exclusion rule and changes only the archive identity. The pinned loader
registers no bad trajectory for this archive, so no recording was excluded.
Every row is finite and in support. Source densities agree with the stored
log densities within 7.7e-5 and the independent calculation agrees with the
source within 1.8e-15, against 3.1e-5 and 7.4e-7 on real-v2; the tighter
independent agreement follows from the simulation archive storing previous
actions in float64. Zero terminal rows fail the action-frame gate, and the
archive holds no zero `raw_actions` row at all. The terminal zero-target
convention is therefore a property of the real recordings, which narrows the
unsent author question to the real car's recording or safety path. Simulation
densities agree where real densities agreed; the sim replay admits nothing on
the real action gate, and no return or ranking was read.

## Reproduce

Use Python 3.11 with `requirements-ope-corrected-v2.txt`. The pinned source
and corrected ZIP paths below are local, outside this repository:

```bash
python -m unittest experiments.test_policy_density_v2
python -m experiments.qualify_policy_synthetic_v2 \
  --agents-source /private/pinned-agents --out /tmp/policy-synthetic.json
python -m experiments.replay_development_policies_v2 \
  --real-zip /private/f110-real-stoch-v2.zip \
  --real-root /private/f110-real-stoch-v2 \
  --agents-source /private/pinned-agents \
  --private-rows /private/policy-replay.jsonl \
  --out /tmp/policy-result.json
```

The replay checks all source, configuration and ZIP hashes before reading
archive rows. Its result remains a failed action-frame gate even though the
density comparison passes. The simulation replay passes the sim protocol with
`--protocol runs/ope_policy_interface_qualification_sim/protocol.json` and the
sim ZIP and root in place of the real ones; it writes a separate result and
private ledger.
