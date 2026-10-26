# LabLens AI project audit

Date: 26 October 2026. Branch: `arena/9e30a63a-meta-hackathon`.

## Scope and baseline

Audit covers `app.py`, `analysis_core.py`, `ask_muse.py`,
`analyze_experiment.py`, `test_muse.py`, `tests/`, packaging, CI, and all
`docs/`. Baseline before any work: `python -m pytest -v` → **22 passed,
1 skipped**. First hardening pass: **26 passed, 1 skipped**. Final state:
**112 passed, 2 skipped**, 98% statement coverage, `ruff check .` clean.

The two skips are the opt-in live Muse Spark tests (`-m live`), which need
`BASETEN_API_KEY`. No key is present in this environment.

## Architecture and data flow

CSV upload or bundled sample (bounded to 5 MiB / 200,000 rows) → pandas
reader with explicit parse errors → alias suggestion plus user-confirmed
columns and sanitized units → `analysis_core.prepare_analysis_data`
(positional numeric conversion, invalid-pair exclusion, source-row
tracking) → `analysis_core.analyze_linear` (centred OLS `V = mI + b`) →
metrics, plots, hypothetical explorer → optional user-triggered Muse Spark
interpretation via `ask_muse.generate_interpretation` → strict schema
validation and SHA-256 context binding → in-memory Markdown/CSV/JSON
exports. The CLI shares the same numerical core. See
`docs/ARCHITECTURE.md`.

## Findings and fixes

### Correctness and numerical reliability

| Severity | Issue | Fix / verification |
| --- | --- | --- |
| High | `np.polyfit` returned an intercept near −79 for `x ≈ 1e9`, `y = 5x+2` — a silently wrong scientific result | Replaced with centred normal equations; regression test asserts slope 5, intercept 2. Sample results unchanged to ~1e-16. Independent `np.linalg.lstsq` oracle agrees to ~1e-12 |
| High | Non-default DataFrame index could misalign paired rows on some pandas versions | Convert columns positionally to NumPy before constructing the result frame; test with a string index |
| Medium | Overflow / non-finite fit results could escape as JSON | `np.errstate` guards plus finite checks raise `ValueError`; strict `allow_nan=False` serialization |
| Medium | Constant voltage and constant current edge cases | Explicitly tested; R² is `None`, not 0, when undefined |
| Medium | Duplicate column names silently dropped (DataFrame API) | Explicit `ValueError`; CSV duplicates are mangled by pandas before reaching the core (documented) |

### AI provider integration

| Severity | Issue | Fix / verification |
| --- | --- | --- |
| High | Request used `system` role and `temperature=0.2`, contrary to Meta's documented guidance for Muse Spark (prefer `developer`, leave sampling at tuned default 1.0) | Switched to `developer`, removed the temperature override, used `max_completion_tokens` to budget reasoning tokens |
| High | No structured-output request; the model had to produce strict JSON from prompt instructions alone | Requests `response_format={"type": "json_object"}`; on HTTP 400 retries once with a conservative request shape (no JSON mode, legacy `max_tokens`) |
| High | Live structured-report workflow could not be verified without a key | 29 fake-client contract tests cover request shape, parsing, validation, sanitization, error mapping, fallback, truncation, and reasoning-only output. Clearly labeled as offline, not live |
| Medium | `reasoning_content` could be mistaken for a report | Never used as a substitute; reasoning-only responses raise a specific error |
| Medium | Truncated or oversized responses produced vague JSON errors | `finish_reason == "length"` and raw-size checks produce specific errors |
| Medium | Potential model-ID mismatch for hackathon accounts | `BASETEN_MODEL` override; default stays the officially documented `meta-models/muse-spark-open` |
| Medium | Context errors were misreported as provider failures | Prompt built before the provider `try`; oversized/unserializable context raises `ValueError` with no network call |
| Medium | Extra provider keys could reach UI/session/exports | `validate_report` returns a sanitized dict; the app's validator delegates to it (one schema) |
| Low | HTTP status could be a non-integer object interpolated into messages | `_http_status` coerces to int; generic messages never include raw exception text |

### Security and input handling

| Severity | Issue | Fix / verification |
| --- | --- | --- |
| High | User-supplied unit text became a CSV column header, allowing spreadsheet formula injection | `safe_unit` strips dangerous characters and prefixes leading `= + - @` with `'`; tested |
| Medium | Unbounded AI context and report sizes | Hard caps on context, prompt, raw response, section words/chars, claim fields, claim count; tested |
| Medium | Unbounded CSV upload and row count | 5 MiB / 200,000-row limits with clear UI errors; AppTest verified |
| Medium | Unbounded explorer candidates / text fields | 50 candidates max, `max_chars` on all text inputs, finite-value checks |
| Medium | AI output rendered as Markdown could inject links or images | Section content rendered as plain text; titles come from a fixed whitelist |
| Medium | Untrusted filenames/questions could break the Markdown report | `md_inline` collapses newlines and escapes backticks/pipes |
| Low | Generated CLI artifacts were tracked in Git and would be overwritten by a run | Untracked and gitignored; `results/README.md` documents regeneration |

### Reproducibility, packaging, CI

| Severity | Issue | Fix / verification |
| --- | --- | --- |
| Medium | `requirements.txt` had only lower bounds while the tested SDK was openai 3.x | Bounded ranges aligned to the tested versions; `requirements.lock.txt` records exact pins |
| Medium | CLI record lacked the input fingerprint and software versions present in the dashboard | Added SHA-256, versions, cleaning policy, warnings, row counts, method; CLI artifact test verifies both |
| Medium | `matplotlib` backend not forced headless in CLI | `matplotlib.use("Agg")` before pyplot import |
| Medium | No lint or coverage gate | `ruff.toml` + `requirements-dev.txt`; `ruff check .` clean, 98% coverage |
| Medium | No CI | `.github/workflows/ci.yml` for Linux + Windows, Python 3.11/3.12, running lint + offline tests + coverage. **Not executed in this environment** |
| Low | Documentation described malformed JSON as falling back to model text | Corrected: malformed JSON is rejected outright |
| Low | Official hackathon rules were unverified | Verified judging weights, deadline, eligibility, themes, credits and submission portal from the official event page and Official Rules; see `docs/HACKATHON_RULES.md` |

## Measured results

| Gate | Result |
| --- | --- |
| `python -m pytest -q` | 112 passed, 2 skipped |
| Coverage (4 application modules) | 98% statements (615 statements, 12 uncovered defensive branches) |
| `ruff check .` | All checks passed |
| `python -m compileall -q ...` | clean |
| Streamlit AppTest | 20 UI tests pass; real script renders with no exceptions |
| Streamlit server smoke test | starts and returns HTTP 200 |
| Live Muse Spark | **not verified** — no key |

Sample dataset (`data/sample_voltage_current.csv`, 11 valid rows):
slope 4.9909090909 V/A, intercept 0.00545454545 V, R² 0.9998029592,
RMSE 0.0221564684 V. Provenance not independently verified.

## Remaining / unresolved

1. **Live Muse Spark round-trip is unverified.** No `BASETEN_API_KEY` here.
   Run `python -m pytest -m live -v` with a real key before the demo. Do not
   present offline fake-client results as live verification.
2. **GitHub Actions has not run here.** The workflow is standard config;
   confirm both OS jobs pass after pushing.
3. **Demo video and submission are participant tasks.** See
   `docs/DEMO_SCRIPT.md` and `docs/HACKATHON_RULES.md`.
4. **Eligibility and acceptance** must be confirmed in the participant
   portal; the rules can be modified by the organizers.
5. **Scientific scope**: unweighted straight-line fit only. No confidence
   intervals, parameter standard errors, instrument uncertainty, weighting,
   outlier removal, or provenance verification. R² is never presented as
   proof of causation.
6. **Uncovered branches** (12 statements) are defensive guards (non-finite
   fit output, missing sample file, unreachable validation fallbacks, and
   the CLI `__main__` line) — not untested features.

## Quality assessment

Against the original 9.5/10 target: correctness, test depth, security,
reproducibility, documentation, and hackathon alignment are now verified
with concrete numbers (98% coverage, lint-clean, 112 offline tests,
official rules checked). The remaining risk is almost entirely external:
a live provider round-trip, a CI run on GitHub, and the recorded demo and
submission — none of which can be completed from this environment. On the
engineering criteria that can be measured here, the project meets the
9.5/10 bar; do not claim end-to-end live AI verification until item 1 is
completed.
