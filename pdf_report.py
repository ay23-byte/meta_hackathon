"""Bounded, text-first PDF rendering of the existing deterministic report.

Figures are not embedded: existing PNG/HTML files are packaged separately in
ZIP/CLI artifacts. No external binaries, network or AI calls are used.
"""
from __future__ import annotations

import io
import textwrap

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

MAX_REPORT_CHARS = 200_000
MAX_PAGES = 80
LINES_PER_PAGE = 54


def render_report_pdf(markdown: str) -> bytes:
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
    if len(pages) > MAX_PAGES:
        raise ValueError("The report exceeds the PDF page limit; use the complete Markdown report.")
    buffer = io.BytesIO()
    with PdfPages(buffer, metadata={"Title": "LabLens AI research report", "Creator": "LabLens AI"}) as pdf:
        for page_no, page in enumerate(pages, 1):
            figure = Figure(figsize=(8.27, 11.69))
            figure.text(.07, .96, "LabLens AI — text report (figures packaged separately)",
                        fontsize=9, va="top", family="DejaVu Sans", parse_math=False)
            figure.text(.07, .93, "\n".join(page), fontsize=7.5, va="top",
                        family="DejaVu Sans Mono", linespacing=1.15, parse_math=False)
            figure.text(.92, .035, f"{page_no} / {len(pages)}", fontsize=8, ha="right")
            pdf.savefig(figure)
    return buffer.getvalue()
