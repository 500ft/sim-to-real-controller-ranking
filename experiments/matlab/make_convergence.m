function make_convergence(root, figDir, S)
%MAKE_CONVERGENCE RK4 timestep convergence figures.
%   Inputs: runs/integrator_convergence/convergence_results.csv and the two
%   refinement tolerances (reports/figures/data/integrator_convergence_tolerances.json).
%   RMS differences are blue circles on solid lines, maximum differences orange
%   squares on dashed lines; a collided run is drawn hollow.

R = read_csv(fullfile(root, 'runs', 'integrator_convergence', 'convergence_results.csv'));
R = sortrows(R, 'dt_s');
tol = jsondecode(fileread(fullfile(root, 'reports', 'figures', 'data', 'integrator_convergence_tolerances.json')));
bad = to_bool(R.collision) | ~to_bool(R.completed_lap);
dt = R.dt_s; refdt = min(dt);
ticks = dt';
labels = arrayfun(@(v) sprintf('%g', v * 1000), dt, 'UniformOutput', false);

% ---- position error and change ----------------------------------------------------
[fig, tl] = new_figure(S.width, 7.6, 1, 2);
stems = {'position_error_vs_ref_progress_m', 'position_change_vs_next_finer_dt_progress_m'};
kinds = {'rms', S.c.blue, 'o', '-'; 'max', S.c.orange, 's', '--'};
for p = 1:2
    ax(p) = nexttile(tl); hold(ax(p), 'on'); %#ok<AGROW>
    rms = R.(['rms_' stems{p}]);
    use = dt > refdt & ~isnan(rms);
    for k = 1:2
        v = R.([kinds{k, 1} '_' stems{p}]);
        ok = use & ~bad; no = use & bad;
        plot(ax(p), dt(ok), v(ok), kinds{k, 4}, 'Color', kinds{k, 2}, 'Marker', kinds{k, 3}, ...
            'MarkerSize', 5, 'MarkerFaceColor', kinds{k, 2}, 'LineWidth', 1.0);
        plot(ax(p), dt(no), v(no), kinds{k, 3}, 'Color', kinds{k, 2}, 'MarkerSize', 5, ...
            'MarkerFaceColor', 'w', 'LineWidth', 1.0);
    end
    set(ax(p), 'XScale', 'log', 'YScale', 'log', 'XTick', ticks, 'XTickLabel', labels, 'XMinorTick', 'off');
    xlim(ax(p), [min(dt) * 0.8, max(dt) * 1.25]);
    xlabel(ax(p), 'RK4 timestep (ms)');
end
ylabel(ax(1), 'Position difference (m)');
yl = [min([ylim(ax(1)) ylim(ax(2))]) max([ylim(ax(1)) ylim(ax(2))])];
yl = [yl(1) / 1.6, yl(2) * 1.6];
set(ax, 'YLim', yl);
ax(2).YTickLabel = {};
ref_y(ax(2), tol.rms_refinement_tol_m, S, ':');
ref_y(ax(2), tol.max_refinement_tol_m, S, '-.');
text(ax(2), min(dt) * 0.85, tol.rms_refinement_tol_m * 1.2, sprintf('RMS tolerance %g m', tol.rms_refinement_tol_m), ...
    'Color', S.c.grey, 'HorizontalAlignment', 'left', 'FontSize', S.size.note);
text(ax(2), min(dt) * 0.85, tol.max_refinement_tol_m * 1.2, sprintf('maximum tolerance %g m', tol.max_refinement_tol_m), ...
    'Color', S.c.grey, 'HorizontalAlignment', 'left', 'FontSize', S.size.note);
first = find(dt > refdt, 1);
dlabel(ax(1), dt(first), R.(['max_' stems{1}])(first) * 1.45, 'maximum', S.c.orange, S);
dlabel(ax(1), dt(first), R.(['rms_' stems{1}])(first) * 0.6, 'RMS', S.c.blue, S);
panel_letter(ax(1), 'a', S); panel_letter(ax(2), 'b', S);
export_pair(fig, fullfile(figDir, 'integrator_convergence_position_error'));

% ---- lap metrics ----------------------------------------------------------------------
specs = {'final_progress_m', 'Final progress (m)'; 'rms_cte_m', 'RMS cross-track error (m)'; ...
         'max_abs_cte_m', 'Peak cross-track error (m)'};
[fig, tl] = new_figure(S.width, 6.6, 1, 3);
for j = 1:3
    ax3 = nexttile(tl); hold(ax3, 'on');
    v = R.(specs{j, 1});
    plot(ax3, dt(~bad), v(~bad), '-o', 'Color', S.c.blue, 'MarkerSize', 5, 'MarkerFaceColor', S.c.blue);
    plot(ax3, dt(bad), v(bad), 'o', 'Color', S.c.orange, 'MarkerSize', 5, 'MarkerFaceColor', 'w', 'LineWidth', 1.0);
    set(ax3, 'XScale', 'log', 'XTick', ticks, 'XTickLabel', labels, 'XMinorTick', 'off');
    xlim(ax3, [min(dt) * 0.8, max(dt) * 1.25]);
    span = span_of(v); ylim(ax3, [min(v) - 0.15 * span, max(v) + 0.15 * span]);
    xlabel(ax3, 'RK4 timestep (ms)'); ylabel(ax3, specs{j, 2});
    panel_letter(ax3, char('a' + j - 1), S);
    if j == 1
        ok = find(~bad);
        dlabel(ax3, dt(ok(1)), v(ok(1)) - 0.09 * span, 'completed lap', S.c.blue, S, 'FontSize', S.size.note);
        b = find(bad, 1);
        dlabel(ax3, dt(b) / 1.15, v(b), 'collided, partial lap', S.c.orange, S, ...
            'HorizontalAlignment', 'right', 'FontSize', S.size.note);
    end
end
export_pair(fig, fullfile(figDir, 'integrator_convergence_metrics'));
end
