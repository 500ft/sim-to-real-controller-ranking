#!/usr/bin/env python3
"""Execute pinned public-source interface checks on synthetic inputs only.

Never opens a dataset ZIP, Groundtruth file, saved return or held-out outcome.
The loader adapter extracts unchanged methods and supplies an in-memory Zarr
stand-in. It does not validate gym construction, maps, physics or archived rows.
"""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from types import SimpleNamespace
from typing import Optional, Union
from urllib.request import urlopen

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'runs/ope_interface_qualification/inputs.json'
TOLERANCE = 1e-12  # Same float64 operations on each row; permits round-off only.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_sources(cache, manifest, fetch):
    cache.mkdir(parents=True, exist_ok=True)
    for name, spec in manifest['files'].items():
        path = cache/name
        if not path.exists() and fetch:
            with urlopen(spec['url']) as response:
                payload = response.read()
            if spec['canonical_tree_json']:
                payload = (json.dumps(json.loads(payload), indent=2)+'\n').encode()
            path.write_bytes(payload)
        if digest(path) != spec['sha256']:
            raise ValueError(f'Source hash mismatch: {name}')
    return {n: cache/n for n in manifest['files']}


def registrations(path):
    return {args['id']: args['kwargs'] for args in (
        {kw.arg: ast.literal_eval(kw.value) for kw in n.keywords}
        for n in ast.walk(ast.parse(path.read_text()))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'register')}


def loader_checks(path):
    parsed = ast.parse(path.read_text())
    cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == 'F1tenthDatasetEnv')
    methods = ['get_dataset', '_find_consecutive_terminals_indices',
               '_remove_indices_from_dataset', 'clip_trajectories', 'add_timesteps']
    selected = [copy.deepcopy(n) for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    subset = ast.Module(body=[ast.ClassDef(name='LoaderMethods', bases=[], keywords=[], body=selected, decorator_list=[])], type_ignores=[])
    scope = {'np': np, 'os': os, 'Union': Union, 'Optional': Optional}
    exec(compile(ast.fix_missing_locations(subset), str(path), 'exec'), scope)
    loader = scope['LoaderMethods']()
    defaults = dict(remove_cons_terminals=True, set_previous_step_terminals=0,
                    include_vesc_fault_trajectories=False, timesteps_to_include=(0, 250),
                    set_terminals=True, use_compute_termination=True, include_time_obs=True,
                    include_progress=False, encode_cyclic=True, use_delta_actions=True,
                    delta_factor=1., flatten_obs=False, reward_config=None,
                    include_pose_time_diff=False, include_action_pose_time_diff=False,
                    bad_agents=[], bad_trajectories=[], train_only=False, eval_only=False,
                    eval_agents=['synthetic'], keys=[])
    for k, v in defaults.items():
        setattr(loader, k, v)

    def fixture(flags):
        size = len(flags)
        obs = {k: np.zeros(size) for k in ('poses_y', 'ang_vels_z', 'linear_vels_x',
                                          'linear_vels_y', 'theta_sin')}
        obs.update(poses_x=np.arange(size), theta_cos=np.ones(size),
                   previous_action=np.tile([.1, 1.], (size, 1)),
                   lidar_occupancy=np.ones((size, 54)))
        return dict(actions=np.tile([.02, .03], (size, 1)),
                    raw_actions=np.tile([.12, 1.03], (size, 1)), observations=obs,
                    done=np.array(flags, dtype=bool), compute_termination=np.array(flags, dtype=bool),
                    truncated=np.arange(size) == size-1, rewards=np.zeros(size), infos={},
                    model_name=np.repeat('synthetic', size), log_prob=np.zeros((size, 2)))

    def execute(flags):
        scope['zarr'] = SimpleNamespace(open=lambda *args, **kwargs: fixture(flags))
        with contextlib.redirect_stdout(io.StringIO()):
            return loader.get_dataset(zarr_path='synthetic-only')

    cases = []
    for name, flags, expected in [
        ('interior_terminal_run', [False, True, True, False, False, False], [0, 1, 3, 4, 5]),
        ('terminal_run_at_array_end', [False, False, True, True, True, True], [0, 1, 2]),
    ]:
        data = execute(flags)
        kept = data['observations']['poses_x'].tolist()
        cases.append(dict(name=name, input_terminals=flags, expected_kept_rows=expected,
                          actual_kept_rows=kept, agrees=kept == expected,
                          actual_terminals=data['terminals'].tolist(), actual_timeouts=data['timeouts'].tolist()))
    data = execute([False]*6)
    assert data['terminals'].tolist() == [False]*5+[True]
    assert data['timeouts'].tolist() == [False]*5+[True]
    assert np.array_equal(data['actions'], np.tile([.02, .03], (6, 1)))
    assert np.array_equal(data['observations']['previous_action_steer'], np.repeat(.1, 6))
    assert np.array_equal(data['observations']['previous_action_speed'], np.repeat(1., 6))
    loader.use_delta_actions = False
    absolute = execute([False]*6)
    assert np.array_equal(absolute['actions'], np.tile([.12, 1.03], (6, 1)))
    loader.use_delta_actions = True
    loader.timesteps_to_include = (0, 4)
    clipped = execute([False]*6)
    assert clipped['observations']['poses_x'].tolist() == [0, 1, 2, 3]
    assert clipped['terminals'].tolist() == [False]*3+[True]
    assert clipped['timeouts'].tolist() == [False]*3+[True]
    failures = []
    for attribute, value in [('include_progress', True), ('reward_config', 'reward_progress.json')]:
        setattr(loader, attribute, value)
        try:
            execute([False]*6)
        except KeyError as exc:
            failures.append({'option': attribute, 'missing_key': str(exc)})
        else:
            raise AssertionError(f'Expected documented missing-field failure for {attribute}')
        setattr(loader, attribute, defaults[attribute])
    return dict(methods_executed=methods, adapter='Original method AST; in-memory synthetic arrays; no gym constructor',
                options=defaults, first_crash_cases=cases, delta_absolute_ordering='steering, speed',
                artificial_horizon_and_natural_timeout_promoted_to_terminal=True,
                missing_sim_fields=failures,
                limitation='Synthetic loader behavior only. No raw record or installed simulator validated.')


def policy_checks(files, manifest, names):
    with tempfile.TemporaryDirectory() as temp:
        package = Path(temp)
        for name, spec in manifest['files'].items():
            if spec['repo'] == 'stochastic_ftg_agents' and spec['path'] not in ('tree.json', 'LICENSE'):
                dest = package/spec['path']
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(files[name], dest)
        sys.path.insert(0, str(package))
        try:
            from f110_agents.agent import Agent
            from f110_agents.agents_numpy import BaseAgent
            scans = np.full((4, 54), .8)
            scans[1, :20] = .1
            scans[2, 30:] = .2
            scans[3, 20:28] = .1
            obs = dict(poses_x=np.array([0., 1., -1., 2.]), poses_y=np.array([0., .5, 1., -1.]),
                       theta_sin=np.sin([-.6, 0., .5, 1.2]), theta_cos=np.cos([-.6, 0., .5, 1.2]),
                       previous_action_steer=np.array([-.1, 0., .1, -.2]),
                       previous_action_speed=np.array([.6, 1., 2., 4.8]), lidar_occupancy=scans)
            results = []
            np.random.seed(1729)  # Synthetic diagnostic sampling only, no performance experiment.
            for name in names:
                agent = Agent().load(name=name, no_print=True)
                _, batch, _ = agent(copy.deepcopy(obs), deterministic=True)
                singles = np.concatenate([agent({k: v[i:i+1].copy() for k, v in obs.items()}, deterministic=True)[1] for i in range(4)])
                _, _, logs = agent(copy.deepcopy(obs), actions=batch.copy())
                one_logs = np.concatenate([agent({k: v[i:i+1].copy() for k, v in obs.items()}, actions=batch[i:i+1].copy())[2] for i in range(4)])
                agent.reset()
                reset = agent(copy.deepcopy(obs), deterministic=True)[1]
                permutation = np.array([3, 1, 0, 2])
                permuted = agent({k: v[permutation].copy() for k, v in obs.items()}, deterministic=True)[1]
                errors = dict(batch_action=float(np.max(abs(batch-singles))),
                              batch_log_density=float(np.max(abs(logs-one_logs))),
                              reset=float(np.max(abs(batch-reset))),
                              permutation=float(np.max(abs(batch[permutation]-permuted))))
                assert batch.shape == logs.shape == (4, 2)
                results.append(dict(policy=name, cases=4, max_abs_error=errors,
                                    finite=bool(np.isfinite(batch).all() and np.isfinite(logs).all()),
                                    agrees=all(v <= TOLERANCE for v in errors.values()),
                                    deterministic_deltas=batch.tolist(), log_densities_at_those_deltas=logs.tolist()))
            # Independent scalar density formula, separate from scipy's logpdf.
            base = BaseAgent(std_vel=.1, std_steer=.03, max_speed=5.)
            base.max_delta, base.deterministic = .3, False
            action = np.array([[.01, .04]])  # steering, speed
            _, logs = base.compute_action_log_probs(np.array([1.]), np.array([0.]),
                                                     np.array([.02]), np.array([-.03]), action=action)
            def logpdf(x, mean, sigma, lo, hi):
                cdf = lambda t: .5*(1+math.erf(t/math.sqrt(2)))
                return -.5*((x-mean)/sigma)**2-math.log(sigma*math.sqrt(2*math.pi))-math.log(cdf((hi-mean)/sigma)-cdf((lo-mean)/sigma))
            expected = [logpdf(.04, .02, .1, -.3, .3), logpdf(.01, -.03, .03, -.3, .3)]
            error = float(np.max(abs(logs[0]-expected)))
            assert error <= TOLERANCE
            return dict(cases_per_policy=4, tolerance=TOLERANCE, observations={k:v.tolist() for k,v in obs.items()},
                        policy_results=results, density_order=['speed', 'steering'],
                        action_order=['steering', 'speed'], density_formula_max_abs_error=error,
                        joint_log_density_rule='sum of dimension log densities for the tested nondegenerate independent truncated normals',
                        limitation='Directed synthetic states only; deterministic means and supplied-action densities. No rollout, archived-action coverage, degenerate-support or simulator qualification.')
        finally:
            sys.path.remove(str(package))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--fetch', action='store_true', help='Fetch only missing pinned public source files')
    args = parser.parse_args()
    manifest = json.loads(INPUTS.read_text())
    files = checked_sources(args.cache, manifest, args.fetch)
    tree = json.loads(files['benchmark-tree.json'].read_text())
    gitlinks = {e['path']: e['sha'] for e in tree['tree'] if e['type'] == 'commit'}
    regs = registrations(files['f1tenth_orl_dataset__f110_orl_dataset____init__.py'])
    names = regs['f110-real-stoch-v2']['eval_model_names']
    assert names == regs['f110-sim-stoch-v2']['eval_model_names']
    licenses = {}
    for repo in manifest['repository_pins']:
        license_text = files[repo+'__LICENSE'].read_text()
        if license_text.startswith('MIT License'):
            licenses[repo] = 'MIT'
        elif license_text.startswith('This is free and unencumbered software released into the public domain.'):
            licenses[repo] = 'Unlicense'
        else:
            raise ValueError(f'Unreviewed license text: {repo}')
    result = dict(scope=manifest['scope'], inputs_sha256=digest(INPUTS), script_sha256=digest(__file__),
                  environment={'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
                  gitlinks=gitlinks, simulator_has_benchmark_gitlink='f110_sim_env' in gitlinks,
                  licenses=licenses, registrations=regs,
                  loader=loader_checks(files['f1tenth_orl_dataset__f110_orl_dataset__dataset_env.py']),
                  policies=policy_checks(files, manifest, names),
                  gates={'corrected_zip_rights': 'unresolved', 'corrected_zip_hashes_and_census': 'not acquired or rerun; old archive hashes retained separately',
                         'simulator_benchmark_revision': 'unqualified: public repository exists but no benchmark gitlink',
                         'original_reply': manifest['reply_status'],
                         'm2_ranking': 'not executed; rights, environment and first-crash filtering unresolved',
                         'm3_m5_outcomes': 'unopened'},
                  reward_contract={'source': 'f1tenth_orl_dataset README and dataset_env at manifest pin',
                                   'sim_missing_per_documentation': ['progress', 'new_rewards'],
                                   'archive_payload_verified': False,
                                   'comparison': 'No shared outcome calculation qualified; collection rewards are not presumed comparable.'})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'policies':len(names), 'loader_cases':result['loader']['first_crash_cases'], 'gates':result['gates']}, indent=2))


if __name__ == '__main__':
    main()
