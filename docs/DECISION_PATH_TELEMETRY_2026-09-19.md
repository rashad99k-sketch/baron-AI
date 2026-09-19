# BARON Decision Path Telemetry — 2026-09-19

## Purpose

This release adds **telemetry only**. It does not change strategy thresholds,
scores, entry gates, portfolio limits, execution logic, SL/TP logic, RF logic,
scanner ranking, or order behaviour.

The telemetry creates:

`runtime/decision_path_trace.jsonl`

The same `trace_id` follows a candidate from its scanner-side hypothesis through
watchlist/institutional analysis, queue admission/re-evaluation, Trend v29 gate,
execution request, gate vetoes, and OPEN confirmation when an order is opened.

## What is captured

At decision points the trace records:

- BUY and SELL hypotheses separately before watchlist side selection.
- selected watchlist direction and both side scores.
- EMA50 / EMA200 and price relationship.
- VWAP, side, and distance.
- ADX, DI+, DI-, and DI spread.
- confirmed-swing EQH/EQL clusters, levels, touches and distance.
- legacy EQH/EQL cluster flags and liquidity pools.
- zone / OB / institutional fields already present in the production pipeline.
- move maturity, queue state, trigger, confirmation count, and gate status.
- the authority/source that emitted each decision.
- final execution rejection reason or OPEN confirmation.

## Important semantics

EQH/EQL telemetry is descriptive. It does not become an entry trigger and does
not modify the production liquidity detector. Confirmed swing clusters use the
existing five-left/five-right swing definition for forensic consistency.

The telemetry is best-effort: if logging fails, the trading path continues
unchanged.

## Reading a trace

From the project root:

```text
python tools/decision_path_trace.py --symbol BTC/USDT:USDT
```

Multiple symbols:

```text
python tools/decision_path_trace.py --symbol BTC/USDT:USDT TIA/USDT:USDT AKE/USDT:USDT ETH/USDT:USDT LINK/USDT NCSKIREN/USDT:USDT
```

The output is JSONL so it can be diffed, filtered, or imported into pandas.

## Release validation

Telemetry unit/integration tests are included in:

`tests/test_decision_path_telemetry.py`

The existing institutional/queue tests remain unchanged.
