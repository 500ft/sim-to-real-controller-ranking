function [fig, ax] = command_and_state(T, command, state, ylab, xlab, h_cm, S)
%COMMAND_AND_STATE Commanded (a, orange dash-dot) and achieved (b, blue solid) on the same axes.
[fig, tl] = new_figure(S.width, h_cm, 2, 1);
t = T.time_s;
cols = {command, state}; styles = {'-.', '-'}; colours = {S.c.orange, S.c.blue};
labels = {'commanded', 'achieved'};
lo = min([T.(command); T.(state)]); hi = max([T.(command); T.(state)]);
pad = 0.08 * (hi - lo);
for i = 1:2
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    plot(ax(i), t, T.(cols{i}), styles{i}, 'Color', colours{i}, 'LineWidth', 0.6);
    ref_y(ax(i), 0, S);
    xlim(ax(i), [t(1) - 0.3, t(end) + 0.3]);
    ylim(ax(i), [lo - pad, hi + 3 * pad]);
    ylabel(ax(i), ylab);
    dlabel(ax(i), t(end) + 0.3, hi + 3 * pad, labels{i}, colours{i}, S, 'HorizontalAlignment', 'right', ...
        'VerticalAlignment', 'top');
    panel_letter(ax(i), char('a' + i - 1), S);
end
ax(1).XTickLabel = {};
xlabel(ax(2), xlab);
end
