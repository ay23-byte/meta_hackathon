# Synthetic example datasets

All files here are **computer-generated** for testing and demonstration. They are
not real experimental measurements and must not be used to support a scientific
claim.

| File | Delimiter / encoding | Demonstrates |
| --- | --- | --- |
| `synthetic_calibration.csv` | comma / UTF-8 | Linear calibration, user-supplied 1-sigma uncertainty column (`abs_sigma`), group column (`batch`), weighted fitting. |
| `synthetic_growth.csv` | comma / UTF-8 | Exponential growth with an additive baseline, numeric and datetime time columns, group column, model comparison. |
| `synthetic_messy_semicolon.csv` | semicolon / cp1252 | Encoding fallback, invalid text, missing values and `inf` tokens, role overrides. |
| `synthetic_quadratic.csv` | comma / UTF-8 | Curved relationship where a straight line is a bad model; polynomial fit and residual diagnostics. |

**Known limitation:** numeric values must use a dot (`.`) as the decimal
separator. Comma decimals are interpreted as text and reported as invalid,
not silently converted. Locale-aware numeric parsing is not implemented.

The original `data/sample_voltage_current.csv` remains available for the
legacy voltage-current sample workflow.
