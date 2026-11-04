function state_errors(T, rows, h_cm, stem, S)
%STATE_ERRORS Stacked model-minus-Gym error traces on a shared time axis.
n = size(rows, 1);
[fig, tl] = new_figure(S.width, h_cm, n, 1);
t = T.time_s;
for i = 1:n
    ax = nexttile(tl); hold(ax, 'on');
    v = T.(rows{i, 1});
    plot(ax, t, v, '-', 'Color', S.c.blue, 'LineWidth', 0.8);
    ref_y(ax, 0, S);
    span = max(v) - min(v); if span == 0, span = 1; end
    ylim(ax, [min(v) - 0.12 * span, max(v) + 0.12 * span]);
    xlim(ax, [t(1) - 0.5, t(end) + 0.5]);
    ylabel(ax, rows{i, 2});
    panel_letter(ax, char('a' + i - 1), S);
    if i < n, ax.XTickLabel = {}; else, xlabel(ax, 'Time (s)'); end
    axs(i) = ax; %#ok<AGROW>
end
export_pair(fig, stem);
end
