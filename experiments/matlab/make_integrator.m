function make_integrator(root, figDir, S)
%MAKE_INTEGRATOR RK4 vs Euler figures from the committed first-lap run.
%   Inputs: runs/first_lap/telemetry.csv, and from reports/figures/data/ the
%   reference path and per-run summary written by experiments/figure_data.py.
%   RK4 is blue and solid, Euler orange and dashed, the RK4 second pass blue
%   dash-dot. A filled circle ends a run at the Gym's normal stop; a hollow
%   square marks a collision.

T = read_csv(fullfile(root, 'runs', 'first_lap', 'telemetry.csv'));
P = read_csv(fullfile(root, 'reports', 'figures', 'data', 'integrator_reference_path.csv'));
M = read_csv(fullfile(root, 'reports', 'figures', 'data', 'integrator_summary.csv'));
keys = ["rk4", "euler"]; names = ["RK4", "Euler"];
col = {S.c.blue, S.c.orange}; ls = {'-', '--'};
for k = 1:2
    G = T(lower(T.integrator) == keys(k), :);
    G = sortrows(G, 'time_s');
    run(k).G = G; %#ok<AGROW>
    run(k).collided = any(double(G.collision) > 0);
    p = G.progress_m;
    wraps = find(diff(p) < -0.5 * max(p)) + 1;
    edges = [1; wraps(:); height(G) + 1];
    run(k).passes = arrayfun(@(i) G(edges(i):edges(i + 1) - 1, :), 1:numel(edges) - 1, 'UniformOutput', false);
end
assert(~run(1).collided && run(2).collided, 'figures assume RK4 completes and Euler collides');
cteTop = max([run(1).G.abs_cte_m; run(2).G.abs_cte_m]) * 1.08;
cteRight = max([run(1).G.progress_m; run(2).G.progress_m]) * 1.02;

% ---- combined: trajectories (a, b) over tracking error (c, d) ----------------
[fig, tl] = new_figure(S.width, 14.5, 5, 2);
for k = 1:2
    ax = nexttile(tl, k, [3 1]);
    trajectory(ax, P, run(k), names(k), col{k}, ls{k}, S);
    panel_letter(ax, char('a' + k - 1), S);
end
for k = 1:2
    ax = nexttile(tl, 6 + k, [2 1]);
    tracking(ax, run(k), names(k), col{k}, ls{k}, S, cteRight, cteTop);
    panel_letter(ax, char('c' + k - 1), S);
end
export_pair(fig, fullfile(figDir, 'first_integrator_comparison'));

% ---- trajectories only ---------------------------------------------------------
[fig, tl] = new_figure(S.width, 8.6, 1, 2);
for k = 1:2
    ax = nexttile(tl);
    trajectory(ax, P, run(k), names(k), col{k}, ls{k}, S);
    panel_letter(ax, char('a' + k - 1), S);
end
export_pair(fig, fullfile(figDir, 'integrator_trajectory_overlay'));

% ---- tracking error only ------------------------------------------------------
[fig, tl] = new_figure(S.width, 9.6, 2, 1);
for k = 1:2
    ax = nexttile(tl);
    tracking(ax, run(k), names(k), col{k}, ls{k}, S, cteRight, cteTop);
    if k == 1, xlabel(ax, ''); ax.XTickLabel = {}; end
    panel_letter(ax, char('a' + k - 1), S);
end
export_pair(fig, fullfile(figDir, 'integrator_tracking_error_vs_progress'));

% ---- summary metrics -------------------------------------------------------------
specs = {'final_time_s', 'Final time (s)'; 'rms_cte_m', 'RMS cross-track error (m)'; ...
         'max_cte_m', 'Peak cross-track error (m)'; 'mean_speed_mps', 'Mean speed (m/s)'};
shapes = {'o', 's'};
[fig, tl] = new_figure(S.width, 5.6, 1, 4);
for j = 1:4
    ax = nexttile(tl); hold(ax, 'on');
    v = M.(specs{j, 1});
    for k = 1:2
        row = M(M.integrator == keys(k), :);
        face = col{k}; if row.collision, face = 'w'; end
        plot(ax, k - 1, row.(specs{j, 1}), shapes{k}, 'MarkerSize', 6, 'LineWidth', 1.1, ...
            'MarkerEdgeColor', col{k}, 'MarkerFaceColor', face);
    end
    set(ax, 'XLim', [-0.6 1.6], 'YLim', [0 max(v) * 1.25], 'XTick', [0 1], 'XTickLabel', cellstr(names));
    ylabel(ax, specs{j, 2});
    panel_letter(ax, char('a' + j - 1), S);
end
export_pair(fig, fullfile(figDir, 'integrator_summary_metrics'));
end

function trajectory(ax, P, r, name, c, ls, S)
hold(ax, 'on');
plot(ax, P.x_m, P.y_m, ':', 'Color', S.c.grey, 'LineWidth', 0.9);
plot(ax, r.G.x_m, r.G.y_m, ls, 'Color', c, 'LineWidth', 1.1);
endmarker(ax, r.G.x_m(end), r.G.y_m(end), r.collided, c);
xs = [P.x_m; r.G.x_m]; ys = [P.y_m; r.G.y_m];
pad = 0.05 * max(span_of(xs), span_of(ys));
axis(ax, 'equal');
set(ax, 'XLim', [min(xs) - pad, max(xs) + pad], 'YLim', [min(ys) - pad, max(ys) + pad]);
xlabel(ax, '$x$ (m)'); ylabel(ax, '$y$ (m)');
dlabel(ax, -36, 3, name, c, S, 'HorizontalAlignment', 'center');
dlabel(ax, -36, -1.5, 'reference path', S.c.grey, S, 'HorizontalAlignment', 'center', 'FontSize', S.size.note);
if r.collided
    dlabel(ax, r.G.x_m(end) + 2, r.G.y_m(end) - 3, 'collision', c, S, 'FontSize', S.size.note);
else
    dlabel(ax, r.G.x_m(end) - 2, r.G.y_m(end) - 3.5, 'run end', c, S, 'FontSize', S.size.note, ...
        'HorizontalAlignment', 'right');
end
end

function tracking(ax, r, name, c, ls, S, right, top)
hold(ax, 'on');
for i = 1:numel(r.passes)
    part = r.passes{i};
    if i == 1
        plot(ax, part.progress_m, part.abs_cte_m, ls, 'Color', c, 'LineWidth', 0.9);
    else
        plot(ax, part.progress_m, part.abs_cte_m, '-.', 'Color', c, 'LineWidth', 0.6);
    end
end
if r.collided
    endmarker(ax, r.G.progress_m(end), r.G.abs_cte_m(end), true, c);
end
set(ax, 'XLim', [0 right], 'YLim', [0 top]);
xlabel(ax, 'Progress along path (m)'); ylabel(ax, '$|$Cross-track error$|$ (m)');
if numel(r.passes) > 1
    dlabel(ax, right * 0.99, top * 0.93, sprintf('%s, first pass (solid); second pass (dash-dot)', name), c, S, ...
        'HorizontalAlignment', 'right', 'FontSize', S.size.note);
else
    dlabel(ax, right * 0.99, top * 0.93, name, c, S, 'HorizontalAlignment', 'right');
end
end

function endmarker(ax, x, y, collided, c)
if collided
    plot(ax, x, y, 's', 'MarkerSize', 6, 'LineWidth', 1.1, 'MarkerEdgeColor', c, 'MarkerFaceColor', 'w');
else
    plot(ax, x, y, 'o', 'MarkerSize', 5, 'MarkerEdgeColor', c, 'MarkerFaceColor', c);
end
end
