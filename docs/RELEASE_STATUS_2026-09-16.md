# BARON Release Status — 2026-09-16

## Implemented
- Preserved the existing RF / portfolio / execution / Unified Trade Management authorities.
- Preserved the existing two-stage TP contract: TP1 = 50% of original size; TP2 = remaining 50%.
- Preserved the six-position policy: 5 technical/institutional + 1 independent news slot.
- Institutional evidence stack includes liquidity sweep, causal order block, market structure, premium/discount, VPA, VWAP, EMA50/EMA200, ADX/DI, ATR, RSI and MACD.
- Added deterministic temporal/sequence-oriented institutional evidence semantics.
- Added dependency-free forecast evidence with multi-horizon paths, dispersion and uncertainty, wired as advisory evidence only.
- Kept external intelligence/news advisory and hard execution/risk fail-closed.

## Validation performed
- `python -m compileall -q core strategy scanner portfolio tests` — PASS
- `python verify_project.py` — PASS
- `python tools/paper_runtime_smoke.py` — PASS
- Forecast + institutional evidence + ready-grace + TP12 + six-slot targeted suite — 35/35 PASS
- Profit engine + unified authority + registry + lifecycle + six-slot targeted suite — 51/51 PASS
- Additional individually executed runtime/portfolio/news/OB/data suites — PASS (one portfolio accounting test skipped by its own fixture contract)

## Environment boundary
- Full monolithic pytest run does not complete within the available execution window; it reaches the mid-suite without assertion failure but exceeds the runtime budget. This is recorded as a release-environment limitation, not converted into a PASS.
- Dashboard runtime check is blocked in this environment because the required `flask` and `ccxt` packages are not installed.
- No real-money BingX order was submitted.

## 2026-09-16 Adaptive Intelligence + Windows Bootstrap Hardening

### Windows startup incident
The Windows launcher was treating one `pip install -r requirements.txt` attempt as a single point of failure. The observed console error was a low-level HTTP/transport connection abort with a Windows access-violation-style `OSError` while pip was downloading/installing a dependency. This is a bootstrap/runtime-environment failure, not evidence that the trading strategy itself failed.

### Fix
- Added `tools/bootstrap_dependencies.py`.
- Uses `--no-cache-dir`, binary preference, bounded retries/timeouts, and a clean pip-cache purge on recovery.
- If the aggregate install fails, dependencies are retried individually so one bad download does not hide the actual failing package.
- `run_windows.bat` now calls the recovery bootstrap instead of a single unbounded pip install.

### Adaptive Trade Intelligence
- Added `core/adaptive_trade_intelligence.py`.
- Captures immutable entry fingerprints from closed-candle data: liquidity/structure/OB/VPA/institutional evidence, market regime, maturity, session, forecast quality, ADX, VWAP and EMA context.
- Labels verified outcomes as `EXPLOSIVE_WIN`, `STRONG_WIN`, `PROFITABLE`, `WEAK_ENTRY`, or `LOSS` using configurable thresholds.
- Dashboard now exposes a read-only AI Trade Coach panel with live setup diagnosis, recent lessons, and repeated strong/explosive patterns.
- Historical similarity requires a minimum sample size before an edge is shown.
- **No live strategy self-mutation:** the learner is advisory/research memory only. It cannot alter thresholds, leverage, execution, portfolio capacity, or the UnifiedTradeManagementBrain.

### Validation after changes
- `verify_project.py` — PASS.
- `compileall` — PASS.
- Targeted BARON regression/intelligence/dashboard/profit/portfolio suite — **150/150 PASS**.
- Paper runtime smoke — PASS.
- The monolithic isolated release runner still exceeds the environment execution budget when run end-to-end; this remains a release-environment limitation and is not reported as a PASS.
- No live BingX order was submitted.
