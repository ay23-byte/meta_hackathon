# LabLens AI — Hackathon submission checklist

This checklist maps the project's verified features to the acceptance
criteria and common hackathon judging criteria. Update it as work
progresses; never mark an item complete unless it has been tested.

## Acceptance criteria (from project plan)

- [ ] The app imports and starts successfully (`import app`, `streamlit run app.py`)
- [ ] Sample data can be loaded (bundled `data/sample_voltage_current.csv`)
- [ ] Invalid data is handled transparently (counts of excluded rows shown)
- [ ] Scientific calculations are deterministic and tested (`pytest`)
- [ ] Graphs and metrics match the underlying analysis
- [ ] AI generation handles missing credentials and provider errors
- [ ] Empty and malformed model responses are rejected
- [ ] Valid reports satisfy the application's schema (8 required sections)
- [ ] Reports correspond to the currently selected dataset (context hash)
- [ ] Exports are consistent with the displayed results (JSON/CSV/Markdown)
- [ ] No secret is exposed in source control, UI, logs, or exports
- [ ] The standard test suite passes (`python -m pytest -v`)
- [ ] The live API status is reported honestly (optional, key-dependent)
- [ ] Documentation matches actual behavior
- [ ] The demo script can be executed with the existing project
- [ ] The submission checklist is complete or lists outstanding items

## Environment and setup

- [ ] `requirements.txt` lists small, justified dependencies
- [ ] `.env.example` present with placeholders only (no real key)
- [ ] `.env` excluded from version control (`.gitignore`)
- [ ] Windows setup steps documented in `README.md`
- [ ] Virtual environment or Conda setup documented

## Deterministic analysis (verified by tests)

- [ ] CSV upload and measurement-column selection
- [ ] Numeric cleaning with excluded-row counts
- [ ] Duplicate column names rejected
- [ ] Linear regression `V = mI + b`: slope, intercept, R², RMSE
- [ ] Observed-versus-fitted plot and residual plot
- [ ] Hypothetical measurement explorer with extrapolation flags
- [ ] Source row correspondence preserved
- [ ] Constant current rejected; undefined R² handled

## Muse Spark AI integration

- [ ] Optional interpretation gated on explicit button press
- [ ] API key never printed, logged, or exported
- [ ] Missing key → clear warning, app remains usable
- [ ] Provider errors mapped to actionable, secret-free messages
- [ ] Empty/malformed model output rejected, not treated as success
- [ ] Structured report validated against the required schema
- [ ] AI claims labeled as not independently verified

## Reproducibility and exports

- [ ] Markdown report download
- [ ] Cleaned data CSV download
- [ ] Analysis record JSON download
- [ ] Source filename and SHA-256 fingerprint recorded
- [ ] Original/cleaned row counts and cleaning rules recorded
- [ ] Software versions recorded in the analysis record
- [ ] AI provider/model and report-generation status recorded

## Documentation

- [ ] `README.md` — purpose, workflow, setup, tests, limitations
- [ ] `docs/ARCHITECTURE.md` — matches actual data flow
- [ ] `docs/SCIENTIFIC_VALIDATION.md` — math definitions and limits
- [ ] `docs/DEMO_SCRIPT.md` — 2–3 minute truthful demo sequence
- [ ] `docs/HACKATHON_CHECKLIST.md` — this file
- [ ] `PROJECT_AUDIT.md` — actual findings, severity, fixes, unresolved items

## Demo readiness

- [ ] Demo script can run with bundled sample data
- [ ] Fallback path prepared when the API is unavailable
- [ ] No mock response presented as a live API result
- [ ] No API key shown during the demo or in recordings

## Notes / outstanding items

- Live Muse Spark end-to-end verification requires a real
  `BASETEN_API_KEY` and network access; it is intentionally skipped in
  the default test suite when credentials are absent.
