# BARON Final Validation — 2026-09-16

## Root cause fixed
The Windows launcher executed `tools/run_isolated_tests.py` without guaranteeing that the development dependency `pytest` existed in the active `.venv`. Because runtime and development requirements were intentionally separated, the launcher reached the test phase and every test wrapper failed with `ModuleNotFoundError: No module named 'pytest'`.

## Corrective changes
- `run_windows.bat` now invokes `python tools\\bootstrap_dependencies.py --dev`.
- `bootstrap_dependencies.py` now supports `--dev` and installs/verifies `requirements-dev.txt` only when the release gate is requested.
- Development dependency recovery uses the same bounded retry/clean-cache/per-package strategy as runtime dependencies.
- The bootstrap handles the case where runtime dependencies are already present and still performs the requested dev bootstrap.
- `run_isolated_tests.py` now fails fast with an explicit release-gate message if pytest is missing instead of launching 91 doomed child processes.

## Validation
- `python verify_project.py` — PASS
- `python tools/paper_runtime_smoke.py` — PASS
- All 91 test modules executed in 5 deterministic batches — PASS
- Total tests passed: **789 passed**
- Batch results: 174 + 113 + 176 + 259 + 67 = 789
- No test failures
- No test timeouts
- `test_profit_engine_phase3.py` — PASS (included in batch 4)
- Dashboard contract/import/schema suites — PASS (included in batch 1)
- Forecast evidence suite — PASS (included in batch 2)
- Institutional/OB/VPA suites — PASS
- Six-slot/portfolio/news separation suites — PASS
- Unified trade authority / registry / TP1-TP2 canonical suites — PASS

## Runtime boundary
No live BingX order was submitted. External-network dependency installation cannot be reproduced inside this offline validation environment. The Windows bootstrap has therefore been tested structurally, while actual PyPI access remains environment-dependent.
