function make_pure_pursuit(root, figDir, S)
%MAKE_PURE_PURSUIT Pure-pursuit lookahead x velocity-gain sweep figures.
%   Input: runs/pure_pursuit_sweep/results.csv. Heatmaps use MATLAB's default
%   parula colour map with a colour bar; hatched cells did not complete a lap
%   (diagonal: no lap within the time limit; crossed: collision); the ink box
%   marks the selected baseline. The region plot draws completed runs filled
%   blue and the rest hollow orange, one marker shape per run class.

R = read_csv(fullfile(root, 'runs', 'pure_pursuit_sweep', 'results.csv'));
done = to_bool(R.completed_lap);
base = find(to_bool(R.selected_baseline));
assert(numel(base) == 1, 'expected one selected baseline');
heatmap_fig(R, done, base, 'rms_cte', fullfile(figDir, 'pure_pursuit_sweep_rms_cte_heatmap'), S);
heatmap_fig(R, done, base, 'lap_time', fullfile(figDir, 'pure_pursuit_sweep_lap_time_heatmap'), S);
regions_fig(R, done, base, fullfile(figDir, 'pure_pursuit_sweep_regions'), S);
end

function heatmap_fig(R, done, base, kind, stem, S)
L = unique(R.lookahead_m)'; G = sort(unique(R.vgain), 'descend')';
grid = nan(numel(G), numel(L)); status = strings(numel(G), numel(L));
for r = 1:height(R)
    i = find(G == R.vgain(r)); j = find(L == R.lookahead_m(r));
    status(i, j) = R.classification(r);
    if strcmp(kind, 'rms_cte'), grid(i, j) = R.rms_cte_m(r);
    elseif done(r), grid(i, j) = R.lap_time_s(r); end
end
[fig, tl] = new_figure(15.2, 10.4, 12, 1);
key = nexttile(tl, 1, [1 1]);
ax = nexttile(tl, 2, [11 1]); hold(ax, 'on');
im = imagesc(ax, grid);
im.AlphaData = ~isnan(grid);
colormap(ax, parula);
cmap = parula(256); clim(ax, [min(grid(:)) max(grid(:))]); cl = clim(ax);
for i = 1:numel(G)
    for j = 1:numel(L)
        if status(i, j) == "incomplete", hatch_cell(ax, j - 0.5, i - 0.5, 1, 1, 'diag', [0.55 0.55 0.55]); end
        if status(i, j) == "collision", hatch_cell(ax, j - 0.5, i - 0.5, 1, 1, 'cross', [0.55 0.55 0.55]); end
        v = grid(i, j);
        if isnan(v), continue; end
        c = cmap(max(1, min(256, round(1 + 255 * (v - cl(1)) / (cl(2) - cl(1))))), :);
        ink = [0 0 0]; if 0.299 * c(1) + 0.587 * c(2) + 0.114 * c(3) <= 0.5, ink = [1 1 1]; end
        if strcmp(kind, 'rms_cte'), s = sprintf('%.2f', v); else, s = sprintf('%.1f', v); end
        text(ax, j, i, s, 'HorizontalAlignment', 'center', 'Color', ink, 'FontSize', S.size.tick, ...
            'BackgroundColor', c, 'Margin', 1);
    end
end
bi = find(G == R.vgain(base)); bj = find(L == R.lookahead_m(base));
rectangle(ax, 'Position', [bj - 0.5, bi - 0.5, 1, 1], 'EdgeColor', S.c.ink, 'LineWidth', 1.6);
set(ax, 'YDir', 'reverse', 'XLim', [0.5 numel(L) + 0.5], 'YLim', [0.5 numel(G) + 0.5], ...
    'XTick', 1:numel(L), 'XTickLabel', compose('%g', L), 'YTick', 1:numel(G), 'YTickLabel', compose('%g', G), ...
    'TickLength', [0 0], 'XColor', S.c.ink, 'YColor', S.c.ink);
hide_spines(ax, S);
xlabel(ax, 'Lookahead distance (m)'); ylabel(ax, 'Velocity gain');
cb = colorbar(ax); cb.Box = 'off'; cb.TickDirection = 'out'; cb.Label.Interpreter = 'latex';
cb.FontSize = S.size.tick;
if strcmp(kind, 'rms_cte'), cb.Label.String = 'RMS cross-track error (m)'; else, cb.Label.String = 'Lap time (s)'; end
cb.Label.FontSize = S.size.label;  % after cb.FontSize, which rescales the label
% key strip: hatch swatches and the baseline box, labelled once
hold(key, 'on'); axis(key, 'off'); set(key, 'XLim', [0 10], 'YLim', [0 1]);
present = intersect(["incomplete", "collision"], status(:)', 'stable');
x = 0.2;
names = struct('incomplete', 'no lap within time limit', 'collision', 'collision');
for k = 1:numel(present)
    rectangle(key, 'Position', [x 0.2 0.35 0.6], 'EdgeColor', [0.55 0.55 0.55], 'LineWidth', 0.4);
    if present(k) == "incomplete", hatch_cell(key, x, 0.2, 0.35, 0.6, 'diag', [0.55 0.55 0.55], 0.34);
    else, hatch_cell(key, x, 0.2, 0.35, 0.6, 'cross', [0.55 0.55 0.55], 0.34); end
    text(key, x + 0.5, 0.5, names.(char(present(k))), 'FontSize', S.size.note, 'Color', S.c.ink);
    x = x + 3.4;
end
rectangle(key, 'Position', [x 0.2 0.35 0.6], 'EdgeColor', S.c.ink, 'LineWidth', 1.6);
text(key, x + 0.5, 0.5, 'selected baseline', 'FontSize', S.size.note, 'Color', S.c.ink);
export_pair(fig, stem);
end

function regions_fig(R, done, base, stem, S)
classes = {'stable', 'Stable', 'o'; 'oscillatory', 'Oscillatory', '^'; 'corner_cutting', 'Corner cutting', 'd'; ...
           'incomplete', 'No lap within time limit', 's'; 'collision', 'Collision', 'x'};
[fig, tl] = new_figure(15.2, 9.4, 1, 1);
ax = nexttile(tl); hold(ax, 'on');
hb = plot(ax, R.lookahead_m(base), R.vgain(base), 'o', 'MarkerSize', 13, 'Color', S.c.ink, 'LineWidth', 0.8);
h = gobjects(0); lab = {};
for k = 1:size(classes, 1)
    sel = R.classification == classes{k, 1};
    if ~any(sel), continue; end
    filled = all(done(sel));
    assert(filled || ~any(done(sel)), 'a run class mixes completed and incomplete runs');
    if filled
        h(end + 1) = plot(ax, R.lookahead_m(sel), R.vgain(sel), classes{k, 3}, 'MarkerSize', 6, ...
            'Color', S.c.blue, 'MarkerFaceColor', S.c.blue); %#ok<AGROW>
    else
        h(end + 1) = plot(ax, R.lookahead_m(sel), R.vgain(sel), classes{k, 3}, 'MarkerSize', 6, ...
            'Color', S.c.orange, 'MarkerFaceColor', 'w', 'LineWidth', 1.0); %#ok<AGROW>
    end
    lab{end + 1} = classes{k, 2}; %#ok<AGROW>
end
L = unique(R.lookahead_m)'; G = unique(R.vgain)';
set(ax, 'XTick', L, 'XTickLabel', compose('%g', L), 'YTick', G, 'YTickLabel', compose('%g', G));
xlim(ax, [min(L) - 0.08 * span_of(L), max(L) + 0.08 * span_of(L)]);
ylim(ax, [min(G) - 0.08 * span_of(G), max(G) + 0.08 * span_of(G)]);
xlabel(ax, 'Lookahead distance (m)'); ylabel(ax, 'Velocity gain');
lg = legend(ax, [h hb], [lab {'Selected baseline'}], 'Location', 'northoutside', 'Orientation', 'horizontal', ...
    'Box', 'off', 'FontSize', S.size.note, 'NumColumns', 3);
lg.ItemTokenSize = [10 10];
export_pair(fig, stem);
end
