function make_ope_structure(root, figDir, S)
%MAKE_OPE_STRUCTURE Structural census of the five F110 archives.
%   Input: runs/ope_qualification/structure.csv (written by
%   experiments/plot_ope_structure.py from result.json). Panel a: recording
%   segments (circles); b: policy-name strings (squares); c: rows with done OR
%   truncated, split into flags at a segment end (filled blue) and before a
%   segment end (hollow orange). All count axes are linear from zero.

T = read_csv(fullfile(root, 'runs', 'ope_qualification', 'structure.csv'));
n = height(T); y = (1:n)';
[fig, tl] = new_figure(S.width, 13.2, 2, 2);
specs = {'segments', 'o', 'Recording segments (count)'; 'policy_names', 's', 'Policy-name strings (count)'};
for p = 1:2
    ax = nexttile(tl); hold(ax, 'on');
    v = T.(specs{p, 1});
    stems_h(ax, 0, v, y, S);
    plot(ax, v, y, specs{p, 2}, 'MarkerSize', 5, 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue);
    set(ax, 'YDir', 'reverse', 'YLim', [0.5 n + 0.5], 'YTick', y, 'XLim', [0 max(v) * 1.1]);
    if p == 1, ax.YTickLabel = cellstr(T.label); else, ax.YTickLabel = {}; end
    hide_y_spine(ax, S);
    xlabel(ax, specs{p, 3});
    comma_labels(ax);
    panel_letter(ax, char('a' + p - 1), S);
end
ax = nexttile(tl, [1 2]); hold(ax, 'on');
a = T.flags_at_segment_end; e = T.flags_before_segment_end; h = 0.24;
for i = 1:n
    patch(ax, [0 a(i) a(i) 0], y(i) + [-h -h h h], S.c.blue, 'EdgeColor', S.c.blue);
    if e(i) > 0
        patch(ax, a(i) + [0 e(i) e(i) 0], y(i) + [-h -h h h], 'w', 'EdgeColor', S.c.orange, 'LineWidth', 1.0);
    end
end
set(ax, 'YDir', 'reverse', 'YLim', [0.5 n + 0.5], 'YTick', y, 'YTickLabel', cellstr(T.label), ...
    'XLim', [0 max(a + e) * 1.05]);
hide_y_spine(ax, S);
xlabel(ax, 'Rows with done OR truncated (count)');
comma_labels(ax);
[~, k] = max(e);
dlabel(ax, a(k) + e(k) / 2, y(k) - 0.42, 'flag before segment end', S.c.orange, S, 'HorizontalAlignment', 'center', ...
    'VerticalAlignment', 'bottom', 'FontSize', S.size.note);
[~, j] = max(a);
dlabel(ax, a(j) + 0.01 * max(a + e), y(j), 'flag at segment end', S.c.blue, S, 'FontSize', S.size.note);
panel_letter(ax, 'c', S);
export_pair(fig, fullfile(figDir, 'ope_structure'));
end
