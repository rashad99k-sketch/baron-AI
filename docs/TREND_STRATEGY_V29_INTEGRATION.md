# BARON TREND Strategy v29 — Integration

## Purpose

BARON now has one technical-entry authority for the main automated path:
`BaronTrendStrategyV29`.

The scanner, RF watchlist, Scanner v2 and Institutional Radar remain discovery /
evidence providers. They do not independently decide a technical order in the
main execution path.

News and explicit manual control remain separate.

## Decision layers

1. **Trend regime**
   - ADX >= 25 for live technical entry.
   - DI spread >= 5 in the requested direction.
   - EMA20/EMA50 + price alignment, with a structural shift allowed to establish
     directional context.
2. **Liquidity map**
   - Confirmed swing highs/lows (5 bars on each side).
   - Equal-high/equal-low clusters from confirmed swings.
   - Liquidity sweep is mandatory for the trend thesis.
   - Repeated levels are also used as attraction targets.
3. **Structure**
   - BOS or directional structure shift.
4. **Pullback state**
   - `NO_PULLBACK`: acceptable.
   - `WEAK_PULLBACK`: preferred continuation state.
   - `MEDIUM_PULLBACK`: allowed only with a nearby structural/liquidity retest
     and directional re-confirmation.
   - `STRONG_PULLBACK`: wait.
   - `REVERSAL`: reject.
5. **Context confirmation**
   - VWAP alignment/reclaim.
   - Volume expansion/normal confirmation.
   - Aggressive flow.
   - EMA9/EMA21 momentum.
   - Optional order-book imbalance.
   - RF signal and distance.
6. **Risk**
   - Initial SL is structural/liquidity-aware, placed beyond the causal sweep /
     invalidation area with an ATR buffer.
   - A technical setup is rejected if the structural stop would be excessively
     wide (> 2.8 ATR).
   - This is not a promise that losses or stop-outs disappear; the objective is
     to avoid placing the stop inside the normal sweep/pullback area.
7. **Profit**
   - Two-stage TP geometry is preserved; existing execution-side ATR floors may
     widen targets.
   - The unified execution/management authority remains responsible for live
     protection and profit management.

## Authority boundary

`smart_opportunity_selection()` now evaluates candidates exclusively through
Trend v29 before calling the existing `execute_entry()` boundary.

`process_queue_entry()` re-evaluates technical queue candidates through the same
Trend v29 logic at the live trigger. News candidates are exempt because the
News slot is a separate strategy.

No direct order placement was added to Trend v29.

## Validation performed

- Python compilation: PASS.
- `verify_project.py`: PASS.
- Targeted suite including Trend v29, single management authority, EMA/VWAP
  management, portfolio capacity and six-slot runtime: **19 passed**.

The full historical release suite was not claimed as passed by this integration
step.
