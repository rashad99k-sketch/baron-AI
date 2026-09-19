import copy
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import engine as E


def make_df(n=60):
    x = np.linspace(100.0, 102.0, n)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC"),
        "open": x - 0.05, "high": x + 0.15, "low": x - 0.15,
        "close": x, "volume": np.full(n, 1000.0),
    })


def test_engine_arms_stop_hunt_reentry_only_with_same_thesis(monkeypatch):
    key = "stop_hunt_rearm_BTC/USDT:USDT"
    candidate = {
        "symbol": "BTC/USDT:USDT", "side": "BUY", "classification": "STOP_HUNT",
        "thesis_fingerprint": "same", "reentries_used": 0,
        "expires_at": 9_999_999_999.0,
    }
    old = copy.deepcopy(E.MEMORY.get(key)) if key in E.MEMORY else None
    old_state = {"reentry_state": E.STATE.get("reentry_state"), "reentry_candidate": E.STATE.get("reentry_candidate")}
    try:
        E.MEMORY[key] = candidate
        assessment = {
            "decision": "APPROVE", "entry_window": "EARLY",
            "setup_type": "LIQUIDITY_REVERSAL",
            "liquidity_event": {"detected": True, "reclaimed": True, "quality": 0.9},
            "thesis": {"fingerprint": "same"},
        }
        result = E._maybe_arm_stop_hunt_reentry("BTC/USDT:USDT", "BUY", assessment)
        assert result["allowed"] is True
        assert E.STATE["reentry_state"] == "REENTRY_READY"
    finally:
        if old is None:
            E.MEMORY.pop(key, None)
        else:
            E.MEMORY[key] = old
        E.STATE.update(old_state)


def test_engine_stop_forensics_does_not_arm_reentry_after_true_failure(monkeypatch):
    old_state = copy.deepcopy(E.STATE)
    old_engine = E.GLOBAL_INSTITUTIONAL_ENTRY_ENGINE
    try:
        class FakeEntryEngine:
            def detect_liquidity_event(self, df, side, atr):
                return {"detected": True, "reclaimed": True, "quality": 0.95, "level": 99.0}
        E.GLOBAL_INSTITUTIONAL_ENTRY_ENGINE = FakeEntryEngine()
        E.STATE.update({
            "close_reason": "INTERNAL_SL", "tp1_hit": False, "side": "BUY",
            "entry": 100.0, "synthetic_sl": 98.8, "sl": 98.8, "mark_price": 98.7,
            "atr": 1.0, "entry_atr": 1.0, "thesis_failure_score": 80.0,
            "entry_intelligence_v2": {
                "setup_type": "LIQUIDITY_REVERSAL",
                "entry_window": "EARLY",
                "thesis": {"fingerprint": "same", "invalidation": 98.8},
            },
            "ema_vwap_management": {"ema200_intact": False, "structure_failure": True},
        })
        candidate = E._prepare_stop_hunt_reentry_candidate("BTC/USDT:USDT", make_df())
        assert candidate is None
        assert E.STATE["stop_forensics"]["classification"] == "TRUE_FAILURE"
    finally:
        E.GLOBAL_INSTITUTIONAL_ENTRY_ENGINE = old_engine
        E.STATE.clear(); E.STATE.update(old_state)
