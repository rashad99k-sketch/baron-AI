# Institutional Entry + Dynamic Trade Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a professional institutional entry engine and dynamic EMA50/EMA200/VWAP management layer to BARON while preserving existing execution, RF, portfolio, and dashboard contracts.

**Architecture:** A pure `InstitutionalEntryEngine` will compute direction, liquidity-event quality, causal-zone evidence, setup type, entry window, thesis invalidation, and dynamic SL candidates. `core/engine.py` will consume this evidence and remain the orchestration boundary. Existing `ExecutionService`, `NativeProtectionManager`, and strict close pipeline remain the only action path.

**Tech Stack:** Python 3.13, pandas, numpy, pytest, existing BARON core helpers, CCXT/BingX adapters.

**Spec:** `docs/superpowers/specs/2026-09-17-institutional-entry-design.md`

## Global Constraints
- Preserve existing strategy/RF/scanner/dashboard/Telegram/execution architecture except surgical integration changes.
- EMA50/EMA200 and VWAP are context/evidence, not standalone entry triggers.
- TP1=50%, TP2=remaining 50%.
- Maximum one stop-hunt re-entry per thesis.
- Closed candles are authoritative for confirmed structure; live price is timing evidence only.
- BingX exchange state is authoritative for execution/protection/close truth.

### Task 1: Add pure institutional entry engine

**Files:**
- Create: `core/institutional_entry_engine.py`
- Test: `tests/test_institutional_entry_engine_v2.py`

**Interfaces:**
- Consumes: OHLCV DataFrame, side, price, ATR, optional VWAP/features, optional orderbook context.
- Produces: `EntryAssessment` with direction context, setup type, liquidity event, causal zone, trigger state, entry window, thesis invalidation, dynamic SL candidate, and reasons.

- [ ] Step 1: Write failing tests for EMA context, VWAP context, liquidity sweep quality, reclaim, causal zone, and late-entry rejection.
- [ ] Step 2: Run `pytest -q tests/test_institutional_entry_engine_v2.py` and confirm RED.
- [ ] Step 3: Implement minimal pure functions/classes: `compute_direction_context`, `compute_vwap_context`, `detect_liquidity_event`, `detect_causal_zone`, `classify_setup`, `classify_entry_window`, `build_thesis_map`, `compute_dynamic_sl`.
- [ ] Step 4: Re-run the test file and require GREEN.
- [ ] Step 5: Add deterministic tests for bullish/ bearish EMA50/200 cross transition evidence without making the cross itself an entry trigger.
- [ ] Step 6: Run the file again and require GREEN.

### Task 2: Integrate entry engine into canonical entry gate

**Files:**
- Modify: `core/engine.py` around `check_institutional_entry`, `get_trend_direction`, `classify_market_narrative`, and entry snapshot publishing.
- Test: `tests/test_institutional_entry_integration.py`

**Interfaces:**
- Consumes: `InstitutionalEntryEngine.assess(...)`.
- Produces: existing `check_institutional_entry` tuple plus `STATE` evidence fields; no direct exchange calls.

- [ ] Step 1: Write failing tests that prove a valid sweep/reclaim/MSS setup passes without requiring ADX to remain inside a fixed 25-38 band, while a late/chase setup fails.
- [ ] Step 2: Run the test file and verify RED.
- [ ] Step 3: Add the smallest integration adapter; preserve existing RF and queue contracts.
- [ ] Step 4: Run the test file and verify GREEN.
- [ ] Step 5: Add tests that verify EMA cross is transition evidence only and VWAP reclaim improves evidence but does not create an entry by itself.
- [ ] Step 6: Run targeted integration tests again.

### Task 3: Dynamic thesis-aware SL and stop forensics

**Files:**
- Modify: `core/engine.py` around SL computation/protection state.
- Create: `core/entry_forensics.py`
- Test: `tests/test_dynamic_entry_sl_forensics.py`

**Interfaces:**
- Consumes: `EntryAssessment`, current position state, current EMA/VWAP/structure context.
- Produces: dynamic SL proposal and stop classification; integrates through `_protection_commit` only.

- [ ] Step 1: Write failing tests for structural invalidation, adaptive ATR buffer, monotonic SL movement, and stop classifications.
- [ ] Step 2: Run and confirm RED.
- [ ] Step 3: Implement dynamic SL candidate and forensic classifier with explicit states `TRUE_FAILURE`, `STOP_HUNT`, `EARLY_ENTRY_ERROR`, `LATE_ENTRY`, `VOLATILITY_SPIKE`, `UNKNOWN`.
- [ ] Step 4: Run and verify GREEN.
- [ ] Step 5: Verify no normal path can loosen an already-confirmed SL.
- [ ] Step 6: Run regression tests for protection firewall and position management.

### Task 4: One-time stop-hunt re-entry

**Files:**
- Modify: `core/engine.py` trade lifecycle state handling.
- Test: `tests/test_stop_hunt_reentry.py`

**Interfaces:**
- Consumes: stop forensic classification + fresh entry assessment.
- Produces: `STOP_HUNT_REARM`, `REENTRY_READY`, or `INVALIDATED` state; no direct exchange action.

- [ ] Step 1: Write failing tests proving no re-entry after true thesis failure, exactly one re-entry after a fresh sweep/reclaim/MSS/displacement sequence, and no second re-entry.
- [ ] Step 2: Run and verify RED.
- [ ] Step 3: Implement one-time rearm state with thesis fingerprint continuity.
- [ ] Step 4: Run and verify GREEN.
- [ ] Step 5: Run existing portfolio-slot tests to prove re-entry cannot bypass six-position capacity.

### Task 5: EMA/VWAP-aware live management

**Files:**
- Modify: `core/engine.py` `LiveTradeManager` management path.
- Test: `tests/test_ema_vwap_trade_management.py`

**Interfaces:**
- Consumes: live price + closed-candle structure + EMA50/EMA200 + VWAP + trade state.
- Produces: hold/protect/trail/exit evidence routed through existing Brain -> ExecutionService -> protection/close pipelines.

- [ ] Step 1: Write failing tests for healthy EMA50 pullback, VWAP reclaim continuation, EMA50 failure + structure loss, and VWAP/EMA conflict.
- [ ] Step 2: Run and verify RED.
- [ ] Step 3: Implement a pure management-context helper and connect it to the existing health/state decision path.
- [ ] Step 4: Run and verify GREEN.
- [ ] Step 5: Verify `HEALTHY_PULLBACK` does not trigger exit solely because price crosses EMA50 intrabar.
- [ ] Step 6: Verify hard exit requires independent thesis failure evidence, except existing emergency safety states.

### Task 6: BingX execution/protection audit regression

**Files:**
- Modify if required: `execution/execution_service.py`, `portfolio/native_protection.py`, `execution/reconciliation.py`.
- Test: existing BingX/protection tests plus `tests/test_bingx_execution_dynamic_protection_v2.py`.

**Interfaces:**
- Consumes: existing execution intents and dynamic SL/TP decisions.
- Produces: verified exchange state; no internal CLOSED claim without verified zero position.

- [ ] Step 1: Write failing tests for One-way/Hedge parameter mapping, protective order verification, strict close verification, and duplicate-close prevention.
- [ ] Step 2: Run and verify RED where behavior is missing.
- [ ] Step 3: Apply minimal fixes only where required by current BingX semantics.
- [ ] Step 4: Run and verify GREEN.
- [ ] Step 5: Run `tests/test_execution_boundary.py tests/test_protection_firewall.py tests/test_native_protection_live_safety.py tests/test_close_101205_hardening.py tests/test_bingx_hedge_contract.py`.

### Task 7: Full regression + paper runtime

**Files:**
- Test existing suite and runtime tools.
- Update: `TEST_REPORT_2026-09-17.md`, `CHANGELOG_UPGRADE_2026-09-17.md`.

- [ ] Step 1: Run compile/static validation.
- [ ] Step 2: Run all new targeted tests.
- [ ] Step 3: Run the existing 95-file isolated gate.
- [ ] Step 4: Run paper runtime including entry -> protection -> TP1 -> management -> TP2 -> strict close -> reconciliation.
- [ ] Step 5: Run a release ZIP integrity test and calculate SHA-256.
- [ ] Step 6: Update reports with exact pass/fail/timeout/crash/environment counts; never convert timeouts to pass.
