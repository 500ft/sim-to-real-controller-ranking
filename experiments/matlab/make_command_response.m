function make_command_response(root, figDir, S)
%MAKE_COMMAND_RESPONSE Public-car same-run development fit.
%   Inputs: runs/real_command_response/comparison.csv, result.json and
%   delay_profile.json. Panel a: Vicon forward velocity (blue, solid) and the
%   delay + affine fit (orange, dashed); b: commanded forward velocity; c: RMSE
%   across the delay search with the no-delay affine RMSE dotted and the
%   selected delay as a filled circle. Traces break where the time step exceeds
%   0.05 s (excluded intervals).

run = fullfile(root, 'runs', 'real_command_response');
C = read_csv(fullfile(run, 'comparison.csv'));
res = jsondecode(fileread(fullfile(run, 'result.json')));
prof = jsondecode(fileread(fullfile(run, 'delay_profile.json')));
lags = [prof.lag_s]'; errs = [prof.rmse_m_s]';
assert(min(errs) == res.delay_affine.rmse_m_s, 'selected delay is not the profile minimum');

t = C.elapsed_s;
gap = find(diff(t) > 0.05) + 1;
gt = with_gaps(t, gap);
[fig, tl] = new_figure(S.width, 15.7, 17, 1);
ax(1) = nexttile(tl, 1, [7 1]); hold(ax(1), 'on');
plot(ax(1), gt, with_gaps(C.tracking_forward_m_s, gap), '-', 'Color', S.c.blue, 'LineWidth', 0.6);
plot(ax(1), gt, with_gaps(C.delay_affine_m_s, gap), '--', 'Color', S.c.orange, 'LineWidth', 0.8);
ylabel(ax(1), 'Forward velocity (m/s)');
ax(2) = nexttile(tl, 8, [3 1]); hold(ax(2), 'on');
plot(ax(2), gt, with_gaps(C.command_forward_m_s, gap), '-', 'Color', S.c.blue, 'LineWidth', 0.6);
ylabel(ax(2), 'Command (m/s)'); xlabel(ax(2), 'Bag elapsed time (s)');
for i = 1:2
    ref_y(ax(i), 0, S); xlim(ax(i), [0, max(t) * 1.02]);
end
ax(1).XTickLabel = {};
yl = ylim(ax(1)); ylim(ax(1), [yl(1), yl(2) * 1.12]); yl = ylim(ax(1));
dlabel(ax(1), 2, yl(2), 'Vicon, tracking axes', S.c.blue, S, 'VerticalAlignment', 'top');
dlabel(ax(1), 28, yl(2), 'delay + affine fit', S.c.orange, S, 'VerticalAlignment', 'top');
ax(3) = nexttile(tl, 12, [6 1]); hold(ax(3), 'on');
plot(ax(3), lags, errs, '-', 'Color', S.c.blue, 'LineWidth', 1.1);
base = res.no_delay_affine.rmse_m_s;
ref_y(ax(3), base, S);
plot(ax(3), res.delay_affine.lag_s, res.delay_affine.rmse_m_s, 'o', 'MarkerSize', 5, 'Color', S.c.blue, ...
    'MarkerFaceColor', S.c.blue);
set(ax(3), 'YLim', [0, max(errs) * 1.12], 'XLim', [min(lags), max(lags)]);
text(ax(3), max(lags), base, sprintf('no-delay affine RMSE %.3f m/s', base), 'Color', S.c.grey, ...
    'FontSize', S.size.note, 'HorizontalAlignment', 'right', 'VerticalAlignment', 'top');
text(ax(3), res.delay_affine.lag_s, res.delay_affine.rmse_m_s * 0.88, ...
    sprintf('selected delay %.2f s, %.3f m/s', res.delay_affine.lag_s, res.delay_affine.rmse_m_s), ...
    'Color', S.c.blue, 'FontSize', S.size.note, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'top');
xlabel(ax(3), 'Apparent delay on recording clock (s)'); ylabel(ax(3), 'Development RMSE (m/s)');
for i = 1:3, panel_letter(ax(i), char('a' + i - 1), S); end
export_pair(fig, fullfile(figDir, 'real_command_response'));
end

function v = with_gaps(v, gap)
% Insert NaN before each index in gap so excluded intervals break the trace.
v = v(:);
for k = numel(gap):-1:1
    v = [v(1:gap(k) - 1); NaN; v(gap(k):end)];
end
end
