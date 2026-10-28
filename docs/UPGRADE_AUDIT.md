# Upgrade audit — 28 October 2026

## Baseline and architecture

Checkout: `arena/efe2e941-meta-hackathon`, based on `708198a`; clean before this work. Linux CPython 3.11.2, Streamlit 1.66.1, pandas 3.1.0, NumPy 2.4.6, SciPy 1.17.1, OpenAI SDK 3.40.0. `ruff check .`: pass; `python -m pytest -q`: **455 passed, 2 skipped** (opt-in live tests). The historical 444-test count predates PR #10.

`general_app.py` orchestrates CSV upload, `data_io`, `column_inference`, `cleaning`, `statistics_core`, `fitting_core`, `domain_modules`, `visualization_core`, `result_schema` and exports. `research_assistant.py` already provides bounded, explicitly user-confirmed Ohmic notes and reliability cautions; its optional research field participates in the AI context fingerprint but is not automatically transmitted. `result_schema` produces JSON, CSV, Markdown and ZIP members. `analyze_experiment.py` and `app.py` preserve a separate legacy voltage/current workflow. The bounded allowlisted agent and its consent remain separate from interpretation.

`provider_config.py` loads environment/project `.env` without environment mutation; `ask_muse.py` uses Baseten's OpenAI-compatible endpoint and configured Muse Spark model, bounded timeout/retries and structured validation. A key alone does not verify a response. Reasoning-only output is rejected; mock and live provenance remain separate. No live credentials/provider round trip was verified here. Normal tests mock provider interactions and live tests are opt-in.

## Prioritized implementation plan

1. Extend the existing opt-in context and offline Ohmic teaching notes with a structured, conditional chapter, explicit symbol and unit definitions, derivation, sample fit linkage, and completeness limitations. Keep raw computed results authoritative and avoid domain inference from column names.
2. Integrate the same chapter into UI and existing Markdown/JSON/ZIP exports, escaping untrusted input and preserving context-sensitive invalidation. Add analytical, unit-conversion, incompatible/missing context, export and Streamlit regression tests.
3. Re-run full suite, offline demo, lint, compilation and HTTP smoke; document remaining work and unknowns.

## Missing capabilities and risks

The existing UI is not a general textbook/literature platform: no verified external literature retrieval or claim-level citations, PDF ingestion/OCR, symbolic equation parser, grounded interactive research chat, multi-experiment comparisons, or full research report/PDF. Arbitrary scientific mechanisms, apparatus, measurements and citations must not be invented. A checked box expresses a user assumption, not experimental validation. A high R² and unit conversion do not prove an Ohmic law or assess calibration. Scientific equations and generated prose require human review. Research context can contain sensitive user input and is included in exports when opted in; do not put credentials there.

## Dependencies and external blockers

This increment reuses installed NumPy, SciPy and Streamlit; no new dependencies. Local deterministic explanations and tests require no key or network. Genuine Muse Spark requests need separately configured credentials and explicit user action. Literature APIs and journal sites are outside this sandbox's permitted outbound hosts; no literature verification, PDF/OCR, or live provider validation will be claimed. Future phases require service-specific permissions, privacy design, robust source provenance, accessible full text and independent scientific validation.
