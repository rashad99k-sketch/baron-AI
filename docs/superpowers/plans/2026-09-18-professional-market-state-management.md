# BARON Professional Market-State + Dynamic Trade Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic market-state intelligence layer and wire it into BARON's existing entry/management/dashboard paths while preserving the BingX execution truth boundary, TP1/TP2 structure, portfolio capacity, and RF behavior.

**Architecture:** `MarketRegimeEngine` is a pure/read-only evidence analyzer. `InstitutionalEntryEngine` consumes its snapshot as context; `UnifiedTradeManagementBrain` remains the final decision authority; `ExecutionService` and reconciliation remain the only action/truth boundaries. Dashboard exposes backend-derived market-state and management evidence without inventing values.

**Tech Stack:** Python 3, pandas, numpy, pytest, existing BARON Flask/CCXT runtime.

**Spec:** `docs/superpowers/specs/2026-09-17-professional-market-state-management-design.md`

## Global Constraints

- Preserve the existing RF engine and confirmed closed-candle structural behavior.
- Preserve exactly 6 total positions: 5 Technical/Institutional + 1 independent News.
- Preserve TP1 = first 50% and TP2 = remaining 50%; no third stage.
- EMA50/EMA200 cross is transition evidence only and never a standalone entry trigger.
- VWAP is value/acceptance context only and never a standalone entry/exit trigger.
- Exchange state is authoritative for actual fills, positions, protection, and final close verification.
- Brain decides; ExecutionService acts; reconciliation verifies; Dashboard reports.
- Missing/stale optional market data is `UNAVAILABLE`, not fabricated neutral evidence.
- LIVE uncertainty fails closed.

## Task 1: Pure Market Regime Engine

**Files:** Create `core/market_regime_engine.py`; Test `tests/test_market_regime_engine.py`.

**Interfaces:** `MarketStateSnapshot.to_dict()`; `MarketRegimeEngine(hysteresis_bars=2)`; `analyze(df, *, structure=None, liquidity=None, vpa=None, depth=None, trades=None, open_interest=None, previous_state=None)`.

- [ ] Write failing tests for required states, EMA cross context-only, VWAP fields, accumulation/distribution, re-accumulation/re-distribution, microstructure unavailable, and deterministic output.
- [ ] Run the test file and verify RED due to missing implementation.
- [ ] Implement deterministic EMA50/EMA200, session VWAP, ATR-normalized distance, compression/range, effort/result, sweep/reclaim, structure and optional microstructure evidence.
- [ ] Implement hysteresis so one noisy bar does not flip a directional state.
- [ ] Run the test file and require PASS.
- [ ] Compile the new module.

## Task 2: Entry Integration

**Files:** Modify `core/institutional_entry_engine.py`, `core/engine.py`; Test `tests/test_institutional_entry_market_state.py`.

**Interfaces:** `InstitutionalEntryEngine.assess(..., market_state=None)`; `_institutional_entry_v2_assessment(...)` attaches market-state evidence.

- [ ] Write failing tests proving EMA crossover alone cannot approve an entry and supportive accumulation/markup or distribution/markdown context is exposed.
- [ ] Run RED.
- [ ] Add a small adapter around `MarketRegimeEngine`; do not duplicate regime logic in `engine.py`.
- [ ] Keep structural prerequisites and LATE rejection unchanged.
- [ ] Run new tests plus institutional-entry regressions.

## Task 3: Per-Trade Thesis and Management Context

**Files:** Modify `core/ema_vwap_trade_management.py`, `core/unified_trade_management_brain.py`, `core/engine.py`; Test `tests/test_market_state_trade_management.py`.

- [ ] Write failing tests for BUY/SELL healthy pullback, adverse distribution, EMA/VWAP-only non-exit, and EMA200+structure failure.
- [ ] Run RED.
- [ ] Implement symmetric state interpretation with hysteresis and preserve monotonic SL.
- [ ] Keep TP1/TP2 exactly 50%/remaining 50%.
- [ ] Run management/profit/protection regressions.

## Task 4: BingX Execution/Reconciliation Correctness

**Files:** Modify `execution/execution_service.py`, `execution/reconciliation.py`, `portfolio/native_protection.py`; Tests `tests/test_bingx_execution_truth_regressions.py`, `tests/test_native_protection_live_safety.py`.

- [ ] Write failing tests for requested-vs-executed TP1 quantity, strict TP2 zero-position close, duplicate close single-flight, Hedge LONG/SHORT isolation, and conditional client-order-id omission.
- [ ] Run RED.
- [ ] Implement only surgical boundary fixes; do not move decision logic into execution.
- [ ] Run execution/protection/position-side tests individually.
- [ ] Run `python tools/paper_runtime_smoke.py`.

## Task 5: Dashboard Market-State Command Center

**Files:** Modify `dashboard/app.py`; Test `tests/test_dashboard_market_state.py`.

- [ ] Write failing contract tests for market-state schema and exchange reconciliation fields.
- [ ] Run RED.
- [ ] Add backend-derived Market State panel: regime, transition, EMA50/EMA200, VWAP, accumulation/distribution, liquidity, VPA, microstructure/data quality, and reasons.
- [ ] Keep existing routes/panels compatible.
- [ ] Run dashboard schema/import tests.

## Task 6: Release Validation and Artifact

**Files:** Modify `CHANGELOG.md`; Create architecture, BingX audit, test, and runtime reports; Create final ZIP.

- [ ] Run `python -m compileall -q .`.
- [ ] Run `python verify_project.py`.
- [ ] Run every test module individually with bounded per-file timeout and report exact counts.
- [ ] Run `python tools/paper_runtime_smoke.py`.
- [ ] Run `python tools/dashboard_runtime_check.py`; classify missing Flask/ccxt as ENVIRONMENT BLOCKED, not PASS.
- [ ] Generate reports from observed outputs.
- [ ] Create ZIP and SHA-256 hash.
- [ ] Verify ZIP contents and absence of secrets.
- [ ] Final status is `LIVE-READY` only if every required gate passes; otherwise `BLOCKED` with exact reasons.
