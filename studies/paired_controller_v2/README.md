# Paired direct-rate controller study

The completed synthetic controller study is now available for source review.
[The stored summary](../../runs/paired_controller_v2/summary.json) holds the
result values; [the protocol](../../runs/paired_controller_v2/protocol.json)
holds the scenario draws, physical cells and unchanged numerical gates.
The research question about predicting real-platform rank reversals remains open.

## Controller and outcome definitions

Pure pursuit uses the source speed PID and steering relay adapter. Scheduled
LQR and linear MPC directly command acceleration and steering rate, with common
pure-pursuit startup below the declared threshold. The plant, command limits,
state access and fixed input-delay queue are common. The oriented rectangular
map screen is a geometric outcome rule; a completed circuit is a simulation
outcome. Historical PP-plus-integrated-trim episodes remain separate and keep
their original two-return finish logic.

Every new trial exceeds the declared lateral-demand proxy in an unsaturated
linear-tire model. Coherent mass/inertia changes cancel in those equations.
Perfect state, the fixed example map and that physical-domain warning limit
interpretation to implementation and model sensitivity. No physical controller
ranking, installed vehicle stability or hardware real-time result follows.

## Stored records and the reader

Run from the repository root with Python 3.10 or newer:

```bash
python tools/check_paired_controller_v2.py
```

The reader uses only the standard library. It checks package hashes, the
protocol-defined case membership, exact saved scenario records, and timing-row
counts. It does not import controllers, invoke a simulator, recompute paired
intervals or independently reproduce trajectory-derived metrics. The copied
`trajectory_readback.csv` is the earlier completed readback record; this
integration did not rerun that reduction.

The compact ZIP preserves the exact saved scalar JSON and all timing CSV bytes.
The full trajectories are retained locally, with their hashes in
[the raw inventory](../../runs/paired_controller_v2/raw-trace-inventory.json).
That inventory is not a substitute for the trajectories. Full public
trajectory reproduction remains dependent on an appropriate evidence attachment.

## Scientific source and portability

`frozen_code/` preserves the executed code except for the recorded repository-root
path binding in `independent_controller_check.py`. A path-redacted description of the single-line change
and both source hashes are retained; the exact diff stays private. The exact original files are also in the local raw
archive. The retained circle-stop trace used by the rectangle self-check is
included byte-for-byte as a diagnostic input; it is not an accepted final case. The review copy reads the current repository root instead of the
original Windows checkout. Plant, gains, constraints, outcome checks and stored
protocol/result bytes are unchanged.

These scripts are audit source, not commands to run as part of the reader or
default CI. Running them directly can create new study output and a fresh
protocol with different source hashes. No new campaign was run for this packet;
any future execution needs a separate empty output location and reviewed run
protocol. Do not write into the retained result package.

The frozen protocol's timing and warm-start labels have known qualifications.
[Instrumentation notes](instrumentation_qualifications.txt) explain the final
clipping exclusion, shifted warm-start feasibility and the separation of host
wall time from fixed simulated delay. Stored historical field names remain
unchanged. [Source notices](NOTICE.md) identify the existing plant/map provenance.

The [current detailed report](https://www.mergenulziibayar.com/downloads/reports/sim-to-real-controller-ranking.pdf)
contains the model equations, controller formulation, poles, paired comparisons
and limitations. This is a review packet with default-branch integration pending. It supplies
no formal independent closure approval or real-data ranking milestone.
