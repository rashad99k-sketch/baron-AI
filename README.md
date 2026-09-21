# BARON — RF Liquidity Pro

**Modular Windows Build | Multi-Market | BingX Futures | PAPER/LIVE | Render-Ready**

---

## Overview

BARON is a production-grade trading system built around the **RF Liquidity Pro v28** trading brain. It adds:

- **Portfolio orchestration** — up to 6 concurrent positions across CRYPTO, STOCKS, INDICES, GOLD, OIL
- **Dynamic Deep Scanner** — venue-driven universe discovery, institutional evidence gating, execution queue
- **News intelligence** — RSS macro/symbol feeds, event classification, risk scoring (advisory only)
- **Flask dashboard + HTTP API** — real-time positions, pipeline accounting, manual controls (token-gated)
- **Forensic/observability layer** — Partition AI, decision-path tracing, trade lifecycle journaling, adaptive trade intelligence
- **Native protection** — exchange-native TP/SL required for LIVE entries (fail-closed)

**Execution venue:** BingX (CCXT). All order execution, position management, and risk logic remain in the preserved RF v28 kernel.

---

## Quick Start — Local (Windows)

```bat
run_windows.bat
```

The launcher:
1. Creates `.venv` if missing
2. Installs `requirements.txt`
3. Creates `.env` from `.env.example` if missing
4. Runs structural verification + isolated regression tests
5. Starts `main.py` → dashboard at `http://127.0.0.1:8000`

**Default mode:** `PAPER_MODE=True` (safe). Never put real API keys in `.env.example`.

---

## Deploy on Render

### 1. Connect Repository

- Push this repository to GitHub
- In Render: **New → Web Service** → connect your repo

### 2. Render Settings (auto-detected from `render.yaml`)

| Setting | Value |
|---------|-------|
| Runtime | Python 3.11+ |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Health Check | `/health` |
| Port | `8000` (injected via `PORT` env var) |

### 3. Required Environment Variables (set in Render Dashboard)

| Variable | Required | Description |
|----------|----------|-------------|
| `PAPER_MODE` | No (default `True`) | `True` = paper trading, `False` = live |
| `BINGX_KEY` | **Yes for LIVE** | BingX API Key |
| `BINGX_SECRET` | **Yes for LIVE** | BingX API Secret |
| `DASHBOARD_CONTROL_TOKEN` | Recommended | Secures `/trade` and `/close` endpoints on public dashboards |
| `TELEGRAM_BOT_TOKEN` | Optional | For close notifications |
| `TELEGRAM_CHAT_ID` | Optional | For close notifications |

> **Never commit real credentials.** Use Render's "Environment" tab → "Add Secret".

### 4. Safety Defaults

- `PAPER_MODE=True` by default (in `render.yaml` and `.env.example`)
- `REQUIRE_NATIVE_PROTECTION_LIVE=1` — LIVE entries **fail-closed** unless exchange-native TP/SL is configured and verified
- `DASHBOARD_CONTROL_TOKEN` empty → manual controls restricted to `127.0.0.1` only

To enable LIVE trading:
1. Set `PAPER_MODE=False`
2. Set `BINGX_KEY` and `BINGX_SECRET`
3. Set `ENABLE_NATIVE_PROTECTION=1` with valid `NATIVE_PROTECTION_PARAMS_JSON`
4. Set `DASHBOARD_CONTROL_TOKEN` (required for public dashboard)

---

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Full dashboard (HTML) |
| `/health` | **Render health check** — returns JSON with system status |
| `/metrics` | Portfolio, scanner, queue, watchlist stats |
| `/data` | Dashboard data feed (JSON) |
| `/trades` | Trade lifecycle journal (read-only) |
| `/intelligence` | Institutional setups, flow, news reactions |
| `/ai-learning` | Adaptive trade intelligence summary |
| `/radar` | Deep institutional radar snapshot |
| `/early-moves` | Early entry signals |
| `/data-fabric` | Normalized evidence view (OpenBB-inspired) |
| `/trade` | **POST** — manual entry (token-gated) |
| `/close` | **POST** — manual close (token-gated) |

---

## Forensic / Observability Layer

The following components are **observational only** — they never place, modify, or close orders:

| Component | Purpose | Output |
|-----------|---------|--------|
| `Partition AI` | Post-exit classification, continuation probability, confidence | `runtime/partition_ai/*.jsonl` |
| `Decision Path Trace` | Full reason chain: STRONG → Waiting → READY → Trade | `runtime/decision_path_trace.jsonl` |
| `Trade Lifecycle Journal` | Open/close/partial/update events with full context | `runtime/trade_lifecycle.jsonl` |
| `Adaptive Trade Intelligence` | Setup fingerprint learning, outcome memory, playbook | `runtime/adaptive_trade_intelligence.jsonl` |
| `Setup Outcomes` | Edge analysis per setup type | `runtime/setup_outcomes.jsonl` |

All forensic data persists as **JSONL** in `runtime/` (git-ignored).

---

## Project Structure

```
/
├── main.py                    # Entrypoint → app.bootstrap.run()
├── app/
│   └── bootstrap.py           # Startup orchestration, PORT binding, thread mgmt
├── dashboard/
│   ├── app.py                 # Flask app + all HTTP endpoints
│   └── __init__.py
├── core/
│   ├── engine.py              # Preserved RF v28 kernel (execution authority)
│   ├── config_loader.py       # .env loading, protection config
│   ├── trade_intelligence.py  # Advisory trade classification
│   └── decision_journal.py    # Hash-chained decision log
├── scanner/                   # Deep scanner, radar, queue, promotion
├── strategy/                  # Strategy facade, institutional analysis
├── portfolio/                 # Multi-position manager, allocator, runtime
├── execution/                 # BingX order entry boundary
├── news/                      # RSS intelligence, event classification
├── config/                    # Centralized runtime settings
├── runtime/                   # Persistent state (git-ignored)
├── tests/                     # Isolated regression test suite
├── tools/                     # Bootstrap, test runners
├── forensic_pipeline.py       # Offline deterministic pipeline trace
├── baron_zone_judge.py        # Institutional zone analysis
├── requirements.txt           # Runtime deps (ccxt, pandas, numpy, Flask, requests, python-dotenv, websocket-client)
├── requirements-runtime.txt
├── requirements-dev.txt
├── render.yaml                # Render blueprint
├── Procfile                   # web: python main.py
├── .env.example               # Safe template (no secrets)
├── .gitignore
├── run_windows.bat            # Windows launcher
└── README.md
```

---

## Safety & Risk

- **PAPER_MODE defaults to `True`** — live trading requires explicit opt-in
- **Native protection required for LIVE** — `REQUIRE_NATIVE_PROTECTION_LIVE=1` blocks live entries without exchange-verified TP/SL
- **Dashboard controls are local-only** unless `DASHBOARD_CONTROL_TOKEN` is set
- **Forensics are read-only** — no execution authority
- **No hard-coded secrets** — all credentials via environment variables

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run isolated test suite (each module in fresh process)
python tools/run_isolated_tests.py

# Verify project compiles
python verify_project.py
```

---

## License

Proprietary — internal use only.