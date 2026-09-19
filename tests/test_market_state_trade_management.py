import numpy as np
import pandas as pd

from core.ema_vwap_trade_management import EMA200VWAPManager


def make_df(side="BUY"):
    if side == "BUY":
        values = np.concatenate([np.full(150, 100.0), np.linspace(100, 112, 70)])
    else:
        values = np.concatenate([np.full(150, 100.0), np.linspace(100, 88, 70)])
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(values), freq="15min", tz="UTC"),
        "open": values,
        "high": values * 1.003,
        "low": values * 0.997,
        "close": values,
        "volume": np.full(len(values), 1000.0),
    })


def test_healthy_buy_pullback_is_hold_and_contains_market_state():
    df = make_df("BUY")
    px = float(df.close.iloc[-1]) * 0.997
    result = EMA200VWAPManager().classify(df, "BUY", px, atr=0.5)
    assert result["exit"] is False
    assert result["market_state"]["state"] != "UNKNOWN"
    assert "accumulation_score" in result
    assert "distribution_score" in result


def test_healthy_sell_pullback_is_hold():
    df = make_df("SELL")
    px = float(df.close.iloc[-1]) * 1.003
    result = EMA200VWAPManager().classify(df, "SELL", px, atr=0.5)
    assert result["exit"] is False
    assert result["market_state"]["state"] != "UNKNOWN"


def test_ema50_or_vwap_change_alone_never_closes_position():
    df = make_df("BUY")
    result = EMA200VWAPManager().classify(df, "BUY", 110.0, atr=0.5)
    assert result["exit"] is False
    assert result["state"] != "THESIS_FAILURE"


def test_ema200_plus_structure_failure_can_trigger_thesis_failure():
    df = make_df("BUY")
    tail = df.tail(8).copy()
    tail.loc[:, "open"] = 95.0
    tail.loc[:, "high"] = 96.0
    tail.loc[:, "low"] = 90.0
    tail.loc[:, "close"] = 91.0
    df.loc[df.index[-8:], ["open", "high", "low", "close"]] = tail[["open", "high", "low", "close"]]
    result = EMA200VWAPManager().classify(df, "BUY", 91.0, atr=0.5)
    assert result["structure_failure"] is True
    assert result["ema200_intact"] is False
    assert result["exit"] is True
    assert result["state"] == "THESIS_FAILURE"
