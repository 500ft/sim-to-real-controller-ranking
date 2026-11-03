function h = ref_x(ax, value, S, style)
%REF_X Grey vertical reference line (dotted unless a style is given).
if nargin < 4, style = ':'; end
h = xline(ax, value, style, 'Color', S.c.grey, 'LineWidth', 0.7);
uistack(h, 'bottom');
end
