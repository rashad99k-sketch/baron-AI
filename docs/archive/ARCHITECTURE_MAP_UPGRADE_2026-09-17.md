# BARON — Architecture Map & Upgrade Audit

## Baseline
The uploaded ZIP was treated as the sole baseline. No older BARON ZIP was used as a source of implementation.

## Current high-level flow
Research / Scanner → Evidence → Execution Queue → Entry Gate → Portfolio Capacity → `execute_entry()` → Exchange Order → Exchange Position Verification → Protection → Trade Management → TP1 / TP2 → Strict Close → Fill Verification → Position Reconciliation → Dashboard / Telegram / Journal.

## Decision vs action separation
- `core/unified_trade_management_brain.py`: named decision facade around the preserved `InstitutionalTradeBrain`.
- `execution/execution_service.py`: action boundary for TP1/TP2/SL/BE/TRAIL/EXIT/RECOVERY.
- Existing `core/engine.py` remains the preserved exchange execution kernel and verification layer.
- The Brain does not call exchange APIs directly.

## BingX execution state model
BARON now routes live order parameters from current BingX position mode:
- Hedge Mode → `positionSide=LONG|SHORT`; no `reduceOnly`.
- One-way Mode → `positionSide=BOTH`; close/reduction orders add `reduceOnly=true`.
- Live execution fails closed when the position mode cannot be established.

## Protection lifecycle
Entry now verifies the venue position before native SL installation. Native protection is only considered active after an exchange order id and order-state verification are obtained. Protection status is surfaced to dashboard state.

## Reconciliation
The existing REST position sync was extended with order/fill checks and explicit reconciliation states. Quantity comparison remains exchange-driven. Provider failures are no longer converted into a false `SYNCED` state.

## Asset classification
`scanner.universe.classify()` is now metadata-first and explicitly supports CRYPTO / STOCK / INDEX / METAL / ENERGY / COMMODITY / FOREX / UNKNOWN. Arbitrary `USDT` suffixes no longer imply CRYPTO.

## Portfolio capacity
The hard portfolio contract is now fixed at 6 concurrent positions: 5 technical/institutional + 1 independent News slot. Runtime and portfolio layers no longer accept an environment override that can raise or lower the master cap.

## News
News assessments now carry freshness, reliability, entity and reaction fields and use explicit NO_DATA / DATA_UNAVAILABLE / STALE-style states rather than treating missing news as Neutral.

## Observability
Critical lifecycle events are enriched with trade id, symbol, asset class, side, position id, order id, client order id, timestamps and quantity fields where available.
