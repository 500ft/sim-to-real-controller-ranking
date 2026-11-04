function make_dynamic_replay(root, figDir, S)
%MAKE_DYNAMIC_REPLAY Known-parameter dynamic replay against the Gym.
%   Inputs: runs/dynamic_model_replay/replay_trace.csv. The Gym reference is
%   blue and solid; the dynamic replay is orange hollow triangles (one every
%   0.4 s) and the kinematic yaw law orange dashed. Dotted grey lines mark zero
%   and t = 2.0 s.

T = read_csv(fullfile(root, 'runs', 'dynamic_model_replay', 'replay_trace.csv'));
t = T.time_s; every = 40;
lo = min([T.gym_yaw_rate_radps; T.dynamic_yaw_rate_radps; T.kinematic_yaw_rate_radps]);
hi = max([T.gym_yaw_rate_radps; T.dynamic_yaw_rate_radps; T.kinematic_yaw_rate_radps]);
pad = 0.06 * (hi - lo);

[fig, tl] = new_figure(S.width, 13.2, 21, 1);
ax(1) = nexttile(tl, 1, [8 1]); hold(ax(1), 'on');
plot(ax(1), t, T.gym_yaw_rate_radps, '-', 'Color', S.c.blue, 'LineWidth', 0.8);
idx = 1:every:numel(t);
plot(ax(1), t(idx), T.dynamic_yaw_rate_radps(idx), '^', 'MarkerSize', 3.5, 'Color', S.c.orange, ...
    'MarkerFaceColor', 'w', 'LineWidth', 0.8);
ax(2) = nexttile(tl, 9, [8 1]); hold(ax(2), 'on');
plot(ax(2), t, T.gym_yaw_rate_radps, '-', 'Color', S.c.blue, 'LineWidth', 0.8);
plot(ax(2), t, T.kinematic_yaw_rate_radps, '--', 'Color', S.c.orange, 'LineWidth', 0.6);
ax(3) = nexttile(tl, 17, [5 1]); hold(ax(3), 'on');
plot(ax(3), t, T.gym_steer_rad, '-', 'Color', S.c.blue, 'LineWidth', 0.8);
for i = 1:2
    ylim(ax(i), [lo - pad, hi + pad]); ylabel(ax(i), 'Yaw rate (rad/s)');
end
ylabel(ax(3), 'Steering (rad)'); xlabel(ax(3), 'Time (s)');
for i = 1:3
    xlim(ax(i), [t(1) - 0.5, t(end) + 0.5]);
    ref_y(ax(i), 0, S); ref_x(ax(i), 2.0, S);
    panel_letter(ax(i), char('a' + i - 1), S);
    if i < 3, ax(i).XTickLabel = {}; end
end
text(ax(1), 2.25, hi + pad * 0.35, '$t = 2.0$ s', 'Color', S.c.grey, 'FontSize', S.size.note, ...
    'VerticalAlignment', 'top');
dlabel(ax(1), t(end), hi + pad * 0.35, 'Gym (reference)', S.c.blue, S, 'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'top');
dlabel(ax(1), t(end), lo - pad * 0.3, 'dynamic replay', S.c.orange, S, 'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'bottom');
dlabel(ax(2), t(end), lo - pad * 0.3, 'kinematic yaw law', S.c.orange, S, 'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'bottom');
dlabel(ax(2), t(end), hi + pad * 0.35, 'Gym (reference)', S.c.blue, S, 'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'top');
export_pair(fig, fullfile(figDir, 'dynamic_replay_yaw_rate_overlay'));

rows = {'error_position_m', 'Position error (m)'; 'error_yaw_rad', 'Yaw error (rad)'; ...
        'error_yaw_rate_radps', 'Yaw-rate error (rad/s)'; 'error_speed_mps', 'Speed error (m/s)'};
state_errors(T, rows, 12.7, fullfile(figDir, 'dynamic_replay_state_errors'), S);
end
