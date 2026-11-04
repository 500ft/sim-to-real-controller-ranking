function h = dlabel(ax, x, y, str, color, S, varargin)
%DLABEL Direct series label in the series colour (9 pt unless overridden).
h = text(ax, x, y, str, 'Color', color, 'FontSize', S.size.label, 'Interpreter', 'latex', varargin{:});
end
