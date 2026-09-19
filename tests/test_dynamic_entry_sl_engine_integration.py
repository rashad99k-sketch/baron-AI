import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import engine as E


def make_df():
    n = 220
    close = np.linspace(100.0, 110.0, n)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": close - 0.05,
        "high": close + 0.15,
        "low": close - 0.15,
        "close": close,
        "volume": np.full(n, 1000.0),
    })


def test_compute_sl_tp_prefers_verified_entry_intelligence_invalidation():
    previous = E.STATE.get("entry_intelligence_v2")
    try:
        E.STATE["entry_intelligence_v2"] = {
            "decision": "APPROVE",
            "side": "BUY",
            "thesis": {"invalidation": 99.0},
            "liquidity_event": {"level": 99.2, "quality": 0.90},
            "entry_window": "EARLY",
        }
        sl, tp1, tp2 = E.compute_sl_tp(100.0, "BUY", "REVERSAL", 1.0, make_df())
        assert abs(sl - 99.0) < 1e-6
        assert tp1 > 100.0
        assert tp2 > tp1
    finally:
        E.STATE["entry_intelligence_v2"] = previous


def test_live_sl_recompute_is_monotonic_against_confirmed_protection():
    previous = {
        "entry_intelligence_v2": E.STATE.get("entry_intelligence_v2"),
        "last_confirmed_sl": E.STATE.get("last_confirmed_sl"),
        "synthetic_sl": E.STATE.get("synthetic_sl"),
        "sl": E.STATE.get("sl"),
    }
    try:
        E.STATE["entry_intelligence_v2"] = {
            "decision": "APPROVE",
            "side": "BUY",
            "thesis": {"invalidation": 99.0},
            "liquidity_event": {"level": 99.2, "quality": 0.90},
            "entry_window": "EARLY",
        }
        E.STATE["last_confirmed_sl"] = 100.5
        E.STATE["synthetic_sl"] = 100.5
        E.STATE["sl"] = 100.5
        proposal = E.propose_dynamic_sl(
            side="BUY", entry=105.0, atr=2.0, invalidation=99.0,
            liquidity_level=99.2, liquidity_quality=0.9,
            volatility_multiplier=0.7,
        )
        ratcheted = E.ratchet_stop("BUY", E.STATE["last_confirmed_sl"], proposal["sl"])
        assert ratcheted == 100.5
    finally:
        for k, v in previous.items():
            E.STATE[k] = v
