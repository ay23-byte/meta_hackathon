# LabLens AI — submission handoff (29 October 2026)

## Technical status

**Offline-first prototype:** supported by local offline tests and a synthetic
rehearsal, subject to human demo review. **Live Meta integration:** not verified
in this environment. No authentic Muse Spark result has been recorded here;
mock text is explicitly not AI. An integration requiring a genuine live model
is blocked until both connectivity and the structured-report tests actually pass
with the user's authorized account, model entitlement and network.

- Local Linux/CPython 3.11 suite: 611 passed, 2 skipped. Linux Ruff,
  compilation, `pip check`, app HTTP health, seven agent cases and synthetic
  CLI PDF/manifest verification passed. Prior PR #19 Linux/Windows CI passed;
  this new increment was not run locally on Windows.
- PDF contains text-first report pages and embedded generated PNG figure pages;
  PNGs are also separately packaged. Layout/accessibility and Unicode remain
  incompletely assessed.
- The evidence guard checks limited explicit values and ID membership, not
  semantic entailment, general units, scientific correctness, or citations.
- No literature search or source-support verification ran. Ohmic comparison is
  conditional and descriptive. Two-dataset comparison is not a general
  experiment manager; Welch inference requires independent observations.

## Before submitting

1. Locally configure `BASETEN_API_KEY` privately, with `BASETEN_MODEL` only if
   your provider/account specifies another supported identifier. Never share a
   key in chat, screenshots, reports or source. Live requests may incur charges.
2. Run `python test_baseten.py` for one small connectivity call, then
   `python -m pytest --run-live -m live -v` for the structured computed-data
   workflow. Both must succeed; a skip or provider error is not success.
   Sandbox access to Baseten is restricted, so this must run somewhere with
   provider network access. Keep confidential data out of provider context.
3. Run the Windows commands below and rehearse the synthetic demo in
   `docs/LIVE_DEMO_GUIDE.md`. Record a demo only after confirming portal rules.
4. Confirm acceptance, eligibility, track, team, form fields, repo visibility,
   demo-video requirements, attribution/licenses, and current deadline in the
   official participant portal. `docs/HACKATHON_RULES.md` records what was
   visible on 26 Oct; official event page previously listed 4 November 2026,
   9 PM ET. Rules and portal are authoritative and may change.
5. Review source, dependency notices and Git history for secrets with suitable
   scanners; our narrow pattern scan is not exhaustive. Rotate any exposed key
   through the provider, without reproducing it.

## Windows PowerShell (repository root)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q -x '\.venv|\.git' .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run_agent_demo.py --case all --strict --output-dir outputs\agent_demo
.\.venv\Scripts\python.exe analyze_dataset.py data\demo\linear_calibration_demo.csv --x time_s --y signal_mV --model linear --output-dir outputs\demo --ai-mock --pdf
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

Choose scratch output directories that do not contain user data. If activation
is desired but blocked by PowerShell policy, use the Python executable directly
as above. These commands are provided for local verification, not claimed to have
run on Windows in this increment.
