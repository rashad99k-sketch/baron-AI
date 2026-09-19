# BARON — Institutional Fusion + Dashboard Intelligence Upgrade

## Scope

This upgrade is additive. It does not replace the Unified Trade Management Brain,
execution service, RF authority, portfolio capacity, risk gates, or TP1/TP2 contract.

## What was found in the supplied build

- The build already contains substantial institutional evidence: liquidity/sweep,
  causal OB, structure, premium/discount, VPA, VWAP/EMA/ADX/ATR/RSI/MACD,
  early-formation detection, forecast evidence, setup memory, and a two-stage
  deep scanner.
- The current Kronos integration is intentionally a dependency-light forecast
  proxy (`core/forecast_evidence.py`), not the heavyweight Kronos foundation model.
- The dashboard is a large Flask-rendered HTML surface with read-only intelligence
  routes, rather than a modular React/terminal frontend.
- The MSB-OB structural engine provides deterministic zones and lifecycle states,
  while the downstream institutional evaluator supplies richer OB scoring.

## Additive change

### `core/institutional_fusion.py`

Creates one explainable, read-only setup fingerprint from the existing scanner
outputs. It combines:

- liquidity sweep evidence
- structure shift / BOS / MSS
- causal zone / OB quality
- VPA confirmation/adverse state
- flow alignment
- early formation / pre-expansion state
- premium/discount location
- forecast quality/consensus/uncertainty
- contradictions and data quality

It emits `WATCH`, `FORMING`, `EARLY_MOVE`, `CONFIRMED`, or `CONFLICTED` state and
an `explosive_candidate` research flag. The score is explicitly an evidence score,
not a probability of profit and not an execution gate.

### Deep Scanner

Each deep watchlist entry now carries `institutional_fusion`,
`institutional_state`, and `explosive_candidate` for downstream research and UI.
No order path was changed.

### Dashboard

The `/intelligence` read-only endpoint now exposes the ranked institutional setup
fingerprints. The existing dashboard gets a read-only `INSTITUTIONAL SETUP RADAR`
panel showing location role, OB grade, sequence evidence, conflicts, and early-
expansion status.

## Validation

Targeted strategy + scanner + dashboard validation after the change:

- **127 passed** across OB/zone, early-entry, pre-expansion, institutional radar,
  forecast, deep scanner, adaptive intelligence, fusion, and dashboard tests.
- `python -m compileall -q core strategy scanner portfolio dashboard tests` passes.

The full 91-file isolated release gate was not claimed from this environment after
modification because the local execution window stopped the long-running full suite;
the user's previous machine run had already established 91/91 on the pre-change build.
The modified build should be re-run through the user's release runner before any
release/live deployment decision.
