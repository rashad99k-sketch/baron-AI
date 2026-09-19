# BARON Management Authority Consolidation — 2026-09-18

## Objective
Eliminate competing trade-management execution paths.

## Canonical runtime
`Evidence -> UnifiedTradeManagementBrain -> ExecutionService -> BingX -> Reconciliation -> State`

## Changes
- Emergency kill-switch closes now enter `FORCE_EXIT` through the unified manager.
- Dashboard/manual close requests route through `PortfolioManager.close_symbol`, which routes through the position's `LiveTradeManager._execute_action`.
- Portfolio direct `engine.close_position_full()` was removed from production close-symbol orchestration.
- `council_exit()` is advisory-only and no longer executes closes.
- Profit-engine routing has no direct-execution fallback when the unified manager is unavailable.
- Entry rollback paths no longer directly invoke the close kernel when the authority is unavailable; they fail closed.
- Legacy profit/dynamic managers remain import-compatible for regression/research, but are not invoked by the production management loop.

## Invariant
No production component other than `ExecutionService` may directly invoke the preserved close kernel.
All market-driven exit decisions are produced by `UnifiedTradeManagementBrain.evaluate()`.
Manual/emergency/safety exits are explicit authority intents and still execute through the same action gateway.

## Validation
Targeted authority/execution/TP/reconciliation/portfolio suite: 70 passed.
