# BARON — Upgrade Changelog 2026-09-17

## Institutional Entry & Dynamic Management

- Added `InstitutionalEntryEngine` for structural/liquidity-first entry assessment.
- Added EMA50/EMA200 directional context and recent-cross transition evidence.
- Added session VWAP context, reclaim/rejection handling, and management integration.
- Added liquidity-event quality rather than relying only on a single-bar low/high break.
- Added entry-window classification to reject late/chase entries.
- Added thesis-aware dynamic SL proposals with adaptive volatility/liquidity buffers.
- Added monotonic stop ratcheting through the existing protection authority.
- Added stop-event forensics and one-time stop-hunt re-entry with thesis fingerprint continuity.
- Added EMA50/EMA200/VWAP management context so healthy pullbacks are not treated as automatic thesis failures.
- Preserved canonical TP1=50% / TP2=remaining 50% and existing Brain -> ExecutionService authority.

## Regression Repairs Discovered During Validation

- Initialized stop-forensics state before closed-trade ledger writes so an INTERNAL_SL cannot leave a paper ghost position after PnL is booked.
- Added a dynamic engine-globals facade so `ExecutionService` remains valid under isolated/reloaded `core.engine` imports.
- Preserved legacy zero-argument close callables without swallowing TypeErrors raised from inside real close functions.

## Verification

- `verify_project.py`: PASS.
- Paper runtime smoke: PASS.
- 102 test files executed in six bounded batches.
- 827/827 collected tests passed across those complete batches.
- Single-process full runner exceeded the sandbox window at ~52%; it was not counted as a pass and was not hidden.

## Non-Goals Preserved

- No sizing redesign.
- No portfolio-capacity redesign.
- No RF redesign.
- No new profit stage.
- No live-money execution during validation.
