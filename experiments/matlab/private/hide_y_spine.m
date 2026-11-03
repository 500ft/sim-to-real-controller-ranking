function hide_y_spine(ax, S)
%HIDE_Y_SPINE Hide the y spine and ticks but keep category labels readable.
try
    ax.YAxis.Color = 'none';
    ax.YAxis.TickLabelColor = S.c.ink;
catch
    ax.YAxis.Color = S.c.ink;
end
end
