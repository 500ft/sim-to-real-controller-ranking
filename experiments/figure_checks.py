"""Assertions shared by the figure tests: clean canvas, and captions that match their files and docs."""
from pathlib import Path

import figure_style as fs

REPO_ROOT = Path(__file__).resolve().parents[1]


def squash(text: str) -> str:
    return " ".join(text.split())


class FigureChecks:
    """Mixin for unittest.TestCase."""

    def assert_clean_canvas(self, fig) -> None:
        stray = fs.printed_text(fig) - fs.allowed_text(fig)
        self.assertEqual(stray, set(), "canvas carries text outside axes, letters and legend")
        self.assertEqual(fs.audit(fig), [])

    def assert_caption(self, text: str, image: Path, docs) -> None:
        """Caption equals its committed file and appears, whitespace-normalized, in every doc under the image."""
        self.assertEqual(text, fs.caption_path(image).read_text(encoding="utf-8").strip())
        for doc in docs:
            body = (REPO_ROOT / doc).read_text(encoding="utf-8")
            self.assertIn(image.name, body, doc)
            self.assertIn(squash(text), squash(body), doc)
            self.assertIn(fs.caption_path(image).name, body, doc)


def capture(draw, *args, **kwargs) -> dict:
    """Run a draw_* function without writing files: {image name: (figure, caption, path)}."""
    built = {}

    def record(fig, path, caption, formats=("png",)):
        built[Path(path).name] = (fig, caption, Path(path))
        return [Path(path).with_suffix(f".{f}") for f in formats]

    original, fs.save = fs.save, record
    try:
        draw(*args, **kwargs)
    finally:
        fs.save = original
    return built


def close_all(built: dict) -> None:
    for fig, _, _ in built.values():
        fs.plt.close(fig)
