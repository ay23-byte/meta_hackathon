# Generated analysis artifacts

This directory is the **default output location** for both command-line tools.
Artifacts here are regenerated outputs, not source, and are gitignored so a CLI
run never dirties the working tree or looks like new scientific results.

## Original CLI (`analyze_experiment.py`)

```bash
python analyze_experiment.py                        # writes into results/
python analyze_experiment.py --output-dir outputs   # scratch alternative
```

- `analysis_results.json` - metrics, input SHA-256, software versions,
  cleaning policy, row counts and warnings
- `cleaned_and_fitted_data.csv` - retained rows with fitted values/residuals
- `voltage_current_fit.png` - measurements and fitted line
- `residuals.png` - residuals against current

## General CLI (`analyze_dataset.py`)

```bash
python analyze_dataset.py data/sample_voltage_current.csv \
  --x current_A --y voltage_V --output-dir results/general
```

Every file derives from **one** result schema (`result_schema.py`, v2.0):

- `results.json` - full result object (strict JSON, no NaN/Infinity)
- `cleaned_data.csv` - original columns plus `__numeric__` companions
- `statistics.csv` - one row per statistic, one column per measurement
- `fit_parameters.csv` / `fit_metrics.csv` - coefficients, errors and metrics
- `report.md` - deterministic Markdown report with clearly attributed AI
  sections when a report was generated
- `plots/*.html` - interactive Altair/Vega-Lite charts (CDN needed to view)
- `plots/*.png` - locally rendered Matplotlib versions of the same charts

The Streamlit apps (`app.py`, `general_app.py`) never write here; downloads are
generated in memory for each browser session.

### Agent audit artifacts

`python analyze_dataset.py <file.csv> --agent` adds an `agent/` subdirectory:

- `agent/agent_audit.json` - plan source/hash, validation decisions, events,
  retries, tool results, final conclusion and evidence refs
- `agent/agent_events.jsonl` - one JSON object per event
- `agent/agent_report.md` - Markdown report with a Mermaid timeline

`python run_agent_demo.py --case all --strict` writes the same three files per
case under `outputs/agent_demo/<case>/`. In `general_app.py`, ticking the agent
consent checkbox includes these files in the downloadable ZIP under `agent/`.

To reproduce the checked-in demo numbers (11 valid rows, slope ≈ 4.99091,
R² ≈ 0.999803, RMSE ≈ 0.0221565):

```bash
python analyze_experiment.py
python -m pytest -q
```

The bundled input is `data/sample_voltage_current.csv`; its provenance is not
independently verified. Synthetic datasets under `data/examples/` are
computer-generated and must not be used as evidence. See
`docs/SCIENTIFIC_VALIDATION.md` and `docs/GENERAL_PLATFORM.md`.
