function [fig, tl] = new_figure(w_cm, h_cm, rows, cols)
%NEW_FIGURE Invisible figure of the given size (cm) with a compact tiled layout.
fig = figure('Visible', 'off', 'Units', 'centimeters', 'Position', [2 2 w_cm h_cm]);
tl = tiledlayout(fig, rows, cols, 'TileSpacing', 'compact', 'Padding', 'compact');
end
