function hatch_cell(ax, x0, y0, w, h, kind, color, step)
%HATCH_CELL Diagonal ('diag') or crossed ('cross') hatching inside one rectangle.
if nargin < 8, step = 0.125; end
for c = -1 + step:step:1 - step          % lines v = u - c in unit coordinates
    u = [max(0, c) min(1, 1 + c)];
    plot(ax, x0 + u * w, y0 + (u - c) * h, '-', 'Color', color, 'LineWidth', 0.4);
end
if strcmp(kind, 'cross')
    for c = step:step:2 - step           % lines v = c - u
        u = [max(0, c - 1) min(1, c)];
        plot(ax, x0 + u * w, y0 + (c - u) * h, '-', 'Color', color, 'LineWidth', 0.4);
    end
end
end
