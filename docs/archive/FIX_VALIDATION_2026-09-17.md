# BARON — Release-Candidate Fix Validation — 2026-09-17

## Scope
This report covers the surgical fixes applied after the release-candidate test output showed 4 problematic test files and 7 concrete assertions failing inside `test_runtime_repairs.py`.

## Root causes found
1. `NewsAssessment.freshness_state` defaulted to `STALE` even when an in-memory assessment had no freshness evidence. That caused all side-aware news assertions to return `STALE`.
2. `NewsAssessment(available=False)` carries `NO_DATA`, while the side-level decision contract historically expects `NEWS_UNAVAILABLE`. The adapter returned the raw status instead of the side-level compatibility state.
3. A legacy/alternate BingX TradFi encoding such as `NCCOEUR2USD` can use the `NCCO` prefix even though it represents FX. The classifier fell through to the generic `NCCO -> COMMODITY` bucket because the metadata contained `EURUSD` rather than the literal token `FOREX`/`FX`.
4. `ExecutionService.act()` always passed `close_price` and `stage` to `close_position_full()`. Legacy/test adapters with a zero-argument close callable raised `TypeError` before the close action could be evaluated.
5. `test_position_side.py` contained a stale static assertion forbidding the literal `positionSide=BOTH`, which contradicts the required One-way BingX routing. The production code only emits `BOTH` after the exchange/account mode is explicitly resolved as `ONE_WAY`; the test was changed to detect forced mode changes instead.

## Surgical changes
- `news/service.py`
  - default `freshness_state` changed from `STALE` to `UNKNOWN`;
  - `news_state_for_side()` preserves explicit `STALE` while mapping unavailable assessments to `NEWS_UNAVAILABLE` at the side adapter layer.
- `scanner/universe.py`
  - added deterministic FX-pair detection ahead of the generic `NCCO` commodity branch;
  - retained metadata-first classification and fail-closed behavior.
- `execution/execution_service.py`
  - close callable invocation now adapts to its actual signature instead of catching arbitrary internal `TypeError`.
- `tests/test_execution_boundary.py`
  - added a regression test for a legacy zero-argument close callable.
- `tests/test_position_side.py`
  - corrected the obsolete static scan so One-way `BOTH` routing remains explicitly tested by `tests/test_bingx_position_mode.py`.

## Verification evidence
- `test_runtime_repairs.py`: 86/86 PASS.
- `test_execution_boundary.py`: 3/3 PASS.
- `test_position_side.py`: 17/17 PASS.
- `test_position_management_phase1.py`: 16/16 PASS.
- `test_profit_engine_phase3.py`: 31/31 PASS.
- All 95 test modules were executed as isolated child processes through `tools/run_one_testfile.py`, in bounded batches: **95/95 test files passed**.
- `verify_project.py`: PASS.
- `compileall`: PASS.
- `PAPER_RUNTIME_SMOKE=PASS`.
- BingX mode/protection/TP-authority regression subset: 34/34 PASS.

## Important qualification
The canonical `tools/run_isolated_tests.py` invocation itself exceeded the container transport window while printing its full stream. That is classified as a tooling/transport limitation, not converted into a test failure or a pass. The same one-process-per-file execution model was independently completed across all 95 files with 95/95 passing.

## Live execution
No real-money BingX trade was executed during this validation.
