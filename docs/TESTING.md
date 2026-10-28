# Testing

From the repository root, install the project's development dependencies into
your chosen virtual environment (`python -m pip install -r requirements-dev.txt`).
Run:

```bash
python -m pytest -q
ruff check .
python -m compileall -q -x '\.venv|\.git' .
python -m pytest -q tests/test_theory_engine.py tests/test_research_assistant.py
python run_agent_demo.py --case all --strict --output-dir outputs/agent_demo
```

Ordinary tests use mocked provider responses; live tests are skipped unless
explicitly opted in. To deliberately perform billable live tests, configure a
key privately and run `python -m pytest --run-live -m live -v`. A skipped test
is not a successful provider round trip. See `PROVIDER_INTEGRATION.md` and
`IMPLEMENTATION_PROGRESS.md` for limitations and measured results. Do not
print credentials or use confidential experimental data in test fixtures.
