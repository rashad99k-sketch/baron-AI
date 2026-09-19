# BARON Professional Market-State + Dynamic Trade Management Design

**Date:** 2026-09-17  
**Baseline:** `BARON_INSTITUTIONAL_ENTRY_PRO_RELEASE_2026-09-17` (current uploaded release)  
**Status:** Design for review — implementation is intentionally gated until this document is approved.

## 1. Objective

Upgrade BARON from a strong structural-entry system into a professional evidence-driven market analyst and per-position manager while preserving the high-risk execution kernel and all existing portfolio constraints.

The upgrade has four primary outcomes:

1. A first-class market-state layer that recognizes **Accumulation, Re-Accumulation, Markup, Trend Pullback, Distribution, Re-Distribution, Markdown, Transition, and Unknown** from multiple independent evidence streams.
2. EMA50/EMA200 and VWAP become explicit context/transition/value signals rather than simplistic crossover triggers.
3. Each open position receives an individualized management thesis, dynamic protection, TP1/TP2, pullback/reversal interpretation, and monotonic trailing behavior based on the setup that created the trade.
4. BingX is treated as the execution state machine and source of truth for fills, position quantity, protection orders, and final close state.

The design does **not** promise or encode a guaranteed win rate. It is intended to improve selectivity, timing, thesis continuity, and loss containment while eliminating false local execution state.

## 2. Baseline and Preservation Rules

The current uploaded release is the only official baseline for this upgrade. Older BARON ZIPs or earlier branches are not valid replacement baselines.

The following remain preserved unless a surgical correctness fix is required by this design:

- Existing Dashboard, Telegram, Scanner, RF engine, execution kernel, Flask routes, metrics, logs, health endpoints, SmartMoney/Momentum/Continuation engines, portfolio sizing, leverage logic, and TradeStateMachine architecture.
- `UnifiedTradeManagementBrain` remains the final decision authority for management actions, but it never calls exchange APIs directly.
- `ExecutionService` remains the application action boundary.
- Existing strict close verification remains mandatory.
- TP structure remains exactly **TP1 = first 50%** and **TP2 = remaining 50%**. No third profit stage is introduced.
- The portfolio hard cap remains **6 total positions = 5 Technical/Institutional + exactly 1 independent News slot**. News does not consume a technical slot and technical flow cannot create additional News slots.
- RF parameters and the existing RF sequence are not redesigned.
- Closed candles remain authoritative for confirmed market structure, liquidity, zone, and phase evidence. Live price may refine execution timing but cannot create a confirmed structural event from an unfinished candle.

## 3. Research Findings That Shape the Design

### 3.1 EMA50/EMA200 crossover

EMA uses greater weight on recent observations, but moving averages remain reactive/lagging indicators. TradingView explicitly describes moving averages as interpretive/confirmation tools rather than predictive signals, and notes that the 50/200 combination is commonly used for longer-term trend context. Crossovers combine two lagging series, so a crossover can confirm a transition after meaningful price movement has already occurred.

**Design consequence:**

- EMA200 = macro/regime context.
- EMA50 = active trend/mean-reversion context.
- EMA50/EMA200 spread = directional separation and transition pressure.
- EMA50/EMA200 slope = trend acceleration/deceleration evidence.
- Recent cross = `TREND_TRANSITION_EVIDENCE`, never a direct BUY/SELL trigger.
- A cross has different meaning depending on price location, VWAP acceptance, structure, liquidity behavior, and volume/effort-result.

### 3.2 VWAP

TradingView defines VWAP as cumulative volume-weighted typical price and describes it as a tool commonly used on intraday charts to interpret directional/value context. Session anchoring resets the cumulative calculation at the chosen anchor period, while Anchored VWAP starts from a selected point.

**Design consequence:**

- Session VWAP is the primary value/acceptance reference.
- `ABOVE`, `BELOW`, `AT`, slope, distance, reclaim, and rejection are explicit evidence fields.
- Optional Anchored VWAP evidence may be calculated from the thesis-origin bar or another deterministic event anchor when the data contract permits it.
- VWAP never creates a trade by itself.
- Price above VWAP is not automatically BUY; it becomes meaningful when combined with structure, trend context, liquidity response, and effort/result.

### 3.3 Accumulation / Distribution

Wyckoff-oriented research treats Accumulation and Distribution as processes that build Cause before the subsequent Markup or Markdown. The evidence is behavioral and sequential: supply/demand changes, absorption, trading-range behavior, tests/sweeps, and effort versus price Result. High effort with a weak result can warn of opposing supply/demand rather than confirming continuation.

**Design consequence:**

Accumulation/Distribution become first-class **market states**, not simple side labels. A state can persist across multiple candles, strengthen, weaken, or transition into a directional phase.

The engine must explicitly distinguish, where evidence permits:

- Accumulation → Markup
- Re-Accumulation → renewed Markup
- Distribution → Markdown
- Re-Distribution → renewed Markdown
- Range/Transition where the evidence is genuinely ambiguous

The engine must not pretend it knows the hidden intentions of institutional participants. It detects observable market behavior that is consistent with absorption, supply/demand imbalance, liquidity consumption, and effort/result relationships.

### 3.4 Market-microstructure / “algorithmic market behavior”

The exchange exposes order-book depth, recent trades, open interest, contract specifications, and other market data. Independent market-microstructure research finds that short-horizon price changes can be strongly related to order-flow imbalance, while liquidity itself is multi-dimensional and can be approximated using spread, depth, and price impact.

**Design consequence:**

BARON gains a bounded microstructure evidence layer using venue-observable proxies:

- bid/ask spread and spread stability;
- top-of-book imbalance;
- depth concentration/depletion when sufficient depth is available;
- signed trade/aggression proxy from recent trades where buyer/seller role is exposed;
- liquidity consumption near detected pools/zones;
- abnormal volume/price impact;
- open-interest change when available;
- order-book data quality and freshness.

These are **evidence inputs**, not direct access to private institutional algorithms, hidden orders, or proprietary execution logic.

## 4. Proposed Architecture

### 4.1 New market-state engine

Create `core/market_regime_engine.py` as a pure/read-only analyzer.

Input:

```text
OHLCV + timestamps
optional depth snapshot
optional recent trades
optional open interest
existing structure/zone/liquidity/VPA evidence
```

Output:

```text
MarketStateSnapshot
- state
- confidence_score (0..100, not a probability)
- side_bias
- persistence_bars
- transition_state
- EMA50/EMA200 evidence
- VWAP evidence
- structure evidence
- liquidity evidence
- VPA / effort-result evidence
- accumulation/distribution evidence
- microstructure evidence
- invalidation/warning flags
- reasons
- data_quality
- timestamp
```

### 4.2 State machine

The canonical states are:

```text
ACCUMULATION
RE_ACCUMULATION
MARKUP
TREND_PULLBACK
DISTRIBUTION
RE_DISTRIBUTION
MARKDOWN
TRANSITION
UNKNOWN
```

State changes should use persistence/hysteresis rather than switching state on a single noisy observation.

Example directional map:

```text
ACCUMULATION -> MARKUP
MARKUP -> TREND_PULLBACK -> MARKUP
MARKUP -> DISTRIBUTION -> MARKDOWN
MARKDOWN -> TREND_PULLBACK -> MARKDOWN
MARKDOWN -> ACCUMULATION -> MARKUP
Any uncertain conflict -> TRANSITION / UNKNOWN
```

### 4.3 Evidence groups

Each evidence group is independently scored and reason-coded. No single indicator can dominate the complete result.

#### Trend context

- EMA50 relative to EMA200.
- EMA50 slope.
- EMA200 slope.
- EMA50/EMA200 normalized spread.
- recent crossover and cross age.
- price location relative to EMA50 and EMA200.

#### Value/acceptance context

- session VWAP side.
- VWAP slope.
- reclaim/rejection.
- distance from VWAP normalized by ATR.
- optional thesis-anchored VWAP.

#### Structure

- swing highs/lows.
- BOS / MSS / CHoCH evidence.
- structural continuation vs failed break.
- causal Order Block / zone quality.
- FVG / displacement when already supported by the existing engines.

#### Liquidity

- clustered equal highs/lows.
- sweep depth.
- reclaim quality.
- liquidity-pool proximity.
- stop-hunt/rejection behavior.

#### Volume / VPA

- volume ratio.
- spread/body efficiency.
- effort vs result.
- absorption proxy.
- displacement effort/result.
- retest volume contraction/expansion.
- adverse attack at a causal zone.

#### Accumulation/Distribution process

- compression/range persistence.
- repeated tests of supply/demand boundaries.
- spring / upthrust-like observable behavior as evidence labels, without claiming canonical Wyckoff certainty.
- failed breakdown/fakeout followed by reclaim for accumulation evidence.
- failed breakout/fakeout followed by rejection for distribution evidence.
- divergence between effort and price Result.
- whether subsequent rallies/declines show quality consistent with re-accumulation/re-distribution.

#### Microstructure

- depth imbalance.
- spread.
- trade aggression proxy.
- liquidity depletion/refill patterns.
- price impact relative to observed volume.
- OI change where available.

If an input is missing or stale, the engine records `UNAVAILABLE` rather than fabricating evidence.

## 5. Accumulation and Distribution Decision Logic

### 5.1 Accumulation candidate

A bullish Accumulation state requires a combination of:

- bounded/compressing range or repeated failed downside attempts;
- sell-side liquidity sweep or failed breakdown;
- evidence that selling effort is producing limited downside Result;
- absorption/effort-result support where available;
- demand-zone/causal-OB context;
- improving structure or reclaim behavior.

A transition to Markup requires subsequent confirmation such as:

- bullish displacement;
- MSS/BOS or equivalent structural confirmation;
- successful reclaim of the relevant liquidity/zone;
- supportive VWAP acceptance;
- no excessive entry distance.

### 5.2 Distribution candidate

A bearish Distribution state is the mirror process:

- bounded/compressing range or repeated failed upside attempts;
- buy-side liquidity sweep or failed breakout;
- high effort with weak upside Result / evidence of supply;
- supply-zone/causal-OB context;
- rejection and structure deterioration.

A transition to Markdown requires subsequent bearish displacement and structural confirmation.

### 5.3 Re-Accumulation vs Distribution

The engine must not classify every post-uptrend range as Distribution. After an uptrend, a range is `RE_ACCUMULATION` only when subsequent tests, volume/result behavior, and attempted breakdowns remain consistent with continuation. Failure to reclaim/hold resistance, repeated lower highs, persistent supply behavior, and bearish structure shift move the state toward `DISTRIBUTION`.

The mirrored logic applies to `RE_DISTRIBUTION` after a downtrend.

## 6. Entry Design

The existing `InstitutionalEntryEngine` remains the entry gate and consumes `MarketStateSnapshot` instead of duplicating phase logic.

### 6.1 BUY

A professional BUY candidate is strongest when the sequence is approximately:

```text
ACCUMULATION / RE_ACCUMULATION evidence
    -> liquidity sweep / failed downside
    -> reclaim / absorption
    -> bullish MSS/BOS
    -> bullish displacement
    -> causal demand/OB retest OR controlled early continuation
    -> VWAP acceptance/reclaim
    -> EMA50/EMA200 context supportive
    -> EARLY or CONFIRMED entry window
```

For TREND_PULLBACK:

```text
MARKUP
    -> controlled pullback
    -> price interacts with EMA50 and/or VWAP and/or causal zone
    -> EMA200 remains intact
    -> structure remains intact
    -> rejection/continuation evidence
    -> re-acceleration
```

### 6.2 SELL

The mirror sequence applies:

```text
DISTRIBUTION / RE_DISTRIBUTION
    -> buy-side sweep / failed upside
    -> rejection / supply evidence
    -> bearish MSS/BOS
    -> bearish displacement
    -> causal supply/OB retest OR controlled early continuation
    -> VWAP rejection/acceptance below
    -> EMA50/EMA200 context supportive
    -> EARLY or CONFIRMED entry window
```

### 6.3 EMA cross rule

`BULLISH_RECENT` and `BEARISH_RECENT` are stored as transition evidence with age and persistence.

The system must explicitly reject this pattern:

```text
EMA50 crosses EMA200 -> BUY
EMA50 crosses back -> SELL
```

unless structural/liquidity/volume/VWAP evidence independently confirms the thesis.

## 7. Entry Window and Anti-Chase

Keep the current EARLY / CONFIRMED / EXPANDED / LATE concept.

Enhance it with:

- distance from liquidity origin in ATR;
- distance from causal zone;
- distance from session VWAP;
- displacement age;
- whether the market is already in a mature expansion;
- adverse spread/impact conditions.

`LATE` remains a hard rejection for normal institutional entries.

A strong score cannot override a late/chase classification.

## 8. Individualized Per-Trade Management

Each accepted position receives an immutable **Trade Thesis Snapshot** at entry.

Required fields:

```text
trade_id
symbol / venue symbol
asset_class
side
setup_type
market_state
entry_window
entry_price
ATR
EMA50 / EMA200 / slopes / spread / cross-state
VWAP value / side / slope / distance
liquidity event + level + quality
causal zone / OB + invalidation
MSS/BOS/CHoCH evidence
VPA summary
microstructure summary (when available)
initial SL
TP1 / TP2 map
thesis fingerprint
```

A later market snapshot is compared against this thesis. Management decisions therefore answer:

- Is the original thesis still valid?
- Is the current move healthy continuation?
- Is this a normal pullback?
- Is price distributing against the position?
- Has the invalidation condition actually occurred?
- Is the position profitable enough that protection should ratchet?
- Has a stop event been a genuine failure or a likely liquidity stop-hunt?

## 9. Management State Machine

Suggested management states:

```text
OPENING_PROTECTION
HEALTHY_MOVE
HEALTHY_PULLBACK
VWAP_RECLAIM
DISTRIBUTION_DEFENSE
PROFIT_PROTECTION
RUNNER
THESIS_FAILURE
CLOSE_PENDING
CLOSED_VERIFIED
RECOVERY
UNKNOWN
```

### BUY healthy pullback

Hold when:

- EMA200 remains structurally intact;
- EMA50 remains supportive or is being reclaimed;
- VWAP is supportive/reclaimed;
- local swing structure has not materially failed;
- no strong bearish displacement + acceptance occurs;
- VPA does not show a confirmed adverse attack at the thesis zone.

### BUY reversal / defense

Escalate toward profit defense when there is a combination of:

- sustained EMA50 loss;
- VWAP loss;
- failed reclaim;
- bearish displacement;
- meaningful swing failure;
- worsening VPA / supply evidence.

EMA200 break plus a meaningful structural failure is the strongest thesis-failure signature.

SELL is mirrored symmetrically.

EMA/VWAP alone never issue a close.

## 10. Dynamic SL

Initial SL is based on the **invalidation that makes the trade thesis false**, then buffered adaptively.

Examples:

- liquidity-reversal trade → beyond sweep extreme + structural/volatility buffer;
- trend-pullback → beyond pullback structure / causal zone invalidation;
- early expansion → beyond expansion origin / structure invalidation;
- high-volatility symbol → wider ATR-derived buffer only when required by venue/market characteristics.

Protection is monotonic:

- never loosen a confirmed live stop through normal management;
- movement toward break-even / profit is allowed;
- contradictory signals must not silently reduce existing protection.

## 11. TP1 / TP2 and Dynamic Profit Handling

The canonical structure remains:

```text
TP1 = 50% of the original position
TP2 = remaining 50%
```

Targets are dynamic and selected from:

- opposing liquidity;
- opposing causal zones;
- structural objectives;
- ATR/volatility context;
- setup-specific continuation room.

There is no universal fixed percentage target added by this design.

### TP1 event

TP1 must be driven by a verified exchange position snapshot and actual fill quantity.

Flow:

```text
Unified Brain decides TP1
-> ExecutionIntent
-> exchange reduction order
-> capture venue order id
-> query order status / executed quantity / fill information
-> fetch exchange position
-> calculate actual reduction
-> only then commit TP1 progress
-> re-arm/adjust protection to actual remaining qty
-> reconcile internal vs exchange state
```

A requested quantity is not treated as executed quantity.

### TP2 / final close

Flow:

```text
Brain decides TP2 / EXIT
-> pre-close exchange snapshot
-> reconcile protection conflicts
-> strict close operation
-> verify order id/status/executed qty/fills
-> fetch live position
-> require zero position before CLOSED_VERIFIED
-> otherwise RECOVERY / retry / reconciliation
```

BARON must never mark a position closed solely because a close request was accepted or a local variable changed.

## 12. BingX Exchange State Machine

The canonical external lifecycle is:

```text
BARON Decision
    -> Execution Intent
    -> BingX Order
    -> Order State
    -> Fill State
    -> Position State
    -> Protection State
    -> Reconciliation
    -> Internal State
```

### 12.1 Position mode

The engine reads the venue's current position mode and fails closed in LIVE if the mode is unknown.

- Hedge Mode: `positionSide=LONG` or `SHORT`; do not send `reduceOnly`.
- One-way Mode: `positionSide=BOTH`; `reduceOnly` may be used for reductions/closures.
- `closePosition` remains restricted to the documented conditional-order semantics; it is not treated as a generic market-close switch.
- `positionId` is supplied only when the selected BingX route actually requires it, such as Separate Isolated close behavior.

### 12.2 Venue trading rules

Before a live order, BARON uses current contract/rule metadata when available to derive:

- symbol validity;
- quantity precision;
- price precision;
- minimum quantity;
- minimum USDT notional;
- contract state / API open-close state;
- maximum leverage constraints.

The bot must never infer asset class solely from a symbol suffix such as `USDT`.

### 12.3 Order identifiers

Venue order IDs are stored as strings at the internal boundary so precision cannot be lost.

The current BingX API documentation states that `clientOrderId` is supported for `MARKET` and `LIMIT` only. Therefore the native protection path must not inject BARON `clientOrderId` into `STOP_MARKET`/other conditional protection orders unless a separately verified venue route explicitly supports it.

BARON continues to use its own `trade_id` / thesis fingerprint / protection key for local correlation, while the venue order ID is the exchange truth.

### 12.4 Native protection isolation

Protective-order registry key must become:

```text
(normalized_symbol, normalized_position_side)
```

not symbol alone.

This is mandatory to prevent a Hedge LONG protection update/cancel from mutating the SHORT protection record.

Place-first / cancel-second replacement remains the preferred sequence so a failed replacement does not intentionally create a protection gap.

## 13. Live Safety and Recovery

All critical live operations are bounded and idempotent.

Required behavior:

- timeouts on network operations;
- bounded retries with backoff;
- single-flight close/protection operations;
- no indefinite locks;
- no duplicate close orders from concurrent management loops;
- explicit `RECOVERY` state on uncertain provider state;
- fail closed when live position/protection state cannot be verified;
- no “success” log until the documented post-condition is observed.

### Emergency cancellation watchdog

BingX's `cancelAllAfter` kill-switch may be used as an emergency safety mechanism, but it is **not** a normal trailing mechanism because it cancels all open orders, including protective orders. Any use must be explicitly scoped, followed by protection re-installation and exchange verification.

## 14. Data Quality Rules

Every market-state snapshot carries data-quality metadata.

If depth, trades, OI, or another optional source is stale/unavailable:

- remove that evidence from the score;
- record the omission;
- never fabricate neutral values that look like real observations;
- allow the existing required structural pipeline to continue when the missing source is not mandatory for that setup.

If a source is mandatory for a LIVE safety condition, fail closed instead.

## 15. Asset-Class Behavior Profiles

The market-state engine is asset-class agnostic at the architecture level.

Each supported asset can consume the same evidence grammar while respecting its existing execution/risk profile. The venue's contract metadata and BARON's current symbol classification determine whether the instrument is crypto, stock/perpetual, index, metal, energy, or another supported class.

No new sizing or leverage model is introduced in this feature.

## 16. News Slot Preservation

The independent News Trading slot stays exactly one.

Market-state intelligence can inform global context and risk, but News remains a separate decision path and cannot silently become an additional technical position or create more than one News slot.

## 17. Observability / Forensics

Every entry and management decision records enough evidence to reconstruct why BARON acted.

Required forensic fields include:

```text
trade_id
symbol
side
setup_type
market_state
EMA50 / EMA200 / slope / spread / cross age
VWAP side / slope / reclaim / distance
accumulation/distribution evidence
liquidity evidence
OB/zone quality
MSS/BOS/CHoCH
VPA effort/result
microstructure evidence and data quality
entry_window
initial SL reason
TP1/TP2 target reasons
actual TP1 executed qty
actual exchange position qty
protection order id / position side
management state transitions
stop-event classification
stop-hunt re-entry decision
final close order id / fills / verified zero state
PnL / fees when available
```

The confidence score is an evidence-strength score bounded to 0..100. It must not be labeled or exposed as a mathematical probability of profit.

## 18. Planned File Boundaries

### Create

- `core/market_regime_engine.py`

### Modify

- `core/institutional_entry_engine.py` — consume market-state evidence; remove duplicated phase/behavior contradictions.
- `core/trade_intelligence.py` — preserve compatible public interfaces while routing accumulation/distribution evidence to the authoritative market-state logic where appropriate.
- `core/ema_vwap_trade_management.py` — add state-aware per-position interpretation and stronger hysteresis while keeping it pure/read-only.
- `core/unified_trade_management_brain.py` — aggregate market-state + trade-thesis + management evidence into the final action decision while remaining exchange-free.
- `core/engine.py` — only surgical integrations/correctness fixes; preserve existing exchange kernel and strict close authority.
- `execution/execution_service.py` — strengthen intent/idempotency/verified-quantity boundaries without moving decision logic into execution.
- `execution/reconciliation.py` — extend from quantity comparison to order/fill/position/protection postconditions.
- `portfolio/native_protection.py` — isolate LONG/SHORT records, remove unsupported conditional `clientOrderId` behavior, and preserve place-first/cancel-second protection updates.

### Test additions/updates

- market-state classifier tests;
- accumulation/distribution transitions;
- re-accumulation vs distribution disambiguation;
- EMA cross as context-only evidence;
- VWAP reclaim/rejection and session anchor behavior;
- healthy pullback vs thesis-failure management;
- dynamic SL monotonicity;
- actual TP1 fill quantity vs requested quantity;
- TP1 protection re-arm using actual remaining position;
- TP2 strict zero-position closure;
- Hedge LONG/SHORT protection isolation;
- conditional-order clientOrderId regression;
- venue rule/precision fail-closed behavior;
- recovery/idempotency/concurrent close behavior.

## 19. Testing and Release Gate

Implementation must use TDD for each change.

Validation sequence:

1. Targeted pure-unit tests for each new evidence block.
2. Existing institutional-entry and EMA/VWAP regression tests.
3. Execution/protection/position-side regression tests.
4. Isolated execution of every test module to detect hangs and shared-state leakage.
5. Paper runtime full lifecycle:

```text
venue discovery
-> candidate analysis
-> BUY/SELL qualification
-> simulated entry
-> protective SL install
-> healthy pullback
-> TP1 50%
-> protection re-arm
-> continuation/trailing
-> TP2 remaining 50%
-> verified zero position
-> ledger/reconciliation
```

6. Repeat the isolated release gate enough times to prove deterministic lifecycle behavior.
7. Only after offline/paper validation may a separate controlled live-readiness check occur.
8. No real-money trade is part of the implementation test suite.

## 20. Live-Ready Acceptance Criteria

The implementation is blocked from live trading unless all of these are true:

- EMA crossover alone cannot open a position.
- VWAP alone cannot open or close a position.
- Accumulation and Distribution are first-class, reason-coded market states.
- Re-Accumulation and Re-Distribution are not collapsed into Distribution/Accumulation by default.
- Late/chase entries are rejected.
- Every live position receives verified protection before the internal lifecycle becomes fully managed.
- Hedge LONG and SHORT protection state is isolated.
- Conditional protection orders do not use unsupported `clientOrderId` semantics.
- TP1 progress is based on actual exchange fills/position quantity, not requested quantity.
- TP2/final closure cannot become `CLOSED_VERIFIED` without exchange-confirmed zero position.
- Protection never loosens through normal management.
- Concurrent close requests are single-flight/idempotent.
- Missing/ambiguous live exchange state fails closed or enters explicit recovery.
- Six-position capacity and the single independent News slot remain unchanged.
- No release claim is based on a timed-out or incomplete test runner.

## 21. Explicit Limits

This design does not claim:

- direct visibility into hidden institutional orders;
- perfect detection of “smart money”; 
- deterministic prediction of the next candle;
- guaranteed profit or win rate;
- that accumulation/distribution labels are certain before subsequent market confirmation.

The professional behavior comes from combining multiple observable evidence streams, treating uncertainty explicitly, and making execution state authoritative rather than from pretending any single indicator can predict the market.

## 22. Research Sources

- TradingView — Exponential Moving Average: https://www.tradingview.com/support/solutions/43000592270-exponential-moving-average/
- TradingView — Moving Averages: https://www.tradingview.com/support/solutions/43000502589-moving-averages/
- TradingView — VWAP: https://www.tradingview.com/support/solutions/43000502018-volume-weighted-average-price-vwap/
- TradingView — Anchored VWAP: https://www.tradingview.com/support/solutions/43000669764-anchored-vwap-drawing-tool/
- StockCharts — The Laws of Wyckoff: https://articles.stockcharts.com/article/articles-wyckoff-2015-12-the-laws-of-wyckoff/
- StockCharts — Distribution or Re-Accumulation?: https://articles.stockcharts.com/article/articles-wyckoff-2022-03-distribution-or-reaccumulation-699/
- StockCharts — Distribution Definitions: https://stockcharts.com/articles/wyckoff/2015/09/distribution-definitions.html
- Cont, Kukanov & Stoikov — The Price Impact of Order Book Events: https://arxiv.org/abs/1011.6402
- BIS — Regulation and liquidity provision: https://www.bis.org/speeches/20151001-regulation-and-liquidity-provision
- BingX-API — Perpetual Swap Trade API Reference: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-trade/api-reference.md
- BingX-API — Swap Market Data API Reference: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-market/api-reference.md
- BingX-API — Swap Account API Reference: https://github.com/BingX-API/api-ai-skills/blob/main/skills/swap-account/api-reference.md

## 23. Implementation Gate

This document intentionally stops before code modification.

After approval, the next process step is to create the detailed implementation plan from this design. Implementation then proceeds task-by-task with tests, verification, and runtime validation checkpoints.
