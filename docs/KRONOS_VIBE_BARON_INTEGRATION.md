# BARON — Vibe-Trading / Kronos Integration

## Purpose

BARON borrows engineering patterns from the reviewed reference projects without
adopting their execution authority. BARON's existing RF, institutional, risk,
portfolio, exchange synchronization and Unified Trade Management authorities
remain canonical.

## Vibe-Trading patterns adopted

- Evidence-gated research rather than direct agent-to-order execution.
- Explicit runtime states and audit-friendly decision packets.
- Fail-closed behavior for invalid, stale or incomplete live evidence.
- Provider boundaries and bounded fallbacks for external intelligence/data.
- Research/shadow concepts for post-trade learning without changing live orders.
- Reconciliation and operational observability around the execution boundary.

## Kronos patterns adopted

BARON now contains a lightweight `core/forecast_evidence.py` adapter. It does
not require the heavy Kronos model at runtime. It preserves the architectural
ideas that are useful immediately:

- multi-horizon path estimates;
- multi-path dispersion and uncertainty;
- ATR-normalized expected movement;
- deterministic, closed-data-only inference;
- batch-safe, dependency-light operation suitable for scanner usage;
- forecast as evidence, not as an execution signal.

A future heavyweight foundation model can plug into the same evidence contract
without becoming a second decision authority.

## Institutional strategy stack

The production analysis chain remains:

`Market Regime -> Liquidity Map -> Liquidity Sweep -> Structure Shift -> Causal
Order Block -> Retest/Rejection -> VPA/Order Flow -> VWAP/EMA50/EMA200/ADX/ATR
Context -> Forecast Evidence/Uncertainty -> BARON Brain -> Risk/Portfolio -> Execution`

A model cannot override a hard risk/execution gate, and missing forecast data is
represented as missing evidence rather than a fabricated bullish/bearish state.
