# Open questions and scope decisions

This record accompanies the [executed qualification](../reports/ope_qualification.md).
The [roadmap](../ROADMAP.md) is the only plan.

## Current software scope

The owner adopted the dependency roadmap and authorized removal of obsolete
active implementation, work orders and presentation assets. The active method
question concerns dispersion of paired controller-performance differences and
calibrated abstention, including near ties. This adoption supplies no data
rights or permission to open reserved outcomes. M2 remains conditional on M1. The
retained confidence-gate baseline, registered prediction and scope limit are in [roadmap M3](../ROADMAP.md#m3-calibrate-a-controller-difference-abstention-rule).

The owner adopted qualification before reference ranking. A candidate
terminal-filter correction is qualified on the registered synthetic domain. Applying it to archive exclusions remains pending
the author's recording, crash, timeout and censoring interpretation. The older
wrong-alias archive census stays historical; corrected ZIPs need separate
permission, hashes and census. The conditional M2 ranking waits for a qualified
shared reward and simulator revision as well as the other M1 gates.

Dataset qualification and owner-approved platform access are parallel possible
routes. Failure of one source requires a route decision, rather than a claim that
all legitimate routes are closed. The [history index](history/README.md) records
what was removed and why useful historical work remains.

## Accepted development comparison direction

The owner accepted a comparison direction for accessible development records,
conditional on M1. These choices do not expose reserved outcomes or qualify the
corrected ZIPs.

| Element | Accepted direction and source | Still required before performance access |
| --- | --- | --- |
| Horizon | 250 steps, consistent with the pinned benchmark's [run_iw.py](https://github.com/HyberionBrew/f110_ope_benchmark/blob/42789222451f4ee0e679475a8798d7c47bf220b5/experiments/run_iw.py) `timesteps_to_include=(0,250)` | Confirm the timestep duration and the cutoff's timeout/terminal treatment on permitted records |
| Starts | Use recorded real start poses. The [author reply record](ope_author_request.txt) says simulation starts came from real rollouts | Establish eligible records and a comparable start distribution; no paired episode IDs were supplied |
| Rewards | Compare the four thesis reward definitions. The pinned [dataset README](https://github.com/HyberionBrew/f1tenth_orl_dataset/blob/536d762ad7b07076551d39ef202199cbaead6a87/README.md) names `reward_progress.json`, `reward_checkpoint.json`, `reward_lifetime.json` and `reward_min_act.json` | Match each thesis reward to executable code and a common calculation on both permitted archives; simulation lacks `new_rewards` |
| Simulator seeds | Start with 10 development seeds, per the owner's current instruction | Fix the exact seed list and verify how the intended simulator uses it; seeds sample simulator randomness, not independent vehicles |

Before opening any development performance outcome, freeze the actual timestep,
reward implementation, discounting, terminal and truncation handling, aggregation,
eligible start distribution and exact seeds. Apply the freeze only to qualifying
accessible development data. Proposed thesis correlations are source-check
candidates, not pass thresholds. No ranking or runtime sweep has been run under
this decision.

## Four proposed assumptions

Source: the local
`/Users/redhose/Projects/critical-audit-20261002/implementation/sim-to-real-assumptions-20261013/ASSUMPTIONS.md`,
SHA-256 `8ca006e41a4fed3bfdd3dcc83cf142904a14038f2fc1c30670067af039c30011`.
It records proposals from a Claude Code conversation with the owner. The file
explicitly says they are not yet owner accepted. The quoted sentences below are
source proposals, not findings or permission to use data.

1. **Data terms.** "Use the two v2 archives (f110-real-stoch-v2, f110-sim-stoch-v2,
   Google Drive, no licence text of their own) for research under the terms
   the author stated in his 2026-10-09 reply: cite the thesis "Deep off-policy
   evaluation with autonomous racing cars" (TU Wien, handle 20.500.12708/201148),
   publish derived results and figures, never redistribute the raw bytes or
   processed subsets." The inspected reply adds MIT terms to code and asks for
   thesis citation; it gives no explicit Drive-ZIP grant for research use,
   derived publication or redistribution. This proposal does not qualify the
   archives. An applicable data grant remains required.
2. **Simulator revision.** "Pin the public f110_sim_env head, commit
   0c15e5ba4e7537390777dc25c67c81628daf1d16 (2024-03-29, Unlicense,
   HyberionBrew/f110_sim_env), as the assumed revision for benchmark
   42789222451f4ee0e679475a8798d7c47bf220b5, whose .gitmodules lists the
   simulator with no gitlink." The public commit is a candidate. A successful
   end-to-end run could establish compatibility, not historical identity. A
   failed run could reflect the revision, another dependency or the environment;
   neither result identifies the author's executed revision. That identity
   remains unconfirmed.
3. **Crash and timeout semantics.** "Adopt the documented helper contract as the
   registered exclusion rule: keep the first terminal sample of a terminal run
   and drop later samples of the same run, including the final array row
   (the candidate correction qualified on the synthetic domain in PR #72)."
   This is a proposal for archive exclusions. The helper test establishes its
   synthetic contract only. Recording boundaries and the meaning of crash,
   intervention and timeout flags still need qualification before any exclusion
   rule is applied to corrected archives. The original pinned loader may then
   serve as a separately labeled sensitivity variant.
4. **Common reward.** "Recompute all four thesis rewards (progress, lifetime,
   minimum action, checkpoint) for both archives with the benchmark's reward
   setup from experiments/run_iw.py, because the sim archive lacks stored
   rewards." The pinned dataset README says simulation lacks `new_rewards`;
   collection rewards still exist. A shared calculation remains to be specified
   and checked. Matching the author's per-agent Groundtruth mean and standard
   deviation, if access is later permitted, would check aggregates only and
   cannot establish a unique implementation or per-record equivalence. A
   mismatch would require investigation before ranking.

The source also proposes a detailed comparison freeze. Its proposal status does
not change the owner's previously accepted high-level development comparison
direction above. Exact operational settings and source rights remain open, and
reserved outcomes stay closed.

| Question | Status | Evidence or action needed |
| --- | --- | --- |
| Data and code reuse rights | Public code licenses inspected; corrected ZIP permission unresolved | See the [artifact-level findings](../reports/ope_interface_qualification.md#inspected-sources-and-rights). The owner-supplied full reply confirms code-license additions without explicit external ZIP terms |
| Recording segment versus episode | Candidate correction qualified on synthetic inputs; archive exclusion unadopted | Determine whether the [candidate correction](../reports/ope_interface_qualification.md#separate-correction-qualification) applies under the author's recording, crash, timeout and censoring rules before processing permitted records |
| Policy correspondence and execution | Synthetic batch, single-state, reset and permutation checks agree | [Executed cases](../runs/ope_interface_qualification/result.json); archived observation coverage and complete environment construction remain unqualified |
| Loader aliases | Corrected registrations inspected; old census historical | Distinct Drive objects replace the old simulation-v1 alias. Corrected ZIP hashes, roots and census remain unverified |
| FQE and probability-ratio methods | Empirical execution remains ineligible | Synthetic delta-action and log-density ordering checked. Archived likelihoods, coverage and degenerate support remain unqualified; separate [estimator gates](../reports/ope_qualification.md#estimator-gates) apply |
| External author contact | Full reply supplied by owner and inspected | [Contact record](ope_author_request.txt). Resolve ZIP permission, simulator revision and archive terminal semantics. No follow-up sent |
| Simulator dependency | Public and Unlicense; benchmark revision unpinned | `.gitmodules` entry has no gitlink. Public head is not automatically the benchmark revision |
| Reward comparison | Common outcome unqualified | Simulation lacks progress and `new_rewards`; qualify one shared reward computation before M2 performance access |
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
