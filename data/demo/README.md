# Synthetic live-demo dataset

`linear_calibration_demo.csv` is **computer-generated**, not experimental data.
It exists solely to make the hackathon demonstration reproducible offline.

Columns:

- `time_s` — synthetic independent variable (seconds).
- `signal_mV` — synthetic response (millivolts), defined as
  `signal_mV = 2.5 * time_s + 0.1` for the 12 valid rows.
- `sigma_mV` — synthetic 1-sigma uncertainty, constant `0.1` mV.
- `batch` — synthetic categorical labels `A`/`B`.

Three deliberately messy rows (rows 13–15 in the file) contain `NA`, `inf`
and `oops` in the response column. They are **retained** in
`cleaned_data.csv` but excluded from fitting by pairwise completeness.

Verified with:

```bash
python analyze_dataset.py data/demo/linear_calibration_demo.csv \
  --x time_s --y signal_mV --model linear \
  --output-dir outputs/demo
```

Expected deterministic results (Python 3.11, this repository):

- source rows: **15**
- rows retained in cleaned CSV: **15**
- rows excluded from fitting: **3**
- observations used: **12**
- slope: **2.5 mV/s**, intercept: **0.1 mV**
- R²: **1.0**, RMSE: approximately **1.65e-16 mV** (floating-point noise)

These numbers describe the synthetic file only. They are not a scientific
discovery and must not be presented as measurements from a real instrument.

## Optional synthetic Ohmic comparison

`synthetic_ohmic_a.csv` and `synthetic_ohmic_b.csv` are hand-constructed
synthetic examples, **not physical measurements or independent replications**.
They use `current_A` and `voltage_V`, with small illustrative deviations from
approximately 10 V/A and 10.25 V/A respectively. Use them only to demonstrate
user-confirmed mappings, model diagnostics and descriptive comparison. A
user-supplied 10 ohm theoretical curve is a demonstration assumption; this
exercise does not validate Ohm's law or establish statistical significance.
