# BARON Architecture Report — 2026-09-18

## Scope
This release continues the 2026-09-17 institutional-entry baseline with a pure market-state evidence layer and tighter BingX truth boundaries.

## New market-state architecture
`core/market_regime_engine.py` is read-only and deterministic. It produces `MarketStateSnapshot` with:
- ACCUMULATION / RE_ACCUMULATION
- MARKUP / TREND_PULLBACK
- DISTRIBUTION / RE_DISTRIBUTION
- MARKDOWN / TRANSITION / UNKNOWN
- EMA50/EMA200 context, slopes, spread, recent-cross evidence
- session VWAP side, value, slope, reclaim/rejection and ATR distance
- structure/liquidity/VPA evidence
- accumulation/distribution process scores
- observable microstructure proxies and explicit data quality

The engine does not claim visibility into hidden institutional algorithms. Missing optional inputs remain `UNAVAILABLE`.

## Entry integration
`InstitutionalEntryEngine` now carries `market_state` in its assessment. EMA crossover remains context-only. Contradictory confirmed market regimes block the corresponding side while the existing structural/anti-chase gate remains authoritative.

## Per-position management
`EMA200VWAPManager` now exposes market-state evidence alongside its existing pullback/thesis classification. EMA50/VWAP changes alone do not close a trade. EMA200 plus structural failure remains the strongest thesis-failure path. Existing monotonic protection and TP1/TP2 lifecycle are preserved.

## BingX execution truth
The existing execution/close kernel remains the action boundary. Reconciliation now carries requested quantity, executed quantity, protection state, and an exchange-quantity-derived zero-position flag. Native conditional protection no longer sends `clientOrderId` because current BingX perpetual-swap documentation limits `clientOrderId` support to MARKET and LIMIT orders.

## Dashboard
`dashboard/app.py` now exposes backend-derived `market_state` data and renders a compact Market State panel containing regime/transition, EMA50/EMA200, VWAP, accumulation, distribution, microstructure quality, and evidence reasons.

## Preserved constraints
- RF engine and confirmed closed-candle structure behavior preserved.
- 6-position capacity preserved: 5 Technical/Institutional + 1 independent News slot.
- TP1 = 50%; TP2 = remaining 50%.
- Brain remains decision authority; execution remains action boundary; exchange/reconciliation remain truth boundaries.
- No real-money order was executed by this validation run.
