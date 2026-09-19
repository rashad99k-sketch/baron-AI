# BARON Test Report — 2026-09-18

## Fresh verification
- `python -m compileall -q .` — PASS
- `python verify_project.py` — PASS
- `python tools/paper_runtime_smoke.py` — PASS
- `python tools/dashboard_runtime_check.py` — ENVIRONMENT BLOCKED: Flask and ccxt unavailable; pip installation could not reach package index because DNS/network access is unavailable.

## Baseline test evidence
The 103 pre-existing test modules in the current audited baseline were executed individually before this continuation work: 832 tests counted as passed, with the existing documented skip(s). The combined pytest process is not treated as a release PASS because it does not complete deterministically inside the available execution window.

## New/changed tests
- `tests/test_market_regime_engine.py` — 8 passed
- `tests/test_institutional_entry_market_state.py` — 2 passed
- `tests/test_market_state_trade_management.py` — 4 passed
- `tests/test_bingx_execution_truth_regressions.py` — 4 passed
- `tests/test_dashboard_market_state.py` — 2 passed

New tests: 20 passed.

Additional fresh regressions passed individually during this continuation:
- institutional entry v2: 7 passed
- institutional entry integration: 3 passed
- native protection live safety: 21 passed
- dashboard contracts: 5 passed
- dashboard schema: 7 passed
- profit engine phase3: 31 passed

## Combined-suite status
A fresh combined pytest run did not complete within the execution transport window. Because the release specification explicitly forbids converting an incomplete/timeout run into PASS, the overall release gate remains BLOCKED.

## Classification
- Assertion failure: none observed in the fresh targeted/new tests.
- Import failure: none after source changes; compile/verify passed.
- Process crash: none observed in targeted validation.
- Timeout: combined/full suite incomplete/timeout.
- Resource/environment: dashboard runtime blocked by missing Flask/ccxt and unavailable package network.

## Live-money status
No real-money BingX trade was executed.
