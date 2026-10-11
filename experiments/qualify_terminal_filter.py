#!/usr/bin/env python3
"""Validate a separate terminal-tail correction on registered synthetic inputs."""
import argparse
import ast
import hashlib
import itertools
import json
from pathlib import Path
import platform
import resource
import tempfile
import time

import numpy as np

from qualify_corrected_interfaces import loader_checks

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'runs/ope_terminal_filter_qualification/protocol.json'
OLD = 'change_points = np.concatenate([[0], change_points, [len(terminals) - 1]])'
NEW = 'change_points = np.concatenate([[0], change_points, [len(terminals)]])'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def oracle(flags):
    remove = []
    in_run = False
    for i, value in enumerate(flags):
        if value:
            if in_run:
                remove.append(i)
            in_run = True
        else:
            in_run = False
    return remove


def extract(text):
    cls = next(n for n in ast.parse(text).body
               if isinstance(n, ast.ClassDef) and n.name == 'F1tenthDatasetEnv')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_find_consecutive_terminals_indices')
    module = ast.Module(body=[method], type_ignores=[])
    scope = {'np': np}
    exec(compile(ast.fix_missing_locations(module), '<pinned-helper>', 'exec'), scope)
    return scope[method.name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='External log/checkpoint/result directory; must be new')
    parser.add_argument('--phase', choices=['pilot', 'full'], required=True)
    args = parser.parse_args()
    start = time.monotonic()
    protocol = json.loads(PROTOCOL.read_text())
    manifest_path = ROOT / protocol['source_manifest']
    manifest = json.loads(manifest_path.read_text())
    key = protocol['source_file_key']
    source = args.cache / key
    assert sha(source) == manifest['files'][key]['sha256']
    original = source.read_text()
    assert original.count(OLD) == 1
    candidate = original.replace(OLD, NEW)
    helpers = {'upstream': extract(original), 'candidate': extract(candidate)}
    literals = [([0], []), ([1], []), ([1, 1], [1]),
                ([0, 1, 1, 0], [2]), ([0, 0, 1, 1, 1, 1], [3, 4, 5]),
                ([1, 1, 0, 1, 1, 0], [1, 4])]
    for flags, expected in literals:
        assert oracle(flags) == expected
        for dtype in protocol['domain']['dtypes']:
            assert helpers['candidate'](None, np.array(flags, dtype=dtype)).tolist() == expected
    # Reuse the established adapter; qualify the candidate in a separate source copy.
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'candidate_loader.py'
        path.write_text(candidate)
        integration = {'upstream': loader_checks(source), 'candidate': loader_checks(path)}
    assert all(c['agrees'] for c in integration['candidate']['first_crash_cases'])
    assert sha(source) == manifest['files'][key]['sha256']
    args.output_dir.mkdir(parents=True, exist_ok=False)
    log_path = args.output_dir / 'cases.jsonl'
    max_length = protocol['domain'][args.phase + '_max_length']
    summary = []
    first_failure = {}
    stopped = False
    with log_path.open('w') as log:
        for length in range(protocol['domain']['min_length'], max_length + 1):
            counts = {dtype: {'cases': 0, 'upstream_disagreements': 0,
                             'candidate_disagreements': 0, 'exceptions': 0}
                      for dtype in protocol['domain']['dtypes']}
            for mask, flags in enumerate(itertools.product(protocol['domain']['values'], repeat=length)):
                expected = oracle(flags)
                for dtype, count in counts.items():
                    row = {'id': f'{length}:{mask}:{dtype}', 'flags': flags,
                           'dtype': dtype, 'expected_removed': expected}
                    count['cases'] += 1
                    for name, helper in helpers.items():
                        try:
                            actual = helper(None, np.array(flags, dtype=dtype)).tolist()
                        except Exception as exc:
                            actual = {'exception': type(exc).__name__, 'message': str(exc)}
                            count['exceptions'] += 1
                        row[name] = actual
                        if actual != expected:
                            count[name + '_disagreements'] += 1
                            first_failure.setdefault(name, dict(row))
                            if name == 'candidate':
                                stopped = True
                    log.write(json.dumps(row, sort_keys=True) + '\n')
                    if stopped:
                        break
                if stopped:
                    break
            summary.append({'length': length, 'by_dtype': counts})
            log.flush()
            checkpoint = {'last_completed_length': length if not stopped else length - 1,
                          'stopped_on_candidate_failure': stopped,
                          'summary': summary}
            (args.output_dir / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
            print(json.dumps(summary[-1]), flush=True)
            if stopped:
                break
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {'phase': args.phase, 'protocol_sha256': sha(PROTOCOL),
              'script_sha256': sha(__file__), 'manifest_sha256': sha(manifest_path),
              'source_sha256': sha(source),
              'candidate_source_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
              'candidate_change': {'old': OLD, 'new': NEW},
              'literal_oracle_checks_passed': True, 'summary': summary,
              'minimal_failures': first_failure, 'loader_adapter': integration,
              'case_log_sha256': sha(log_path), 'case_log_bytes': log_path.stat().st_size,
              'elapsed_seconds': time.monotonic() - start,
              'peak_rss_bytes': rss if platform.system() == 'Darwin' else rss * 1024,
              'environment': {'python': platform.python_version(), 'numpy': np.__version__},
              'completed_registered_domain': not stopped,
              'interpretation': protocol['interpretation']}
    (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if stopped:
        raise SystemExit('Candidate failure recorded; stopped before expansion')


if __name__ == '__main__':
    main()
