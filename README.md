# Sim-to-Real Controller Ranking

Can dispersion in the predicted performance difference between controllers,
across physically justified models consistent with development data, identify
rankings that should be withheld? The corrected-source qualification loads all
15 evaluation policies on synthetic inputs, but reproduces a first-crash loader
failure. Ranking remains blocked by corrected data permission, archive-level
qualification and an unpinned simulator dependency.

[![CI](https://github.com/500ft/sim-to-real-controller-ranking/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/500ft/sim-to-real-controller-ranking/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-276C6B)](LICENSE)

[Results](#results) · [Roadmap](ROADMAP.md) · [Quick start](#quick-start) ·
[Qualification report](reports/ope_qualification.md) · [History](docs/history/README.md)

![Structural census of five pinned archives: recording segments, policy-name strings and terminal-flag alignment; real-v1 has flags before segment ends](runs/ope_qualification/structure.png)

*Historical census at the original source pins. Unfiltered counts from [result.json](runs/ope_qualification/result.json).
Panel C separates flagged rows at recording ends from flags within recordings.
Segments do not establish independent episodes; names do not establish execution eligibility.
[Accessible tables and archive identities](runs/ope_qualification/structure.md) ·
[SVG](runs/ope_qualification/structure.svg).*

## Results

The [corrected-source interface report](reports/ope_interface_qualification.md)
and [executed result](runs/ope_interface_qualification/result.json) record the
new source pins, license inspection, policy batch checks and loader failure.
The simulator repository is now public and licensed; its required benchmark
revision is still unconfirmed. No corrected ZIP or performance outcome was opened.

The preserved census below uses the earlier pins:

- Real v1 contains 311 recording segments and 29 distinct policy-name strings.
  Its 10,813 `done | truncated` rows cannot be treated as separate recordings.
- Real stochastic v2 contains 1,375 segments and 57 policy-name strings. All
  those names match configuration filenames in the pinned benchmark source;
  execution on archived observations remains unqualified.
- At those earlier pins, both real-stochastic registrations loaded the
  simulation-v1 archive. The corrected source now uses distinct Drive objects.
  The original qualification binds each inspected archive by filename, hash
  and internal array root.

The [executed table](runs/ope_qualification/structure.md) and
[qualification report](reports/ope_qualification.md) give the source pins,
method, policy-name discrepancies and separate gates for FQE and probability-ratio
estimators. [result.json](runs/ope_qualification/result.json) is the source for
structural numbers; the table and plot are generated views.

## Quick start

The structural reader uses Python 3.11 in its own environment. Unit checks need
no archive download, upstream policy package or vehicle:

```bash
python3.11 -m venv .venv-ope
source .venv-ope/bin/activate
python -m pip install -r requirements-ope-qualification.txt
python experiments/test_ope_qualification.py
```

The optional integration test is skipped unless the pinned cache is supplied.
See [reproduction](reports/ope_qualification.md#reproduce) for the executed
archive check and figure commands. Source data and third-party code are kept
outside this repository while reuse terms remain unknown.

## What's next

Obtain the original author reply, corrected ZIP permission, the required
simulator revision and a disposition of the first-crash filter failure. The
[roadmap](ROADMAP.md) keeps M2 conditional on these prerequisites. Its outcome
and uncertainty rules must be committed before performance data is read.
[Open questions](docs/OPEN_QUESTIONS.md) retains the data and physical decisions.
No empirical ranking or finite-horizon return calculation has been run.

## Retained work

The licensed [public-driving comparison](reports/real_command_response.md)
remains a same-run development result. Its
[split qualification](reports/driving_split_qualification.md) admitted no
separate final group. Unopened bags stay unopened.

The [history index](docs/history/README.md) retains simulator identification,
controller comparisons, mast hand calculations, FEA, useful CAD and calibration
tooling. Same-model simulator consistency does not validate real controller
rankings. Mast mounting and physical scope remain pending; this software pivot
approves no deck design, height, fabrication or physical campaign.

## Documentation

| Document | Purpose |
| --- | --- |
| [Roadmap](ROADMAP.md) | Finish line and current stop condition |
| [Qualification report](reports/ope_qualification.md) | Executed structural result and estimator gates |
| [Open questions](docs/OPEN_QUESTIONS.md) | Current unknowns and superseded questions |
| [Reading and reproduction guide](docs/START_HERE.md) | Environments and retained checks |
| [Data and figures](docs/data-and-figures.md) | Current and historical figure provenance |
| [History](docs/history/README.md) | Preserved driving, simulation and mechanical work |

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). A pull request
must identify the result it changes and the checks actually run.

## License and attribution

Repository code uses the [MIT License](LICENSE), preserving upstream simulator
attribution. This grants no rights to the separately inspected F110 archives or
policy code. The [artifact-level source inspection](reports/ope_interface_qualification.md#inspected-sources-and-rights)
verifies upstream code licenses; corrected ZIP permission remains unresolved. The earlier
public-driving bag has its own [CC BY 4.0 source record](runs/real_command_response/source.json).
See the [source register](docs/upstream_roboracer_sources.md) and
[identity note](docs/REPOSITORY_IDENTITY.md) for the retained project history.
