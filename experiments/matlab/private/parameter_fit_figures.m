function parameter_fit_figures(runDir, fitStem, residualStem, S)
%PARAMETER_FIT_FIGURES One-step fit overlay and held-out rollout residuals.
%   Inputs: <runDir>/fit_trace.csv and heldout_replay_trace.csv. The Gym state is
%   blue and solid; the fitted model's one-step prediction is orange hollow
%   squares on every N-th interval (N = floor(n/60)); the shaded span holds the
%   held-out intervals.

F = read_csv(fullfile(runDir, 'fit_trace.csv'));
V = read_csv(fullfile(runDir, 'heldout_replay_trace.csv'));
held = F(F.partition == "heldout", :);
t0 = held.time_s(1); t1 = F.time_s(end);
every = max(floor(height(F) / 60), 1);
idx = 1:every:height(F);

[fig, tl] = new_figure(S.width, 9.7, 2, 1);
rows = {'yaw_rate_radps', 'Yaw rate (rad/s)'; 'slip_angle_rad', 'Slip angle (rad)'};
for i = 1:2
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    m = F.(['measured_' rows{i, 1}]); p = F.(['predicted_' rows{i, 1}]);
    plot(ax(i), F.time_s, m, '-', 'Color', S.c.blue, 'LineWidth', 0.8);
    plot(ax(i), F.time_s(idx), p(idx), 's', 'MarkerSize', 3.5, 'Color', S.c.orange, 'MarkerFaceColor', 'w', 'LineWidth', 0.8);
    ref_y(ax(i), 0, S);
    lo = min([m; p]); hi = max([m; p]); pad = 0.08 * (hi - lo);
    ylim(ax(i), [lo - pad, hi + 3.2 * pad]);
    xlim(ax(i), [F.time_s(1) - 0.3, t1 + 0.3]);
    shade_x(ax(i), t0, t1, S);
    ylabel(ax(i), rows{i, 2});
    panel_letter(ax(i), char('a' + i - 1), S);
end
ax(1).XTickLabel = {}; xlabel(ax(2), 'Time (s)');
yl = ylim(ax(1));
dlabel(ax(1), F.time_s(1), yl(2), 'Gym (measured)', S.c.blue, S, 'VerticalAlignment', 'top');
dlabel(ax(1), F.time_s(1) + 0.2 * (t1 - F.time_s(1)), yl(2), 'fitted model, one step ahead', S.c.orange, S, ...
    'VerticalAlignment', 'top');
text(ax(1), (t0 + t1) / 2, yl(2), 'held-out intervals', 'Color', S.c.grey, 'FontSize', S.size.note, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top');
export_pair(fig, fitStem);

rows = {'yaw_rate_error_radps', {'Yaw-rate error', '($10^{-9}$ rad/s)'}; ...
        'slip_angle_error_rad', {'Slip-angle error', '($10^{-9}$ rad)'}; 'yaw_error_rad', {'Yaw error', '($10^{-9}$ rad)'}};
[fig, tl] = new_figure(S.width, 11.2, 3, 1);
for i = 1:3
    bx(i) = nexttile(tl); hold(bx(i), 'on'); %#ok<AGROW>
    v = V.(rows{i, 1}) * 1e9;
    plot(bx(i), V.time_s, v, '-', 'Color', S.c.blue, 'LineWidth', 0.7);
    ref_y(bx(i), 0, S);
    span = max(v) - min(v); ylim(bx(i), [min(v) - 0.12 * span, max(v) + 0.12 * span]);
    xlim(bx(i), [V.time_s(1) - 0.1, V.time_s(end) + 0.1]);
    ylabel(bx(i), rows{i, 2});
    panel_letter(bx(i), char('a' + i - 1), S);
    if i < 3, bx(i).XTickLabel = {}; end
end
xlabel(bx(3), 'Time (s)');
export_pair(fig, residualStem);
end
