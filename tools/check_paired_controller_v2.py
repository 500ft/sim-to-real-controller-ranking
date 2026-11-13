#!/usr/bin/env python3
"""Read stored study evidence only; never import or execute the controllers.

This checks copied bytes, cohort membership and timing-row counts. It does not
independently reproduce trajectory metrics, intervals or scientific conclusions.
Stops at the first mismatch and does not modify any file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'runs' / 'paired_controller_v2'


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-archive', type=Path,
                        help='Optional retained full archive: verify its registered bytes only.')
    args = parser.parse_args()
    manifest = json.loads((DATA / 'source-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        path = ROOT / entry['path']
        require(path.is_file(), 'Missing packaged file: ' + entry['path'])
        require(path.stat().st_size == entry['bytes'], 'Byte count differs: ' + entry['path'])
        require(digest(path) == entry['sha256'], 'SHA-256 differs: ' + entry['path'])

    # Existing plant/planner/map files are referenced in-place; no extracted copy.
    for entry in manifest['existing_repository_inputs']:
        require(digest(ROOT / entry['path']) == entry['review_checkout_sha256'],
                'Repository input differs from the reviewed checkout: ' + entry['path'])

    protocol = json.loads((DATA / 'protocol.json').read_text(encoding='utf-8'))
    progress = json.loads((DATA / 'progress.json').read_text(encoding='utf-8'))
    summary = json.loads((DATA / 'summary.json').read_text(encoding='utf-8'))
    require(progress['state'] == 'completed', 'Stored campaign is incomplete')
    require(summary['complete_campaign'], 'Stored summary is incomplete')
    require(summary['protocol_sha256'] == digest(DATA / 'protocol.json'),
            'Summary protocol hash differs')
    scenarios = {row['seed']: row for row in protocol['scenario_draws']}
    require(len(scenarios) == len(protocol['scenario_draws']), 'Duplicate scenario seed')
    controllers = ('pure_pursuit', 'lqr', 'mpc')
    expected = {(cell['name'], seed, name)
                for cell in protocol['cells'] for seed in scenarios for name in controllers}
    require(len(expected) == protocol['case_count'], 'Protocol case count differs')
    require(progress['completed_cases'] == len(expected), 'Progress case count differs')
    require(summary['saved_cases'] == len(expected), 'Summary case count differs')

    seen = set()
    timing_samples = 0
    with zipfile.ZipFile(DATA / 'case-results-and-timings.zip') as archive:
        names = archive.namelist()
        members = {entry['path']: entry for entry in manifest['case_archive_members']}
        require(len(names) == len(set(names)), 'Duplicate ZIP member')
        require(set(names) == set(members), 'ZIP member set differs')
        # Hash every stored member before reading its declared metadata.
        for name in names:
            raw = archive.read(name)
            entry = members[name]
            require(len(raw) == entry['bytes'], 'ZIP member byte count differs: ' + name)
            require(hashlib.sha256(raw).hexdigest() == entry['sha256'],
                    'ZIP member SHA-256 differs: ' + name)
        for cell, seed, controller in sorted(expected):
            prefix = f'{cell}/{seed}/{controller}/'
            result = json.loads(archive.read(prefix + 'result.json'))
            require(result['scenario'] == scenarios[seed], 'Scenario record differs: ' + prefix)
            require((result['cell'], result['scenario']['seed'], result['controller']) ==
                    (cell, seed, controller), 'Case identity differs: ' + prefix)
            require(result['numerical_input_checks_passed'] is True,
                    'Stored numerical/input status is not passing: ' + prefix)
            seen.add((cell, seed, controller))
            rows = csv.reader(io.StringIO(archive.read(prefix + 'controller_times_s.csv').decode('utf-8')))
            require(next(rows) == ['full_controller_call_seconds'],
                    'Timing header differs: ' + prefix)
            count = 0
            for row in rows:
                require(len(row) == 1, 'Timing row shape differs: ' + prefix)
                value = float(row[0])
                require(math.isfinite(value) and value >= 0, 'Invalid recorded time: ' + prefix)
                count += 1
            require(count == result['control_calls'], 'Timing row count differs: ' + prefix)
            timing_samples += count
    require(seen == expected, 'Case cohort differs')
    inventory = json.loads((DATA / 'raw-trace-inventory.json').read_text(encoding='utf-8'))
    require(len(inventory['traces']) == len(expected), 'Trace inventory count differs')
    raw_verified = False
    if args.raw_archive is not None:
        record = inventory['local_full_archive']
        require(args.raw_archive.stat().st_size == record['archive_bytes'],
                'Full raw archive byte count differs')
        require(digest(args.raw_archive) == record['archive_sha256'],
                'Full raw archive SHA-256 differs')
        raw_verified = True
    print(json.dumps({
        'status': 'PASS',
        'scope': 'Stored byte/cohort/timing-row consistency only; no scientific reproduction.',
        'saved_cases': len(seen),
        'recorded_timing_samples': timing_samples,
        'full_raw_archive_hash_checked': raw_verified,
        'trajectory_metrics_recomputed': False,
        'campaign_or_model_executed': False,
        'acceptance_limits_changed': False,
    }, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print('STOP_FIRST_MISMATCH: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
