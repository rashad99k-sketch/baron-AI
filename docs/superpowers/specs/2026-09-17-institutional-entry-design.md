# BARON Institutional Entry Intelligence Design

## Goal
Upgrade BARON's entry and live trade-management logic so EMA50/EMA200 define directional context, VWAP provides intraday value/acceptance context, and actual entries are triggered by a causal liquidity/structure sequence rather than indicator stacking.

## Core Design
1. EMA200 is macro trend context; EMA50 is active trend context. EMA50/200 crosses are transition evidence, never standalone entries.
2. VWAP is session-anchored volume-weighted value. It is used for trend/value context, reclaim/rejection, pullback classification, and profit-management decisions. VWAP is not a standalone trigger.
3. Entry requires a structural core: valid causal zone + meaningful liquidity event or valid trend pullback + structure trigger + defined invalidation. Displacement/volume/flow/RF/VWAP improve quality but are not all mandatory on every setup.
4. Supported setup types: LIQUIDITY_REVERSAL, TREND_PULLBACK, EARLY_EXPANSION.
5. Live price is used for timing/refinement; closed candles remain the source of truth for confirmed structure and zone history.
6. SL is based on thesis invalidation plus adaptive volatility/liquidity buffer. Position sizing remains outside this feature.
7. After SL, classify the event as TRUE_FAILURE, STOP_HUNT, EARLY_ENTRY_ERROR, LATE_ENTRY, VOLATILITY_SPIKE, or UNKNOWN. Permit at most one re-entry when a fresh sweep/reclaim/MSS/displacement sequence revalidates the thesis.
8. Live management uses EMA50, EMA200, VWAP, structure, liquidity and trade state to distinguish healthy pullbacks from thesis failure. EMA/VWAP do not directly close positions.
9. TP remains exactly TP1 50% and TP2 remaining 50%. Protection changes must go through the existing protection authority and exchange verification.
10. BingX remains the external execution source of truth. Current documented semantics for positionSide/reduceOnly/closePosition, conditional orders, order queries and fills must be respected.

## Non-Goals
- Do not change portfolio capacity, leverage, risk-budget rules, RF parameters, News slot behavior, Dashboard routes, Telegram, or scanner capacity.
- Do not introduce additional profit stages.
- Do not claim institutional order flow can be observed directly; institutional metrics remain evidence.

## Success Criteria
- Long and short entry logic agree with EMA50/200 direction context without making EMA crosses mandatory.
- VWAP context is correctly available and materially represented in entry and management decisions.
- Entry requires a causal structural trigger and rejects late/chase entries.
- Dynamic SL follows thesis invalidation and cannot loosen confirmed protection through normal management.
- One stop-hunt re-entry is possible only after fresh structural confirmation.
- Existing strict close/protection semantics remain intact.
- New behavior has deterministic unit tests and paper-runtime validation.
