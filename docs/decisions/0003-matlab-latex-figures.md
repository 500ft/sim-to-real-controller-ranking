# Draw the data figures in MATLAB with LaTeX text

Status: Owner decision, 2026-11-02.

On 2026-11-02 the owner asked for every data visual in their research
repositories to be redone in MATLAB R2025b with LaTeX text, matching a
before/after demo they approved. Visuals here means plots, graphs, charts,
headline result tables and equations. This is the owner authorization that the
AGENTS.md rule against cross-repository template passes asks for.

In this repository MATLAB now draws 31 data figures from committed run files
and writes six headline result tables as LaTeX. Equations in the Markdown use
GitHub math. No result file, Markdown results table or analysis step changed.
The Python generators keep the plotted values, captions and checks.
[Data and figures](../data-and-figures.md#figure-rules-and-redraw) holds the
rules, the redraw commands and the images that were not redrawn. This record
replaces the rendering choices in [0002](0002-figure-rules.md).
