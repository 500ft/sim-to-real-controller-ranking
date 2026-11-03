function panel_letter(ax, L, S)
%PANEL_LETTER Bold panel letter as a left-aligned axes title (exportgraphics keeps it).
title(ax, ['\textbf{' L '}'], 'FontSize', S.size.letter, 'FontWeight', 'normal', 'Interpreter', 'latex');
ax.TitleHorizontalAlignment = 'left';
end
