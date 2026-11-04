function h = shade_x(ax, x0, x1, S)
%SHADE_X Light grey interval across the current y-limits, drawn under the data.
yl = ylim(ax);
h = patch(ax, [x0 x1 x1 x0], [yl(1) yl(1) yl(2) yl(2)], S.c.span, 'EdgeColor', 'none');
ylim(ax, yl);
uistack(h, 'bottom');
end
