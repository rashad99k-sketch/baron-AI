# BARON — Institutional Entry & Dynamic Trade Management Upgrade

## Objective

Upgrade BARON's entry timing and live management around a structural/liquidity thesis while preserving the existing RF, portfolio-capacity, execution, protection, dashboard, and Telegram contracts.

## Strategy Design

### Direction context

- EMA200 = macro directional context.
- EMA50 = active trend context.
- EMA50/EMA200 cross = transition evidence only; it is never a standalone order trigger.
- The entry decision remains based on structural/liquidity evidence.

### VWAP

- Session VWAP is derived from HLC3 and volume.
- VWAP provides value/acceptance context, reclaim/rejection evidence, and pullback-management context.
- A VWAP reclaim can strengthen a setup but cannot create an entry on its own.
- During management, EMA50/VWAP are used to distinguish a normal pullback from a thesis failure while EMA200 remains the deeper regime boundary.

### Institutional entry sequence

1. Market/regime context.
2. Visible liquidity map.
3. Causal zone context.
4. Liquidity event / sweep.
5. Reclaim or pullback response.
6. Displacement and structure response.
7. Entry-window / anti-chase test.
8. Thesis invalidation map.
9. Dynamic SL proposal.
10. UnifiedTradeManagementBrain approval.
11. Existing execution service.

Supported setup types:

- `LIQUIDITY_REVERSAL`
- `TREND_PULLBACK`
- `EARLY_EXPANSION`

## Dynamic Stop Logic

The initial SL is anchored to the thesis invalidation level when institutional entry evidence is approved. The proposal adds an adaptive volatility/liquidity buffer and is constrained by the existing monotonic protection rule.

Normal management cannot loosen a confirmed SL. Protection changes continue through `_protection_commit()` and, in LIVE mode, the native protection manager/exchange verification path.

## Stop-Hunt Re-entry

A stop hit is classified instead of being treated as a single generic failure.

Possible classifications:

- `TRUE_FAILURE`
- `STOP_HUNT`
- `EARLY_ENTRY_ERROR`
- `LATE_ENTRY`
- `VOLATILITY_SPIKE`
- `UNKNOWN`

A re-entry is permitted only when:

- the prior stop was classified `STOP_HUNT`;
- a fresh institutional assessment is approved;
- the new entry remains `EARLY` or `CONFIRMED`;
- a fresh liquidity sweep/reclaim has quality >= 0.75;
- the structural thesis fingerprint remains continuous;
- no previous re-entry was consumed.

Maximum: **one re-entry per thesis**.

## BingX Execution

Current official BingX documentation was checked before changing the execution/protection boundary.

Relevant current semantics:

- Perpetual order endpoint: `POST /openApi/swap/v2/trade/order`.
- One-way mode uses `positionSide=BOTH`.
- Hedge mode uses `positionSide=LONG` or `SHORT`.
- `reduceOnly` must not be sent in Hedge mode.
- `closePosition` is for conditional full-position closes and must not be combined with `reduceOnly`.
- `positionId` is relevant for Separate Isolated close flows.
- Current order APIs expose order ID/client order ID and execution state; current position state remains the final source for close verification.

The strict close pipeline remains:

`Decision -> Close Intent -> Position Snapshot -> Close Order -> Order/Fills -> Position Recheck -> CLOSED_VERIFIED or RECOVERY`.

No internal `CLOSED` state is granted merely because a local close function returned.

## Preserved Contracts

No change was made to:

- RF parameters/behavior.
- Portfolio hard cap: 5 Technical + 1 News.
- TP1/TP2 contract: 50% + remaining 50%.
- Leverage/risk-budget configuration.
- Dashboard routes or Telegram interface.
- Core exchange synchronization semantics.
- UnifiedTradeManagementBrain as the final decision authority.

## Files Added / Modified for This Upgrade

### New modules

- `core/institutional_entry_engine.py`
- `core/ema_vwap_trade_management.py`
- `core/entry_forensics.py`
- `core/stop_hunt_reentry.py`

### Integration changes

- `core/engine.py`
- `execution/execution_service.py`
- `portfolio/manager.py`
- `requirements-runtime.txt`

### Tests

- `tests/test_institutional_entry_engine_v2.py`
- `tests/test_institutional_entry_integration.py`
- `tests/test_ema_vwap_trade_management.py`
- `tests/test_dynamic_entry_sl_forensics.py`
- `tests/test_dynamic_entry_sl_engine_integration.py`
- `tests/test_stop_hunt_reentry.py`
- `tests/test_stop_hunt_reentry_engine_integration.py`
- Existing BingX/protection/position-management suites were re-run.

## Validation Evidence

- `verify_project.py`: PASS — all Python modules parse and compile.
- Paper runtime smoke: PASS.
- All 102 test files were executed in deterministic file-batch runs.
- Total collected tests: **827**.
- Total observed passing tests across those complete batch runs: **827/827**.

### Batch evidence

| Batch | Files | Tests | Result |
|---|---:|---:|---|
| 1 | 26 | 202 | PASS |
| 2 | 26 | 137 | PASS |
| 3 | 13 | 132 | PASS |
| 4 | 14 | 131 | PASS |
| 5 | 12 | 174 | PASS |
| 6 | 11 | 51 | PASS |
| **Total** | **102** | **827** | **827 PASS** |

A single-process `pytest -q` run exceeded the sandbox execution window after 52% progress without a logical test failure being reported at that point. The complete test population was therefore verified by the six bounded batch runs above instead of inflating or masking the timeout.

## Important Limitation

The validation is paper/offline validation. No real-money BingX order was placed during this upgrade. Live mode remains fail-closed when required native protection/configuration is unavailable.

## External References Checked

- BingX official API reference: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-trade/api-reference.md
- BingX official swap-trade skill: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-trade/SKILL.md
- TradingView official VWAP support: https://www.tradingview.com/support/solutions/43000502018-volume-weighted-average-price-vwap/
