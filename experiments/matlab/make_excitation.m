function make_excitation(root, figDir, S)
%MAKE_EXCITATION Steering chirp excitation figures.
%   Inputs: runs/sysid_steering_excitation/telemetry.csv and metadata.json.
%   Commands are orange dash-dot, Gym states blue solid; grey dotted lines are zero.

run = fullfile(root, 'runs', 'sysid_steering_excitation');
T = read_csv(fullfile(run, 'telemetry.csv'));
meta = jsondecode(fileread(fullfile(run, 'metadata.json')));

[fig, ~] = command_and_state(T, 'command_steer_rad', 'steer_rad', 'Steering (rad)', 'Time (s)', 8.6, S);
export_pair(fig, fullfile(figDir, 'sysid_steering_input'));

[fig, tl] = new_figure(S.width, 9.1, 2, 1);
rows = {'yaw_rate_radps', 'Yaw rate (rad/s)'; 'slip_angle_rad', 'Slip angle (rad)'};
for i = 1:2
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    plot(ax(i), T.time_s, T.(rows{i, 1}), '-', 'Color', S.c.blue, 'LineWidth', 0.8);
    ref_y(ax(i), 0, S);
    xlim(ax(i), [T.time_s(1) - 0.3, T.time_s(end) + 0.3]);
    ylabel(ax(i), rows{i, 2});
    panel_letter(ax(i), char('a' + i - 1), S);
end
ax(1).XTickLabel = {}; xlabel(ax(2), 'Time (s)');
export_pair(fig, fullfile(figDir, 'sysid_yaw_response'));

target = meta.target_speed_mps; lo = 0.85 * target; hi = 1.15 * target;
[fig, ax] = command_and_state(T, 'command_speed_mps', 'speed_mps', 'Speed (m/s)', 'Time (s)', 8.6, S);
for i = 1:2
    ylim(ax(i), [0, hi * 1.25]);
    shade_y(ax(i), lo, hi, S);
end
delete(findobj(ax(1), 'Type', 'Text', '-not', 'String', '')); %#ok<*NASGU>
delete(findobj(ax(2), 'Type', 'Text', '-not', 'String', ''));
xl = xlim(ax(1));
for i = 1:2
    names = {'commanded', 'achieved'}; cs = {S.c.orange, S.c.blue};
    dlabel(ax(i), xl(2), hi * 1.25, names{i}, cs{i}, S, 'HorizontalAlignment', 'right', 'VerticalAlignment', 'top');
end
text(ax(2), xl(2), lo, sprintf('$\\pm$15\\%% band around the %g m/s target', target), 'Color', S.c.grey, ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'top', 'FontSize', S.size.note);
panel_letter(ax(1), 'a', S); panel_letter(ax(2), 'b', S);
export_pair(fig, fullfile(figDir, 'sysid_speed_hold'));
end
