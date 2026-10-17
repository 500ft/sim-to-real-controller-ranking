"""Shared figure rules: a data-only canvas with the words in a caption file.

Every generator under experiments/ that writes a report figure calls
``apply()`` before drawing and ``save()`` to write the image and its caption.
Only presentation lives here; no plotted value is computed in this module.

Rules every report figure follows:

- The canvas carries data, axes, tick labels, axis labels, panel letters and
  one framed legend. Titles, takeaways, sample sizes and notes live in the
  caption file written next to the image and in the report under it.
- Condition (which model, integrator or estimator) is carried by line style
  and marker shape. State (completed or collided, passed or failed) is carried
  by marker fill: filled is the nominal state, hollow the failed one. Colour is
  used only for heatmap fields, with a colourbar; text is never coloured.
- Nothing printed may touch another printed thing or the data. ``audit``
  returns every pair that does, and ``save`` refuses to write unless it is empty.
- Type is Computer Modern (matplotlib's bundled ``cmr10``) with mathtext "cm".
  cmr10 has no underscore, minus or multiplication glyphs, so labels that need
  them use mathtext.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import Collection  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.text import Text  # noqa: E402

INK = "black"
# Marker fill carries state: filled is nominal (completed, passed), hollow failed.
FILL = {True: INK, False: "white"}
MARKER = {"color": INK, "mec": INK, "ms": 5, "mew": 0.9, "ls": "none"}
REFERENCE = {"color": INK, "lw": 0.6, "ls": (0, (1, 2))}  # zero lines, tolerances, limits
SPAN = {"facecolor": "0.88", "edgecolor": "none", "lw": 0}  # held-out or dropout intervals

# Line style per entity. A reference trace is solid; a model replaying it is
# dashed; a third series is dash-dot. Marker shapes repeat the distinction on
# sparse series so the figure reads the same in greyscale print.
STYLE = {
    "reference": {"ls": "-", "lw": 1.0, "marker": "o"},  # Gym RK4 state or measured motion
    "rk4": {"ls": "-", "lw": 1.0, "marker": "o"},
    "euler": {"ls": (0, (5, 2)), "lw": 1.0, "marker": "s"},
    "kinematic": {"ls": (0, (5, 2)), "lw": 1.0, "marker": "s"},
    "dynamic": {"ls": (0, (5, 2)), "lw": 1.0, "marker": "^"},
    "fit": {"ls": (0, (5, 2)), "lw": 1.0, "marker": "s"},
    "command": {"ls": (0, (5, 2, 1, 2)), "lw": 0.9, "marker": "^"},
    "ekf": {"ls": "-", "lw": 1.0, "marker": "o"},
    "dead_reckoning": {"ls": (0, (5, 2)), "lw": 1.0, "marker": "s"},
    "path": {"ls": (0, (1, 1.5)), "lw": 0.8, "marker": None},  # reference path on the map
    "second_pass": {"ls": (0, (3, 1, 1, 1, 1, 1)), "lw": 0.8, "marker": None},
}

# Three type sizes, chosen by role: axis labels and legend, then panel
# letters, then tick labels and heatmap cell numbers.
LABEL_SIZE, LETTER_SIZE, TICK_SIZE = 9, 9, 7
WIDTH_IN = 7.0  # the repository's report width (178 mm)
DPI = 600


def apply(hashsalt: str = "sim-to-real-figures") -> None:
    """Set the shared rcParams for the current process."""
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["cmr10"],
        "mathtext.fontset": "cm",
        # cmr10 has no Unicode minus; mathtext tick labels carry a proper one.
        "axes.formatter.use_mathtext": True,
        "axes.unicode_minus": False,
        "font.size": LABEL_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "axes.titlesize": LETTER_SIZE,
        "axes.titlelocation": "left",
        "axes.titleweight": "normal",
        "legend.fontsize": LABEL_SIZE,
        "xtick.labelsize": TICK_SIZE,
        "ytick.labelsize": TICK_SIZE,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": INK,
        "lines.linewidth": 1.0,
        "lines.color": INK,
        "legend.frameon": True,
        "legend.fancybox": False,
        "legend.edgecolor": INK,
        "legend.framealpha": 1.0,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "figure.dpi": 100,
        "savefig.dpi": DPI,
        # Editable SVG text and stable element ids, so reruns give the same bytes.
        "svg.fonttype": "none",
        "svg.hashsalt": hashsalt,
    })


def subplots(nrows: int = 1, ncols: int = 1, height_in: float = 3.2, width_in: float = WIDTH_IN, **kwargs):
    """Constrained-layout subplots at the shared width."""
    return plt.subplots(nrows, ncols, figsize=(width_in, height_in), layout="constrained", **kwargs)


def figure(height_in: float, width_in: float = WIDTH_IN):
    return plt.figure(figsize=(width_in, height_in), layout="constrained")


def letter(ax, index: int) -> None:
    """Panel letter "(a)", "(b)", ... above the top-left corner of the axes."""
    ax.set_title(f"({'abcdefghij'[index]})", loc="left", pad=4)


def letters(axes) -> None:
    for i, ax in enumerate(axes):
        letter(ax, i)


def legend(fig, handles, ncol: int | None = None, **kwargs):
    """One framed legend above the panels."""
    return fig.legend(handles=handles, loc="outside upper center", ncol=ncol or len(handles),
                      columnspacing=1.4, handletextpad=0.5, handlelength=2.6, **kwargs)


def line(ax, x, y, entity: str, every: int | None = None, **kwargs):
    """Draw one series in its entity style; ``every`` places markers on a long trace."""
    style = {**STYLE[entity], **{k: kwargs.pop(k) for k in ("lw", "ls") if k in kwargs}}
    marker = style.pop("marker")
    if every is None or marker is None:
        marker = None
    return ax.plot(x, y, color=INK, marker=marker, markevery=every, ms=3.5, mfc="white", mew=0.8,
                   **style, **kwargs)[0]


def handle(entity: str, label: str, marker: bool = True):
    style = dict(STYLE[entity])
    shape = style.pop("marker")
    shape = shape if marker else None
    return matplotlib.lines.Line2D([], [], color=INK, marker=shape, ms=3.5, mfc="white", mew=0.8,
                                   label=label, **style)


def zero_line(ax) -> None:
    ax.axhline(0.0, zorder=1, **REFERENCE)


def _data_artists(ax):
    """Visible lines, collections and patches drawn as data; heatmap images and colour bars excluded."""
    if getattr(ax, "_colorbar", None) is not None:
        return []
    found = list(ax.lines)
    found += [c for c in ax.collections if isinstance(c, Collection)]
    found += [p for p in ax.patches if isinstance(p, Patch)]
    return [artist for artist in found if artist.get_visible()]


def audit(fig) -> list[tuple[str, str]]:
    """Pairs of printed things whose boxes touch. Empty means the canvas is clean.

    Every drawn text (tick labels inside the view, axis labels, panel letters,
    legend entries, colourbar labels) is checked against every other drawn
    text, against the data drawn in each axes, against each legend frame and
    against the figure edge. Data is not checked against data. Texts inside a
    legend are not checked against their own frame. Heatmap cell numbers
    (gid "cell") are printed on their own cell and are checked against other
    text only.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    legends = list(fig.legends) + [ax.get_legend() for ax in fig.axes if ax.get_legend()]
    owner = {id(child): lg for lg in legends for child in lg.findobj()}
    tick_labels, drawn = set(), []
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            # Compare in scale space so a log axis does not admit ticks far below its view.
            scale = axis.get_transform()
            low, high = sorted(scale.transform(np.asarray(axis.get_view_interval(), float)))
            slack = 1e-9 * (high - low)
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                loc = scale.transform(np.asarray([tick.get_loc()], float))[0]
                for label in (tick.label1, tick.label2):
                    tick_labels.add(id(label))
                    if label.get_visible() and label.get_text().strip() and low - slack <= loc <= high + slack:
                        drawn.append(label)
    drawn += [t for t in fig.findobj(Text)
              if id(t) not in tick_labels and t.get_visible() and t.get_text().strip()]
    texts = [(f"text {t.get_text()!r}", t.get_window_extent(renderer).padded(1), owner.get(id(t)), t.get_gid() == "cell")
             for t in drawn]
    others = [(f"data in {ax.get_ylabel() or 'axes'}", artist.get_window_extent(renderer), None)
              for ax in fig.axes for artist in _data_artists(ax)]
    others += [("legend frame", lg.get_window_extent(renderer), lg) for lg in legends]
    hits = []
    edge = fig.bbox
    for i, (name_a, box_a, legend_a, cell_a) in enumerate(texts):
        if box_a.x0 < edge.x0 or box_a.y0 < edge.y0 or box_a.x1 > edge.x1 or box_a.y1 > edge.y1:
            hits.append((name_a, "figure edge"))
        pairs = [(n, b, lg) for n, b, lg, _ in texts[i + 1:]]
        if not cell_a:
            pairs += others
        for name_b, box_b, legend_b in pairs:
            if legend_a is not None and legend_a is legend_b:
                continue
            if box_a.overlaps(box_b):
                hits.append((name_a, name_b))
    return hits


def printed_text(fig) -> set[str]:
    """Every visible non-empty string on the canvas."""
    return {t.get_text() for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()}


def allowed_text(fig) -> set[str]:
    """Strings the rules allow: ticks, axis labels, panel letters, legend entries and colourbar labels."""
    allowed = {f"({c})" for c in "abcdefghij"}
    for ax in fig.axes:
        allowed |= {t.get_text() for t in ax.get_xticklabels(which="both") + ax.get_yticklabels(which="both")}
        allowed |= {ax.get_xlabel(), ax.get_ylabel()}
        allowed |= {t.get_text() for t in ax.texts if t.get_gid() == "cell"}
        for axis in (ax.xaxis, ax.yaxis):
            allowed.add(axis.get_offset_text().get_text())
    for lg in list(fig.legends) + [ax.get_legend() for ax in fig.axes if ax.get_legend()]:
        allowed |= {t.get_text() for t in lg.get_texts()}
    return allowed


def save(fig, path: Path, caption: str, formats: tuple[str, ...] = ("png",)) -> list[Path]:
    """Refuse a touching canvas, write each format and ``<stem>.caption.md``, then close the figure."""
    path = Path(path)
    hits = audit(fig)
    if hits:
        raise ValueError(f"{path.name}: printed items touch: {hits}")
    path.parent.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in formats:
        out = path.with_suffix(f".{fmt}")
        metadata = {"png": {"Software": None}, "svg": {"Date": None}}[fmt]
        fig.savefig(out, dpi=DPI, metadata=metadata)
        if fmt == "svg":
            # Matplotlib path lines carry trailing spaces; normalize the text export.
            out.write_text("\n".join(row.rstrip() for row in out.read_text().splitlines()) + "\n")
        written.append(out)
    caption_path(path).write_text(caption + "\n", encoding="utf-8")
    plt.close(fig)
    return written


def caption_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(f"{path.stem}.caption.md")


def caption_markdown(image: Path, alt: str, relative_dir: str = "figures") -> str:
    """Image line, caption paragraph and caption link for a report that embeds ``image``."""
    image = Path(image)
    text = caption_path(image).read_text(encoding="utf-8").strip()
    return (f"![{alt}]({relative_dir}/{image.name})\n\n{text}\n"
            f"[Caption file]({relative_dir}/{caption_path(image).name}).")
