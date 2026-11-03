"""Markdown for a headline result table: the typeset image, then the text table in a fold.

experiments/matlab/make_tables.m writes each table as LaTeX from the committed
CSV; the typeset PNG and PDF live in reports/figures/tables/. Reports show the
PNG and keep the Markdown table under it so the values stay searchable.
"""


def block(image: str, alt: str, table: str) -> str:
    """Image line followed by ``table`` inside a <details> fold."""
    return f"![{alt}]({image})\n\n<details><summary>Table as text</summary>\n\n{table}\n\n</details>"
