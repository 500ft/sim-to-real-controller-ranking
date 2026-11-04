function hide_spines(ax, S)
%HIDE_SPINES Hide both axis lines and ticks of a heatmap, keep the tick labels.
try
    ax.XAxis.Color = 'none'; ax.XAxis.TickLabelColor = S.c.ink; ax.XAxis.Label.Color = S.c.ink;
    ax.YAxis.Color = 'none'; ax.YAxis.TickLabelColor = S.c.ink; ax.YAxis.Label.Color = S.c.ink;
catch
    ax.XColor = S.c.ink; ax.YColor = S.c.ink;
end
end
