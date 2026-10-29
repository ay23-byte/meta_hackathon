"""Bounded, text-first PDF rendering of the existing deterministic report.

Selected locally generated PNG figures can be embedded as individual pages;
all original PNG/HTML files remain separately packaged. No network or AI calls.
"""
from __future__ import annotations

import io
import textwrap

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from PIL import Image, UnidentifiedImageError

MAX_REPORT_CHARS = 200_000
MAX_PAGES = 80
LINES_PER_PAGE = 54
MAX_FIGURES = 12
MAX_FIGURE_BYTES = 10_000_000
MAX_FIGURE_PIXELS = 16_000_000


def render_report_pdf(markdown: str, *, figures: dict[str, bytes] | None = None) -> bytes:
    """Render the report as printable literal text, refusing oversized output."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("A nonempty report is required for PDF export.")
    if len(markdown) > MAX_REPORT_CHARS:
        raise ValueError("The report is too large for PDF export; use the complete Markdown report.")
    lines = []
    for line in markdown.splitlines():
        lines.extend(textwrap.wrap(line, width=105, replace_whitespace=False,
                                   drop_whitespace=True, break_long_words=True) or [""])
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    figures = figures or {}
    if len(figures) > MAX_FIGURES or len(pages) + len(figures) > MAX_PAGES:
        raise ValueError("The report exceeds the PDF page or figure limit; use the complete Markdown report and separate figures.")
    if any(not isinstance(payload, bytes) or len(payload) > MAX_FIGURE_BYTES for payload in figures.values()):
        raise ValueError("A figure is invalid or too large for PDF export; use the separate figures.")
    buffer = io.BytesIO()
    with PdfPages(buffer, metadata={"Title": "LabLens AI research report", "Creator": "LabLens AI"}) as pdf:
        total_pages = len(pages) + len(figures)
        for page_no, page in enumerate(pages, 1):
            figure = Figure(figsize=(8.27, 11.69))
            figure.text(.07, .96, "LabLens AI — text report (figures packaged separately)",
                        fontsize=9, va="top", family="DejaVu Sans", parse_math=False)
            figure.text(.07, .93, "\n".join(page), fontsize=7.5, va="top",
                        family="DejaVu Sans Mono", linespacing=1.15, parse_math=False)
            figure.text(.92, .035, f"{page_no} / {total_pages}", fontsize=8, ha="right")
            pdf.savefig(figure)
        for page_no, (name, payload) in enumerate(figures.items(), len(pages) + 1):
            try:
                with Image.open(io.BytesIO(payload)) as image:
                    if image.format != "PNG" or image.width * image.height > MAX_FIGURE_PIXELS:
                        raise ValueError("A figure is not a supported bounded PNG; use the separate figures.")
                    image.load()
                    pixels = image.convert("RGBA")
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("A figure could not be opened for PDF export; use the separate figures.") from exc
            figure = Figure(figsize=(8.27, 11.69))
            figure.text(.07, .96, "Generated figure (also packaged separately)", fontsize=10, va="top")
            figure.text(.07, .92, str(name)[:120], fontsize=8, va="top", parse_math=False)
            axis = figure.add_axes([.07, .13, .86, .74])
            axis.imshow(pixels)
            axis.axis("off")
            figure.text(.92, .035, f"{page_no} / {total_pages}", fontsize=8, ha="right")
            pdf.savefig(figure)
    return buffer.getvalue()
