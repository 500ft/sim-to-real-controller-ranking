function comma_labels(ax)
%COMMA_LABELS Freeze the x ticks and print them with thousands separators.
t = ax.XTick;
ax.XTickMode = 'manual';
lab = strings(size(t));
for i = 1:numel(t)
    s = sprintf('%.0f', t(i));
    n = numel(s);
    for k = n - 3:-3:1
        s = [s(1:k) '{,}' s(k + 1:end)];
    end
    lab(i) = s;
end
ax.XTickLabel = cellstr(lab);
end
