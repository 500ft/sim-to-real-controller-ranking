function make_controller_pipeline(root, figDir, S)
%MAKE_CONTROLLER_PIPELINE Simulation controller-pipeline figures.
%   Inputs: the derived tables reports/figures/data/controller_*.csv and
%   controller_pipeline_bands.json, written by experiments/figure_data.py from
%   runs/controller_pipeline/. Grey bands are the registered near-tie region,
%   grey dotted lines mark zero. Blue is the example track or the selected line,
%   orange MapZoo Berlin or the source line; hollow markers fail a target check.

data = fullfile(root, 'reports', 'figures', 'data');
B = jsondecode(fileread(fullfile(data, 'controller_pipeline_bands.json')));
pairs = ["pure_pursuit|lqr", "pure_pursuit|mpc", "lqr|mpc"];

% ---- delay sensitivity ---------------------------------------------------------------
D = read_csv(fullfile(data, 'controller_delay_sensitivity.csv'));
[fig, tl] = new_figure(S.width, 6.6, 1, 3);
for i = 1:3
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    P = D(D.pair == pairs(i), :);
    plot(ax(i), 1:height(P), P.delta_lap_s, '-o', 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue, 'MarkerSize', 4);
    set(ax(i), 'XTick', 1:height(P), 'XTickLabel', cellstr(P.delay_label), 'XLim', [0.7 height(P) + 0.3], ...
        'YLim', [-0.13 0.37], 'TickDir', 'out');
    shade_y(ax(i), -B.delay_near_tie_s, B.delay_near_tie_s, S);
    ref_y(ax(i), 0, S);
    xlabel(ax(i), 'Command delay');
    pair_letter(ax(i), char('a' + i - 1), P.pair_label(1), S);
    if i > 1, ax(i).YTickLabel = {}; end
end
ylabel(ax(1), 'Gym finish difference (s)');
text(ax(1), 0.8, -B.delay_near_tie_s + 0.012, 'registered near tie', 'Color', S.c.grey, ...
    'FontSize', S.size.note, 'VerticalAlignment', 'bottom');
export_pair(fig, fullfile(figDir, 'controller_delay_sensitivity'));
clear ax

% ---- paired model sensitivity --------------------------------------------------------
M = read_csv(fullfile(data, 'controller_model_dispersion.csv'));
tracks = ["example", "mapzoo_berlin"]; names = ["example", "MapZoo Berlin"];
col = {S.c.blue, S.c.orange}; sty = {'-o', '--s'};
yr = [min([M.delta_lap_s; -B.model_near_tie_s]) - 0.35, max(M.delta_lap_s) + 0.45];
[fig, tl] = new_figure(S.width, 7.0, 1, 3);
for i = 1:3
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    for t = 1:2
        P = M(M.pair == pairs(i) & M.track == tracks(t), :);
        plot(ax(i), 1:height(P), P.delta_lap_s, sty{t}, 'Color', col{t}, 'MarkerFaceColor', col{t}, ...
            'MarkerSize', 4, 'LineWidth', 0.9);
        if i == 1
            dlabel(ax(i), 1, P.delta_lap_s(1) - 0.3, names(t), col{t}, S, 'VerticalAlignment', 'top');
        end
    end
    set(ax(i), 'XTick', 1:height(P), 'XTickLabel', cellstr(P.model_label), 'XLim', [0.7 height(P) + 0.3], ...
        'YLim', yr, 'TickDir', 'out');
    shade_y(ax(i), -B.model_near_tie_s, B.model_near_tie_s, S);
    ref_y(ax(i), 0, S);
    xlabel(ax(i), 'Model variant');
    pair_letter(ax(i), char('a' + i - 1), P.pair_label(1), S);
    if i > 1, ax(i).YTickLabel = {}; end
end
ylabel(ax(1), 'Paired Gym finish difference (s)');
text(ax(2), 0.8, B.model_near_tie_s + 0.05, 'near tie', 'Color', S.c.grey, 'FontSize', S.size.note, ...
    'VerticalAlignment', 'bottom');
export_pair(fig, fullfile(figDir, 'controller_model_dispersion'));
clear ax

% ---- offline line candidates and final-minus-source change ---------------------------
C = read_csv(fullfile(data, 'controller_offline_candidates.csv'));
Q = read_csv(fullfile(data, 'controller_offline_deltas.csv'));
[fig, tl] = new_figure(S.width, 6.8, 1, 2);
ax = nexttile(tl); hold(ax, 'on');
plot(ax, C.order, C.mean_tuning_gym_finish_s, '-o', 'Color', S.c.blue, 'MarkerFaceColor', S.c.blue, 'MarkerSize', 5);
set(ax, 'XTick', C.order, 'XLim', [min(C.order) - 0.25, max(C.order) + 0.25], 'TickDir', 'out');
yl = ylim(ax); ylim(ax, yl + [-0.04 0.04]);
xlabel(ax, 'Offline candidate order');
ylabel(ax, 'Mean tuning Gym finish (s)');
panel_letter(ax, 'a', S);
bx = nexttile(tl); hold(bx, 'on');
plot(bx, 1:height(Q), Q.final_minus_source_s, '-', 'Color', S.c.orange, 'LineWidth', 0.9);
plot(bx, 1:height(Q), Q.final_minus_source_s, 's', 'Color', S.c.orange, 'MarkerFaceColor', 'w', ...
    'MarkerSize', 6, 'LineWidth', 1.0);
set(bx, 'XTick', 1:height(Q), 'XTickLabel', cellstr(Q.label), 'XLim', [0.7 height(Q) + 0.3], ...
    'YLim', [min(Q.final_minus_source_s) - 0.08, 0.06], 'TickDir', 'out');
ref_y(bx, 0, S);
xlabel(bx, 'Controller');
ylabel(bx, 'Final minus source line (s)');
panel_letter(bx, 'b', S);
export_pair(fig, fullfile(figDir, 'controller_offline_progress'));
clear ax

% ---- zoomed source and selected line overlay -----------------------------------------
O = read_csv(fullfile(data, 'controller_offline_overlay.csv'));
ctrl = ["pure_pursuit", "lqr", "mpc"]; lab = ["PP", "LQR", "MPC"];
cx = B.overlay_center_x_m; cy = B.overlay_center_y_m; hw = B.overlay_half_width_m;
dark = [0.35 0.35 0.35];
[fig, tl] = new_figure(S.width, 7.4, 1, 3);
for i = 1:3
    ax(i) = nexttile(tl); hold(ax(i), 'on'); %#ok<AGROW>
    h1 = draw(ax(i), O(O.series == "source_line", :), ':', S.c.grey, 1.1);
    h2 = draw(ax(i), O(O.series == "selected_line", :), '-.', dark, 0.9);
    h3 = draw(ax(i), O(O.series == "source_replay" & O.controller == ctrl(i), :), '--', S.c.orange, 1.0);
    h4 = draw(ax(i), O(O.series == "selected_replay" & O.controller == ctrl(i), :), '-', S.c.blue, 1.1);
    axis(ax(i), 'equal');
    set(ax(i), 'XLim', [cx - hw, cx + hw], 'YLim', [cy - hw, cy + hw], 'TickDir', 'out');
    xlabel(ax(i), '$x$ (m)');
    pair_letter(ax(i), char('a' + i - 1), lab(i), S);
    if i > 1, ax(i).YTickLabel = {}; end
end
ylabel(ax(1), '$y$ (m)');
lg = legend(ax(1), [h1 h2 h3 h4], {'source line', 'selected line', 'source-line replay', 'selected-line replay'}, ...
    'Orientation', 'horizontal', 'Box', 'off', 'FontSize', S.size.note);
lg.Layout.Tile = 'north';
export_pair(fig, fullfile(figDir, 'controller_offline_overlay'));
end

function h = draw(ax, T, style, color, width)
%DRAW One line per contiguous segment inside the zoom window; returns the first handle.
segs = unique(T.segment);
h = gobjects(1);
for k = 1:numel(segs)
    R = T(T.segment == segs(k), :);
    hk = plot(ax, R.x_m, R.y_m, style, 'Color', color, 'LineWidth', width);
    if k == 1, h = hk; end
end
end

function pair_letter(ax, L, name, S)
%PAIR_LETTER Bold panel letter followed by the panel's pair or controller name at 8 pt.
name = strrep(char(name), ' - ', ' $-$ ');
title(ax, ['\textbf{' L '}\enspace{\fontsize{' num2str(S.size.note) '}{10}\selectfont ' name '}'], ...
    'FontSize', S.size.letter, 'FontWeight', 'normal', 'Interpreter', 'latex');
ax.TitleHorizontalAlignment = 'left';
end
