# BARON BingX Integration Audit — 2026-09-18

## Current documented semantics checked
Official BingX Perpetual Swap Trade API documentation was checked before the execution-boundary change.

Reference: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-trade/api-reference.md

Current documented points used by BARON:
- `/openApi/swap/v2/trade/order` is the perpetual order endpoint.
- Supported order types include MARKET, LIMIT, STOP_MARKET, STOP, TAKE_PROFIT_MARKET, TAKE_PROFIT, TRAILING_STOP_MARKET and TRAILING_TP_SL.
- `positionSide` is BOTH for one-way and LONG/SHORT for hedge operation.
- `reduceOnly` must not be sent in Hedge Mode.
- `closePosition` is restricted to conditional stop/take-profit semantics; it is not treated as a generic market-close switch.
- STOP_MARKET and TAKE_PROFIT_MARKET still require quantity and stopPrice when using closePosition according to the current reference.
- `workingType` supports MARK_PRICE, CONTRACT_PRICE and INDEX_PRICE.
- Current documentation states `clientOrderId` is supported for MARKET and LIMIT only.
- Order details expose `executedQty` and status, which BARON must reconcile before committing profit-stage state.
- BingX provides order history/open-order queries and position/close routes for reconciliation.

## BARON safety model
Decision -> Execution Intent -> BingX Order -> Order State -> Fill State -> Position State -> Protection State -> Reconciliation -> Internal State.

A local close request is not treated as a verified close. Final closure requires exchange position verification.

## Protection correction
`portfolio/native_protection.py` now keeps the venue `clientOrderId` out of conditional native protection parameters such as STOP_MARKET/TAKE_PROFIT_MARKET. BARON correlates these orders using its own trade/protection key and the venue order ID.

## Position-side isolation
Protection registry keys remain `(symbol, position_side)`, preventing Hedge LONG and SHORT protection from sharing a single record.

## Validation limitation
No real-money BingX order was submitted. Dashboard runtime could not be started in this environment because Flask/ccxt are unavailable and package installation was blocked by network/DNS. Paper runtime passed.
