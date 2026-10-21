"""Apply the registered lexicographic ranking to complete checkpointed runs."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from experiments.controller_combinations import OUT, PROTOCOL, read, sha


def summarize() -> dict:
    protocol = read(PROTOCOL)
    names = protocol["architecture_order"]
    cases = [(track, scenario, timing)
             for track in protocol["tracks"]
             for timing, scenarios in protocol["timing_modes"].items()
             for scenario in scenarios]
    runs = {}
    for track, scenario, timing in cases:
        for name in names:
            path = OUT / f"{track}_{scenario}_{timing}_{name}.json"
            if not path.exists():
                raise FileNotFoundError(path)
            run = read(path)
            if run["protocol_sha256"] != sha(PROTOCOL):
                raise ValueError(f"Stale run: {path}")
            trace = Path(__file__).resolve().parents[1] / run["telemetry"]
            if sha(trace) != run["telemetry_sha256"]:
                raise ValueError(f"Changed telemetry: {trace}")
            runs[(track, scenario, timing, name)] = run
    ranking = []
    for index, name in enumerate(names):
        selected = [runs[(*case, name)] for case in cases]
        complete = [r for r in selected if r["completed_lap"] and not r["collision"]]
        motion_fails = sum(not r["motion_constraint_pass"] for r in selected)
        deadline_misses = sum(r["whole_compute_deadline_misses"] for r in selected if r["timing_mode"] == "deadline_aware")
        eligible = len(complete) == len(cases) and motion_fails == 0 and deadline_misses == 0
        row = {
            "architecture": name, "attempted": len(cases), "executed": len(selected),
            "completed": len(complete), "noncompleted": len(cases) - len(complete),
            "motion_failed_runs": motion_fails, "deadline_aware_misses": deadline_misses,
            "qualifies": eligible,
            "worst_completed_gym_finish_s": max((r["lap_time_s"] for r in complete), default=None),
            "mean_completed_gym_finish_s": sum(r["lap_time_s"] for r in complete) / len(complete) if complete else None,
            "mean_completed_rms_reference_distance_m": sum(r["rms_reference_distance_m"] for r in complete) / len(complete) if complete else None,
            "max_whole_compute_s": max(r["whole_compute_max_s"] for r in selected),
            "total_switches": sum(r["switch_count"] for r in selected),
            "non_nominal_completed": sum(r["completed_lap"] and not r["collision"] for r in selected if r["scenario"] != "nominal"),
            "non_nominal_attempted": sum(r["scenario"] != "nominal" for r in selected),
        }
        ranking.append(row)
    ranking.sort(key=lambda row: (int(not row["qualifies"]), row["noncompleted"],
                                  row["motion_failed_runs"], row["deadline_aware_misses"],
                                  row["worst_completed_gym_finish_s"] if row["worst_completed_gym_finish_s"] is not None else float("inf"),
                                  row["mean_completed_rms_reference_distance_m"] if row["mean_completed_rms_reference_distance_m"] is not None else float("inf"),
                                  names.index(row["architecture"])))
    pairs = []
    for track, scenario, timing in cases:
        for a, b in itertools.combinations(names, 2):
            left, right = runs[(track, scenario, timing, a)], runs[(track, scenario, timing, b)]
            difference = (left["lap_time_s"] - right["lap_time_s"]
                          if left["completed_lap"] and right["completed_lap"] and not left["collision"] and not right["collision"]
                          else None)
            pairs.append({"track": track, "scenario": scenario, "timing_mode": timing,
                          "pair": [a, b], "finish_difference_s": difference,
                          "inside_near_tie": abs(difference) <= protocol["ranking"]["near_tie_s"] if difference is not None else None})
    criteria = {
        "completion_and_constraints": sorted(names, key=lambda n: (-next(x for x in ranking if x["architecture"] == n)["completed"],
                                                     next(x for x in ranking if x["architecture"] == n)["motion_failed_runs"],
                                                     next(x for x in ranking if x["architecture"] == n)["deadline_aware_misses"])),
        "finish_time": sorted(names, key=lambda n: next(x for x in ranking if x["architecture"] == n)["mean_completed_gym_finish_s"] or float("inf")),
        "tracking": sorted(names, key=lambda n: next(x for x in ranking if x["architecture"] == n)["mean_completed_rms_reference_distance_m"] or float("inf")),
        "compute_deadlines": sorted(names, key=lambda n: (next(x for x in ranking if x["architecture"] == n)["deadline_aware_misses"],
                                                    next(x for x in ranking if x["architecture"] == n)["max_whole_compute_s"])),
        "disturbance_robustness": sorted(names, key=lambda n: -next(x for x in ranking if x["architecture"] == n)["non_nominal_completed"]),
    }
    by_name = {row["architecture"]: row for row in ranking}
    def tied_extrema(order, score, tolerance=0.0):
        best, worst = score(by_name[order[0]]), score(by_name[order[-1]])
        return {"best": [name for name in order if score(by_name[name]) == best or abs(score(by_name[name]) - best) <= tolerance],
                "worst": [name for name in order if score(by_name[name]) == worst or abs(score(by_name[name]) - worst) <= tolerance]}
    extrema = {
        "finish_time": tied_extrema(criteria["finish_time"],
                                    lambda row: row["mean_completed_gym_finish_s"] if row["mean_completed_gym_finish_s"] is not None else float("inf"),
                                    protocol["ranking"]["near_tie_s"]),
        "tracking": tied_extrema(criteria["tracking"],
                                 lambda row: row["mean_completed_rms_reference_distance_m"] if row["mean_completed_rms_reference_distance_m"] is not None else float("inf"),
                                 protocol["shared_limits"]["numeric_tolerance"]),
        "disturbance_robustness": tied_extrema(criteria["disturbance_robustness"],
                                                lambda row: -row["non_nominal_completed"]),
    }
    for criterion, fields in (("completion_and_constraints", ("completed", "motion_failed_runs", "deadline_aware_misses")),
                              ("compute_deadlines", ("deadline_aware_misses",))):
        order = criteria[criterion]
        def key(name):
            row = by_name[name]
            return tuple(row[field] for field in fields)
        extrema[criterion] = {"best": [name for name in order if key(name) == key(order[0])],
                              "worst": [name for name in order if key(name) == key(order[-1])]}
    return {"protocol_sha256": sha(PROTOCOL), "cases_per_architecture": len(cases),
            "architecture_count": len(names), "run_count": len(runs),
            "has_qualifying_overall_winner": any(r["qualifies"] for r in ranking),
            "overall_order": [r["architecture"] for r in ranking],
            "ranking": ranking, "criterion_orders": criteria,
            "criterion_tied_extrema": extrema, "pairwise": pairs}


def main():
    summary = summarize()
    (OUT / "ranking.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: summary[key] for key in ("run_count", "has_qualifying_overall_winner", "overall_order")}, indent=2))


if __name__ == "__main__":
    main()
