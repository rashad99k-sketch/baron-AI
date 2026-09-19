import json
import numpy as np
import pandas as pd


def _frame(n=80):
    x = np.arange(n, dtype=float)
    close = 100 + x * 0.1
    open_ = close - 0.03
    high = close + 0.05
    low = close - 0.05
    # Confirmed equal highs/lows among swing points.
    for i in (20, 30):
        high[i] = 103.0
    for i in (45, 55):
        low[i] = 104.0
    volume = np.ones(n) * 100
    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="min"),
    })


def test_market_snapshot_contains_forensic_indicators_and_liquidity(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISION_PATH_TRACE_PATH", str(tmp_path / "trace.jsonl"))
    from core.decision_path_telemetry import market_snapshot
    snap = market_snapshot(_frame(), "BUY")
    for key in ("price", "ema50", "ema200", "vwap", "adx", "di_plus", "di_minus", "di_spread", "liquidity"):
        assert key in snap
    assert "legacy_eqh" in snap["liquidity"]
    assert "legacy_eql" in snap["liquidity"]
    assert "eqh_levels" in snap["liquidity"]
    assert "eql_levels" in snap["liquidity"]


def test_emit_writes_trace_without_affecting_return(monkeypatch, tmp_path):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("DECISION_PATH_TRACE_PATH", str(path))
    from core.decision_path_telemetry import emit
    row = emit(
        trace_id="T1", symbol="BTC/USDT:USDT", side="BUY",
        stage="SCANNER_SIDE_HYPOTHESIS", decision="BUY",
        authority="DISCOVERY_HYPOTHESIS", source="test",
        fields={"x": 1},
    )
    assert row["trace_id"] == "T1"
    assert path.exists()
    data = json.loads(path.read_text().strip())
    assert data["trace_id"] == "T1"
    assert data["event_hash"]
