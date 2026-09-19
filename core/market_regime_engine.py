"""Deterministic market-regime intelligence for BARON.

The engine is deliberately read-only: it consumes observable market/evidence
inputs and produces a structured snapshot. It never places, changes, or closes
orders and it never claims visibility into hidden institutional algorithms.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


STATES = (
    "ACCUMULATION",
    "RE_ACCUMULATION",
    "MARKUP",
    "TREND_PULLBACK",
    "DISTRIBUTION",
    "RE_DISTRIBUTION",
    "MARKDOWN",
    "TRANSITION",
    "UNKNOWN",
)


@dataclass(frozen=True)
class MarketStateSnapshot:
    state: str
    confidence_score: float
    side_bias: str
    persistence_bars: int
    transition_state: str
    ema: dict[str, Any]
    vwap: dict[str, Any]
    structure: dict[str, Any]
    liquidity: dict[str, Any]
    vpa: dict[str, Any]
    accumulation: dict[str, Any]
    distribution: dict[str, Any]
    microstructure: dict[str, Any]
    warnings: list[str]
    reasons: list[str]
    data_quality: str
    timestamp: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketRegimeEngine:
    """Pure evidence analyzer with deterministic state hysteresis."""

    def __init__(self, hysteresis_bars: int = 2) -> None:
        self.hysteresis_bars = max(1, int(hysteresis_bars))

    @staticmethod
    def _empty_snapshot(reason: str, timestamp: Any = None) -> MarketStateSnapshot:
        return MarketStateSnapshot(
            state="UNKNOWN", confidence_score=0.0, side_bias="UNKNOWN",
            persistence_bars=0, transition_state="UNKNOWN",
            ema={"available": False, "cross_state": "UNAVAILABLE", "ema50": None, "ema200": None,
                 "ema50_slope": 0.0, "ema200_slope": 0.0, "spread": None, "spread_pct": None,
                 "price_above_50": None, "price_above_200": None,
                 "crossing_phase": "UNKNOWN", "cross_age": None, "spread_delta_3": 0.0, "slope_delta": 0.0},
            vwap={"available": False, "value": None, "side": "UNKNOWN", "slope": 0.0,
                  "distance_atr": None, "reclaim": False, "rejection": False},
            structure={"direction": "UNKNOWN", "quality": 0.0, "bos": False, "mss": False, "choc": False},
            liquidity={"direction": "UNKNOWN", "quality": 0.0, "sweep": False, "reclaimed": False},
            vpa={"effort_result": "UNAVAILABLE", "volume_ratio": None, "displacement": "UNAVAILABLE",
                 "absorption": False, "quality": 0.0},
            accumulation={"score": 0.0, "process": "UNAVAILABLE"},
            distribution={"score": 0.0, "process": "UNAVAILABLE"},
            microstructure={"data_quality": "UNAVAILABLE", "top_of_book_imbalance": None,
                            "spread": None, "trade_aggression": None, "open_interest_change": None},
            warnings=[reason], reasons=[reason], data_quality="INSUFFICIENT_HISTORY", timestamp=timestamp,
        )

    @staticmethod
    def _num(value: Any, default: float | None = None) -> float | None:
        try:
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bool(value: Any) -> bool:
        return bool(value) if value is not None else False

    @staticmethod
    def _score01(value: Any) -> float:
        x = MarketRegimeEngine._num(value, 0.0) or 0.0
        if x > 1.0:
            x /= 100.0
        return max(0.0, min(1.0, x))

    def _ema_context(self, close: pd.Series) -> dict[str, Any]:
        e50 = close.ewm(span=50, adjust=False).mean()
        e200 = close.ewm(span=200, adjust=False).mean()
        spread = e50 - e200
        lookback = min(5, len(close) - 1)
        s50 = float(e50.iloc[-1] - e50.iloc[-1 - lookback])
        s200 = float(e200.iloc[-1] - e200.iloc[-1 - lookback])
        cross = "NONE"
        cross_age = None
        start = max(1, len(spread) - 10)
        for i in range(start, len(spread)):
            p, c = float(spread.iloc[i - 1]), float(spread.iloc[i])
            if p <= 0 < c:
                cross = "BULLISH_RECENT"; cross_age = len(spread) - 1 - i
            elif p >= 0 > c:
                cross = "BEARISH_RECENT"; cross_age = len(spread) - 1 - i
        px = float(close.iloc[-1])
        e50v, e200v = float(e50.iloc[-1]), float(e200.iloc[-1])

        # "Beginning of the crossing" is intentionally broader than the exact
        # EMA50/EMA200 crossover candle. Waiting for the mathematical cross
        # alone is late by construction. We therefore expose a deterministic
        # onset phase when the EMA spread is compressing toward zero, its slope
        # is turning in the new direction, or the cross happened only a few
        # closed candles ago. This remains context/timing evidence, never a
        # standalone BUY/SELL trigger.
        spread_now = float(spread.iloc[-1])
        spread_3 = float(spread.iloc[-4]) if len(spread) >= 4 else spread_now
        spread_delta = spread_now - spread_3
        spread_abs = abs(spread_now)
        slope_delta = s50 - s200
        direction_onset = "NONE"
        if cross == "BULLISH_RECENT" or (spread_now >= 0 and spread_delta > 0 and slope_delta > 0):
            direction_onset = "BULLISH"
        elif cross == "BEARISH_RECENT" or (spread_now <= 0 and spread_delta < 0 and slope_delta < 0):
            direction_onset = "BEARISH"

        if cross_age is not None and cross_age <= 3:
            crossing_phase = "POST_CROSS_EARLY"
        elif direction_onset == "BULLISH" and spread_now < 0 and spread_delta > 0 and slope_delta > 0:
            crossing_phase = "PRE_CROSS_BULLISH"
        elif direction_onset == "BEARISH" and spread_now > 0 and spread_delta < 0 and slope_delta < 0:
            crossing_phase = "PRE_CROSS_BEARISH"
        elif cross_age is not None and cross_age <= 8:
            crossing_phase = "POST_CROSS_DEVELOPING"
        else:
            crossing_phase = "MATURE"

        return {
            "available": True, "ema50": e50v, "ema200": e200v,
            "ema50_slope": s50, "ema200_slope": s200,
            "spread": spread_now,
            "spread_pct": float(spread_now / e200v * 100.0) if e200v else 0.0,
            "price_above_50": px > e50v, "price_above_200": px > e200v,
            "cross_state": cross, "cross_age": cross_age,
            "crossing_phase": crossing_phase,
            "spread_delta_3": spread_delta,
            "slope_delta": slope_delta,
            "spread_abs": spread_abs,
            "bias": "BULLISH" if px > e200v and e50v > e200v else ("BEARISH" if px < e200v and e50v < e200v else "TRANSITION"),
        }

    def _vwap_context(self, df: pd.DataFrame, atr: float) -> dict[str, Any]:
        close = pd.to_numeric(df["close"], errors="coerce")
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        volume = pd.to_numeric(df["volume"], errors="coerce").clip(lower=0.0)
        typical = (high + low + close) / 3.0
        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            key = ts.dt.floor("D") if not ts.isna().all() else pd.Series(0, index=df.index)
        else:
            key = pd.Series(0, index=df.index)
        pv = typical * volume
        vwap = (pv.groupby(key, sort=False).cumsum() / volume.groupby(key, sort=False).cumsum().replace(0, np.nan)).ffill().bfill().fillna(close)
        value = float(vwap.iloc[-1]); px = float(close.iloc[-1])
        prev = float(vwap.iloc[-2]); prev_px = float(close.iloc[-2])
        reclaim = (prev_px <= prev and px > value) or (prev_px >= prev and px < value)
        rejection = float(low.iloc[-1]) <= value <= float(high.iloc[-1]) and not reclaim and abs(px - value) > 0
        return {
            "available": True, "value": value,
            "side": "ABOVE" if px > value else ("BELOW" if px < value else "AT"),
            "slope": float(vwap.iloc[-1] - vwap.iloc[-2]),
            "distance": float((px - value) / value) if value else 0.0,
            "distance_atr": float(abs(px - value) / atr) if atr > 0 else None,
            "reclaim": bool(reclaim), "rejection": bool(rejection),
            "reclaim_side": "BUY" if prev_px <= prev and px > value else ("SELL" if prev_px >= prev and px < value else None),
        }

    def _vpa_context(self, df: pd.DataFrame, vpa: dict | None) -> dict[str, Any]:
        if vpa:
            result = dict(vpa)
            result.setdefault("effort_result", "UNAVAILABLE")
            result.setdefault("volume_ratio", None)
            result.setdefault("displacement", "UNAVAILABLE")
            result.setdefault("absorption", False)
            result["quality"] = self._score01(result.get("quality", 0.0))
            return result
        volume = pd.to_numeric(df["volume"], errors="coerce").astype(float)
        body = (pd.to_numeric(df["close"], errors="coerce") - pd.to_numeric(df["open"], errors="coerce")).abs()
        rng = (pd.to_numeric(df["high"], errors="coerce") - pd.to_numeric(df["low"], errors="coerce")).clip(lower=1e-12)
        vr = float(volume.iloc[-1] / max(float(volume.tail(20).mean()), 1e-12))
        efficiency = float(body.iloc[-1] / rng.iloc[-1])
        displacement = "BULLISH" if float(df["close"].iloc[-1]) > float(df["open"].iloc[-1]) and body.iloc[-1] / max(float(df["high"].iloc[-1] - df["low"].iloc[-1]), 1e-12) >= 0.65 else ("BEARISH" if float(df["close"].iloc[-1]) < float(df["open"].iloc[-1]) and efficiency >= 0.65 else "NONE")
        return {"effort_result": "EXPANSION" if vr >= 1.5 and efficiency >= 0.55 else "NORMAL", "volume_ratio": vr,
                "displacement": displacement, "absorption": False, "quality": min(1.0, 0.5 * min(vr / 2.0, 1.0) + 0.5 * efficiency)}

    def _microstructure(self, depth: dict | None, trades: list | None, open_interest: float | None) -> dict[str, Any]:
        if not depth and not trades and open_interest is None:
            return {"data_quality": "UNAVAILABLE", "top_of_book_imbalance": None, "spread": None,
                    "trade_aggression": None, "open_interest_change": None}
        bid = self._num((depth or {}).get("bid_volume")); ask = self._num((depth or {}).get("ask_volume"))
        imbalance = None if bid is None or ask is None or bid + ask <= 0 else float((bid - ask) / (bid + ask))
        spread = self._num((depth or {}).get("spread"))
        aggression = None
        if trades:
            signed = []
            for t in trades[-100:]:
                if not isinstance(t, dict):
                    continue
                side = str(t.get("side") or t.get("taker_side") or "").upper()
                qty = self._num(t.get("amount", t.get("qty", t.get("volume"))), 0.0) or 0.0
                if side in ("BUY", "SELL"):
                    signed.append(qty if side == "BUY" else -qty)
            if signed:
                denom = sum(abs(x) for x in signed)
                aggression = sum(signed) / denom if denom else 0.0
        return {"data_quality": "FRESH", "top_of_book_imbalance": imbalance, "spread": spread,
                "trade_aggression": aggression, "open_interest_change": open_interest}

    def _process_scores(self, df: pd.DataFrame, structure: dict, liquidity: dict, vpa: dict) -> tuple[float, float, dict[str, Any]]:
        close = pd.to_numeric(df["close"], errors="coerce").astype(float)
        high = pd.to_numeric(df["high"], errors="coerce").astype(float)
        low = pd.to_numeric(df["low"], errors="coerce").astype(float)
        volume = pd.to_numeric(df["volume"], errors="coerce").astype(float)
        look = min(30, len(df))
        range_pct = float((high.tail(look).max() - low.tail(look).min()) / max(abs(close.tail(look).mean()), 1e-12))
        atr = float((high - low).tail(14).mean())
        compression = 1.0 if range_pct <= 0.06 else max(0.0, 1.0 - range_pct / 0.15)
        effort = str(vpa.get("effort_result", "")).upper()
        absorption = self._bool(vpa.get("absorption")) or effort == "ABSORPTION"
        liq_q = self._score01(liquidity.get("quality", 0.0))
        struct_q = self._score01(structure.get("quality", 0.0))
        sweep = self._bool(liquidity.get("sweep")) or self._bool(liquidity.get("detected"))
        reclaim = self._bool(liquidity.get("reclaimed"))
        mss = self._bool(structure.get("mss"))
        direction = str(structure.get("direction") or "UNKNOWN").upper()
        bull = direction == "BULLISH" or str(liquidity.get("direction", "")).upper() == "BUY"
        bear = direction == "BEARISH" or str(liquidity.get("direction", "")).upper() == "SELL"
        acc = 25*compression + 20*(1.0 if sweep and bull else 0.0) + 20*(1.0 if reclaim and bull else 0.0) + 20*(1.0 if absorption and bull else 0.0) + 15*max(liq_q, struct_q)
        dist = 25*compression + 20*(1.0 if sweep and bear else 0.0) + 20*(1.0 if reclaim and bear else 0.0) + 20*(1.0 if absorption and bear else 0.0) + 15*max(liq_q, struct_q)
        return min(100.0, acc), min(100.0, dist), {"compression": compression, "range_pct": range_pct, "atr": atr, "mss": mss, "volume_mean": float(volume.tail(20).mean())}

    def _state(self, ema: dict, vwap: dict, structure: dict, liquidity: dict, vpa: dict,
               acc: float, dist: float, previous_state: str | None) -> tuple[str, float, str, str, list[str]]:
        reasons: list[str] = []
        bull = ema["bias"] == "BULLISH"
        bear = ema["bias"] == "BEARISH"
        structure_dir = str(structure.get("direction", "UNKNOWN")).upper()
        liq_buy = str(liquidity.get("direction", "")).upper() == "BUY"
        liq_sell = str(liquidity.get("direction", "")).upper() == "SELL"
        displacement = str(vpa.get("displacement", "")).upper()
        bullish_confirmation = structure_dir == "BULLISH" and (self._bool(structure.get("mss")) or self._bool(structure.get("bos"))) and displacement == "BULLISH"
        bearish_confirmation = structure_dir == "BEARISH" and (self._bool(structure.get("mss")) or self._bool(structure.get("bos"))) and displacement == "BEARISH"
        if acc >= 60 and not bullish_confirmation:
            state = "RE_ACCUMULATION" if previous_state in {"MARKUP", "TREND_PULLBACK", "RE_ACCUMULATION"} else "ACCUMULATION"
            reasons.append(f"Accumulation process score={acc:.1f}")
            return state, acc, "BUY", "ACCUMULATION_PROCESS", reasons
        if dist >= 60 and not bearish_confirmation:
            state = "RE_DISTRIBUTION" if previous_state in {"MARKDOWN", "TREND_PULLBACK", "RE_DISTRIBUTION"} else "DISTRIBUTION"
            reasons.append(f"Distribution process score={dist:.1f}")
            return state, dist, "SELL", "DISTRIBUTION_PROCESS", reasons
        if bullish_confirmation and bull and vwap["side"] == "ABOVE":
            reasons.extend(["EMA trend aligned bullish", "VWAP acceptance", "bullish structure/displacement confirmed"])
            return "MARKUP", max(70.0, (acc + 80) / 2), "BUY", "BULLISH_CONFIRMATION", reasons
        if bearish_confirmation and bear and vwap["side"] == "BELOW":
            reasons.extend(["EMA trend aligned bearish", "VWAP acceptance below", "bearish structure/displacement confirmed"])
            return "MARKDOWN", max(70.0, (dist + 80) / 2), "SELL", "BEARISH_CONFIRMATION", reasons
        if bull and (structure_dir == "BULLISH" or liq_buy) and (vwap["side"] in {"ABOVE", "AT"} or vwap["reclaim_side"] == "BUY"):
            reasons.append("Bullish trend context without expansion confirmation")
            return "TREND_PULLBACK", 62.0, "BUY", "TREND_CONTEXT", reasons
        if bear and (structure_dir == "BEARISH" or liq_sell) and (vwap["side"] in {"BELOW", "AT"} or vwap["reclaim_side"] == "SELL"):
            reasons.append("Bearish trend context without expansion confirmation")
            return "TREND_PULLBACK", 62.0, "SELL", "TREND_CONTEXT", reasons
        if acc >= 45 and dist >= 45:
            reasons.append("Accumulation and distribution evidence conflict")
            return "TRANSITION", max(acc, dist), "NEUTRAL", "CONFLICT", reasons
        reasons.append("No multi-factor regime confirmation")
        return "TRANSITION", 35.0, "NEUTRAL", "UNCONFIRMED", reasons

    def analyze(self, df: pd.DataFrame, *, structure: dict | None = None, liquidity: dict | None = None,
                vpa: dict | None = None, depth: dict | None = None, trades: list | None = None,
                open_interest: float | None = None, previous_state: str | None = None) -> MarketStateSnapshot:
        if not isinstance(df, pd.DataFrame) or len(df) < 200:
            return self._empty_snapshot("INSUFFICIENT_HISTORY", df["timestamp"].iloc[-1] if isinstance(df, pd.DataFrame) and len(df) and "timestamp" in df else None)
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return self._empty_snapshot("MISSING_OHLCV_COLUMNS")
        work = df.copy()
        for col in required:
            work[col] = pd.to_numeric(work[col], errors="coerce")
        if work[list(required)].isna().any().any():
            return self._empty_snapshot("INVALID_OHLCV_DATA")
        close = work["close"].astype(float)
        high = work["high"].astype(float); low = work["low"].astype(float)
        atr = float((high - low).tail(14).mean())
        ema = self._ema_context(close)
        vwap = self._vwap_context(work, atr)
        structure_ctx = dict(structure or {})
        structure_ctx.setdefault("direction", "UNKNOWN"); structure_ctx.setdefault("quality", 0.0)
        structure_ctx.setdefault("bos", False); structure_ctx.setdefault("mss", False); structure_ctx.setdefault("choc", False)
        liquidity_ctx = dict(liquidity or {})
        liquidity_ctx.setdefault("direction", "UNKNOWN"); liquidity_ctx.setdefault("quality", 0.0)
        liquidity_ctx.setdefault("sweep", liquidity_ctx.get("detected", False)); liquidity_ctx.setdefault("reclaimed", False)
        vpa_ctx = self._vpa_context(work, vpa)
        acc, dist, proc = self._process_scores(work, structure_ctx, liquidity_ctx, vpa_ctx)
        micro = self._microstructure(depth, trades, open_interest)
        state, confidence, bias, transition, reasons = self._state(ema, vwap, structure_ctx, liquidity_ctx, vpa_ctx, acc, dist, previous_state)
        if ema["cross_state"] != "NONE":
            reasons.append(f"EMA transition evidence={ema['cross_state']} age={ema.get('cross_age')}")
        if ema.get("crossing_phase") not in (None, "MATURE", "UNKNOWN"):
            reasons.append(f"EMA crossing phase={ema.get('crossing_phase')}")
        warnings = []
        if micro["data_quality"] == "UNAVAILABLE":
            warnings.append("MICROSTRUCTURE_UNAVAILABLE")
        if vwap.get("distance_atr") is not None and vwap["distance_atr"] > 3.0:
            warnings.append("VWAP_EXTENDED")
        persistence = self.hysteresis_bars if previous_state == state else 1
        timestamp = work["timestamp"].iloc[-1] if "timestamp" in work.columns else None
        return MarketStateSnapshot(
            state=state, confidence_score=round(float(min(100.0, confidence)), 2), side_bias=bias,
            persistence_bars=persistence, transition_state=transition,
            ema=ema, vwap=vwap, structure=structure_ctx, liquidity=liquidity_ctx, vpa=vpa_ctx,
            accumulation={"score": round(float(acc), 2), "process": "BULLISH_PROCESS" if acc >= 45 else "WEAK"},
            distribution={"score": round(float(dist), 2), "process": "BEARISH_PROCESS" if dist >= 45 else "WEAK"},
            microstructure=micro, warnings=warnings, reasons=reasons,
            data_quality="FRESH", timestamp=timestamp,
        )
