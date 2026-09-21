- Early institutional preparation is now a fast path: one high-value precursor starts Institutional Zone Analysis immediately; two or more precursor signals can mark the candidate PREPARED_FOR_ENTRY and enter the execution queue for live confirmation.
- A-GRADE remains preferred but is no longer a mandatory intermediate stop before queue preparation; final trigger/zone/ATOM/risk gates remain mandatory.
# Changelog — RF Liquidity Pro

## 2026-09-05 — Institutional Pipeline Separation Repair

### Pipeline
- Separated `WATCHLIST / ACTIVE CANDIDATES` from `INSTITUTIONAL ZONE ANALYSIS`.
- `MEDIUM` is now an analysis trigger only; it is never an execution-queue admission.
- Added a dynamic institutional-zone registry driven by MEDIUM/STRONG + institutional precursor evidence.
- Institutional-zone membership now rotates automatically when evidence disappears, a setup expires, or the phase becomes overextended/exhausted.
- Added explicit `A-GRADE_READY` qualification before execution-queue admission.
- Execution Queue is now downstream of Institutional Zone Analysis and accepts only explicit A-grade candidates.

### Deep Analysis
- Preserved the zone-first institutional sequence: liquidity/sweep, displacement, MSS/BOS/CHoCH, OB, FVG/imbalance, retest/mitigation, rejection, volume/flow, HTF, session, news, expansion/exhaustion and entry geometry.
- Added dashboard visibility for the dynamic Institutional Zone Analysis population separately from the Execution Queue.

### Reliability
- Fixed the promotion-path type error caused by attempting `float("WAIT_RETEST")`; timing labels are now kept as labels while numeric timing scores use a defensive numeric conversion.
- Removed the automatic `PRE_ENTRY_READY -> queue` shortcut.

### Validation
- Project compile/verify passes.
- Targeted institutional/promotion regression suite: 49 passed, 1 skipped.


## 2026-08-19

### Architecture
- Reduced `main.py` to startup/orchestration only.
- Added explicit `strategy`, `portfolio`, `execution`, `news`, `config`, and `scanner/deep_scanner` boundaries.
- Preserved the supplied 9,885-line source as `source_original_mBOT_1.py`.
- Kept the existing RF/Institutional core as the compatibility kernel instead of performing a risky all-at-once rewrite.

### Portfolio
- Added per-symbol state isolation around the legacy single-position engine.
- Added configurable `MAX_OPEN_POSITIONS` with default 6.
- Added portfolio ranking and multi-position supervision.
- Dashboard now displays all active positions and available capacity.
- Manual dashboard trades use the same portfolio boundary.

### Deep Scanner
- Added venue-wide crypto discovery.
- Added configurable Gold/Oil/Index/Stock symbols with strict venue validation.
- Added institutional scoring, momentum/flow evidence, narrative evidence, and news risk adjustment.
- Added ranked portfolio candidates.

### News
- Added optional RSS event-risk service.
- News is advisory only; unavailable feeds do not block the strategy.

### Reliability
- Fixed the paper-mode close/finalization ordering bug.
- Added a safe fallback for paper-mode mark price during finalization.
- Fixed runtime orchestration so `keep_alive` and `safe_main_loop` are actually provided by `core.runtime`.
- Expanded compile and structural tests.

### Validation
- Full first-party Python compilation passes.
- Portfolio isolation test passes.
- News scoring test passes.

## Known limitation
Live non-crypto execution requires the connected broker/exchange to expose those instruments. The build deliberately does not fake support for assets that are absent from the venue.

## 2026-08-19 — Windows Test Runner Hotfix
- Fixed `tests/test_news_service.py` leaking a fake `requests` module into `sys.modules`.
- The leak caused the dashboard import test to fail inside CCXT with `cannot import name 'Session' from requests`.
- News tests now patch `requests.get` locally without replacing the real Requests package.

## 2026-08-19 — Modular Portfolio + Deep Radar Hardening

- Fixed dashboard `/` crash caused by an unescaped JavaScript object literal inside a Python f-string.
- Added canonical `core.engine.get_smart_zones()` so strategy/deep paths do not depend on scanner import order.
- Upgraded DeepScanner to staged venue-wide radar -> deep institutional analysis -> news risk -> ranked candidates.
- Added asset-class discovery for crypto, gold, oil, indices and venue-exposed stocks.
- Kept non-supported instruments explicit: unavailable venue instruments are skipped, never fabricated.
- Enabled six-position portfolio capacity with portfolio-safe default sizing: 10% margin per position and 60% aggregate cap.
- Added configurable per-asset-class exposure cap.
- Added Deep Institutional Radar panel to the existing dashboard.
- Added regression tests for the dashboard crash, smart-zone provider and six-position sizing policy.

## 2026-08-20 — Institutional Queue Hardening

- Changed the engine's implicit default to PAPER mode when `PAPER_MODE` is absent; LIVE still requires explicit credentials and `PAPER_MODE=False`.
- Reworked Execution Queue order-block scoring to require a causal displacement leg, volume support, freshness/touch count, and broken-zone detection instead of treating the latest candle wick as an order block.
- Added a hard institutional readiness gate: READY now requires persistent confirmation plus minimum order-block, liquidity, institutional-confidence, and structure scores.
- Added regression coverage for fake-vs-causal order blocks, the institutional READY gate, and safe paper defaults.
- Windows launcher now installs dependencies only when imports are missing, avoiding unnecessary network/package operations on every restart.

## 2026-09-03 — External Intelligence + reliability hardening
- Added alert-only Finviz/OpenInsider/SEC EDGAR intelligence providers.
- Added multi-source evidence fusion with conservative BUY-bias gating.
- Added dashboard publication and Telegram alerting for high-confidence external setups.
- Added bounded HTTP timeout/cache/retry layer for external providers.
- Set CCXT exchange timeout from environment (default 10s).
- Removed packaged `.env` credentials and sanitized `.env.example`.
- Updated stale pipeline test expectation to match the existing ATOM hard-reject invariant for over-mitigated zones.

## 2026-09-05 — Research/Production Hardening

- Added a persistent, hash-chained decision journal for structured gate/veto audit events; persistence is best-effort and never a trading dependency.
- Added a side-effect-free OHLCV integrity audit utility covering duplicate/non-monotonic timestamps, invalid OHLC relationships, non-positive values, and stale data.
- Preserved the existing Institutional Precursor → Institutional Zone → A-GRADE → Execution Queue architecture and all production risk/position limits.

- FIX: runtime scanner promotion now admits PREPARED_FOR_ENTRY precursor clusters (>=2) into Execution Queue for live re-evaluation; A-GRADE remains preferred but is no longer mandatory.
- FIX: queue admission labels distinguish PREPARED_ADMITTED from A_GRADE_ADMITTED.
- SAFETY: no direct entry is created by preparation; fresh zone/trigger/confirmation/ATOM/portfolio/risk/execution gates remain authoritative.

## 2026-09-07 — Final trade-management hardening pass

- Centralized TP1/TP2 execution through the canonical two-stage profit adapter.
- Enforced strict 50% TP1 + 50% TP2 lifecycle and post-TP1-only runner mode.
- Removed legacy main-loop execution bypasses for council exits and scaling.
- Hardened PAPER finalization price fallback and dashboard state reads.
- Added unified trade-authority regression coverage.
- Added final release validation report covering trade management, ROI/PnL, news reaction, UI telemetry, reconciliation and reference-project extraction.

## 2026-09-16 — BARON intelligence consolidation
- Added dependency-free `core/forecast_evidence.py` for multi-horizon,
  multi-path forecast evidence with explicit uncertainty and ATR normalization.
- Wired forecast evidence into queue re-evaluation, execution context and
  candidate observability without granting it execution authority.
- Added Kronos/Vibe integration documentation and preserved the single-decision
  authority model.
- Added deterministic forecast evidence tests; targeted regression suite remains
  green after integration.

## 2026-09-16 — Adaptive Intelligence / Windows Bootstrap Hardening
- Added deterministic Adaptive Trade Intelligence memory and setup fingerprint learning.
- Added explosive/strong/weak trade outcome classification and conservative historical playbook extraction.
- Added read-only `/ai-learning` dashboard API and modern AI Trade Coach panel.
- Captured entry-time EMA50/EMA200, VWAP, ADX/DI, RSI, MACD and ATR features for outcome learning without look-ahead.
- Added Windows dependency bootstrap recovery with clean pip-cache retry and per-package fallback.
- Preserved execution authority, portfolio capacity, TP1/TP2 contract, RF, Smart Money, and Unified Trade Management authority.

## 2026-09-18 — Professional Market-State Continuation
- Added pure `core/market_regime_engine.py` with EMA50/EMA200, session VWAP, accumulation/distribution, structure/liquidity/VPA and observable microstructure evidence.
- Integrated market-state evidence into institutional entry assessments; EMA crossover remains transition evidence rather than a standalone trigger.
- Added per-position market-state context to EMA/VWAP management and preserved EMA/VWAP-only HOLD behavior.
- Added explicit requested-vs-executed quantity and exchange-zero-position fields to reconciliation.
- Corrected native conditional protection parameter generation so unsupported `clientOrderId` is not sent to BingX conditional protection orders.
- Added backend-driven Market State dashboard panel.
- Validation remains BLOCKED for full release because the combined suite is incomplete in this execution environment and live dashboard dependencies are unavailable.

## 2026-09-18 — Professional timing + single management authority hardening
- Enforced an early-transition entry contract for automated technical entries: EMA50/EMA200 crossing onset or the first few closed candles after the cross, with an EMA50 ATR-distance anti-chase bound.
- Added `PRE_CROSS_BULLISH/BEARISH`, `POST_CROSS_EARLY`, `POST_CROSS_DEVELOPING`, and `MATURE` crossing-phase evidence to the canonical Market Regime Engine.
- Unified live management decisions through `UnifiedTradeManagementBrain.evaluate()`; legacy PPE, profit-engine, dynamic-management and stale state-machine branches are compatibility-only and no longer execute runtime management orders.
- Canonical Market State now drives the live management state label, preventing stale `RANGE_CHOP` from surviving while the canonical regime is expanding/markup/pullback.
- Removed direct thesis-failure/profit-lock execution from pre-Brain branches; those signals are evidence only and are converted to one action by the Brain.
- Tightened thesis-failure exits to require a strong negative failure signature or EMA200 + structural failure, avoiding zero-ROE false closes caused by generic distribution labels.
- Reset per-trade protection/management fields on every new entry to prevent confirmed-SL leakage across portfolio symbols.
- Preserved TP1/TP2 execution at 50%/50%, exchange verification, native protection, reconciliation, portfolio capacity and News-slot separation.

## 2026-09-18 — Zone Lifecycle Contract Hotfix
- FIX: `check_institutional_entry()` maturity hard-reject path now preserves the canonical `(bool, classification, reason)` return contract used by all queue/scanner callers.
- FIX: prevents `TypeError: cannot unpack non-iterable bool object` during `ExecutionQueue.re_evaluate_all()` on mature/exhausted synthetic or live candidate frames.
- TEST: added a regression test for the maturity rejection return shape and verified all return paths in the function are three-item tuples.
- PRESERVED: early-transition entry timing, Market Regime authority, Unified Trade Management Brain authority, TP1/TP2 50/50, RF, portfolio capacity and BingX execution/reconciliation architecture.

## 2026-09-19 — Decision Path Telemetry (read-only)
- Added `core/decision_path_telemetry.py` for persistent forensic decision-path events.
- Added separate BUY/SELL scanner hypothesis events and selected-direction events.
- Added queue admission/re-evaluation/state telemetry and Trend v29 gate telemetry.
- Captures EMA50/EMA200, VWAP, ADX, DI+/DI-, and EQH/EQL liquidity evidence at decision time.
- Added `tools/decision_path_trace.py` to filter traces by symbol.
- Added telemetry tests. No strategy thresholds, scores, gates, portfolio rules, SL/TP, RF, or execution behaviour were changed.
