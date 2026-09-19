import os
import numpy as np
import pandas as pd

import core.engine as E
from core.market_regime_engine import MarketRegimeEngine


def _mature_bull(n=260):
    vals = np.concatenate([np.full(210, 100.0), np.linspace(100.0, 125.0, n - 210)])
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": vals, "high": vals + 0.3, "low": vals - 0.3,
        "close": vals, "volume": np.full(n, 1000.0),
    })


def _recent_cross_bull(n=260):
    vals = np.concatenate([np.full(150, 120.0), np.linspace(120.0, 80.0, 80), np.linspace(80.0, 140.0, 30)])
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(vals), freq="15min", tz="UTC"),
        "open": vals, "high": vals + 10.0, "low": vals - 10.0,
        "close": vals, "volume": np.full(len(vals), 1000.0),
    })


def test_mature_expansion_is_not_an_early_entry():
    ms = MarketRegimeEngine().analyze(_mature_bull()).to_dict()
    assert ms["ema"]["crossing_phase"] == "MATURE"


def test_recent_cross_is_early_transition_evidence_not_standalone_trigger():
    ms = MarketRegimeEngine().analyze(_recent_cross_bull()).to_dict()
    assert ms["ema"]["crossing_phase"] in {"POST_CROSS_EARLY", "PRE_CROSS_BULLISH", "MATURE"}  # data-shape guard
    assert ms["ema"].get("cross_state") == "BULLISH_RECENT"


def test_execute_entry_central_gate_blocks_mature_technical_entry(monkeypatch):
    df = _mature_bull()
    monkeypatch.setenv("EARLY_TREND_ENTRY_HARD_GATE", "1")
    ok, info = E._technical_entry_timing_gate("TEST/USDT:USDT", "BUY", df, 125.0, 0.6, "SCANNER")
    assert ok is False
    assert info["phase"] == "MATURE"


def test_execute_entry_timing_gate_allows_recent_cross_when_not_extended(monkeypatch):
    df = _recent_cross_bull()
    ms = MarketRegimeEngine().analyze(df).to_dict()
    phase = ms["ema"]["crossing_phase"]
    # This test only validates the gate's contract for a genuinely early phase;
    # if the synthetic EMA math does not produce one, fail explicitly rather than
    # weakening the production rule.
    assert phase == "POST_CROSS_EARLY"
    px = float(df["close"].iloc[-1])
    atr = float((df["high"] - df["low"]).tail(14).mean())
    monkeypatch.setenv("EARLY_TREND_ENTRY_HARD_GATE", "1")
    ok, info = E._technical_entry_timing_gate("TEST/USDT:USDT", "BUY", df, px, atr, "SCANNER")
    assert ok is True
    assert info["phase"] == phase
