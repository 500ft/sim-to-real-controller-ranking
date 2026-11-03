function make_tables(root, tableDir, ~)
%MAKE_TABLES Write the headline result tables as LaTeX (booktabs + siunitx).
%   Every number is read from a committed CSV and printed here; nothing is
%   typed by hand. Each table is a tabular fragment <name>.tex; typeset it to
%   PDF and 300-dpi PNG with a standalone booktabs/siunitx document (see
%   experiments/matlab/README.md).

controller_comparison(root, tableDir);
dynamic_replay_yaw_rate(root, tableDir);
ekf_summary(root, tableDir);
parameter_id_robustness(root, tableDir);
command_response(root, tableDir);
ope_structure(root, tableDir);
end

function controller_comparison(root, d)
T = read_csv(fullfile(root, 'runs', 'controller_comparison', 'results.csv'));
names = struct('pure_pursuit', 'Pure pursuit', 'lqr', 'LQR', 'mpc', 'MPC');
cases = struct('selected_baseline', 'selected baseline', 'nominal', 'nominal');
assert(all(to_bool(T.completed_lap)) && ~any(to_bool(T.collision)), 'table assumes every run completes the lap');
rows = strings(height(T), 1);
for i = 1:height(T)
    p95 = T.mpc_p95_solve_time_s(i);
    if isnan(p95), p95s = '{\textendash}'; else, p95s = sprintf('%.2f', 1000 * p95); end
    rows(i) = sprintf('%s & %s & %.3f & %.3f & %.3f & %.2f & %.4f & %.3f & %s \\\\', ...
        names.(char(T.controller(i))), cases.(char(T.("case")(i))), T.lap_time_s(i), T.rms_cte_m(i), ...
        T.max_abs_cte_m(i), T.steering_effort_rad(i), T.mean_abs_command_steer_rad(i), ...
        T.max_abs_command_steer_rad(i), p95s);
end
L = [header('controller_comparison', 'runs/controller_comparison/results.csv')
"\begin{tabular}{@{}ll S[table-format=2.3] S[table-format=1.3] S[table-format=1.3] S[table-format=1.2] S[table-format=1.4] S[table-format=1.3] S[table-format=1.2]@{}}"
"\toprule"
" & & {Lap time} & \multicolumn{2}{c}{Cross-track error (\unit{\metre})} & {Steering effort} & \multicolumn{2}{c}{$|\delta_\mathrm{cmd}|$ (\unit{\radian})} & {MPC p95 solve} \\"
"\cmidrule(lr){4-5}\cmidrule(lr){7-8}"
"Controller & Case & {(\unit{\second})} & {RMS} & {max} & {(\unit{\radian})} & {mean} & {max} & {(\unit{\milli\second})} \\"
"\midrule"
rows
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'controller_comparison.tex'));
end

function dynamic_replay_yaw_rate(root, d)
m = metric_struct(fullfile(root, 'runs', 'dynamic_model_replay', 'metrics.csv'));
L = [header('dynamic_replay_yaw_rate', 'runs/dynamic_model_replay/metrics.csv')
"\begin{tabular}{@{}l S[table-format=1.4]@{}}"
"\toprule"
"Yaw-rate model, same first-lap inputs & {Yaw-rate RMSE (\unit[per-mode=symbol]{\radian\per\second})} \\"
"\midrule"
sprintf("Kinematic yaw law & %.4f \\\\", m.kinematic_yaw_rate_rmse_radps)
sprintf("Dynamic single-track replay & %.4f \\\\", m.dynamic_yaw_rate_rmse_radps)
"\midrule"
sprintf("RMSE reduction (\\unit{\\percent}) & {\\num{%.2f}} \\\\", m.yaw_rate_rmse_improvement_percent)
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'dynamic_replay_yaw_rate.tex'));
end

function ekf_summary(root, d)
T = read_csv(fullfile(root, 'runs', 'ekf_study', 'summary.csv'));
order = ["clean_measurements", "low_noise", "high_noise", "dropout_1s", "dropout_3s"];
label = ["Clean measurements", "Low noise", "High noise", "1 s dropout", "3 s dropout"];
rows = strings(0, 1);
for i = 1:numel(order)
    e = T(T.scenario == order(i) & T.estimator == "ekf", :);
    r = T(T.scenario == order(i) & T.estimator == "dead_reckoning", :);
    assert(height(e) == 1 && height(r) == 1, 'expected one EKF and one dead-reckoning row per scenario');
    rows(end + 1, 1) = sprintf('%s & %.4f & %.2f & %.3f & %.2f & %.4f & %.3f & %.2f \\\\', label(i), ...
        e.position_rmse_m, r.position_rmse_m, e.max_position_error_m, r.max_position_error_m, ...
        e.theta_rmse_rad, r.theta_rmse_rad, 100 * e.ekf_position_rmse_improvement_fraction); %#ok<AGROW>
end
L = [header('ekf_summary', 'runs/ekf_study/summary.csv')
"\begin{tabular}{@{}l S[table-format=1.4] S[table-format=2.2] S[table-format=1.3] S[table-format=2.2] S[table-format=1.4] S[table-format=1.3] S[table-format=2.2]@{}}"
"\toprule"
" & \multicolumn{2}{c}{Position RMSE (\unit{\metre})} & \multicolumn{2}{c}{Max position error (\unit{\metre})} & \multicolumn{2}{c}{Yaw RMSE (\unit{\radian})} & {EKF RMSE} \\"
"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}"
"Scenario & {EKF} & {DR} & {EKF} & {DR} & {EKF} & {DR} & {reduction (\unit{\percent})} \\"
"\midrule"
rows
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'ekf_summary.tex'));
end

function parameter_id_robustness(root, d)
T = read_csv(fullfile(root, 'runs', 'parameter_id_robustness', 'results.csv'));
L0 = read_csv(fullfile(root, 'reports', 'figures', 'data', 'parameter_id_robustness.csv'));
assert(isequal(T.scenario, L0.scenario), 'label table and results disagree on scenario order');
pass = to_bool(T.acceptance_passed);
rows = strings(height(T), 1);
for i = 1:height(T)
    gate = '\textendash';
    if ~pass(i), gate = ['\texttt{' strrep(char(T.first_failed_gate(i)), '_', '\_') '}']; end
    yn = 'yes'; if ~pass(i), yn = 'no'; end
    rows(i) = sprintf('%s & %.4f & %.4f & %.2e & %.2e & %.3f & %s & %s \\\\', L0.label(i), T.fitted_C_Sf(i), ...
        T.fitted_C_Sr(i), T.C_Sf_oracle_relative_error(i), T.C_Sr_oracle_relative_error(i), ...
        T.jacobian_condition_number(i), yn, gate);
end
L = [header('parameter_id_robustness', 'runs/parameter_id_robustness/results.csv')
"\begin{tabular}{@{}l S[table-format=1.4] S[table-format=1.4] S[table-format=1.2e-2] S[table-format=1.2e-2] S[table-format=1.3] cl@{}}"
"\toprule"
" & \multicolumn{2}{c}{Fitted stiffness} & \multicolumn{2}{c}{Relative error vs Gym} & {Jacobian} & {Passed} & {First failed} \\"
"\cmidrule(lr){2-3}\cmidrule(lr){4-5}"
"Perturbation & {$C_{Sf}$} & {$C_{Sr}$} & {$C_{Sf}$} & {$C_{Sr}$} & {condition} & {all gates} & {gate} \\"
"\midrule"
rows
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'parameter_id_robustness.tex'));
end

function command_response(root, d)
T = read_csv(fullfile(root, 'runs', 'real_command_response', 'comparison_metrics.csv'));
rows = strings(height(T), 1);
for i = 1:height(T)
    lag = T.lag_s(i);
    if isnan(lag), lags = '{not applicable}'; else, lags = sprintf('%.2f', lag); end
    rows(i) = sprintf('%s & %.3f & %s \\\\', strrep(char(T.comparison(i)), '+', '$+$'), T.rmse_m_s(i), lags);
end
L = [header('command_response', 'runs/real_command_response/comparison_metrics.csv')
"\begin{tabular}{@{}l S[table-format=1.3] S[table-format=1.2]@{}}"
"\toprule"
"Comparison & {Development RMSE (\unit[per-mode=symbol]{\metre\per\second})} & {Apparent delay (\unit{\second})} \\"
"\midrule"
rows
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'command_response.tex'));
end

function ope_structure(root, d)
T = read_csv(fullfile(root, 'runs', 'ope_qualification', 'structure.csv'));
rows = strings(height(T), 1);
for i = 1:height(T)
    rows(i) = sprintf('%s & \\texttt{%s} & %d & %d & %d & %d & %d & %d & %d \\\\', T.label(i), ...
        strrep(char(T.archive(i)), '_', '\_'), T.("rows")(i), T.segments(i), T.policy_names(i), ...
        T.min_rows_per_segment(i), T.max_rows_per_segment(i), T.flags_at_segment_end(i), T.flags_before_segment_end(i));
end
L = [header('ope_structure', 'runs/ope_qualification/structure.csv')
"\begin{tabular}{@{}ll S[table-format=6.0] S[table-format=4.0] S[table-format=2.0] S[table-format=3.0] S[table-format=3.0] S[table-format=4.0] S[table-format=5.0]@{}}"
"\toprule"
" & & & & {Policy-name} & \multicolumn{2}{c}{Rows per segment} & \multicolumn{2}{c}{Rows with done OR truncated} \\"
"\cmidrule(lr){6-7}\cmidrule(l){8-9}"
"Archive & File & {Rows} & {Segments} & {strings} & {min} & {max} & {at segment end} & {before end} \\"
"\midrule"
rows
"\bottomrule"
"\end{tabular}"];
writelines(L, fullfile(d, 'ope_structure.tex'));
end

function h = header(name, source)
h = [string(sprintf('%% %s.tex: generated by experiments/matlab/make_tables.m from %s; do not edit by hand.', name, source))
     "\sisetup{group-minimum-digits=4, group-digits=integer}"];
end
