# BARON — BingX Integration Audit

## Official documentation checked
Current official BingX API material was reviewed from the BingX-API GitHub repository on 2026-09-17.

## Verified semantics used by the patch
1. Perpetual order `positionSide` is `LONG|SHORT` in Hedge Mode and `BOTH` in One-way Mode.
2. `reduceOnly` is used for reducing orders in One-way Mode and is not sent in Hedge Mode.
3. `closePosition` is a conditional-order feature for supported STOP/TAKE-PROFIT market orders; it is not treated as a generic market-close switch.
4. `positionId` is not automatically injected into regular Hedge Mode orders; BingX documents it as required for the Separate Isolated close route.
5. BingX order responses expose both an order id and status/fill fields, and order queries can retrieve filled/cancelled states.
6. Authenticated account WebSocket uses a listenKey; the current official guidance specifies gzip messages, exact Swap `Ping` heartbeat handling, and listenKey renewal.

## BARON implementation
- Signed REST helper supports listenKey create / extend / delete.
- Account WebSocket monitor reconnects and degrades safely.
- Position-mode lookup is cached briefly and is fail-closed in LIVE when unavailable.
- Generic market close/open parameter generation no longer assumes Hedge Mode.
- Native protection parameters use `stopPrice` and mode-aware `positionSide` / `reduceOnly` semantics.
- Existing close verification remains mandatory: order acknowledgement alone never commits CLOSED.

## Explicit limitations
- No real-money BingX order was executed during this audit.
- The current environment does not have the live `ccxt` / Flask dependencies available, and no credentials were used.
- The Separate Isolated `positionId` close route is exposed as a documented integration point rather than being guessed from an ambiguous `isolated` boolean.
