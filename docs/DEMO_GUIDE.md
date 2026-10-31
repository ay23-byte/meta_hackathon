# Local Ollama demo (Windows)

1. Install Python 3.11/3.12 and Ollama separately. In PowerShell from the repo:
   `py -3.11 -m venv .venv`, then `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
2. Start Ollama locally (`ollama serve` if not already running); explicitly run
   `ollama pull llama3.2:3b` once (or use the existing `llama3.2:1b`). This downloads a large model; LabLens does
   not pull it or require an API key. Run `ollama list` to inspect availability.
3. Start `.\.venv\Scripts\python.exe -m streamlit run general_app.py` on the
   same machine. Load the bundled synthetic `linear_calibration_demo.csv`.
   Show cleaning, choose X `time_s` and Y `signal_mV`, inspect fit/residuals and
   evidence. Expected 12 valid pairs, slope 2.5 and intercept 0.1 are synthetic.
4. Open **Meta Llama 3.2 — Local Ollama (optional)**, enable controls, select 3B,
   check status, enter an optional question, and request a local report once.
   If it fails validation, show the error and continue with deterministic results;
   do not show the offline mock as Llama. Local Llama output is unverified.
5. Inspect the evidence panel and download the ZIP, including report and
   manifest; PDF is optional. Check the report for sensitive metadata before
   sharing. Experiment templates are guidance, not auto-validated physics.

This repository's automated provider tests use stubs. An actual Ollama/model
round trip on the user's machine has not been verified in this sandbox.

### If the local model's report fails validation

The 1B model may return missing, duplicate, overlong, or invalid sections or
claim evidence IDs. Existing computed results and exports remain available.
Under **AI report sections (optional)**, select a smaller set of sections
(e.g. Executive Summary, Quantitative Results, Uncertainty and Limitations),
then request the local report again. This makes the report shorter; it does
not guarantee a valid answer. Avoid sharing raw provider responses that may
contain private experiment information.

The local Ollama request now passes a JSON schema to constrain generation and
still runs the existing strict validator and numeric guard. Automated tests use
stubs; this change has not been verified against a real Ollama service here.
