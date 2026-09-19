# BARON — Windows Test-Gate Hotfix 2 — 2026-09-18

## Root causes fixed

### 1. Windows source decoding failure
`tests/test_single_management_authority.py` used `Path.read_text()` without an explicit encoding. On the user's Windows/Python 3.12 environment the process default is `cp1252`, while BARON source files are UTF-8. This caused four structural-test failures before any assertion could run.

Fix: all source reads in this test are now explicitly `encoding="utf-8"`.

### 2. Portfolio close regression at the test seam
The production `PortfolioManager.close_symbol()` was intentionally hardened to route closes only through the per-position manager's `_execute_action("FORCE_EXIT", ...)` boundary. Two existing regression tests still supplied legacy test doubles that had no `_execute_action` method and therefore returned `False`.

Fix: the tests now model the canonical management-action boundary with a test-only adapter. No production direct call to `close_position_full()` or `close_partial()` was restored.

## Architecture preserved

The production close authority remains:

```text
Evidence / signal providers
        -> UnifiedTradeManagementBrain
        -> LiveTradeManager action boundary
        -> ExecutionService
        -> strict close kernel
        -> BingX
        -> fill / position verification
        -> reconciliation
```

No direct production `close_position_full()` / `close_partial()` calls were added outside `execution/execution_service.py`.

## Verification performed

- `verify_project.py`: PASS
- `tools/verify_single_management_authority.py`: PASS
- `test_single_management_authority.py`: 5 passed
- `test_portfolio_isolation.py`: 3 passed
- `test_manual_position_adoption.py`: 6 passed
- Consolidated targeted regression set: **127 passed**
- `tools/paper_runtime_smoke.py`: PASS

A complete 110-file isolated release-gate run was attempted with `BARON_TEST_TIMEOUT=120`. The execution window ended after the first 50 isolated child test files had completed; all completed files were green. The remaining files were not claimed as verified in this environment.

## Scope

Only three test files were changed for Windows portability and to bring their test doubles in line with the already-enforced unified management boundary. Production trading strategy, scanner, dashboard, execution kernel, and close authority were not changed by this hotfix.
