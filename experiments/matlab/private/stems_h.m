function stems_h(ax, x0, x1, y, S)
%STEMS_H Thin grey connectors for a horizontal dot plot.
x0 = x0(:) .* ones(numel(y), 1);
for i = 1:numel(y)
    plot(ax, [x0(i) x1(i)], [y(i) y(i)], '-', 'Color', S.c.stem, 'LineWidth', 1.0);
end
end
