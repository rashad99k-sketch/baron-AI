"""EMA50/EMA200 + VWAP position-management context.

Pure/read-only. It classifies pullbacks and trend failures; it never sends orders.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.institutional_entry_engine import InstitutionalEntryEngine
from core.market_regime_engine import MarketRegimeEngine


class EMA200VWAPManager:
    def __init__(self):
        self._entry_engine = InstitutionalEntryEngine()
        self._regime_engine = MarketRegimeEngine()

    def vwap_context(self, df: pd.DataFrame, price: float | None = None) -> dict[str, Any]:
        return self._entry_engine.compute_vwap_context(df, price)

    @staticmethod
    def _ema_context(df: pd.DataFrame, side: str) -> dict[str, Any]:
        close = pd.to_numeric(df["close"], errors="coerce").astype(float)
        e50 = close.ewm(span=50, adjust=False).mean()
        e200 = close.ewm(span=200, adjust=False).mean()
        ema50 = float(e50.iloc[-1])
        ema200 = float(e200.iloc[-1])
        side = str(side).upper()
        last3 = close.tail(3)
        if side == "BUY":
            ema200_intact = int((last3 > ema200).sum()) >= 2
        else:
            ema200_intact = int((last3 < ema200).sum()) >= 2
        spread = float(ema50 - ema200)
        spread_prev = float(e50.iloc[-2] - e200.iloc[-2])
        return {
            "ema50": ema50,
            "ema200": ema200,
            "ema50_slope": float(e50.iloc[-1] - e50.iloc[-6]),
            "ema200_slope": float(e200.iloc[-1] - e200.iloc[-6]),
            "ema_spread": spread,
            "ema_cross": (
                "BULLISH_RECENT" if spread_prev <= 0 < spread
                else "BEARISH_RECENT" if spread_prev >= 0 > spread
                else "NONE"
            ),
            "ema200_intact": bool(ema200_intact),
        }

    def classify(self, df: pd.DataFrame, side: str, price: float, atr: float) -> dict[str, Any]:
        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 200:
            return {
                "state": "UNKNOWN", "exit": False, "available": False,
                "ema200_intact": None, "structure_failure": False,
                "vwap_reclaim": False, "vwap_supportive": False,
            }
        side = str(side).upper()
        px = float(price)
        atr = max(float(atr or 0.0), 1e-9)
        ema = self._ema_context(df, side)
        vwap = self.vwap_context(df, px)
        regime = self._regime_engine.analyze(
            df,
            structure={"direction": "BULLISH" if side == "BUY" else "BEARISH"},
        ).to_dict()
        closes = pd.to_numeric(df["close"], errors="coerce").astype(float)
        highs = pd.to_numeric(df["high"], errors="coerce").astype(float)
        lows = pd.to_numeric(df["low"], errors="coerce").astype(float)

        ema50 = ema["ema50"]
        ema200 = ema["ema200"]
        if side == "BUY":
            touch_ema50 = float(lows.tail(6).min()) <= ema50 + 0.60 * atr
            ema50_breach = float(closes.tail(3).min()) < ema50
            previous_swing_low = float(lows.iloc[-20:-8].min()) if len(lows) >= 20 else float(lows.iloc[:-8].min())
            structure_failure = int((closes.tail(3) < ema200).sum()) >= 2 and px < previous_swing_low
            vwap_reclaim = bool(
                vwap.get("reclaim") and vwap.get("side") == "ABOVE"
            )
            vwap_supportive = vwap["side"] == "ABOVE" or vwap_reclaim or (
                vwap.get("slope", 0.0) >= 0 and vwap.get("distance", 0.0) > -0.35 * atr / max(vwap.get("value", px), 1e-9)
            )
            recovery = px > ema50 or vwap_reclaim
        else:
            touch_ema50 = float(highs.tail(6).max()) >= ema50 - 0.60 * atr
            ema50_breach = float(closes.tail(3).max()) > ema50
            previous_swing_high = float(highs.iloc[-20:-8].max()) if len(highs) >= 20 else float(highs.iloc[:-8].max())
            structure_failure = int((closes.tail(3) > ema200).sum()) >= 2 and px > previous_swing_high
            vwap_reclaim = bool(
                vwap.get("reclaim") and vwap.get("side") == "BELOW"
            )
            vwap_supportive = vwap["side"] == "BELOW" or vwap_reclaim or (
                vwap.get("slope", 0.0) <= 0 and vwap.get("distance", 0.0) < 0.35 * atr / max(vwap.get("value", px), 1e-9)
            )
            recovery = px < ema50 or vwap_reclaim

        if side == "BUY" and structure_failure and not ema["ema200_intact"]:
            state, exit_now = "THESIS_FAILURE", True
        elif side == "SELL" and structure_failure and not ema["ema200_intact"]:
            state, exit_now = "THESIS_FAILURE", True
        elif ema["ema200_intact"] and touch_ema50 and (vwap_supportive or recovery):
            state, exit_now = "HEALTHY_PULLBACK", False
        elif ema50_breach and ema["ema200_intact"]:
            state, exit_now = "EMA50_BREACH", False
        elif vwap.get("reclaim") and vwap_supportive:
            state, exit_now = "VWAP_RETEST", False
        elif (side == "BUY" and px > ema200 and ema50 > ema200) or (side == "SELL" and px < ema200 and ema50 < ema200):
            state, exit_now = "TREND_RIDE", False
        else:
            state, exit_now = "TRANSITION", False

        return {
            "state": state,
            "market_state": regime,
            "accumulation_score": float((regime.get("accumulation") or {}).get("score", 0.0) or 0.0),
            "distribution_score": float((regime.get("distribution") or {}).get("score", 0.0) or 0.0),
            "exit": bool(exit_now),
            "available": True,
            "ema50": ema50,
            "ema200": ema200,
            "ema50_slope": ema["ema50_slope"],
            "ema200_slope": ema["ema200_slope"],
            "ema_spread": ema["ema_spread"],
            "ema_cross": ema["ema_cross"],
            "ema200_intact": bool(ema["ema200_intact"]),
            "ema50_breach": bool(ema50_breach),
            "vwap_reclaim": bool(vwap_reclaim),
            "vwap_supportive": bool(vwap_supportive),
            "vwap_side": vwap.get("side"),
            "vwap": vwap,
            "structure_failure": bool(structure_failure),
            "touch_ema50": bool(touch_ema50),
            "recovery": bool(recovery),
        }
