# Open questions and scope decisions

This record accompanies the [executed qualification](../reports/ope_qualification.md).
The [roadmap](../ROADMAP.md) is the only plan.

## Current software scope

The owner adopted the dependency roadmap and authorized removal of obsolete
active implementation, work orders and presentation assets. The active method
question concerns dispersion of paired controller-performance differences and
calibrated abstention, including near ties. This authorization supplies no data
rights or permission to execute the future research milestones. The
retained confidence-gate baseline, registered prediction and scope limit are in [roadmap M3](../ROADMAP.md#m3-calibrate-a-controller-difference-abstention-rule).

Dataset qualification and owner-approved platform access are parallel possible
routes. Failure of one source requires a route decision, rather than a claim that
all legitimate routes are closed. The [history index](history/README.md) records
what was removed and why useful historical work remains.

| Question | Status | Evidence or action needed |
| --- | --- | --- |
| Data and code reuse rights | Public code licenses inspected; corrected ZIP permission unresolved | See the [artifact-level findings](../reports/ope_interface_qualification.md#inspected-sources-and-rights). The owner-supplied full reply confirms code-license additions without explicit external ZIP terms |
| Recording segment versus episode | Full reply inspected; filter candidate qualified on synthetic inputs | Review the [candidate correction](../reports/ope_interface_qualification.md#separate-correction-qualification), then verify exclusions, terminal/censoring rules and independent acquisition groups against permitted records |
| Policy correspondence and execution | Synthetic batch, single-state, reset and permutation checks agree | [Executed cases](../runs/ope_interface_qualification/result.json); archived observation coverage and complete environment construction remain unqualified |
| Loader aliases | Corrected registrations inspected | Distinct Drive objects replace the old simulation-v1 alias. Corrected ZIP hashes, roots and census remain unverified |
| FQE and probability-ratio methods | Empirical execution remains ineligible | Synthetic delta-action and log-density ordering checked. Archived likelihoods, coverage and degenerate support remain unqualified; separate [estimator gates](../reports/ope_qualification.md#estimator-gates) apply |
| External author contact | Full reply supplied by owner and inspected | [Contact record](ope_author_request.txt). Resolve ZIP permission, simulator revision and first-crash filtering. No follow-up sent |
| Simulator dependency | Public and Unlicense; benchmark revision unpinned | `.gitmodules` entry has no gitlink. Public head is not automatically the benchmark revision |
| Reward comparison | Common outcome unqualified | Simulation documentation lacks progress and `new_rewards`; never equate collection rewards by selecting `reward_config=None` |
| Reviewer, physical study, publication and campaign | No new approval supplied | Conditional M2 scope is in the roadmap; M3/M5 still require their separate prerequisites |

## Qualification pins

The [corrected-source input record](../runs/ope_interface_qualification/inputs.json)
pins the inspected benchmark, submodules and source files. The
[interface report](../reports/ope_interface_qualification.md) records executed
synthetic checks and the blocked archive census. The earlier
[archive input record](../runs/ope_qualification/inputs.json) retains its original
checksums. Do not substitute a Drive object based only on its filename.

## Superseded active questions, with decisions retained

| Earlier question | Disposition |
| --- | --- |
| Held-out command response and transfer to the owner's vehicle | Superseded as the active finish line by this software scope. [Development result](../reports/real_command_response.md) and [split blocker](../reports/driving_split_qualification.md) remain intact. K2 closure-or-wait remains unanswered; no final bags opened. |
| Fleet study | K1 adoption and K3 actual access remain unanswered. This pivot does not approve fleet work or establish vehicles. |
| Mast mounting, deck height and D2 study scope | Separately pending physical decision. Keep the delegated low-mount assessment provisional. No approved height, deck, fabrication, modal requirement or new frequency threshold. |
| Static stiffness as vibration evidence | Superseded as a sufficient modal/racing finish line. The [optional static protocol](specs/mast-physical-validation/design.md) remains historical preparation. |
| Funding, physical inventory, naming | No new decisions supplied. No purchase, successor repository or campaign created. |

Superseded means removed from the active software question, not answered or
approved. The [history index](history/README.md) retains the supporting work.
