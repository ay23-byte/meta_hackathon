"""Presentation helpers for the existing Streamlit scientific workflow.

Dynamic values are escaped. No credentials, analysis calculations or provider
calls belong in this module.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

THEME = Path(__file__).resolve().parent / "ui" / "theme.css"


def apply_theme() -> None:
    st.markdown(f"<style>{THEME.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def navigation() -> None:
    """In-page links preserve all native widgets and their session state."""
    links = [
        ("overview", "01", "Overview"), ("upload", "02", "Data workspace"),
        ("clean", "03", "Validation & cleaning"), ("configure", "04", "Configure analysis"),
        ("explore", "05", "Statistics & charts"), ("fit", "06", "Models & predictions"),
        ("interpret", "07", "AI research assistant"), ("export", "08", "Reports & export"),
    ]
    items = "".join(f'<a href="#{anchor}"><span class="ll-nav-icon">{index}</span>{label}</a>'
                    for anchor, index, label in links)
    st.markdown('<div class="ll-brand"><div class="ll-logo" aria-hidden="true">L</div>'
                '<div><div class="ll-brand-name">LabLens AI</div>'
                '<div class="ll-brand-sub">Research workspace</div></div></div>'
                '<div class="ll-nav-label">Workspace</div>'
                f'<nav class="ll-nav" aria-label="Workspace sections">{items}</nav>', unsafe_allow_html=True)


def anchor(name: str) -> None:
    """Only called with static internal section identifiers."""
    st.markdown(f'<span id="{escape(name, quote=True)}" class="ll-section-anchor"></span>', unsafe_allow_html=True)


def hero() -> None:
    anchor("overview")
    st.markdown('<div class="ll-breadcrumb">Workspace &nbsp;/&nbsp; Overview</div>'
                '<section class="ll-hero"><div class="ll-kicker">Scientific analysis workspace</div>'
                '<h1>From data to defensible insights.</h1>'
                '<p>Explore your experiment, understand the numbers, and build an evidence-grounded '
                'report in one reproducible workspace.</p>'
                '<div class="ll-actions"><a class="ll-primary" href="#upload">Start an analysis &nbsp; →</a>'
                '<a class="ll-secondary" href="#interpret">Explore AI assistant</a></div></section>',
                unsafe_allow_html=True)


def overview(source: str, rows: int, columns: int, *, provider: str, provider_note: str,
             fit_note: str, report_note: str, source_note: str) -> None:
    """Render current analysis facts, not fabricated history or connection status."""
    source, provider, provider_note, fit_note, report_note, source_note = map(
        escape, (source, provider, provider_note, fit_note, report_note, source_note))
    st.markdown(f'''<div class="ll-overview" aria-label="Current workspace summary">
      <div class="ll-card"><div class="ll-card-label">Current dataset</div>
        <div class="ll-card-value">{source}</div><div class="ll-card-note">{rows:,} rows · {columns:,} columns · {source_note}</div></div>
      <div class="ll-card"><div class="ll-card-label">Analysis status</div>
        <div class="ll-card-value">{fit_note}</div><div class="ll-card-note">{report_note}</div></div>
      <div class="ll-card"><div class="ll-card-label">AI provider</div>
        <div class="ll-card-value">{provider}</div><div class="ll-card-note">{provider_note}</div></div>
    </div>''', unsafe_allow_html=True)
