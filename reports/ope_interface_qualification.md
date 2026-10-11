# Corrected benchmark interface qualification

The corrected policy code agrees between batches and single states on the
executed synthetic cases, but the loader retains a final post-crash row when a
terminal run reaches the end of an array. The [executed result](../runs/ope_interface_qualification/result.json)
records every case, including that failure. No ranking is admissible from this
qualification: corrected ZIP rights and the required simulator revision remain
unresolved, and the first-crash discrepancy needs an explicit disposition.

This is a public-source and synthetic-interface result. The corrected archive
census was not rerun, and its ZIPs were not acquired or decoded. The
[original census](ope_qualification.md) and its checksums remain intact at the
old pins. A matching archive name cannot transfer those checksums to a Drive file.

## Inspected sources and rights

[inputs.json](../runs/ope_interface_qualification/inputs.json) pins the benchmark,
submodule revisions, selected source files, configuration files, racelines and
licenses with SHA-256 hashes. The benchmark's current GitHub head matched that
pin when inspected. Source downloads stay outside this repository.

| Artifact | Inspected source finding | Qualification consequence |
| --- | --- | --- |
| Benchmark, gym, dataset loader, agent code and OPE-method code | Each pinned repository has an MIT license | Code-only inspection and synthetic execution have a source license; this does not supply an explicit grant for external data ZIPs |
| `f110_sim_env` | Public repository with an Unlicense file | The old missing-public-repository claim is superseded |
| Benchmark simulator dependency | `.gitmodules` names `f110_sim_env`, but the benchmark tree has no corresponding gitlink | The inspected public simulator revision is a candidate, not a confirmed benchmark dependency |
| Corrected real and simulation ZIPs | Registrations now identify separate Drive objects; no archive-specific permission or immutable ZIP checksum established here | Acquisition, corrected census and empirical use remain pending |
| Author reply | Full text supplied by the owner and inspected; MIT additions concern subrepositories, and recursive cloning is recommended | No explicit Drive-ZIP terms or simulator revision supplied; the reply's intended post-crash filtering is the test oracle |

The benchmark tree does pin the gym, loader, agents and OPE methods. Exact
revisions and source URLs are in the input record; the public simulator head
must not be substituted for a missing benchmark pin. The benchmark README's
published OPE comparison was read as requested. No `Groundtruth` files, saved
returns, archive performance arrays or reserved driving bags were opened.

The owner-supplied reply confirms the same car/configuration and real starting
poses for simulation, with no explicit paired episode IDs or recording-session
mapping. Its description of the raw `done` flag and recording span is qualified
by the author's recollection. These statements cannot establish independent
sessions or a cross-car claim. The original correspondence stays local; its
provenance and text hash are recorded in the input manifest. The author requests
citation of the thesis, “Deep off-policy evaluation with autonomous racing cars.”

## Executed interface checks

[qualify_corrected_interfaces.py](../experiments/qualify_corrected_interfaces.py)
loads the pinned `Agent().load(name=...)` implementations and each evaluation
configuration. It uses directed synthetic poses, heading encodings, previous
actions and lidar scans. For each policy it compares deterministic action means,
supplied-action log densities, reset behavior and a reordered batch against
single-state calls. The input arrays, tolerance and per-policy differences are
in `result.json`. All policies returned finite values and agreed on these cases.
This does not qualify archived observation coverage, stochastic rollouts or a
simulator installation.

The density check independently evaluates the scalar truncated-normal formula
using `erf`. It verifies the reversed coordinate conventions: actions are
`[steering, speed]`, while returned log densities are `[speed, steering]`.
Their sum is the joint log density for the tested nondegenerate independent
truncated-normal case. Degenerate support and recorded simulator log densities
remain untested; constant or zero arrays must not be accepted as valid densities.

The loader test executes unchanged methods extracted from the pinned class on
an in-memory synthetic Zarr stand-in. It checks previous-action separation,
delta versus absolute action selection, terminal/timeout handling and horizon
clipping. It bypasses the gym constructor, downloads, track installation and
flattening. The upstream example's explicit options must be reviewed before
using real records; this adapter is not a replacement loader.

### First-crash failure

The interior terminal-run control removes subsequent terminal rows as expected.
At the end of an array, `_find_consecutive_terminals_indices` ends its final
range at `len(terminals) - 1`, leaving the last row outside the removal range.
The full extracted `get_dataset` path retains it. See `loader.first_crash_cases`
in the result for inputs, expected rows, observed rows and flags. This is an
executed source defect; its incidence in the corrected ZIPs is unknown. No
upstream code or recorded data was silently repaired.

The fixture also confirms that `set_terminals=True` can promote natural timeouts
and the chosen horizon cutoff into terminals. A numerical comparison must
therefore state its finite-horizon and censoring interpretation rather than
inherit these flags as physical crash labels.

### Observation and reward mismatch

The pinned dataset README documents that simulation lacks progress observations
and the `new_rewards` group. The synthetic missing-field checks reproduce errors
when those fields are requested. `include_progress=True` is a loader default;
the benchmark example explicitly disables it. A non-null `reward_config` asks
for a relabeled reward; `None` selects collection reward. Neither selecting
`None` on both files nor using the real-data example on simulation establishes
a common outcome. No archive-level reward equivalence was tested.

The README also distinguishes estimated real velocities from zero simulated
lateral/yaw velocities. Those conventions and lidar preprocessing require
archive-level validation before target actions at logged states are eligible
for FQE. Probability-ratio methods additionally require qualified executed-action
joint densities and support. Passing synthetic policy checks alone closes
neither estimator gate.

## Reproduce this source-only result

Use a separate Python 3.11 environment:

```bash
python -m pip install -r requirements-ope-interface.txt
MPLBACKEND=Agg python experiments/qualify_corrected_interfaces.py \
  --fetch --cache /tmp/racing-interface-sources \
  --output /tmp/racing-interface-result.json
```

Only missing manifest-listed public source files are fetched, then every source
hash is checked before execution. No archive or outcome URL is in this fetch
list. `pkg_resources` emits an upstream deprecation warning; the environment
pins its provider. Compare the reproduced numerical fields and gates with the
committed result; environment versions are recorded separately within it.

## Stop condition

Obtain explicit permission for the corrected Drive archives and intended derived
outputs, and the simulator revision used with the benchmark.
Resolve the demonstrated first-crash filter behavior without changing exclusions
silently. Then pin ZIP checksums and run the corrected structural census before
considering M2. Before any performance outcome is read, commit the finite horizon,
common outcome computation, start-distribution comparison, terminal/censoring
rules and whole-record uncertainty treatment. That registration was not created
because the preceding gates failed. Missing session and pairing IDs must not be
invented. The owner-authorized conditional M2 request does not authorize M3/M5
outcome use or a cross-car claim.
