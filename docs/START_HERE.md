# Start here: Sim-to-Real Controller Ranking

The [README](../README.md) is the overview and the [roadmap](../ROADMAP.md) is
the plan. This guide is for reading the work quickly or rerunning part of it.

## Reading paths

| Purpose | Read |
| --- | --- |
| Current question and result | [README](../README.md), [qualification report](../reports/ope_qualification.md) |
| Review the executed checks | [Structural result](../runs/ope_qualification/result.json), [reproduction commands](../reports/ope_qualification.md#reproduce) |
| Understand what remains unresolved | [Roadmap](../ROADMAP.md), [open questions](OPEN_QUESTIONS.md) |
| Reuse earlier work | [History index](history/README.md), [data and figures](data-and-figures.md) |

The study asks whether variation in predicted differences between controller
pairs can identify choices likely to reverse on a real platform. Abstention
means withholding a controller choice when the evidence is insufficient. The
[roadmap](../ROADMAP.md) states each milestone's prerequisites and completion
evidence. The original archive census remains available. [Corrected-source
checks](../reports/ope_interface_qualification.md) found a loader defect, and
the [corrected-v2 census](../reports/ope_corrected_v2.md) established archive
identity and recording boundaries. Corrected ZIP reuse terms, reward agreement
with the published reference and the benchmark's historical simulator revision
remain unresolved. Earlier command-response, simulator and mast studies remain
at their original paths; their old task lists do not restart those studies.

## Reproduce by environment

Run commands from the repository root. Keep the environments separate;
their dependency versions differ on purpose.

### Historical portable checks: Python 3.10

Use a separate Python 3.10 environment with `requirements-item11-regression.txt`
and `requirements-report.txt`, then run the [CI checks](../.github/workflows/ci.yml):

```bash
PYTHONPATH=gym python experiments/test_rosbag_to_telemetry.py
PYTHONPATH=gym python experiments/test_bag_evidence.py
PYTHONPATH=gym python experiments/validate_item11.py
PYTHONPATH=gym python experiments/test_mast_physical_validation.py
PYTHONPATH=gym python experiments/test_cad_inputs.py
PYTHONPATH=gym python experiments/test_final_report.py
```

Each should exit 0. They need no ROS install, vehicle or test rig.

### Corrected-source interfaces: Python 3.11

Use [requirements-ope-interface.txt](../requirements-ope-interface.txt) and the
[source-only reproduction command](../reports/ope_interface_qualification.md#reproduce-this-source-only-result).
It executes pinned policy code on synthetic observations and loader methods on
synthetic arrays. It opens no archive or performance outcome.

### Original archive qualification: Python 3.11

Use [requirements-ope-qualification.txt](../requirements-ope-qualification.txt)
and the [executed qualification commands](../reports/ope_qualification.md#reproduce).
The archives stay in an external cache. Do not run policies or read outcomes.

### Historical public driving data

Use the isolated environment and reproduction command in the
[development report](../reports/real_command_response.md#reproduce).
The [metadata census](../reports/driving_split_qualification.md#reproduce-the-metadata-census)
uses only its committed metadata snapshot.

### CAD — pinned CadQuery environment

The [CAD workflow](../.github/workflows/cad-geometry.yml) uses the package
pins in [cad/requirements.lock](../cad/requirements.lock). They pin direct
packages only, not the full dependency tree. With Conda:

```bash
conda create -n racing-cad -c conda-forge --strict-channel-priority --file cad/requirements.lock
conda activate racing-cad
python cad/input_requests.py --check
python cad/generate.py --parameters cad/roboracer/parameters.csv --output /tmp/racing-cad-review
python -m pytest cad/tests -q
```

The generator writes `mast_tube.step` and `geometry.json`, and the tests
compare them with the [geometry contract](../cad/contract.json). If pytest
crashes while importing `readline` on your machine, this works around it:

```bash
python -c 'import sys,types; sys.modules["readline"]=types.ModuleType("readline"); import pytest; raise SystemExit(pytest.main(["cad/tests","-q"]))'
```

### Legacy simulation — Python 3.9

The [Gym environment](../environment.yml) keeps the older simulator stack.
Regenerate results in a separate checkout so they aren't mixed with other
edits.

```bash
conda env create -f environment.yml
conda activate f1tenth-gym
python -m pip install -e .
./run_all.sh
```

The long MPC and robustness sweeps are opt-in:

```bash
RUN_FULL_MPC=1 RUN_ROBUSTNESS=1 ./run_all.sh
```

[Data and figures](data-and-figures.md) gives single-study commands. GUI
rendering needs OpenGL.

### ROS 2

Follow the [Ubuntu Humble](ros2_verification_ubuntu_humble.md) or
[RoboStack macOS](ros2_verification_robostack_macos.md) setup first. The
package is [`f1tenth_modeling`](../ros2_ws/src/f1tenth_modeling), and the
[telemetry dictionary](telemetry_data_dictionary.md) defines its data format.

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
```

Don't launch excitation against a physical vehicle as a first test; choose the
simulator or hardware context on purpose.

## Before reusing or citing

Read the [upstream source register](upstream_roboracer_sources.md), the
[license](../LICENSE) and [CONTRIBUTING.md](../CONTRIBUTING.md). Give the
source commit in any review or citation. Historical task status is retained in the
[CAD task record](history/CAD_TASKS.csv); current work follows the roadmap. The September 11
[completion correction](COMPLETION_RECONCILIATION.md) explains which early
deliverables were preparation rather than finished work.
