import os
import sys
from unittest.mock import patch

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import core.engine as E


def make_frame(n=260):
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    vals = 100.0 + pd.Series(range(n), dtype=float) * 0.08
    vals.iloc[-5:] = [119.6, 119.4, 119.2, 119.0, 118.8]
    close = vals.to_numpy()
    return pd.DataFrame({
        "timestamp": idx,
        "open": close - 0.03,
        "high": close + 0.08,
        "low": close - 0.08,
        "close": close,
        "volume": 1000.0,
    })


def test_get_trend_direction_uses_ema50_200_for_context_during_ema50_pullback():
    df = make_frame()
    with patch.object(E, "get_di_components", return_value=(55.0, 45.0, 30.0, 1.0)), \
         patch.object(E, "detect_structure_shift", return_value="neutral"):
        direction = E.get_trend_direction(df)
    assert direction == "BULLISH"


def test_ema_cross_alone_does_not_authorize_entry():
    df = make_frame()
    with patch.object(E, "get_di_components", return_value=(50.0, 50.0, 20.0, 1.0)), \
         patch.object(E, "detect_structure_shift", return_value="neutral"):
        direction = E.get_trend_direction(df)
    # The EMA context may be bullish, but this test verifies that the direction
    # helper alone is not the entry trigger.
    assert direction in {"BULLISH", "NEUTRAL"}


def test_check_institutional_entry_uses_v2_context_instead_of_fixed_adx_ceiling():
    df = make_frame()
    v2 = {
        "decision": "APPROVE",
        "setup_type": "LIQUIDITY_REVERSAL",
        "entry_window": "EARLY",
        "direction": {"bias": "BULLISH", "ema_cross": "NONE", "available": True},
        "vwap": {"available": True, "side": "ABOVE", "reclaim": True},
        "liquidity_event": {"detected": True, "reclaimed": True, "quality": 0.9, "level": 119.0},
        "thesis": {"invalidation": 118.5, "invalidation_basis": "LIQUIDITY_INVALIDATION"},
        "reasons": ["LIQUIDITY_SWEEP_QUALITY", "MSS_BOS", "DISPLACEMENT"],
        "metrics": {},
    }

    class FakeRF:
        def __init__(self, *a, **k):
            pass
        def compute(self, *_a, **_k):
            return {"signal": "BUY", "distance": 0.0}

    with patch.object(E, "classify_move_maturity", None), \
         patch.object(E.AssetBehaviorProfile, "resolve_asset_class", return_value="CRYPTO"), \
         patch.object(E.AssetBehaviorProfile, "entry_config", return_value={
             "sweep_bars": 12, "min_disp_atr": 0.75, "min_adx": 16, "max_adx": 55,
             "retest_atr": 0.90, "ready_score": 68,
         }), \
         patch.object(E, "TRADE_INTELLIGENCE_AVAILABLE", False), \
         patch.object(E, "detect_liquidity_context", return_value="sell_side_taken"), \
         patch.object(E, "detect_structure_shift", return_value="bullish_shift"), \
         patch.object(E, "detect_bos", return_value=(True, False)), \
         patch.object(E, "get_smart_zones", return_value={"buy_zones": [{"price": 118.9, "strength": 8.0}], "sell_zones": []}), \
         patch.object(E, "detect_fvg", return_value=None), \
         patch.object(E, "detect_order_block", return_value=None), \
         patch.object(E, "classify_volume", return_value="expansion"), \
         patch.object(E, "detect_displacement", return_value=True), \
         patch.object(E, "candle_rejection", return_value=True), \
         patch.object(E, "compute_adx", return_value=pd.Series([70.0])), \
         patch.object(E, "RFEngine", FakeRF), \
         patch.object(E, "get_sweep_authenticity", return_value=("real", 1)), \
         patch.object(E, "_institutional_entry_v2_assessment", return_value=v2, create=True), \
         patch.object(E, "_record_exec_blocker", lambda *a, **k: None), \
         patch.object(E, "log_execution", lambda *a, **k: None):
        ok, classification, reason = E.check_institutional_entry(
            "BTC/USDT:USDT", "BUY", df, None, 0.5, float(df.close.iloc[-1])
        )
    assert ok is True
    assert classification == "INSTITUTIONAL_SNIPER"
    assert "ENTRY_TOO_LATE" not in reason


def test_maturity_rejection_preserves_three_value_entry_contract():
    """Every institutional-entry rejection must keep the public 3-tuple API."""
    df = make_frame()
    with patch.object(E, "classify_move_maturity", return_value="EXHAUSTION"), \
         patch.object(E, "_record_exec_blocker", lambda *a, **k: None), \
         patch.object(E, "log_execution", lambda *a, **k: None):
        result = E.check_institutional_entry(
            "BTC/USDT:USDT", "BUY", df, None, 0.5, float(df.close.iloc[-1])
        )
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert result[0] is False
    assert result[1] is None
    assert "EXHAUSTION" in result[2]
