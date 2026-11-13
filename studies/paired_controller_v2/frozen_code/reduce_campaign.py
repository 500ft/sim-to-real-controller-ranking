"""Independent, read-only reduction of the frozen synthetic controller campaign.

No trajectory is rerun, excluded, relabeled or tuned here. Bootstrap units are
paired scenario draws; controller timing calls are reported descriptively.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'campaign_v2'
N_BOOT = 20000
BOOT_SEED = 994130


def distribution(x):
    x = np.asarray(x, dtype=float)
    if not len(x):
        return {'n': 0}
    if not np.all(np.isfinite(x)):
        raise ValueError('Nonfinite reduction input')
    return {'n': len(x), 'mean': float(np.mean(x)), 'median': float(np.median(x)),
            'p05': float(np.percentile(x, 5)), 'p95': float(np.percentile(x, 95)),
            'min': float(np.min(x)), 'max': float(np.max(x))}


def paired_difference(values, label):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {'n_pairs': 0, 'estimand': label}
    rng = np.random.default_rng(BOOT_SEED)
    samples = values[rng.integers(0, len(values), size=(N_BOOT, len(values)))].mean(axis=1)
    return {'n_pairs': len(values), 'estimand': label,
            'mean_difference': float(np.mean(values)),
            'paired_bootstrap_percentile_95': np.percentile(samples, [2.5, 97.5]).tolist(),
            'bootstrap_resamples': N_BOOT, 'bootstrap_seed': BOOT_SEED,
            'individual_differences': values.tolist()}


def csv_write(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def binomial_interval(k, n):
    # Exact Clopper-Pearson interval over this declared scenario-draw population.
    return [0. if k == 0 else float(beta.ppf(.025, k, n-k+1)),
            1. if k == n else float(beta.ppf(.975, k+1, n-k))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    protocol = json.loads((ROOT/'PROTOCOL.json').read_text())
    progress = json.loads((ROOT/'progress.json').read_text())
    files = sorted((ROOT/'cases').glob('*/*/*/result.json'))
    if not args.partial and (progress['state'] != 'completed' or len(files) != 420):
        raise RuntimeError(f'Campaign incomplete: {progress["state"]}, {len(files)}/420 results; no final reduction')
    results = [json.loads(p.read_text()) for p in files]
    keys = [(r['cell'], r['scenario']['seed'], r['controller']) for r in results]
    if len(set(keys)) != len(keys):
        raise RuntimeError('Duplicate case')
    if not all(r['numerical_input_checks_passed'] for r in results):
        raise RuntimeError('Invalid case present; no automatic exclusion')
    draws = {r['seed']: r for r in protocol['scenario_draws']}
    for path, r in zip(files, results):
        if r['scenario'] != draws[r['scenario']['seed']]:
            raise RuntimeError(f'Scenario realization differs from frozen draw: {path}')
    ctrl = ['pure_pursuit', 'lqr', 'mpc']
    cells = [r['name'] for r in protocol['cells']]
    seeds = [r['seed'] for r in protocol['scenario_draws']]
    expected = {(cell, seed, name) for cell in cells for seed in seeds for name in ctrl}
    if not set(keys).issubset(expected) or (not args.partial and set(keys) != expected):
        raise RuntimeError('Observed case identities differ from frozen factorial design')
    for relative, expected_hash in protocol['source_hashes'].items():
        if hashlib.sha256((HERE/relative).read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError(f'Frozen study code changed: {relative}')
    lookup = dict(zip(keys, results))
    by_case = {key: path for key, path in zip(keys, files)}
    out = ROOT / ('reduction_partial' if args.partial else 'reduction')
    out.mkdir(exist_ok=True)
    summary = {'complete_campaign': progress['state'] == 'completed' and len(results) == 420,
               'saved_cases': len(results), 'expected_cases': 420,
               'protocol_sha256': hashlib.sha256((ROOT/'PROTOCOL.json').read_bytes()).hexdigest(),
               'reducer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'interpretation': 'Synthetic scenario sensitivity in an unsaturated linear-tire model with perfect state. Intervals describe these perturbation draws, not physical performance or generalization. Times conditional on common completed one-circuit trials. Recorded controller computation includes trim/model-cache/optimization but excludes final output clipping and return; full_call_* field names are preserved historical labels. Timing samples are nested within trials and descriptive only.',
               'by_cell_controller': {}, 'paired_controllers': {}, 'paired_OAT': {},
               'mass_structural_null_checks': {}}
    if not args.partial:
        checked = []
        for path, r in zip(files, results):
            trace = np.loadtxt(path.parent/'trace.csv', delimiter=',', skiprows=1)
            if trace.ndim != 2 or trace.shape[1] != 13 or not np.all(np.isfinite(trace)):
                raise RuntimeError(f'Invalid saved trajectory: {path}')
            readback = {'time_s': float(trace[-1, 0]), 'progress_m': float(trace[-1, 11]),
                        'rms_cte_m': float(np.sqrt(np.mean(trace[:, 10]**2))),
                        'max_abs_cte_m': float(np.max(np.abs(trace[:, 10]))),
                        'max_abs_beta_rad': float(np.max(np.abs(trace[:, 7])))}
            residuals = {key: abs(value-r[key]) for key, value in readback.items()}
            if max(residuals.values()) > 1e-10:
                raise RuntimeError(f'Saved trajectory metric readback disagrees: {path}: {residuals}')
            checked.append({'case': '/'.join(path.parent.relative_to(ROOT/'cases').parts),
                            'saved_steps': len(trace), 'max_metric_absolute_readback_error': max(residuals.values())})
        csv_write(out/'trajectory_readback.csv', checked)
        summary['independent_trajectory_readback'] = {'checked_cases': len(checked),
            'max_metric_absolute_error': max(r['max_metric_absolute_readback_error'] for r in checked),
            'comparison_tolerance': 1e-10, 'passed': True}
    rows = []
    for cell in cells:
        for name in ctrl:
            group = [lookup[cell, s, name] for s in seeds if (cell, s, name) in lookup]
            if not group:
                continue
            done = [r for r in group if r['completed_one_circuit']]
            timings = []
            for r in group:
                path = by_case[cell, r['scenario']['seed'], name].parent/'controller_times_s.csv'
                t = np.atleast_1d(np.loadtxt(path, skiprows=1))
                if len(t) != r['control_calls'] or not np.all(np.isfinite(t)) or np.any(t < 0):
                    raise RuntimeError(f'Invalid timing input {path}')
                if int(sum(t > .010)) != r['calls_over_10ms']:
                    raise RuntimeError(f'Timing miss readback disagrees {path}')
                timings.append(t)
            all_t = np.concatenate(timings)
            reasons = {reason: sum(r['reason'] == reason for r in group)
                       for reason in sorted({r['reason'] for r in group})}
            group_summary = {'attempted': len(group), 'completed': len(done), 'outcomes': reasons,
                             'completion_binomial_exact_95_for_declared_scenarios': binomial_interval(len(done), len(group)),
                             'completion_time_s_conditional': distribution([r['time_s'] for r in done]),
                             'rms_cte_m_completed_only': distribution([r['rms_cte_m'] for r in done]),
                             'max_cte_m_all_outcomes': distribution([r['max_abs_cte_m'] for r in group]),
                             'full_call_timing_ms': distribution(all_t * 1000),
                             'calls_over_10ms': int(sum(all_t > .010)),
                             'trials_with_call_over_10ms': sum(r['calls_over_10ms'] > 0 for r in group),
                             'max_beta_rad': max(r['max_abs_beta_rad'] for r in group),
                             'max_lateral_accel_over_mu_g_proxy': max(r['max_lateral_accel_over_mu_g_proxy'] for r in group),
                             'trials_above_lateral_mu_g_proxy': sum(r['physics_steps_above_lateral_mu_g_proxy'] > 0 for r in group),
                             'total_physics_steps_above_lateral_mu_g_proxy': sum(r['physics_steps_above_lateral_mu_g_proxy'] for r in group)}
            summary['by_cell_controller'][cell+'/'+name] = group_summary
            rows.append({'cell': cell, 'controller': name, 'attempted': len(group), 'completed': len(done),
                         'contact': reasons.get('rectangular_map_contact', 0), 'timeout': reasons.get('timeout', 0),
                         'conditional_mean_time_s': group_summary['completion_time_s_conditional'].get('mean', ''),
                         'conditional_mean_rms_cte_m': group_summary['rms_cte_m_completed_only'].get('mean', ''),
                         'full_call_p50_ms': float(np.median(all_t)*1000),
                         'full_call_p95_ms': float(np.percentile(all_t, 95)*1000),
                         'full_call_max_ms': float(max(all_t)*1000),
                         'control_calls': len(all_t), 'calls_over_10ms': int(sum(all_t > .010)),
                         'max_beta_rad': group_summary['max_beta_rad'],
                         'max_lateral_accel_over_mu_g_proxy': group_summary['max_lateral_accel_over_mu_g_proxy']})
        for a, b in [('lqr', 'pure_pursuit'), ('mpc', 'pure_pursuit'), ('mpc', 'lqr')]:
            pairs = [(lookup[cell,s,a], lookup[cell,s,b]) for s in seeds
                     if (cell,s,a) in lookup and (cell,s,b) in lookup]
            common = [(x,y) for x,y in pairs if x['completed_one_circuit'] and y['completed_one_circuit']]
            summary['paired_controllers'][cell+'/'+a+'-minus-'+b] = {
                'completed_minus_completed': paired_difference([int(x['completed_one_circuit'])-int(y['completed_one_circuit']) for x,y in pairs], 'All paired outcome indicators, A minus B'),
                'time_s': paired_difference([x['time_s']-y['time_s'] for x,y in common], 'Mean one-circuit duration difference among common completions, A minus B'),
                'rms_cte_m': paired_difference([x['rms_cte_m']-y['rms_cte_m'] for x,y in common], 'Mean RMS CTE difference among common completions, A minus B')}
    for cell in cells[1:]:
        for name in ctrl:
            pairs = [(lookup[cell,s,name], lookup['nominal',s,name]) for s in seeds
                     if (cell,s,name) in lookup and ('nominal',s,name) in lookup]
            common = [(x,y) for x,y in pairs if x['completed_one_circuit'] and y['completed_one_circuit']]
            summary['paired_OAT'][cell+'/'+name] = {
                'completion_difference': paired_difference([int(x['completed_one_circuit'])-int(y['completed_one_circuit']) for x,y in pairs], 'Perturbed minus nominal completion indicator'),
                'time_s': paired_difference([x['time_s']-y['time_s'] for x,y in common], 'Perturbed minus nominal conditional duration'),
                'rms_cte_m': paired_difference([x['rms_cte_m']-y['rms_cte_m'] for x,y in common], 'Perturbed minus nominal conditional RMS CTE')}
            if cell.startswith('mass_I') and pairs:
                summary['mass_structural_null_checks'][cell+'/'+name] = {
                    metric: max(abs(x[metric]-y[metric]) for x,y in pairs)
                    for metric in ['time_s', 'rms_cte_m', 'max_abs_cte_m', 'progress_m']}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    csv_write(out/'cell_summary.csv', rows)
    lines = ['FROZEN SYNTHETIC RACING CAMPAIGN — REDUCTION', '',
             f'Status: {len(results)}/420 saved cases; complete={summary["complete_campaign"]}.',
             summary['interpretation'], '',
             'cell | controller | completed/attempted | mean completed time (s) | mean completed RMS CTE (m) | timing p95/max (ms) | misses/calls']
    for r in rows:
        time_text = f'{r["conditional_mean_time_s"]:.4f}' if r['conditional_mean_time_s'] != '' else '—'
        cte_text = f'{r["conditional_mean_rms_cte_m"]:.5f}' if r['conditional_mean_rms_cte_m'] != '' else '—'
        lines.append(f'{r["cell"]} | {r["controller"]} | {r["completed"]}/{r["attempted"]} | {time_text} | {cte_text} | {r["full_call_p95_ms"]:.3f}/{r["full_call_max_ms"]:.3f} | {r["calls_over_10ms"]}/{r["control_calls"]}')
    lines.extend(['', 'Paired bootstrap: 20,000 percentile resamples of scenario pairs, fixed seed 994130.',
                  'Timing samples are preserved in each case; percentiles are descriptive, not independent-trial confidence intervals.',
                  'No multiplicity correction or inferential ranking is claimed. Common-completion denominators are explicit in summary.json.',
                  'An all-zero paired completion difference gives a degenerate empirical bootstrap interval; it does not establish equal underlying reliability. Exact binomial completion intervals are included separately.',
                  'Coherent mass and inertia scaling is a structural null in this normalized-tire plant. It does not establish physical payload robustness.'])
    (out/'SUMMARY.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
