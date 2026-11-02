"""Reusable presentation for the existing Streamlit scientific workflow.

Dynamic values are escaped. This module performs no calculations or provider calls.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

THEME = Path(__file__).resolve().parent / "ui" / "theme.css"

# Decorative, static icons. Navigation remains native links to existing sections.
ICONS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "upload": '<path d="M4 6h16v13H4zM4 10h16M9 6v13"/>',
    "clean": '<path d="M4 7h16M7 12h10M10 17h4"/><circle cx="8" cy="7" r="1.5"/><circle cx="15" cy="12" r="1.5"/>',
    "configure": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',
    "explore": '<path d="M4 19V5M4 19h16M7 15l4-4 3 2 5-7"/>',
    "fit": '<path d="M4 19V5M4 19h16M7 16c3-7 5-8 8-7s4-2 5-4"/>',
    "interpret": '<path d="M5 5h14v11H9l-4 3zM9 9h6M9 12h4"/>',
    "export": '<path d="M6 3h9l3 3v15H6zM15 3v4h4M9 12h6M9 16h6"/>',
}


def icon(name: str) -> str:
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            + ICONS[name] + '</svg>')


def apply_theme() -> None:
    st.markdown(f"<style>{THEME.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def navigation() -> None:
    """Section links keep all existing widgets and session state intact."""
    links = [
        ("overview", "Overview"), ("upload", "Data workspace"),
        ("clean", "Data cleaning"), ("configure", "Configure analysis"),
        ("explore", "Statistics & charts"), ("fit", "Models & predictions"),
        ("interpret", "AI research assistant"), ("export", "Reports & export"),
    ]
    items = "".join(f'<a href="#{anchor}"><span class="ll-nav-icon">{icon(anchor)}</span>{label}</a>'
                    for anchor, label in links)
    st.markdown('<div class="ll-brand"><div class="ll-logo" aria-hidden="true"><span>✳</span></div>'
                '<div><div class="ll-brand-name">LabLens <span>AI</span></div>'
                '<div class="ll-brand-sub">Scientific workspace</div></div></div>'
                '<div class="ll-nav-label">WORKSPACE <span> / 01</span></div>'
                f'<nav class="ll-nav" aria-label="Workspace sections">{items}</nav>'
                '<div class="ll-side-divider"></div><div class="ll-nav-label">SESSION &amp; PROVIDER</div>',
                unsafe_allow_html=True)


def anchor(name: str) -> None:
    st.markdown(f'<span id="{escape(name, quote=True)}" class="ll-section-anchor"></span>', unsafe_allow_html=True)


def hero() -> None:
    anchor("overview")
    st.markdown('''<div class="ll-topline"><div class="ll-breadcrumb">WORKSPACE <span>/</span> OVERVIEW</div>
        <span class="ll-top-tag"><i></i> SCIENTIFIC WORKSPACE</span></div>
      <section class="ll-hero"><div class="ll-hero-copy"><div class="ll-kicker"><span></span> YOUR RESEARCH, IN FOCUS</div>
        <h1>Welcome to <span>LabLens AI.</span></h1>
        <p>Transform experimental data into reliable scientific insights.</p>
        <div class="ll-actions"><a class="ll-primary" href="#upload" title="Open the upload section; current analysis is not reset">Start New Analysis <b>↗</b></a>
        <a class="ll-secondary" href="#explore">Explore Workspace <b>→</b></a></div>
        <div class="ll-hero-foot"><span>●</span> Local-first analysis <i></i> Evidence-led interpretation</div></div>
        <div class="ll-hero-art" aria-hidden="true"><div class="ll-orbit ll-orbit-one"></div><div class="ll-orbit ll-orbit-two"></div>
        <div class="ll-orbit ll-orbit-three"></div><div class="ll-art-center">✳</div><div class="ll-art-dot ll-art-dot-a"></div><div class="ll-art-dot ll-art-dot-b"></div>
        <div class="ll-art-caption">FROM DATA<br><b>TO DISCOVERY</b></div></div></section>''', unsafe_allow_html=True)


def overview_empty() -> None:
    """Shown if import or configuration stops before the computed overview exists."""
    st.markdown('''<div class="ll-dashboard-heading"><div><span>YOUR WORKSPACE</span><h2>Research overview</h2></div></div>
    <div class="ll-panel"><div class="ll-panel-head"><div><span class="ll-panel-eyebrow">GET STARTED</span>
    <h3>No analysis ready yet</h3></div><a href="#upload">Open data workspace ↗</a></div>
    <div class="ll-report-state"><span class="ll-dataset-icon">''' + icon("upload") + '''</span><div>
    <strong>Load and configure a dataset</strong><small>The overview appears after a dataset is parsed and the analysis is configured.</small></div></div>
    <div class="ll-panel-foot">Analysis history is not stored. AI requests are optional and require an explicit action.</div></div>''', unsafe_allow_html=True)


def overview(source: str, rows: int, columns: int, *, provider: str, provider_note: str,
             fit_note: str, report_note: str, source_note: str, pairs: int, model: str) -> None:
    """Use the current computed state; do not invent history or connection status."""
    source, provider, provider_note, fit_note, report_note, source_note, model = map(
        escape, (source, provider, provider_note, fit_note, report_note, source_note, model))
    st.markdown(f'''<div class="ll-dashboard-heading"><div><span>YOUR WORKSPACE</span><h2>Research overview</h2></div>
      <span class="ll-session-tag"><i></i> CURRENT SESSION</span></div>
    <div class="ll-overview" aria-label="Current workspace summary">
      <div class="ll-card"><div class="ll-card-top"><span>DATASET</span><span class="ll-card-icon">{icon("upload")}</span></div>
        <div class="ll-card-value">{rows:,} <small>rows</small></div><div class="ll-card-note">{columns:,} columns · {source_note}</div></div>
      <div class="ll-card"><div class="ll-card-top"><span>VALID PAIRS</span><span class="ll-card-icon">{icon("clean")}</span></div>
        <div class="ll-card-value">{pairs:,}</div><div class="ll-card-note">Current X / Y selection</div></div>
      <div class="ll-card"><div class="ll-card-top"><span>ANALYSIS</span><span class="ll-card-icon">{icon("fit")}</span></div>
        <div class="ll-card-value ll-card-value-text">{fit_note}</div><div class="ll-card-note">Model: {model}</div></div>
      <div class="ll-card"><div class="ll-card-top"><span>AI PROVIDER</span><span class="ll-card-icon">{icon("interpret")}</span></div>
        <div class="ll-card-value ll-card-value-text">{provider}</div><div class="ll-card-note">{provider_note}</div></div>
    </div>
    <div class="ll-dashboard-grid"><div class="ll-panel"><div class="ll-panel-head"><div><span class="ll-panel-eyebrow">YOUR DATA</span><h3>Current dataset</h3></div><a href="#upload">Open workspace ↗</a></div>
      <div class="ll-dataset-row"><span class="ll-dataset-icon">{icon("upload")}</span><div class="ll-dataset-name"><strong>{source}</strong><small>{source_note} · {rows:,} rows · {columns:,} columns</small></div><span class="ll-status">LOADED</span></div>
      <div class="ll-panel-foot">Only the current dataset is shown. Analysis history is not stored.</div></div>
    <div class="ll-panel"><div class="ll-panel-head"><div><span class="ll-panel-eyebrow">RESEARCH OUTPUT</span><h3>Latest report</h3></div><a href="#interpret">Open assistant ↗</a></div>
      <div class="ll-report-state"><span class="ll-dataset-icon">{icon("export")}</span><div><strong>Interpretation</strong><small>{report_note}</small></div></div>
      <div class="ll-panel-foot">AI text is a hypothesis, not experimental evidence.</div></div></div>
    <div class="ll-workflow"><div><span class="ll-panel-eyebrow">A GUIDED WORKFLOW</span><h3>Move from data to evidence</h3></div>
      <div class="ll-flow-steps"><a href="#upload"><b>01</b> Upload</a><span>→</span><a href="#clean"><b>02</b> Validate</a><span>→</span><a href="#explore"><b>03</b> Analyze</a><span>→</span><a href="#interpret"><b>04</b> Interpret</a><span>→</span><a href="#export"><b>05</b> Export</a></div></div>''', unsafe_allow_html=True)


def assistant_intro(provider: str, model: str) -> None:
    """A descriptive UI panel; it must not report unchecked live connectivity."""
    st.markdown(f'''<div class="ll-assistant"><div class="ll-assistant-avatar">✳</div>
    <div class="ll-assistant-body"><div class="ll-assistant-label">RESEARCH ASSISTANT <span> / </span> EVIDENCE-GROUNDED</div>
      <h3>Interpret your analysis, responsibly.</h3>
      <p>Ask a research question in Configure, then request an interpretation grounded in the current computed results. Review every claim and limitation.</p>
      <div class="ll-assistant-meta"><span>{escape(provider)}</span><span>{escape(model)}</span><span>Python calculations remain authoritative</span></div>
      <div class="ll-assistant-links"><a href="#configure">Set research question ↗</a><a href="#export">Report &amp; exports ↗</a></div>
    </div></div>''', unsafe_allow_html=True)
