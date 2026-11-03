function h = shade_y(ax, y0, y1, S)
%SHADE_Y Light grey band across the current x-limits, drawn under the data.
xl = xlim(ax);
h = patch(ax, [xl(1) xl(2) xl(2) xl(1)], [y0 y0 y1 y1], S.c.span, 'EdgeColor', 'none');
xlim(ax, xl);
uistack(h, 'bottom');
end
