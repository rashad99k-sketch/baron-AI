import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.ema_vwap_trade_management import EMA200VWAPManager


def make_uptrend(n=240):
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = 100 + np.arange(n, dtype=float) * 0.08
    return pd.DataFrame({
        "timestamp": idx,
        "open": close - 0.03,
        "high": close + 0.10,
        "low": close - 0.10,
        "close": close,
        "volume": 1000.0,
    })


def test_pullback_to_ema50_is_healthy_when_ema200_and_vwap_hold():
    df = make_uptrend()
    # Create a controlled pullback into EMA50 while preserving the EMA200 trend.
    ema50 = df.close.ewm(span=50, adjust=False).mean().iloc[-6]
    for i, c in enumerate([ema50 + 0.10, ema50 + 0.02, ema50 - 0.08, ema50 - 0.02, ema50 + 0.18, ema50 + 0.35], start=len(df)-6):
        df.loc[i, "close"] = c
        df.loc[i, "open"] = c + 0.03 if i < len(df)-2 else c - 0.03
        df.loc[i, "high"] = max(df.loc[i, "open"], c) + 0.08
        df.loc[i, "low"] = min(df.loc[i, "open"], c) - 0.08
    manager = EMA200VWAPManager()
    ctx = manager.classify(df, "BUY", float(df.close.iloc[-1]), atr=0.35)
    assert ctx["state"] == "HEALTHY_PULLBACK"
    assert ctx["ema200_intact"] is True
    assert ctx["exit"] is False


def test_ema50_breach_is_not_a_reversal_without_ema200_and_structure_failure():
    df = make_uptrend()
    e50 = df.close.ewm(span=50, adjust=False).mean().iloc[-1]
    for i, c in enumerate([e50 - 0.20, e50 - 0.15, e50 - 0.10], start=len(df)-3):
        df.loc[i, "close"] = c
        df.loc[i, "open"] = c + 0.05
        df.loc[i, "high"] = max(df.loc[i, "open"], c) + 0.08
        df.loc[i, "low"] = min(df.loc[i, "open"], c) - 0.08
    ctx = EMA200VWAPManager().classify(df, "BUY", float(df.close.iloc[-1]), atr=0.35)
    assert ctx["ema200_intact"] is True
    assert ctx["state"] in {"EMA50_BREACH", "HEALTHY_PULLBACK", "VWAP_RETEST"}
    assert ctx["exit"] is False


def test_confirmed_ema200_loss_and_structure_break_is_thesis_failure():
    df = make_uptrend()
    e200 = df.close.ewm(span=200, adjust=False).mean().iloc[-1]
    base = float(e200 - 0.8)
    for i in range(len(df)-3, len(df)):
        c = base - (i - (len(df)-3)) * 0.05
        df.loc[i, "close"] = c
        df.loc[i, "open"] = c + 0.05
        df.loc[i, "high"] = c + 0.08
        df.loc[i, "low"] = c - 0.10
    ctx = EMA200VWAPManager().classify(df, "BUY", float(df.close.iloc[-1]), atr=0.35)
    assert ctx["ema200_intact"] is False
    assert ctx["structure_failure"] is True
    assert ctx["exit"] is True


def test_vwap_reclaim_is_positive_management_evidence():
    df = make_uptrend()
    manager = EMA200VWAPManager()
    # Put previous close below the computed session VWAP and current close above it.
    v = manager.vwap_context(df, float(df.close.iloc[-1]))["value"]
    prev = v - 0.20
    cur = v + 0.25
    df.loc[len(df)-2, "close"] = prev
    df.loc[len(df)-1, "close"] = cur
    for i in (len(df)-2, len(df)-1):
        c = df.loc[i, "close"]
        df.loc[i, "open"] = c - 0.03
        df.loc[i, "high"] = c + 0.08
        df.loc[i, "low"] = c - 0.08
    ctx = manager.classify(df, "BUY", cur, atr=0.35)
    assert ctx["vwap_reclaim"] is True
    assert ctx["vwap_supportive"] is True
    assert ctx["exit"] is False
