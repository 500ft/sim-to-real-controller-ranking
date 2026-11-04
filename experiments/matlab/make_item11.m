function make_item11(root, figDir, S)
%MAKE_ITEM11 Simulator-backed ROS 2 capture figures (steering and enriched fit).
%   Inputs: evidence/item11/telemetry/enriched_bridge.csv and
%   evidence/item11/metrics/enriched_fit/{fit_trace,heldout_replay_trace}.csv.
ev = fullfile(root, 'evidence', 'item11');
T = read_csv(fullfile(ev, 'telemetry', 'enriched_bridge.csv'));
[fig, ~] = command_and_state(T, 'command_steer_rad', 'steer_rad', 'Steering (rad)', 'Simulator time (s)', 8.6, S);
export_pair(fig, fullfile(figDir, 'steering_command_vs_achieved'));
parameter_fit_figures(fullfile(ev, 'metrics', 'enriched_fit'), fullfile(figDir, 'enriched_ros_fit'), ...
    fullfile(figDir, 'enriched_ros_residuals'), S);
end
