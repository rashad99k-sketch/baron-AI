# BARON Hotfix Report — 2026-09-18

## Release blocker
`tests/test_zone_lifecycle_waves.py` failed in `ExecutionQueue.re_evaluate_all()` because
`check_institutional_entry()` returned a bare boolean from the move-maturity hard gate while
all callers expect the canonical three-value contract:

`(should_enter: bool, classification: Optional[str], reason: str)`

The failure was:

`TypeError: cannot unpack non-iterable bool object`

## Root cause
The `EXHAUSTION` / `LATE_EXPANSION` early-entry maturity rejection was added as a fail-closed
boolean return, but the function's public/internal API is tuple-based at every call site.

## Surgical fix
Changed the maturity rejection to preserve the canonical tuple contract:

`return False, None, "Move maturity <phase> is too mature"`

No entry logic, portfolio limits, TP1/TP2 rules, RF logic, execution authority, or trade-management
architecture was changed by this hotfix.

## Regression protection
Added `test_maturity_rejection_preserves_three_value_entry_contract` to
`tests/test_institutional_entry_integration.py` and verified via AST that every return path in
`check_institutional_entry()` returns a three-item tuple.

## Validation
- `tests/test_zone_lifecycle_waves.py`: **7 passed**
- `tests/test_institutional_entry_integration.py`: **4 passed**
- `tests/test_unified_trade_authority.py`: **6 passed**
- `tests/test_vpa_prestrong.py`: **3 passed**
- `tests/test_watchlist_symbol_zone_cache.py`: **1 passed**
- `tests/test_institutional_entry_market_state.py`: **2 passed**
- `tests/test_institutional_entry_engine_v2.py`: **7 passed**
- `tests/test_market_state_trade_management.py`: **4 passed**
- `tests/test_early_institutional_radar.py`: **7 passed**
- `tests/test_profit_engine_phase3.py`: **31 passed**
- `tests/test_bingx_execution_truth_regressions.py`: **4 passed**
- `tests/test_native_protection_live_safety.py`: **21 passed**
- `tests/test_dashboard_market_state.py`: **2 passed**
- `tests/test_dashboard_contracts.py`: **5 passed**
- `tests/test_dashboard_schema.py`: **7 passed**
- `python -m compileall -q .`: **PASS**
- `python verify_project.py`: **PASS**
- `python tools/paper_runtime_smoke.py`: **PASS**

The full release gate is still not claimed as PASS until the complete isolated suite is rerun end-to-end.
