function make_parameter_id(root, figDir, S)
%MAKE_PARAMETER_ID Parameter-identification robustness figures.
%   Input: reports/figures/data/parameter_id_robustness.csv (labels written by
%   experiments/figure_data.py from runs/parameter_id_robustness/results.csv).
%   Front stiffness: blue circles, solid; rear: orange squares, dashed. Filled
%   markers passed every acceptance gate; hollow markers failed at least one.

R = read_csv(fullfile(root, 'reports', 'figures', 'data', 'parameter_id_robustness.csv'));
degradation(R, "noise", 'Telemetry noise level', fullfile(figDir, 'parameter_id_noise_degradation'), S);
degradation(R, "latency", 'Added telemetry latency', fullfile(figDir, 'parameter_id_latency_degradation'), S);

% ---- Jacobian condition number ---------------------------------------------------------
n = height(R); y = (n:-1:1)';
[fig, tl] = new_figure(14.2, 8.6, 1, 1);
ax = nexttile(tl); hold(ax, 'on');
stems_h(ax, 1, R.jacobian_condition_number, y, S);
plot(ax, R.jacobian_condition_number, y, 'o', 'MarkerSize', 5, 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue);
ref_x(ax, 1.0, S);
set(ax, 'YTick', flipud(y), 'YTickLabel', cellstr(flipud(R.label)), 'YLim', [0.4 n + 0.9], ...
    'XLim', [0.95, max(R.jacobian_condition_number) * 1.08]);
hide_y_spine(ax, S);
text(ax, 1.01, n + 0.6, 'ideal value 1', 'Color', S.c.grey, 'FontSize', S.size.note);
xlabel(ax, 'Normalized Jacobian condition number');
export_pair(fig, fullfile(figDir, 'parameter_id_condition_number'));
end

function degradation(R, kind, xlab, stem, S)
sub = R(R.kind == "nominal" | R.kind == kind, :);
x = (0:height(sub) - 1)';
pass = to_bool(sub.acceptance_passed);
specs = {'C_Sf_oracle_relative_error', S.c.blue, 'o', '-', -0.06, 'front, $C_{Sf}$'; ...
         'C_Sr_oracle_relative_error', S.c.orange, 's', '--', 0.06, 'rear, $C_{Sr}$'};
[fig, tl] = new_figure(15.2, 7.6, 1, 1);
ax = nexttile(tl); hold(ax, 'on');
ends = [sub.(specs{1, 1})(end), sub.(specs{2, 1})(end)];
ly = log10(ends);
if abs(ly(1) - ly(2)) < 0.5
    mid = mean(ly); up = 1 + (ly(2) >= ly(1)); dn = 3 - up;
    ly(up) = mid + 0.25; ly(dn) = mid - 0.25;
end
for k = 1:2
    v = sub.(specs{k, 1}); xx = x + specs{k, 5};
    plot(ax, xx, v, specs{k, 4}, 'Color', specs{k, 2}, 'LineWidth', 0.9);
    plot(ax, xx(pass), v(pass), specs{k, 3}, 'MarkerSize', 5, 'Color', specs{k, 2}, 'MarkerFaceColor', specs{k, 2});
    plot(ax, xx(~pass), v(~pass), specs{k, 3}, 'MarkerSize', 5, 'Color', specs{k, 2}, 'MarkerFaceColor', 'w', 'LineWidth', 1.0);
    dlabel(ax, xx(end) + 0.2, 10 ^ ly(k), specs{k, 6}, specs{k, 2}, S, 'VerticalAlignment', 'middle');
end
set(ax, 'YScale', 'log', 'XTick', x, 'XTickLabel', cellstr(sub.label), 'XLim', [-0.35, x(end) + 0.75]);
yl = ylim(ax); ylim(ax, [yl(1), yl(2) * 4]);
ylabel(ax, 'Relative error vs Gym value');
xlabel(ax, xlab);
yl = ylim(ax);
text(ax, x(end) + 0.7, yl(1) * 3, {'filled: passed every acceptance gate', 'hollow: failed at least one'}, ...
    'Color', S.c.ink, 'FontSize', S.size.note, 'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'right');
export_pair(fig, stem);
end
