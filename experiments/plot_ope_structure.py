#!/usr/bin/env python3
"""Render the structural figure, its caption and tables from the committed result, without archives."""
import argparse
import csv
import json
from pathlib import Path

from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from matplotlib.patches import Patch

import figure_style as fs

# Pair real/sim versions; the final archive has no corresponding sim-v2 file.
ARCHIVES = {
    'dataset_real_v0.zip': 'Real v0',
    'dataset_sim_v0.zip': 'Sim v0',
    'f110-real-v1.zip': 'Real v1',
    'f110-sim-v1.zip': 'Sim v1',
    'f110-real-stoch-v2.zip': 'Real stochastic v2',
}


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / 'reports' / 'figures' / 'ope_structure.png'
FROZEN = REPO_ROOT / 'runs'


def counts(result):
    """Per-archive counts in figure order: segments, policy names, flags at and before a segment end."""
    archives = result['archives']
    rows = []
    for name, label in ARCHIVES.items():
        a = archives[name]
        early = a['flags_before_segment_end']
        rows.append(dict(label=label, segments=a['segments'], names=a['policy_names'],
                         at_end=a['done_or_truncated_rows'] - early, early=early))
    return rows


def caption(result):
    rows = counts(result)
    most = max(rows, key=lambda r: r['segments'])
    flagged = [r for r in rows if r['early']]
    names = [r['names'] for r in rows]
    listing = '; '.join(f"{r['label']} {r['segments']:,} segments, {r['names']:,} names, {r['at_end']:,} + "
                        f"{r['early']:,} flagged rows" for r in rows)
    early = (f"{' and '.join(r['label'] for r in flagged)} alone raises flags before a segment ends "
             f"({sum(r['early'] for r in flagged):,} rows)" if len(flagged) == 1 else
             f"{len(flagged)} archives raise flags before a segment ends")
    return ('Historical census at the original source pins. F110 archives, structural census of unfiltered '
            f'records; episode meaning and policy execution are unresolved. {most["label"]} has the most recording segments ({most["segments"]:,}); archives hold '
            f'{min(names):,} to {max(names):,} policy-name strings each; {early}. Panel (a): recording segments '
            'per archive (circles). Panel (b): exact policy-name strings per archive (squares). Panel (c): rows '
            'with done OR truncated, each counted once and split into flags at a segment end (filled) and before '
            'a segment end (hollow). All count axes are linear and start at zero. Per archive, with flagged rows as at end + before end: '
            f'{listing}. Resets do not establish independent episodes, and name matches do not establish executable '
            'policies. Counts only; no return or ranking analysis. Archive filenames and sources: runs/ope_qualification/structure.md. '
            'Source: runs/ope_qualification/result.json.')


def render_figure(result):
    rows = counts(result)
    labels = [r['label'] for r in rows]
    y = range(len(rows))
    fig = fs.figure(height_in=5.2)
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1])
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1]), fig.add_subplot(grid[1, :])]
    for ax, key, shape, xlabel in zip(axes[:2], ('segments', 'names'), ('o', 's'),
                                     ('Recording segments [count]', 'Policy-name strings [count]')):
        values = [r[key] for r in rows]
        for yi, value in zip(y, values):
            ax.plot([0, value], [yi, yi], color=fs.INK, lw=0.5, zorder=1)
        ax.plot(values, list(y), marker=shape, mfc=fs.FILL[True], zorder=3, **fs.MARKER)
        ax.set_xlim(0, max(values) * 1.1)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.set_xlabel(xlabel)
    ax = axes[2]
    at_end = [r['at_end'] for r in rows]
    early = [r['early'] for r in rows]
    ax.barh(list(y), at_end, height=.48, color=fs.FILL[True], edgecolor=fs.INK, linewidth=0.8)
    ax.barh(list(y), early, left=at_end, height=.48, color=fs.FILL[False], edgecolor=fs.INK, linewidth=0.8)
    ax.set_xlim(0, max(a + b for a, b in zip(at_end, early)) * 1.05)
    ax.set_xlabel('Rows with done OR truncated [count]')
    for ax in axes:
        ax.set_yticks(list(y), labels)
        ax.set_ylim(len(rows) - .5, -.5)
        ax.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    axes[1].tick_params(labelleft=False)
    fs.letters(axes)
    fs.legend(fig, [Patch(facecolor=fs.FILL[True], edgecolor=fs.INK, label='Flag at segment end'),
                    Patch(facecolor=fs.FILL[False], edgecolor=fs.INK, label='Flag before segment end')])
    return fig


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_tables(result, directory):
    rows = []
    for name, label in ARCHIVES.items():
        a = result['archives'][name]
        rows.append(dict(
            label=label, archive=name, rows=a['rows'], segments=a['segments'],
            policy_names=a['policy_names'], min_rows_per_segment=a['length_range_rows'][0],
            max_rows_per_segment=a['length_range_rows'][1], done_rows=a['done_rows'],
            truncated_rows=a['truncated_rows'], both_flags_rows=a['both_flags_rows'],
            done_or_truncated_rows=a['done_or_truncated_rows'],
            flags_at_segment_end=a['done_or_truncated_rows']-a['flags_before_segment_end'],
            flags_before_segment_end=a['flags_before_segment_end'],
            unflagged_segment_ends=a['unflagged_segment_ends'],
            bundled_config_matches=sum(v is not None for v in a['bundled_config_mapping'].values()),
            benchmark_config_matches=sum(v is not None for v in a['benchmark_config_mapping'].values()),
        ))
    aliases = [dict(registration=name, archive=a['archive'],
                    listed_eval_names=len(a['eval_model_names']),
                    missing_eval_names=len(a['eval_names_missing_from_loaded_archive']),
                    listed_bad_indices=len(a['bad_trajectory_indices']),
                    bad_indices_outside_rows=len(a['bad_indices_outside_loaded_rows']))
               for name, a in result['registrations'].items()]
    write_csv(directory/'structure.csv', rows)
    write_csv(directory/'loader_aliases.csv', aliases)
    lines = [
        '# Unfiltered archive structure', '',
        'Generated by `experiments/plot_ope_structure.py` from [result.json](result.json).',
        'Download [archive counts](structure.csv) and [loader aliases](loader_aliases.csv).',
        'All numbers below are counts or observed row-count ranges, with no filtering.', '',
        '## Archive identity and recordings', '',
        '| Figure label | Explicit archive filename | Rows | Segments | Policy-name strings | Rows/segment, min to max |',
        '| --- | --- | ---: | ---: | ---: | ---: |',
    ]
    for r in rows:
        lines.append(f"| {r['label']} | `{r['archive']}` | {r['rows']:,} | {r['segments']:,} | {r['policy_names']:,} | {r['min_rows_per_segment']:,} to {r['max_rows_per_segment']:,} |")
    lines += ['', 'A segment begins when timestep stops increasing. A reset flag does not',
              'establish an independent episode. Pairing real/sim rows here expresses archive',
              'versions only; no experimental pairing has been established.', '',
              '## Apparent terminal flags', '',
              '| Archive label | done rows | truncated rows | Either flag rows | Before segment end rows | Unflagged ends |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['label']} | {r['done_rows']:,} | {r['truncated_rows']:,} | {r['done_or_truncated_rows']:,} | {r['flags_before_segment_end']:,} | {r['unflagged_segment_ends']:,} |")
    lines += ['', '`Either` is the union, so a row with both flags is counted once. Figure C',
              'splits that union into rows at and before segment ends. Those early flags',
              'cannot be counted as independent recordings; their physical meaning is unresolved.', '',
              '## Loader registrations', '',
              '| Registration | Selected archive | Missing / listed evaluation names | Out-of-range / listed bad indices |',
              '| --- | --- | ---: | ---: |']
    for r in aliases:
        missing = f"{r['missing_eval_names']} / {r['listed_eval_names']}" if r['listed_eval_names'] else 'None listed'
        bad = f"{r['bad_indices_outside_rows']} / {r['listed_bad_indices']}" if r['listed_bad_indices'] else 'None listed'
        lines.append(f"| `{r['registration']}` | `{r['archive']}` | {missing} | {bad} |")
    lines += ['', '“None listed” means the registration supplied no entries for that field.',
              'The explicit real-stochastic archive remains separate from the similarly named',
              'registrations that select simulation-v1. These are source-code mappings;',
              'they do not establish which file a published experiment used.', '',
              '## Exact configuration-filename correspondence', '',
              '| Archive label | Archived names | Bundled config matches | Benchmark config matches |',
              '| --- | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['label']} | {r['policy_names']:,} | {r['bundled_config_matches']:,} | {r['benchmark_config_matches']:,} |")
    lines += ['', 'Zero means no exact filename match in that pinned tree. A match does not',
              'qualify policy execution, observation reconstruction or action probabilities.',
              'Rights, episode semantics and independence remain unresolved. See the',
              '[qualification report](../../reports/ope_qualification.md) for the separate gates.', '']
    (directory/'structure.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT, help='PNG path; SVG and caption saved beside it')
    parser.add_argument('--tables', type=Path, help='directory for structure.md and the CSV tables (not written by default)')
    args = parser.parse_args()
    # runs/ holds the frozen 2026 census and its original figure; the live figure lives in reports/figures.
    if args.output.resolve().is_relative_to(FROZEN):
        parser.error(f'{args.output} is under runs/, which is frozen; write the figure elsewhere')
    result = json.loads(args.result.read_text())
    fs.apply(hashsalt='racing-structure')
    fs.save(render_figure(result), args.output, caption(result), ('png', 'svg'))
    if args.tables:
        render_tables(result, args.tables)


if __name__ == '__main__':
    main()
