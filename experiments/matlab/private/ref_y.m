function h = ref_y(ax, value, S, style)
%REF_Y Grey horizontal reference line (dotted unless a style is given).
if nargin < 4, style = ':'; end
h = yline(ax, value, style, 'Color', S.c.grey, 'LineWidth', 0.7);
uistack(h, 'bottom');
end
