# Generated analysis artifacts

This directory is the **default output location** for the command-line
analysis:

```bash
python analyze_experiment.py                       # writes into results/
python analyze_experiment.py --output-dir outputs # scratch alternative
```

Files produced here are regenerated outputs, not source:

- `analysis_results.json` — metrics, input SHA-256, software versions,
  cleaning policy, row counts, and warnings
- `cleaned_and_fitted_data.csv` — retained rows with fitted values/residuals
- `voltage_current_fit.png` — measurements and fitted line
- `residuals.png` — residuals against current

They are gitignored on purpose: a CLI run must not dirty the working tree or
make a commit look like new scientific results. The dashboard never writes
here — its Markdown/CSV/JSON downloads are generated in memory.

To reproduce the checked-in demo numbers (11 valid rows, slope ≈ 4.99091,
R² ≈ 0.999803, RMSE ≈ 0.0221565):

```bash
python analyze_experiment.py
python -m pytest -q
```

The bundled input is `data/sample_voltage_current.csv`; its provenance is not
independently verified. See `docs/SCIENTIFIC_VALIDATION.md` for definitions
and `docs/ARCHITECTURE.md` for the data flow.
