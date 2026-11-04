function make_fmea(root, figDir, S)
%MAKE_FMEA Failure-mode screen figures.
%   Input: reports/figures/data/fmea.csv (labels and signal groups written by
%   experiments/figure_data.py from runs/failure_mode_fmea/results.csv).
%   Filled blue: failure reproduced in simulation; hollow orange: not reproduced.

F = read_csv(fullfile(root, 'reports', 'figures', 'data', 'fmea.csv'));
rep = to_bool(F.reproduced);

% ---- RPN bars -------------------------------------------------------------------------
[~, order] = sort(F.rpn, 'ascend');
[fig, tl] = new_figure(S.width, 7.4, 1, 1);
ax = nexttile(tl); hold(ax, 'on');
h = 0.3;
for k = 1:numel(order)
    i = order(k);
    if rep(i)
        patch(ax, [0 F.rpn(i) F.rpn(i) 0], k + [-h -h h h], S.c.blue, 'EdgeColor', S.c.blue);
    else
        patch(ax, [0 F.rpn(i) F.rpn(i) 0], k + [-h -h h h], 'w', 'EdgeColor', S.c.orange, 'LineWidth', 1.1);
    end
end
set(ax, 'YTick', 1:numel(order), 'YTickLabel', cellstr(F.label(order)), 'YLim', [0.4 numel(order) + 0.6], ...
    'XLim', [0 max(F.rpn) * 1.42]);
hide_y_spine(ax, S);
xlabel(ax, 'Risk priority number (RPN)');
top = order(end);
dlabel(ax, F.rpn(top) + 4, numel(order), 'reproduced in simulation', S.c.blue, S, 'FontSize', S.size.note);
kn = find(~rep(order), 1, 'last');
dlabel(ax, F.rpn(order(kn)) + 4, kn, 'not reproduced', S.c.orange, S, 'FontSize', S.size.note);
export_pair(fig, fullfile(figDir, 'fmea_rpn_bar'));

% ---- detection signals, one panel per unit ------------------------------------------
groups = {'time', 'Time to collision (s)'; 'position', 'Position error (m)'; 'steer', 'Steering command at limit (rad)'};
sizes = cellfun(@(g) max(sum(F.signal_group == g), 1), groups(:, 1));
[fig, tl] = new_figure(S.width, 11.7, sum(sizes) + 3, 1);
row = 1;
for g = 1:3
    ax = nexttile(tl, row, [sizes(g) + 1 1]); hold(ax, 'on');
    row = row + sizes(g) + 1;
    P = F(F.signal_group == groups{g, 1}, :);
    P = sortrows(P, 'detection_metric');
    y = (1:height(P))' - 1;
    stems_h(ax, 0, P.detection_metric, y, S);
    r = to_bool(P.reproduced);
    plot(ax, P.detection_metric(r), y(r), 'o', 'MarkerSize', 5, 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue);
    plot(ax, P.detection_metric(~r), y(~r), 'o', 'MarkerSize', 5, 'Color', S.c.orange, 'MarkerFaceColor', 'w', 'LineWidth', 1.0);
    set(ax, 'YTick', y, 'YTickLabel', cellstr(P.label), 'YLim', [-0.6, height(P) - 0.4], ...
        'XLim', [0, max(P.detection_metric) * 1.12]);
    hide_y_spine(ax, S);
    xlabel(ax, groups{g, 2});
    panel_letter(ax, char('a' + g - 1), S);
    if any(~r)
        k = find(~r, 1);
        dlabel(ax, P.detection_metric(k) + 0.02 * max(P.detection_metric), y(k), 'not reproduced', S.c.orange, S, ...
            'FontSize', S.size.note);
    end
    if any(r) && g == 1
        k = find(r, 1, 'last');
        dlabel(ax, P.detection_metric(k), y(k) + 0.55, 'reproduced in simulation', S.c.blue, S, ...
            'FontSize', S.size.note, 'HorizontalAlignment', 'right');
    end
end
export_pair(fig, fullfile(figDir, 'fmea_detection_signals'));
end
