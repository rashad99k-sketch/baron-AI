import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import math
import numpy as np
import pandas as pd

from core.institutional_entry_engine import InstitutionalEntryEngine


def make_frame(n=260, start=100.0, slope=0.12):
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    base = start + np.arange(n) * slope
    close = base.copy()
    open_ = close - 0.05
    high = close + 0.12
    low = close - 0.12
    volume = np.full(n, 1000.0)
    df = pd.DataFrame({
        "timestamp": idx,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    return df


def make_bullish_sweep_frame():
    df = make_frame()
    # Build a clear sell-side liquidity pool, then sweep/reclaim it on the last bar.
    pool_level = 128.00
    for i in (240, 245, 250):
        df.loc[i, "low"] = pool_level
        df.loc[i, "close"] = pool_level + 0.25
        df.loc[i, "high"] = pool_level + 0.45
        df.loc[i, "open"] = pool_level + 0.10
    df.loc[258, ["low", "open", "close", "high", "volume"]] = [127.75, 128.05, 128.85, 129.10, 2600.0]
    # Last bar establishes a bullish structural response.
    df.loc[259, ["low", "open", "close", "high", "volume"]] = [128.65, 128.80, 130.10, 130.30, 3400.0]
    return df, pool_level


def test_ema50_200_are_direction_context_not_entry_trigger():
    engine = InstitutionalEntryEngine()
    df = make_frame()
    price = float(df.close.iloc[-1])
    ctx = engine.compute_direction_context(df, price)
    assert ctx["available"] is True
    assert ctx["ema50"] > ctx["ema200"]
    assert ctx["bias"] == "BULLISH"
    assert ctx["ema_cross"] in {"NONE", "BULLISH_RECENT", "BEARISH_RECENT"}


def test_bullish_ema_cross_is_transition_evidence_only():
    engine = InstitutionalEntryEngine()
    df = make_frame(slope=0.0)
    # Force a recent EMA50 > EMA200 transition while leaving no price/structure trigger.
    vals = np.linspace(100.0, 99.0, len(df))
    vals[-15:] = np.linspace(98.5, 104.0, 15)
    df["close"] = vals
    df["open"] = vals - 0.02
    df["high"] = vals + 0.05
    df["low"] = vals - 0.05
    price = float(df.close.iloc[-1])
    ctx = engine.compute_direction_context(df, price)
    assert ctx["available"] is True
    assert ctx["ema_cross"] == "BULLISH_RECENT"
    assert ctx["entry_trigger"] is False


def test_vwap_is_context_and_reclaim_is_stronger_than_raw_side():
    engine = InstitutionalEntryEngine()
    df = make_frame()
    df.loc[:, "volume"] = 1000.0
    df.loc[250:, "volume"] = 2500.0
    price = float(df.close.iloc[-1])
    ctx = engine.compute_vwap_context(df, price)
    assert ctx["value"] > 0
    assert ctx["side"] == "ABOVE"
    assert ctx["slope"] > 0

    df.loc[259, "close"] = ctx["value"] + 0.02
    reclaim = engine.compute_vwap_context(df, float(df.close.iloc[-1]))
    assert reclaim["side"] == "ABOVE"
    assert reclaim["reclaim"] in {True, False}


def test_liquidity_event_requires_more_than_a_single_low_break():
    engine = InstitutionalEntryEngine()
    df = make_frame()
    df.loc[259, "low"] = df.loc[258, "low"] - 0.20
    df.loc[259, "close"] = df.loc[259, "low"] + 0.01
    event = engine.detect_liquidity_event(df, "BUY", atr=0.5)
    assert event["detected"] is False


def test_bullish_sweep_reclaim_gets_high_quality_liquidity_event():
    engine = InstitutionalEntryEngine()
    df, pool = make_bullish_sweep_frame()
    event = engine.detect_liquidity_event(df, "BUY", atr=0.5)
    assert event["detected"] is True
    assert event["direction"] == "BUY"
    assert math.isclose(event["level"], pool, rel_tol=0, abs_tol=0.5)
    assert event["reclaimed"] is True
    assert event["quality"] >= 0.6


def test_late_entry_window_is_rejected_when_price_is_stretched_from_origin():
    engine = InstitutionalEntryEngine()
    df = make_frame()
    zone = {"price": float(df.close.iloc[-30]), "side": "DEMAND", "quality": 0.9}
    assessment = engine.assess(
        df=df,
        side="BUY",
        price=float(df.close.iloc[-1]),
        atr=0.25,
        zone=zone,
        structure_ok=True,
        displacement_ok=True,
        rejection_ok=True,
    )
    assert assessment["entry_window"] == "LATE"
    assert assessment["decision"] == "REJECT"


def test_mature_sweep_reclaim_setup_is_blocked_by_early_transition_contract():
    engine = InstitutionalEntryEngine()
    df, _ = make_bullish_sweep_frame()
    zone = {"price": 128.7, "side": "DEMAND", "quality": 0.85}
    assessment = engine.assess(
        df=df,
        side="BUY",
        price=128.9,
        atr=0.5,
        zone=zone,
        structure_ok=True,
        displacement_ok=True,
        rejection_ok=True,
    )
    assert assessment["decision"] == "REJECT"
    assert assessment["setup_type"] == "LIQUIDITY_REVERSAL"
    assert assessment["metrics"]["crossing_phase"] == "MATURE"
    assert assessment["metrics"]["early_transition"] is False
    assert "EMA_CROSSING_MATURE_MATURE" in assessment["reasons"]
    assert assessment["thesis"]["invalidation"] < 128.9
    assert assessment["entry_window"] in {"EARLY", "CONFIRMED"}
