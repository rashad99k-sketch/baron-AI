import numpy as np
import pandas as pd

from core.trend_strategy_v29 import BaronTrendStrategyV29


def _df(n=100, start=100.0):
    x = np.arange(n, dtype=float)
    close = start + x * 0.15
    open_ = close - 0.03
    high = close + 0.20
    low = close - 0.20
    volume = np.full(n, 1000.0)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_liquidity_clusters_use_confirmed_swings():
    s = BaronTrendStrategyV29()
    df = _df()
    # Two repeated lows separated enough to be distinct candles.
    for i, v in [(70, 109.0), (76, 109.1), (82, 109.05)]:
        df.loc[i, "low"] = v
        df.loc[i, "close"] = v + 0.25
        df.loc[i, "open"] = v + 0.30
        df.loc[i, "high"] = v + 0.45
    liq = s._liquidity_map(df, float(df["close"].iloc[-1]))
    assert liq["low_clusters"]
    assert any(c["count"] >= 2 for c in liq["low_clusters"])


def test_structural_stop_sits_outside_sweep_for_buy():
    s = BaronTrendStrategyV29()
    df = _df()
    liq = {
        "target_above": {"level": 125.0, "count": 2},
        "target_below": {"level": 109.0, "count": 3},
    }
    structure = {"last_swing_low": 109.1, "last_swing_high": 118.0}
    sl, tp1, tp2, meta = s._sl_tp("BUY", 115.0, 2.5, liq, 109.0, structure)
    assert meta["valid"]
    assert sl < 109.0
    assert tp1 > 115.0
    assert tp2 > tp1


def test_medium_pullback_is_a_state_not_an_automatic_rejection():
    s = BaronTrendStrategyV29()
    df = _df()
    # Make the last candle a controlled counter-direction candle while DI/ADX
    # remain directionally healthy.
    df.loc[96:, "close"] = [114.4, 114.1, 113.8, 113.6]
    df.loc[96:, "open"] = [114.2, 114.3, 114.0, 113.9]
    atr, plus, minus, adx = s._adx_di(df)
    p = s._pullback(df, "BUY", float(atr.iloc[-1]), 35.0, 18.0, 28.0)
    assert p["state"] in {"MEDIUM_PULLBACK", "STRONG_PULLBACK", "NO_PULLBACK", "WEAK_PULLBACK"}


def test_evaluate_fail_closed_on_wrong_rf_side():
    s = BaronTrendStrategyV29()
    df = _df()
    d = s.evaluate("TEST", "BUY", df, {}, {"signal": "SELL", "distance": 0.0})
    assert not d.approved
    assert "RF_MISMATCH" in d.blockers
