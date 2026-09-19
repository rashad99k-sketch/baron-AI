# BARON — Partition AI Trade Forensics

## Purpose

Partition AI is an **observability / forensic learning layer**. It does not make entry, exit, sizing, leverage, scanner, or strategy decisions.

It records the complete lifecycle of a confirmed BARON trade:

`ENTRY → LIVE SNAPSHOTS → MILESTONES → EXIT → POST-SL WATCH`

## Files produced

- `partition_ai/trade_ledger.jsonl` — one entry/exit forensic record per trade.
- `partition_ai/trade_snapshots.jsonl` — live snapshots while the trade is open.
- `partition_ai/post_exit_watch.jsonl` — post-stop observations used to detect reclaim/reversal behavior.
- `partition_ai/forensic_summary.json` — aggregate counts by asset class, exit classification, milestones and SL-reversal observations.

## Recorded evidence

### Entry

- Trade ID
- symbol / asset class
- BUY / SELL
- leverage (BARON defaults to 10x)
- score / classification / entry type / trade type
- ADX, DI+, DI-, DI spread, ATR, regime, confidence
- RF / VWAP fields when available in BARON memory
- liquidity context
- volume
- structure shift
- momentum
- Smart Money
- news-event payload when the running bot exposes `STATE['news_event']` or `MEMORY['news_event']`

### Live

For each snapshot:

- price move % (unlevered market move)
- actual ROE if BARON supplies it; otherwise theoretical ROE = price move × leverage
- MFE / MAE
- ADX / DI and other live evidence when available
- liquidity, volume, structure, momentum, Smart Money and news evidence
- milestones: +0.5%, +1%, +1.5%, +2%, +3%, +5%

### Exit / post-exit

The record stores result, PnL, exit reason, MFE/MAE and TP state. Stop-loss trades are watched after exit for a configurable period (default 30 minutes) to detect whether price reclaims the stop area and continues in the original direction.

## Important interpretation rule

10x leverage is **not** the same thing as a 10x price move. A +1% underlying price move is approximately +10% ROE before fees/funding/slippage when the position uses 10x leverage. BARON records both quantities so later analysis does not confuse leverage with market movement.

## News slot

The forensic layer can store a news-event payload and classify the asset class independently. It does **not** create or validate a news signal itself. If the BARON news engine populates `STATE['news_event']` or `MEMORY['news_event']`, that payload is captured at entry and during live snapshots. The existing source inspected here did not expose a dedicated news engine, so news-event attribution must come from the actual news component when present.

## Validation

The module has a deterministic synthetic smoke test covering:

- 10x ROE conversion
- milestones
- MFE
- asset classification
- ledger creation
- summary aggregation

For a real 2–3 hour observation, run BARON in the intended PAPER/LIVE environment and inspect the generated `partition_ai/` directory. A local tool session cannot honestly claim a 2–3 hour live exchange observation without actually running the user's exchange-connected process.
