function make_kinematic_replay(root, figDir, S)
%MAKE_KINEMATIC_REPLAY Kinematic bicycle replay against the Gym first lap.
%   Inputs: runs/model_vs_gym_comparison/replay_trace.csv. The Gym RK4 path is
%   blue and solid, the kinematic replay orange and dashed. The open ring marks
%   the start, the blue square the Gym end and the orange triangle the replay end.

T = read_csv(fullfile(root, 'runs', 'model_vs_gym_comparison', 'replay_trace.csv'));
[fig, tl] = new_figure(15.2, 12.7, 1, 1);
ax = nexttile(tl); hold(ax, 'on');
plot(ax, T.gym_x_m, T.gym_y_m, '-', 'Color', S.c.blue, 'LineWidth', 1.1);
plot(ax, T.model_x_m, T.model_y_m, '--', 'Color', S.c.orange, 'LineWidth', 1.0);
plot(ax, T.gym_x_m(1), T.gym_y_m(1), 'o', 'MarkerSize', 10, 'Color', S.c.ink, 'MarkerFaceColor', 'none', 'LineWidth', 0.9);
plot(ax, T.gym_x_m(end), T.gym_y_m(end), 's', 'MarkerSize', 5, 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue);
plot(ax, T.model_x_m(end), T.model_y_m(end), '^', 'MarkerSize', 5, 'Color', S.c.orange, 'MarkerFaceColor', S.c.orange);
axis(ax, 'equal');
xs = [T.gym_x_m; T.model_x_m]; ys = [T.gym_y_m; T.model_y_m];
pad = 0.05 * max(span_of(xs), span_of(ys));
set(ax, 'XLim', [min(xs) - pad, max(xs) + pad], 'YLim', [min(ys) - pad, max(ys) + pad]);
xlabel(ax, '$x$ (m)'); ylabel(ax, '$y$ (m)');
dlabel(ax, -25, 27.5, 'Gym RK4 (reference)', S.c.blue, S, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
dlabel(ax, 28, 6, 'kinematic replay', S.c.orange, S, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');
text(ax, T.gym_x_m(1) - 2.2, T.gym_y_m(1) + 2.6, 'start', 'Color', S.c.ink, 'HorizontalAlignment', 'right');
text(ax, T.gym_x_m(end) + 1.5, T.gym_y_m(end) - 2.8, 'Gym end', 'Color', S.c.blue);
text(ax, T.model_x_m(end) + 1.5, T.model_y_m(end), 'replay end', 'Color', S.c.orange);
export_pair(fig, fullfile(figDir, 'model_vs_gym_trajectory_error'));

rows = {'error_position_m', 'Position error (m)'; 'error_yaw_rad', 'Wrapped yaw error (rad)'; ...
        'error_speed_mps', 'Speed error (m/s)'};
state_errors(T, rows, 10.7, fullfile(figDir, 'model_vs_gym_state_errors'), S);
end
