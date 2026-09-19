"""Pure institutional entry intelligence for BARON.

This module never places, modifies, or closes orders. It converts market data into
structured evidence that the existing BARON decision/execution layers can consume.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import hashlib
import json

import numpy as np
import pandas as pd

from core.market_regime_engine import MarketRegimeEngine


@dataclass(frozen=True)
class EntryAssessment:
    decision: str
    side: str
    setup_type: str
    entry_window: str
    direction: dict[str, Any]
    vwap: dict[str, Any]
    liquidity_event: dict[str, Any]
    thesis: dict[str, Any]
    reasons: list[str]
    metrics: dict[str, Any]
    market_state: dict[str, Any] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstitutionalEntryEngine:
    """Deterministic market-structure evidence engine.

    EMA50/EMA200 provide directional context. VWAP provides value/acceptance
    context. The structural trigger is based on liquidity + reclaim + structure
    rather than indicator stacking.
    """

    REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}

    def compute_direction_context(self, df: pd.DataFrame, price: float | None = None) -> dict[str, Any]:
        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 200:
            return {
                "available": False,
                "bias": "UNKNOWN",
                "ema50": None,
                "ema200": None,
                "price_above_50": None,
                "price_above_200": None,
                "ema_cross": "UNAVAILABLE",
                "ema50_slope": 0.0,
                "ema200_slope": 0.0,
                "entry_trigger": False,
            }
        close = pd.to_numeric(df["close"], errors="coerce").astype(float)
        if close.isna().any():
            return {
                "available": False,
                "bias": "UNKNOWN",
                "ema50": None,
                "ema200": None,
                "price_above_50": None,
                "price_above_200": None,
                "ema_cross": "UNAVAILABLE",
                "ema50_slope": 0.0,
                "ema200_slope": 0.0,
                "entry_trigger": False,
            }
        px = float(close.iloc[-1] if price is None else price)
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        e50 = float(ema50.iloc[-1])
        e200 = float(ema200.iloc[-1])
        bull = px > e200 and e50 > e200
        bear = px < e200 and e50 < e200
        spread = ema50 - ema200
        cross = "NONE"
        recent_start = max(1, len(spread) - 6)
        for idx in range(recent_start, len(spread)):
            prev = float(spread.iloc[idx - 1])
            curr = float(spread.iloc[idx])
            if prev <= 0 < curr:
                cross = "BULLISH_RECENT"
            elif prev >= 0 > curr:
                cross = "BEARISH_RECENT"
        spread_prev = float(spread.iloc[-2])
        spread_now = float(spread.iloc[-1])
        lookback = min(5, len(ema50) - 1)
        slope50 = float(ema50.iloc[-1] - ema50.iloc[-1 - lookback])
        slope200 = float(ema200.iloc[-1] - ema200.iloc[-1 - lookback])
        return {
            "available": True,
            "bias": "BULLISH" if bull else ("BEARISH" if bear else "TRANSITION"),
            "ema50": e50,
            "ema200": e200,
            "price_above_50": px > e50,
            "price_above_200": px > e200,
            "ema_cross": cross,
            "ema50_slope": slope50,
            "ema200_slope": slope200,
            "entry_trigger": False,
        }

    def compute_vwap_context(self, df: pd.DataFrame, price: float | None = None) -> dict[str, Any]:
        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 2:
            return {"available": False, "value": None, "side": "UNKNOWN", "slope": 0.0, "reclaim": False, "reject": False}
        work = df.copy()
        close = pd.to_numeric(work["close"], errors="coerce").astype(float)
        high = pd.to_numeric(work["high"], errors="coerce").astype(float)
        low = pd.to_numeric(work["low"], errors="coerce").astype(float)
        vol = pd.to_numeric(work["volume"], errors="coerce").astype(float).clip(lower=0.0)
        typical = (high + low + close) / 3.0
        ts = work["timestamp"] if "timestamp" in work.columns else None
        if ts is not None:
            parsed = pd.to_datetime(ts, utc=True, errors="coerce")
        else:
            parsed = None
        if parsed is not None and not parsed.isna().all():
            session_key = parsed.dt.floor("D")
        else:
            session_key = pd.Series(0, index=work.index)
        pv = typical * vol
        cum_pv = pv.groupby(session_key, sort=False).cumsum()
        cum_vol = vol.groupby(session_key, sort=False).cumsum()
        session_vwap = cum_pv / cum_vol.replace(0, np.nan)
        session_vwap = session_vwap.ffill().bfill().fillna(close)
        v = float(session_vwap.iloc[-1])
        px = float(close.iloc[-1] if price is None else price)
        slope = float(session_vwap.iloc[-1] - session_vwap.iloc[-2])
        side = "ABOVE" if px > v else ("BELOW" if px < v else "AT")
        prev_px = float(close.iloc[-2])
        prev_v = float(session_vwap.iloc[-2])
        reclaim_up = prev_px <= prev_v and px > v
        reclaim_down = prev_px >= prev_v and px < v
        reclaim = reclaim_up or reclaim_down
        reclaim_side = "BUY" if reclaim_up else ("SELL" if reclaim_down else None)
        # Rejection means the last bar crossed VWAP intrabar but closed back away.
        last_high = float(high.iloc[-1])
        last_low = float(low.iloc[-1])
        reject = (last_low <= v <= last_high) and not reclaim and abs(px - v) > 0
        return {
            "available": True,
            "value": v,
            "side": side,
            "slope": slope,
            "distance": (px - v) / v if v else 0.0,
            "reclaim": bool(reclaim),
            "reclaim_side": reclaim_side,
            "reject": bool(reject),
        }

    def detect_liquidity_event(self, df: pd.DataFrame, side: str, atr: float) -> dict[str, Any]:
        side = str(side).upper()
        default = {
            "detected": False, "direction": side, "level": None, "depth": 0.0,
            "depth_atr": 0.0, "reclaimed": False, "wick_ratio": 0.0,
            "touches": 0, "quality": 0.0, "sweep_index": None,
            "reclaim_index": None,
        }
        if df is None or not isinstance(df, pd.DataFrame) or len(df) < 6 or atr <= 0:
            return default
        look = df.tail(min(40, len(df))).reset_index(drop=True)
        atr = float(atr)
        # Evaluate a small event window so a sweep on the previous bar followed
        # by a reclaim on the current bar remains actionable. This avoids the
        # fragile "only inspect the last candle" behaviour of the old engine.
        candidate_indices = list(range(max(1, len(look) - 4), len(look)))
        for sweep_idx in reversed(candidate_indices):
            if sweep_idx >= len(look) - 1:
                continue
            current = look.iloc[sweep_idx]
            prior = look.iloc[:sweep_idx]
            if side == "BUY":
                raw = prior["low"].astype(float).tail(30).to_numpy()
                cur_low = float(current["low"])
                cur_open = float(current["open"])
                cur_close = float(current["close"])
            else:
                raw = prior["high"].astype(float).tail(30).to_numpy()
                cur_high = float(current["high"])
                cur_open = float(current["open"])
                cur_close = float(current["close"])
            if len(raw) < 3:
                continue
            band = max(0.20 * atr, abs(float(raw[-1])) * 0.0005)
            levels = []
            for value in raw:
                cluster = [x for x in raw if abs(float(x) - float(value)) <= band]
                if len(cluster) >= 2:
                    levels.append((float(np.mean(cluster)), len(cluster)))
            if not levels:
                continue
            if side == "BUY":
                ceiling = cur_low + max(1.5 * atr, abs(cur_low) * 0.005)
                relevant = [item for item in levels if cur_low < item[0] <= ceiling]
                if not relevant:
                    continue
                level, touches = max(relevant, key=lambda x: (float(x[0]), x[1]))
                depth = level - cur_low
                wick = min(cur_open, cur_close) - cur_low
                favorable_close = cur_close > level
            else:
                relevant = [item for item in levels if item[0] >= cur_high - band]
                if not relevant:
                    continue
                level, touches = min(relevant, key=lambda x: (float(x[0]), -x[1]))
                depth = cur_high - level
                wick = cur_high - max(cur_open, cur_close)
                favorable_close = cur_close < level
            threshold = max(0.10 * atr, abs(level) * 0.00025)
            if depth <= threshold:
                continue
            body = abs(cur_close - cur_open)
            wick_ratio = wick / max(body, 1e-9)
            depth_atr = depth / atr
            # Reclaim may happen on the same sweep bar or the immediately following bar.
            reclaim_idx = sweep_idx if favorable_close else None
            if reclaim_idx is None and sweep_idx + 1 < len(look):
                nxt = look.iloc[sweep_idx + 1]
                next_close = float(nxt["close"])
                reclaimed_next = next_close > level if side == "BUY" else next_close < level
                if reclaimed_next:
                    reclaim_idx = sweep_idx + 1
            if reclaim_idx is None:
                continue
            touch_score = min(touches / 3.0, 1.0)
            depth_score = min(depth_atr / 1.0, 1.0)
            wick_score = min(max(wick_ratio, 0.0) / 2.0, 1.0)
            quality = 0.45 + 0.20 * touch_score + 0.20 * depth_score + 0.15 * wick_score
            return {
                "detected": True,
                "direction": side,
                "level": level,
                "depth": depth,
                "depth_atr": depth_atr,
                "reclaimed": True,
                "wick_ratio": wick_ratio,
                "touches": touches,
                "quality": min(1.0, quality),
                "sweep_index": sweep_idx,
                "reclaim_index": reclaim_idx,
            }
        return default

    def classify_entry_window(self, price: float, atr: float, origin: float | None, setup_type: str) -> str:
        if atr <= 0 or origin is None or origin <= 0:
            return "UNKNOWN"
        distance_atr = abs(float(price) - float(origin)) / float(atr)
        if setup_type == "LIQUIDITY_REVERSAL":
            if distance_atr <= 1.5:
                return "EARLY"
            if distance_atr <= 2.5:
                return "CONFIRMED"
            if distance_atr <= 3.5:
                return "EXPANDED"
            return "LATE"
        if distance_atr <= 1.0:
            return "EARLY"
        if distance_atr <= 2.0:
            return "CONFIRMED"
        if distance_atr <= 3.0:
            return "EXPANDED"
        return "LATE"

    def compute_dynamic_sl(self, side: str, price: float, atr: float, event: dict[str, Any], zone: dict[str, Any] | None) -> tuple[float, str]:
        side = str(side).upper()
        atr = float(atr or 0.0)
        px = float(price)
        event_level = float(event.get("level") or 0.0)
        zone = zone or {}
        zone_low = float(zone.get("low") or zone.get("price") or 0.0)
        zone_high = float(zone.get("high") or zone.get("price") or 0.0)
        quality = float(event.get("quality", 0.0) or 0.0)
        depth_atr = float(event.get("depth_atr", 0.0) or 0.0)
        buffer_atr = 0.20 + min(0.35, max(0.05, depth_atr * 0.15))
        buffer = atr * buffer_atr
        if quality >= 0.75 and event_level:
            if side == "BUY":
                sl = event_level - buffer
            else:
                sl = event_level + buffer
            basis = "LIQUIDITY_INVALIDATION"
        else:
            if side == "BUY":
                anchor = zone_low if zone_low > 0 else px - atr
                sl = anchor - buffer
            else:
                anchor = zone_high if zone_high > 0 else px + atr
                sl = anchor + buffer
            basis = "ZONE_INVALIDATION"
        if side == "BUY":
            sl = min(sl, px - max(0.25 * atr, px * 0.001))
        else:
            sl = max(sl, px + max(0.25 * atr, px * 0.001))
        return float(sl), basis

    def assess(
        self,
        *,
        df: pd.DataFrame,
        side: str,
        price: float,
        atr: float,
        zone: dict[str, Any] | None = None,
        structure_ok: bool = False,
        displacement_ok: bool = False,
        rejection_ok: bool = False,
        compression: bool | None = None,
        market_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        side = str(side).upper()
        direction = self.compute_direction_context(df, price)
        vwap = self.compute_vwap_context(df, price)
        event = self.detect_liquidity_event(df, side, float(atr or 0.0))
        if market_state is None:
            regime_engine = MarketRegimeEngine()
            market_state = regime_engine.analyze(
                df,
                structure={
                    "direction": side if structure_ok else "UNKNOWN",
                    "mss": bool(structure_ok),
                    "bos": bool(structure_ok),
                },
                liquidity={
                    "direction": side,
                    "detected": bool(event.get("detected")),
                    "sweep": bool(event.get("detected")),
                    "reclaimed": bool(event.get("reclaimed")),
                    "quality": float(event.get("quality", 0.0) or 0.0),
                },
                vpa={
                    "displacement": "BULLISH" if side == "BUY" and displacement_ok else ("BEARISH" if side == "SELL" and displacement_ok else "NONE"),
                    "absorption": bool(event.get("detected")) and bool(rejection_ok),
                    "effort_result": "ABSORPTION" if rejection_ok else "UNAVAILABLE",
                },
            ).to_dict()
        zone = zone or {}
        zone_quality = float(zone.get("quality", zone.get("strength", 0.0)) or 0.0)
        if zone_quality > 10:
            zone_quality /= 10.0
        zone_price = float(zone.get("price") or 0.0)
        near_zone = bool(zone_price and atr and abs(float(price) - zone_price) <= 2.0 * float(atr))
        if event["detected"] and structure_ok:
            setup_type = "LIQUIDITY_REVERSAL"
            origin = event.get("level") or zone_price
        elif (compression is True or self._compression_proxy(df)) and displacement_ok and structure_ok:
            setup_type = "EARLY_EXPANSION"
            origin = zone_price or price
        elif near_zone and structure_ok:
            setup_type = "TREND_PULLBACK"
            origin = zone_price
        else:
            setup_type = "UNDEFINED"
            origin = zone_price or event.get("level")

        window = self.classify_entry_window(float(price), float(atr or 0.0), origin, setup_type)
        trigger_ok = bool(structure_ok and (displacement_ok or rejection_ok))
        directional_context_ok = (
            (side == "BUY" and direction["bias"] in {"BULLISH", "TRANSITION"})
            or (side == "SELL" and direction["bias"] in {"BEARISH", "TRANSITION"})
        )
        aligned_vwap_reclaim = bool(vwap.get("reclaim") and vwap.get("reclaim_side") == side)
        context_support = (
            (side == "BUY" and vwap["side"] == "ABOVE")
            or (side == "SELL" and vwap["side"] == "BELOW")
            or aligned_vwap_reclaim
        )
        structural_core = bool(zone_quality >= 0.60 and trigger_ok and (event["detected"] or near_zone))
        if setup_type == "LIQUIDITY_REVERSAL":
            structural_core = structural_core and bool(event["reclaimed"] and event["quality"] >= 0.55)
        regime_state = str((market_state or {}).get("state", "UNKNOWN")).upper()
        ema_ctx = (market_state or {}).get("ema", {}) or {}
        crossing_phase = str(ema_ctx.get("crossing_phase", "UNKNOWN")).upper()
        early_cross_phase = crossing_phase in {"PRE_CROSS_BULLISH", "PRE_CROSS_BEARISH", "POST_CROSS_EARLY"}
        transition_side_ok = (
            (side == "BUY" and crossing_phase in {"PRE_CROSS_BULLISH", "POST_CROSS_EARLY"})
            or (side == "SELL" and crossing_phase in {"PRE_CROSS_BEARISH", "POST_CROSS_EARLY"})
        )
        contradictory_regime = (
            (side == "BUY" and regime_state in {"DISTRIBUTION", "RE_DISTRIBUTION", "MARKDOWN"})
            or (side == "SELL" and regime_state in {"ACCUMULATION", "RE_ACCUMULATION", "MARKUP"})
        )
        if contradictory_regime:
            structural_core = False
        if not directional_context_ok and event["quality"] < 0.80:
            structural_core = False
        if window == "LATE":
            structural_core = False
        # Professional early-trend contract: technical entries are only admitted
        # while the EMA transition is forming or has just crossed. EMA50/EMA200
        # remain context; the actual trigger is still structure + liquidity +
        # displacement/rejection. This gate exists to prevent the exact failure
        # where BARON buys a mature expansion after the trend has already run.
        if not transition_side_ok:
            structural_core = False
        decision = "REJECT" if window == "LATE" or not transition_side_ok else ("APPROVE" if structural_core else "WAIT")
        if not direction["available"] or not vwap["available"]:
            decision = "WAIT" if decision == "APPROVE" else decision
        sl, sl_basis = self.compute_dynamic_sl(side, float(price), float(atr or 0.0), event, zone)
        reasons = []
        reasons.append(f"DIRECTION_{direction['bias']}")
        reasons.append(f"VWAP_{vwap['side']}")
        if aligned_vwap_reclaim:
            reasons.append("VWAP_RECLAIM")
        if event["detected"]:
            reasons.append("LIQUIDITY_SWEEP_QUALITY")
            if event["reclaimed"]:
                reasons.append("LIQUIDITY_RECLAIM")
        if structure_ok:
            reasons.append("STRUCTURE_TRIGGER")
        if displacement_ok:
            reasons.append("DISPLACEMENT")
        if rejection_ok:
            reasons.append("REJECTION")
        if window == "LATE":
            reasons.append("ENTRY_TOO_LATE")
        if transition_side_ok:
            reasons.append(f"EMA_CROSSING_START_{crossing_phase}")
        else:
            reasons.append(f"EMA_CROSSING_MATURE_{crossing_phase}")
        if not context_support:
            reasons.append("VWAP_NOT_SUPPORTIVE")
        if regime_state != "UNKNOWN":
            reasons.append(f"MARKET_STATE_{regime_state}")
        if contradictory_regime:
            reasons.append("MARKET_STATE_CONTRADICTION")
        thesis = {
            "invalidation": sl,
            "invalidation_basis": sl_basis,
            "origin": origin,
            "context_support": context_support,
            "directional_context_ok": directional_context_ok,
            # Stable identity for stop-hunt continuity. Volatility-dependent
            # stop distance is deliberately excluded so a later revalidation
            # can match the same structural thesis even if ATR changed.
            "fingerprint": hashlib.sha256(json.dumps({
                "side": side,
                "setup_type": setup_type,
                "origin": round(float(origin or 0.0), 8),
                "liquidity_level": round(float(event.get("level") or 0.0), 8),
                "zone_price": round(float(zone_price or 0.0), 8),
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20],
        }
        assessment = EntryAssessment(
            decision=decision,
            side=side,
            setup_type=setup_type,
            entry_window=window,
            direction=direction,
            vwap=vwap,
            liquidity_event=event,
            thesis=thesis,
            reasons=reasons,
            market_state=market_state or {},
            metrics={
                "atr": float(atr or 0.0),
                "zone_quality": zone_quality,
                "near_zone": near_zone,
                "trigger_ok": trigger_ok,
                "structural_core": structural_core,
                "market_state": market_state or {},
                "crossing_phase": crossing_phase,
                "early_transition": bool(transition_side_ok),
            },
        )
        return assessment.to_dict()

    @staticmethod
    def _compression_proxy(df: pd.DataFrame) -> bool:
        if df is None or len(df) < 20:
            return False
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        ranges = (high - low).rolling(20).mean()
        current = float(ranges.iloc[-1])
        prior = float(ranges.iloc[-6]) if pd.notna(ranges.iloc[-6]) else current
        return current < prior * 0.8 if prior > 0 else False
