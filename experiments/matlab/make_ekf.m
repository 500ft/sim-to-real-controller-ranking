function make_ekf(root, figDir, S)
%MAKE_EKF EKF estimator study figures.
%   Inputs: runs/ekf_study/trace.csv and metadata.json, and the labelled RMSE
%   table reports/figures/data/ekf_rmse_summary.csv. The EKF is blue and solid,
%   dead reckoning orange and dashed; shaded spans are measurement dropouts.

run = fullfile(root, 'runs', 'ekf_study');
T = read_csv(fullfile(run, 'trace.csv'));
meta = jsondecode(fileread(fullfile(run, 'metadata.json')));
dead = T(T.scenario == "low_noise" & T.estimator == "dead_reckoning", :);

% ---- position error over the lap --------------------------------------------------
scen = ["low_noise", "dropout_1s"];
[fig, tl] = new_figure(S.width, 9.7, 2, 1);
for i = 1:2
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    E = T(T.scenario == scen(i) & T.estimator == "ekf", :);
    plot(ax(i), dead.time_s, dead.position_error_m, '--', 'Color', S.c.orange, 'LineWidth', 0.9);
    plot(ax(i), E.time_s, E.position_error_m, '-', 'Color', S.c.blue, 'LineWidth', 0.5);
    set(ax(i), 'YScale', 'log');
    ylabel(ax(i), 'Position error (m)');
    xlim(ax(i), [0, max(T.time_s) + 0.3]);
    panel_letter(ax(i), char('a' + i - 1), S);
end
yl = [min([ylim(ax(1)) ylim(ax(2))]) max([ylim(ax(1)) ylim(ax(2))]) * 8];
set(ax, 'YLim', yl);
for i = 1:2
    w = windows(meta, scen(i));
    for k = 1:size(w, 1), shade_x(ax(i), w(k, 1), w(k, 2), S); end
end
ax(1).XTickLabel = {}; xlabel(ax(2), 'Time (s)');
dlabel(ax(1), max(T.time_s), yl(2), 'dead reckoning', S.c.orange, S, 'HorizontalAlignment', 'right', 'VerticalAlignment', 'top');
dlabel(ax(1), max(T.time_s), yl(1) * 1.5, 'EKF', S.c.blue, S, 'HorizontalAlignment', 'right', 'VerticalAlignment', 'bottom');
w = windows(meta, "dropout_1s");
text(ax(2), w(1, 2) + 0.4, yl(1) * 3, 'measurement dropout', 'Color', S.c.grey, 'FontSize', S.size.note);
export_pair(fig, fullfile(figDir, 'ekf_position_error_over_time'));

% ---- whole-lap RMSE ----------------------------------------------------------------
M = read_csv(fullfile(root, 'reports', 'figures', 'data', 'ekf_rmse_summary.csv'));
n = height(M); y = (n:-1:1)';
[fig, tl] = new_figure(S.width, 6.6, 1, 1);
bx = nexttile(tl); hold(bx, 'on');
stems_h(bx, M.ekf_position_rmse_m, M.dead_reckoning_position_rmse_m, y, S);
plot(bx, M.dead_reckoning_position_rmse_m, y, 's', 'MarkerSize', 5, 'Color', S.c.orange, 'MarkerFaceColor', S.c.orange);
plot(bx, M.ekf_position_rmse_m, y, 'o', 'MarkerSize', 5, 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue);
set(bx, 'XScale', 'log', 'YTick', flipud(y), 'YTickLabel', cellstr(flipud(M.label)), 'YLim', [0.4 n + 0.9]);
xr = [min(M.ekf_position_rmse_m) / 2, max(M.dead_reckoning_position_rmse_m) * 2];
xlim(bx, xr);
hide_y_spine(bx, S);
xlabel(bx, 'Position RMSE (m)');
dlabel(bx, M.ekf_position_rmse_m(1), n + 0.45, 'EKF', S.c.blue, S, 'HorizontalAlignment', 'center');
dlabel(bx, M.dead_reckoning_position_rmse_m(1), n + 0.45, 'dead reckoning', S.c.orange, S, 'HorizontalAlignment', 'right');
export_pair(fig, fullfile(figDir, 'ekf_rmse_summary'));

% ---- 3 s dropout zoom ----------------------------------------------------------------
w = windows(meta, "dropout_3s");
lo = w(1, 1) - 1.5; hi = w(1, 2) + 1.0;
Z = T(T.scenario == "dropout_3s" & T.time_s >= lo & T.time_s <= hi, :);
[fig, tl] = new_figure(S.width, 7.1, 1, 1);
cx = nexttile(tl); hold(cx, 'on');
D = Z(Z.estimator == "dead_reckoning", :); E = Z(Z.estimator == "ekf", :);
plot(cx, D.time_s, D.position_error_m, '--', 'Color', S.c.orange, 'LineWidth', 1.0);
plot(cx, E.time_s, E.position_error_m, '-', 'Color', S.c.blue, 'LineWidth', 0.7);
set(cx, 'YScale', 'log'); xlim(cx, [lo hi]);
yl = ylim(cx); ylim(cx, [yl(1) yl(2) * 3]);
shade_x(cx, w(1, 1), w(1, 2), S);
xlabel(cx, 'Time (s)'); ylabel(cx, 'Position error (m)');
yl = ylim(cx);
dlabel(cx, lo + 0.1, D.position_error_m(1) * 1.6, 'dead reckoning', S.c.orange, S, 'VerticalAlignment', 'bottom');
dlabel(cx, lo + 0.1, yl(1) * 1.4, 'EKF', S.c.blue, S, 'VerticalAlignment', 'bottom');
text(cx, mean(w(1, :)), yl(1) * 1.4, 'measurement dropout', 'Color', S.c.grey, 'FontSize', S.size.note, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
export_pair(fig, fullfile(figDir, 'ekf_dropout_zoom'));
end

function w = windows(meta, scenario)
d = meta.scenarios.(char(scenario)).dropout_windows;
w = zeros(0, 2);
if isempty(d), return; end
if iscell(d), d = [d{:}]; end
for k = 1:numel(d)
    w(end + 1, :) = [d(k).start_s, d(k).start_s + d(k).duration_s]; %#ok<AGROW>
end
end
