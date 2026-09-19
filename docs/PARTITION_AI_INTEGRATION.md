# BARON — Partition AI Forensic Integration

## Purpose
Partition AI is a **read-only forensic/observability layer**. It does not qualify entries, move stops, close positions, change portfolio capacity, or override the Unified Trade Management Brain / LiveTradeManager. The production execution authority remains unchanged.

## What is recorded
Each opened trade keeps the existing BARON `trade_id` and records:
- asset class and underlying asset class (including `NEWS` + underlying symbol class)
- BUY/SELL, entry, quantity, leverage, margin, SL, TP1, TP2
- entry score and measurement-only component scores
- ADX, ADX slope, DI+/DI-, DI spread, EMA9/20/21/50/200, VWAP, RSI, MACD, ATR
- volume ratio/state, structure, pullback, momentum and order-book evidence
- V29 liquidity map: swing highs/lows, clusters, EQH/EQL, nearest target above/below, distance, ATR distance, attraction and sweep/reclaim state
- existing BARON thesis / institutional / execution context as a forensic snapshot
- News event and measured news reaction when the NEWS slot populates those fields

## 10x accounting
Partition stores **price move %** and **ROE %** separately. It also stores a theoretical ROE derived as `price_move_pct * leverage` and the actual BARON/exchange ROE when available. At 10x, a +1% favorable price move is approximately +10% theoretical ROE before fees/funding/slippage.

## Lifecycle
`OPEN_CONFIRMED -> LIVE SNAPSHOTS -> PARTIAL_CLOSE(S) -> TRADE_CLOSED -> POST_EXIT_WATCH (SL only)`

Milestones include favorable `+0.5/+1/+1.5/+2/+3/+5%` and adverse `-0.5/-1/-1.5/-2/-3/-5%` price moves. MFE/MAE and peak/min ROE are retained.

## Stop-loss forensic watch
A losing trade closed by SL remains observable for the configured watch window. Partition records whether the stop zone was reclaimed, whether the original entry was recovered, and whether original TP1/TP2 was later reached. This is evidence for distinguishing thesis failure from stop-placement/liquidity-sweep behavior. It does not reopen or manage the position.

## News validation trail
For a NEWS trade the record preserves the normalized news payload and `news_reaction`. This allows later analysis of:
1. whether an event was actually detected,
2. which asset the event was mapped to,
3. headline direction vs trade direction,
4. post-headline reaction direction/magnitude/causality,
5. whether the dedicated NEWS slot opened the trade, and
6. what the trade subsequently did.

## Runtime files
Default directory: `runtime/partition_ai/`

- `trade_ledger.jsonl` — entry/exit/partial lifecycle records
- `trade_snapshots.jsonl` — periodic live evidence snapshots
- `partial_close_events.jsonl` — verified partial/TP events
- `post_exit_watch.jsonl` — post-SL observations
- `forensic_summary.json` — aggregate counts

## Safe rollout
The feature is enabled by default because it is observability-only. It can be disabled with `PARTITION_AI_ENABLED=False` without changing any strategy logic.
