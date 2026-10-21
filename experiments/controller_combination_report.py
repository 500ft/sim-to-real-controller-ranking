"""Render the executed combination ledger without hand-copying result numbers."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/controller_combinations/ranking.json"
TARGET = ROOT / "reports/controller_combinations.md"

LABELS = {
    "pp": "PP",
    "pp_lqr": "PP + LQR correction",
    "pp_mpc": "PP + MPC correction",
    "lqr_active_mpc_shadow": "PP + LQR active; PP + MPC shadow",
    "mpc_active_lqr_shadow": "PP + MPC active; PP + LQR shadow",
    "mpc_lqr_fallback": "PP + MPC primary; PP + LQR fallback",
    "pp_blend": "PP + weighted LQR/MPC corrections",
}


def value(number, digits=3):
    return "NA" if number is None else f"{number:.{digits}f}"


def render():
    summary = json.loads(SOURCE.read_text())
    protocol = json.loads((SOURCE.parent / "protocol.json").read_text())
    rows = summary["ranking"]
    lines = ["# Controller combinations on two development tracks", "",
             "This is a simulation-development comparison on the checked-in example and licensed MapZoo Berlin lines. "
             "Legacy `lqr` and `mpc` in the earlier pipeline already meant PP plus bounded LQR or MPC correction; "
             "the labels below make that architecture explicit. No real-data or physical-platform ranking follows from these runs.", "",
             "[Registered protocol](../runs/controller_combinations/protocol.json) · "
             "[frozen blend choice](../runs/controller_combinations/frozen_blend.json) · "
             "[machine-readable ranking and pairwise differences](../runs/controller_combinations/ranking.json)", "",
             "## Frozen candidates and exclusions", "",
             "PP, PP plus LQR correction, and PP plus MPC correction are the three active baselines. "
             "The two pure-shadow wrappers apply only the named active controller; the shadow receives the same observation "
             "and its bypassed state is synchronized to the applied command. Their shadow proposals are diagnostics, "
             "not counterfactual lap times. The fallback switches from MPC to LQR after registered solver, finite-output, "
             "command-domain or timing failure, with five control ticks of dwell and three valid MPC ticks for recovery. "
             "The blend adds weighted bounded corrections to one PP base, subtracting each correction controller's own PP feedforward first. "
             "The LQR-primary selective MPC takeover was excluded before outcomes because no distinct justified trigger was available.", "",
             "The seven candidates share the frozen per-track source-line controller settings. Only the blend added a three-weight "
             "offline search on the prior tuning start, then froze its choice before evaluation. Those tuning records, "
             "including constraint failures, remain in [the run directory](../runs/controller_combinations/frozen_blend.json). "
             "The faster Berlin line from the earlier pipeline remains excluded because its closed-loop motion limits failed.", "",
             "## Overall development ordering", "",
             "The preregistered order first requires every case to finish without collision, pass shared motion limits, "
             "and meet the measured compute deadline in timing-aware runs. It then compares noncompletions, motion-limit "
             "failures, deadline misses, worst completed Gym finish and mean tracking distance. A noncompletion receives no finite lap time. "
             "Each track/scenario/timing case has equal count weight; the worst finish is a separate lexicographic criterion.", ""]
    if summary["has_qualifying_overall_winner"]:
        lines += [f"Qualifying best under this rule: **{LABELS[rows[0]['architecture']]}**. "
                  f"Measured worst in this candidate set: **{LABELS[rows[-1]['architecture']]}**.", ""]
    else:
        lines += ["**No candidate qualifies as an overall winner** under the registered motion and timing requirements. "
                  f"The conditional development order begins with **{LABELS[rows[0]['architecture']]}** "
                  f"and ends with **{LABELS[rows[-1]['architecture']]}**. "
                  "This is an ordering of measured candidates under failed requirements, not a recommended vehicle controller.", ""]
    lines += ["| Conditional order | Architecture | Completed / attempted | Motion-failed runs | Deadline-aware misses | Mean completed Gym finish [s] | Mean completed RMS distance [m] | Max whole-call compute [ms] |",
              "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for index, row in enumerate(rows, 1):
        lines.append(f"| {index} | {LABELS[row['architecture']]} | {row['completed']} / {row['attempted']} | "
                     f"{row['motion_failed_runs']} | {row['deadline_aware_misses']} | "
                     f"{value(row['mean_completed_gym_finish_s'])} | "
                     f"{value(row['mean_completed_rms_reference_distance_m'], 4)} | "
                     f"{value(row['max_whole_compute_s'] * 1000, 2)} |")
    lines += ["", "Completed-time and tracking averages include only completed cases, so compare them alongside coverage. "
              "The 0.1 s near-tie rule and 2 ms Gym integration grid bound interpretation of small finish differences; "
              "[pairwise differences](../runs/controller_combinations/ranking.json) retain each common case.", "",
              "## Criterion-specific order", "",
              "| Criterion | Best measured candidate | Worst measured candidate | Scope |",
              "| --- | --- | --- | --- |"]
    for criterion, order in summary["criterion_orders"].items():
        extrema = summary["criterion_tied_extrema"][criterion]
        best = ", ".join(LABELS[name] for name in extrema["best"])
        worst = ", ".join(LABELS[name] for name in extrema["worst"])
        lines.append(f"| {criterion.replace('_', ' ')} | {best} | {worst} | "
                     "Ties use the registered near-tie bound for finish, exact counts for coverage and deadline misses. |")
    lines += ["", "## Execution and interpretation", "",
              f"The ledger contains {summary['run_count']} executed full-horizon runs, "
              f"{summary['cases_per_architecture']} common cases per architecture on two tracks. "
              "Ideal simulated-time and measured deadline-aware runs are separate; late commands wait for a later control tick. "
              "The injected MPC timeout and actuator delay are deterministic development assumptions, not measured hardware latency. "
              "Whole-call timing includes shadow computation and is host-dependent. Stiffness variants retain paired front/rear values "
              "from earlier synthetic identification, not an identified vehicle uncertainty distribution. No grip range was qualified. "
              "Repeated deterministic cases are neither independent vehicles nor real-platform transfer evidence.", "",
              "Each [run JSON](../runs/controller_combinations/ranking.json) links a compressed control-tick trace and its SHA-256. "
              "The final terminal integration row is retained. Full 2 ms integration traces and their hashes were kept locally "
              "outside git after extracting compact telemetry; the runner regenerates them. Earlier source errors and exploratory "
              "runs remain in [history](../runs/controller_combinations/history/pre_sync/README.md).", "",
              "The synchronized videos show real sampled simulator positions, applied steering, active and shadow identities, "
              "switches and terminal status. They do not infer a shadow controller's hypothetical trajectory.", "",
              "- [Example timeout comparison video](../runs/controller_combinations/example_mpc_timeout_deadline_aware_comparison.mp4) "
              "and [preview](../runs/controller_combinations/example_mpc_timeout_deadline_aware_preview.png)",
              "- [MapZoo Berlin timeout comparison video](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_comparison.mp4) "
              "and [preview](../runs/controller_combinations/mapzoo_berlin_mpc_timeout_deadline_aware_preview.png)", "",
              "## Reproduce", "", "Use the Python 3.9 Gym environment specified by the parent "
              "[pipeline report](controller_pipeline.md). The commands use only checked-in and pinned public simulation assets.", "",
              "```bash", "export PYTHONPATH=gym:.", "python -m unittest roboracer.test_controller_combinations -v",
              "python -m experiments.controller_combinations pilot", "python -m experiments.controller_combinations tune",
              "python -m experiments.controller_combinations freeze", "# Commit frozen_blend.json before evaluation.",
              "python -m experiments.controller_combinations evaluate", "python -m experiments.controller_combination_publish",
              "python -m experiments.controller_combination_ranking", "python -m experiments.controller_combination_video example mpc_timeout deadline_aware",
              "python -m experiments.controller_combination_video mapzoo_berlin mpc_timeout deadline_aware",
              "python -m unittest experiments.test_controller_combination_results -v", "```", "",
              "The paper's M1/M2/M3/M5 qualification gates and reserved groups remain unchanged.", ""]
    TARGET.write_text("\n".join(lines))


if __name__ == "__main__":
    render()
