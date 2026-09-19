"""BARON Trend Strategy v29 - unified, liquidity-aware trend entry authority.

This module is deliberately side-effect free: it evaluates a completed OHLCV
frame and optional order book, then returns an explainable decision packet.
It never opens, closes, sizes, or manages a position.

Design:
    Liquidity map -> structure -> trend context -> pullback quality
    -> momentum/volume/flow -> RF -> entry timing -> structural invalidation SL
    -> two-stage targets.

The strategy is intended to be the single technical-entry decision layer.
Existing scanners remain discovery/evidence providers; they are not independent
technical entry authorities once this strategy is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np
import pandas as pd


@dataclass
class TrendDecision:
    approved: bool
    side: str
    score: float
    classification: str
    reason: str
    reasons: List[str]
    blockers: List[str]
    metrics: Dict[str, Any]
    sl: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    context: Dict[str, Any] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["context"] = self.context or {}
        return d


class BaronTrendStrategyV29:
    """Strict trend-continuation strategy with liquidity-aware risk."""

    def __init__(
        self,
        *,
        swing_lb: int = 5,
        cluster_tol: float = 0.002,
        eq_tol: float = 0.0015,
        rf_max_distance: float = 0.003,
        min_score: float = 78.0,
        min_adx: float = 25.0,
        max_adx: float = 45.0,
        min_di_spread: float = 5.0,
    ):
        self.swing_lb = swing_lb
        self.cluster_tol = cluster_tol
        self.eq_tol = eq_tol
        self.rf_max_distance = rf_max_distance
        self.min_score = min_score
        self.min_adx = min_adx
        self.max_adx = max_adx
        self.min_di_spread = min_di_spread

    @staticmethod
    def _rma(s: pd.Series, period: int = 14) -> pd.Series:
        return s.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    def _adx_di(self, df: pd.DataFrame, period: int = 14):
        h, l, c = df["high"], df["low"], df["close"]
        tr = pd.concat(
            [(h-l), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1
        ).max(axis=1)
        atr = self._rma(tr, period)
        up = h.diff()
        down = -l.diff()
        plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
        plus_di = 100.0 * self._rma(plus_dm, period) / atr.replace(0, np.nan)
        minus_di = 100.0 * self._rma(minus_dm, period) / atr.replace(0, np.nan)
        denom = (plus_di + minus_di).replace(0, np.nan)
        dx = (100.0 * (plus_di - minus_di).abs() / denom).fillna(0)
        adx = self._rma(dx, period)
        return atr, plus_di, minus_di, adx

    @staticmethod
    def _vwap(df: pd.DataFrame) -> float:
        vol = df["volume"].astype(float)
        denom = float(vol.sum())
        if denom <= 0:
            return float(df["close"].iloc[-1])
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        return float((tp * vol).sum() / denom)

    def _swings(self, df: pd.DataFrame) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        lb = self.swing_lb
        highs, lows = [], []
        if len(df) < 2 * lb + 3:
            return highs, lows
        h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float)
        for i in range(lb, len(df)-lb):
            if h[i] >= np.max(h[i-lb:i+lb+1]):
                highs.append((i, float(h[i])))
            if l[i] <= np.min(l[i-lb:i+lb+1]):
                lows.append((i, float(l[i])))
        return highs, lows

    @staticmethod
    def _clusters(points: List[Tuple[int, float]], tol: float) -> List[dict]:
        if not points:
            return []
        vals = sorted(points, key=lambda x: x[1])
        clusters = []
        cur = [vals[0]]
        for p in vals[1:]:
            anchor = cur[-1][1]
            if anchor and abs(p[1] - anchor) / abs(anchor) <= tol:
                cur.append(p)
            else:
                clusters.append(cur)
                cur = [p]
        clusters.append(cur)
        out = []
        for c in clusters:
            prices = [x[1] for x in c]
            out.append({
                "level": float(np.mean(prices)),
                "count": len(c),
                "min": float(min(prices)),
                "max": float(max(prices)),
                "indices": [x[0] for x in c],
            })
        return out

    def _liquidity_map(self, df: pd.DataFrame, price: float) -> dict:
        sh, sl = self._swings(df)
        high_clusters = self._clusters(sh, self.cluster_tol)
        low_clusters = self._clusters(sl, self.cluster_tol)
        eqh = [c for c in high_clusters if c["count"] >= 2]
        eql = [c for c in low_clusters if c["count"] >= 2]

        def nearest_above(clusters):
            xs = [c for c in clusters if c["level"] > price * 1.0001]
            return min(xs, key=lambda x: x["level"]) if xs else None

        def nearest_below(clusters):
            xs = [c for c in clusters if c["level"] < price * 0.9999]
            return max(xs, key=lambda x: x["level"]) if xs else None

        # A liquidity target gets stronger as the repeated level count rises and
        # as the level is close enough to be a realistic next objective.
        def attraction(c):
            if not c:
                return 0.0
            dist = abs(c["level"] - price) / price
            count_bonus = min(30.0, 12.0 * max(0, c["count"] - 1))
            proximity = max(0.0, 35.0 * (1.0 - dist / 0.03))
            return min(100.0, 35.0 + count_bonus + proximity)

        return {
            "swing_highs": sh[-8:],
            "swing_lows": sl[-8:],
            "high_clusters": high_clusters[-12:],
            "low_clusters": low_clusters[-12:],
            "equal_highs": eqh[-8:],
            "equal_lows": eql[-8:],
            "target_above": nearest_above(eqh) or nearest_above(high_clusters),
            "target_below": nearest_below(eql) or nearest_below(low_clusters),
            "target_above_attraction": attraction(nearest_above(eqh) or nearest_above(high_clusters)),
            "target_below_attraction": attraction(nearest_below(eql) or nearest_below(low_clusters)),
        }

    def _sweep(self, df: pd.DataFrame, liq: dict) -> Tuple[bool, bool, float, str]:
        if len(df) < 2:
            return False, False, 0.0, "NONE"
        last, prev = df.iloc[-1], df.iloc[-2]
        high_pools = [c["level"] for c in liq["equal_highs"]]
        low_pools = [c["level"] for c in liq["equal_lows"]]
        # If no equal cluster exists, use the most recent confirmed swing.
        if not high_pools and liq["swing_highs"]:
            high_pools = [liq["swing_highs"][-1][1]]
        if not low_pools and liq["swing_lows"]:
            low_pools = [liq["swing_lows"][-1][1]]

        swept_high = False
        swept_low = False
        sweep_level = 0.0
        for x in high_pools:
            if float(last["high"]) > x and float(prev["high"]) <= x and float(last["close"]) < x:
                swept_high, sweep_level = True, float(x)
                break
        for x in low_pools:
            if float(last["low"]) < x and float(prev["low"]) >= x and float(last["close"]) > x:
                swept_low, sweep_level = True, float(x)
                break
        if swept_low:
            return False, True, sweep_level, "SELL_SIDE_TAKEN"
        if swept_high:
            return True, False, sweep_level, "BUY_SIDE_TAKEN"
        return False, False, 0.0, "NONE"

    def _structure(self, df: pd.DataFrame) -> dict:
        sh, sl = self._swings(df)
        bos_up = bos_down = False
        shift = None
        if len(df) >= 8:
            prior_h = float(df["high"].iloc[-7:-1].max())
            prior_l = float(df["low"].iloc[-7:-1].min())
            close = float(df["close"].iloc[-1])
            bos_up, bos_down = close > prior_h, close < prior_l
        if len(sh) >= 2 and len(sl) >= 2:
            if sh[-1][1] > sh[-2][1] and sl[-1][1] > sl[-2][1]:
                shift = "bullish_shift"
            elif sh[-1][1] < sh[-2][1] and sl[-1][1] < sl[-2][1]:
                shift = "bearish_shift"
        return {"bos_up": bos_up, "bos_down": bos_down, "shift": shift,
                "last_swing_high": sh[-1][1] if sh else None,
                "last_swing_low": sl[-1][1] if sl else None}

    def _pullback(self, df: pd.DataFrame, side: str, atr: float, plus: float, minus: float, adx: float) -> dict:
        n = min(4, len(df))
        x = df.iloc[-n:]
        bodies = (x["close"] - x["open"]).abs()
        ranges = (x["high"] - x["low"]).replace(0, np.nan)
        lower = np.minimum(x["open"], x["close"]) - x["low"]
        upper = x["high"] - np.maximum(x["open"], x["close"])
        avg_body = float(bodies.mean())
        avg_lower = float(lower.mean())
        avg_upper = float(upper.mean())
        avg_vol = float(df["volume"].iloc[-20:].mean())
        last_vol = float(df["volume"].iloc[-1])
        trend_dom = (side == "BUY" and plus > minus) or (side == "SELL" and minus > plus)
        adx_series = self._adx_di(df)[3]
        rising_adx = len(adx_series.dropna()) >= 2 and float(adx_series.iloc[-1]) >= float(adx_series.iloc[-2])

        weak = (
            avg_body < atr * 0.4 and
            ((side == "BUY" and avg_lower > avg_body) or (side == "SELL" and avg_upper > avg_body)) and
            (last_vol < avg_vol * 0.9 if avg_vol > 0 else True) and
            trend_dom and rising_adx and adx >= 18
        )

        # Medium pullback: deeper correction, but no thesis failure. It must be
        # followed by a trigger candle in the intended direction; entry is only
        # allowed when price is at/near a structural/liquidity zone.
        opposite_body = float(abs(x["close"].iloc[-1] - x["open"].iloc[-1]))
        opposite = (side == "BUY" and x["close"].iloc[-1] < x["open"].iloc[-1]) or \
                   (side == "SELL" and x["close"].iloc[-1] > x["open"].iloc[-1])
        depth = float(abs(x["close"].iloc[-1] - x["close"].iloc[0]) / max(atr, 1e-12))
        medium = (
            opposite and depth >= 0.35 and depth <= 1.8 and
            trend_dom and adx >= 20
        )

        reversal = bool(opposite and avg_vol > 0 and last_vol > avg_vol * 1.5 and not trend_dom)
        if reversal:
            return {"state": "REVERSAL", "depth_atr": depth, "avg_body": avg_body}
        if weak:
            state = "WEAK_PULLBACK"
        elif medium:
            state = "MEDIUM_PULLBACK"
        elif opposite:
            state = "STRONG_PULLBACK"
        else:
            state = "NO_PULLBACK"
        return {"state": state, "depth_atr": round(depth, 3), "avg_body": avg_body,
                "avg_lower": avg_lower, "avg_upper": avg_upper, "trend_dom": trend_dom,
                "rising_adx": rising_adx}

    def _rejection(self, df: pd.DataFrame, side: str) -> bool:
        c = df.iloc[-1]
        body = abs(float(c["close"] - c["open"]))
        rng = max(float(c["high"] - c["low"]), 1e-12)
        lw = min(float(c["open"]), float(c["close"])) - float(c["low"])
        uw = float(c["high"]) - max(float(c["open"]), float(c["close"]))
        if side == "BUY":
            return lw > max(body * 1.2, rng * 0.35) and c["close"] >= c["open"]
        return uw > max(body * 1.2, rng * 0.35) and c["close"] <= c["open"]

    def _volume_flow(self, df: pd.DataFrame, side: str) -> dict:
        avg = float(df["volume"].iloc[-20:].mean())
        vol = float(df["volume"].iloc[-1])
        ratio = vol / avg if avg > 0 else 0.0
        body = float(df["close"].iloc[-1] - df["open"].iloc[-1])
        rng = max(float(df["high"].iloc[-1] - df["low"].iloc[-1]), 1e-12)
        if ratio >= 1.8:
            state = "EXPANSION"
        elif ratio >= 1.3:
            state = "NORMAL"
        elif ratio < 0.7:
            state = "EXHAUSTION"
        else:
            state = "NEUTRAL"
        flow = "aggressive_buy" if ratio >= 1.5 and body > 0 else \
               "aggressive_sell" if ratio >= 1.5 and body < 0 else \
               "absorption" if ratio >= 1.0 and abs(body) / rng < 0.3 else "neutral"
        aligned = (side == "BUY" and flow == "aggressive_buy") or (side == "SELL" and flow == "aggressive_sell")
        return {"state": state, "ratio": round(ratio, 3), "flow": flow, "aligned": aligned}

    def _momentum(self, df: pd.DataFrame, side: str) -> dict:
        e9 = df["close"].ewm(span=9, adjust=False).mean()
        e21 = df["close"].ewm(span=21, adjust=False).mean()
        spread = float((e9.iloc[-1] - e21.iloc[-1]) / max(e21.iloc[-1], 1e-12) * 100)
        rsi_delta = df["close"].diff()
        gain = rsi_delta.clip(lower=0)
        loss = -rsi_delta.clip(upper=0)
        ag = self._rma(gain, 14)
        al = self._rma(loss, 14).replace(0, np.nan)
        rsi = float((100 - 100 / (1 + ag.iloc[-1] / al.iloc[-1])) if pd.notna(al.iloc[-1]) else 50.0)
        aligned = spread > 0 if side == "BUY" else spread < 0
        return {"ema9_21_spread_pct": round(spread, 4), "rsi": round(rsi, 2),
                "aligned": aligned, "expansion": abs(spread) > 0.35,
                "decay": abs(spread) < 0.05, "climax": rsi > 75 if side == "BUY" else rsi < 25}

    def _orderbook(self, ob: Any, side: str) -> dict:
        if not isinstance(ob, dict):
            return {"imbalance": 0.0, "aligned": False}
        bids, asks = ob.get("bids") or [], ob.get("asks") or []
        try:
            b = sum(float(x[1]) for x in bids[:10])
            a = sum(float(x[1]) for x in asks[:10])
            total = b + a
            imb = (b-a)/total if total > 0 else 0.0
        except Exception:
            imb = 0.0
        aligned = (side == "BUY" and imb > 0.05) or (side == "SELL" and imb < -0.05)
        return {"imbalance": round(imb, 4), "aligned": aligned}

    def _sl_tp(self, side: str, price: float, atr: float, liq: dict, sweep_level: float, structure: dict) -> Tuple[float, float, float, dict]:
        # Structural invalidation first; liquidity sweep level is part of the
        # causal thesis. The buffer keeps the stop outside the normal sweep zone.
        if side == "BUY":
            candidates = [x for x in [
                sweep_level,
                structure.get("last_swing_low"),
                (liq.get("target_below") or {}).get("level"),
            ] if x and x < price]
            base = min(candidates) if candidates else price - 1.6 * atr
            sl = base - 0.28 * atr
            min_dist = 0.8 * atr
            max_dist = 2.8 * atr
            if price - sl < min_dist:
                sl = price - min_dist
            valid = price - sl <= max_dist
            target = (liq.get("target_above") or {}).get("level")
            floor1, floor2 = price + 2.5*atr, price + 4.0*atr
            tp1 = max(price + 0.008*price, floor1)
            tp2 = max(price + 0.02*price, floor2)
            if target and target > price:
                tp2 = max(tp2, float(target))
                tp1 = min(tp2 - max(1.5*atr, 0.004*price), max(price + 0.008*price, floor1))
        else:
            candidates = [x for x in [
                sweep_level,
                structure.get("last_swing_high"),
                (liq.get("target_above") or {}).get("level"),
            ] if x and x > price]
            base = max(candidates) if candidates else price + 1.6 * atr
            sl = base + 0.28 * atr
            min_dist = 0.8 * atr
            max_dist = 2.8 * atr
            if sl - price < min_dist:
                sl = price + min_dist
            valid = sl - price <= max_dist
            target = (liq.get("target_below") or {}).get("level")
            floor1, floor2 = price - 2.5*atr, price - 4.0*atr
            tp1 = min(price - 0.008*price, floor1)
            tp2 = min(price - 0.02*price, floor2)
            if target and target < price:
                tp2 = min(tp2, float(target))
                tp1 = max(tp2 + max(1.5*atr, 0.004*price), min(price - 0.008*price, floor1))
        return float(sl), float(tp1), float(tp2), {"structural": True, "valid": valid, "sweep_level": sweep_level}

    def evaluate(self, symbol: str, side: str, df: pd.DataFrame, ob: Any = None, rf: Optional[dict] = None) -> TrendDecision:
        side = str(side).upper()
        blockers, reasons = [], []
        if side not in ("BUY", "SELL") or df is None or len(df) < 80:
            return TrendDecision(False, side, 0, "NO_TRADE", "INSUFFICIENT_DATA", [], ["INSUFFICIENT_DATA"], {}, context={})

        required = ("open", "high", "low", "close", "volume")
        if any(c not in df.columns for c in required):
            return TrendDecision(False, side, 0, "NO_TRADE", "MISSING_OHLCV", [], ["MISSING_OHLCV"], {}, context={})

        df = df.copy()
        atr_s, plus_s, minus_s, adx_s = self._adx_di(df)
        atr = float(atr_s.iloc[-1]); plus = float(plus_s.iloc[-1]); minus = float(minus_s.iloc[-1]); adx = float(adx_s.iloc[-1])
        price = float(df["close"].iloc[-1])
        vwap = self._vwap(df)
        ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])
        di_spread = plus - minus if side == "BUY" else minus - plus
        aligned = (side == "BUY" and plus > minus and ema20 > ema50 and price > ema20) or \
                   (side == "SELL" and minus > plus and ema20 < ema50 and price < ema20)
        structure = self._structure(df)
        if side == "BUY" and structure["shift"] == "bullish_shift": aligned = True
        if side == "SELL" and structure["shift"] == "bearish_shift": aligned = True

        liq = self._liquidity_map(df, price)
        swept_high, swept_low, sweep_level, sweep_state = self._sweep(df, liq)
        sweep_ok = swept_low if side == "BUY" else swept_high
        pull = self._pullback(df, side, atr, plus, minus, adx)
        vf = self._volume_flow(df, side)
        mom = self._momentum(df, side)
        obx = self._orderbook(ob, side)
        rf_signal = (rf or {}).get("signal")
        rf_dist = abs(float((rf or {}).get("distance", 999))) if (rf or {}).get("distance") is not None else 999
        vwap_aligned = price >= vwap if side == "BUY" else price <= vwap
        vwap_reclaim = False
        if len(df) >= 2:
            prev = float(df["close"].iloc[-2])
            vwap_reclaim = (prev < vwap <= price) if side == "BUY" else (prev > vwap >= price)
        rejection = self._rejection(df, side)
        structure_ok = (side == "BUY" and (structure["bos_up"] or structure["shift"] == "bullish_shift")) or \
                       (side == "SELL" and (structure["bos_down"] or structure["shift"] == "bearish_shift"))
        target = liq["target_above"] if side == "BUY" else liq["target_below"]
        target_attraction = liq["target_above_attraction"] if side == "BUY" else liq["target_below_attraction"]

        # Hard thesis gates.
        if adx < self.min_adx: blockers.append(f"ADX<{self.min_adx:.0f}")
        if adx > self.max_adx and not (di_spread > 10 and float(adx_s.iloc[-1]) > float(adx_s.iloc[-2])):
            blockers.append("ADX_EXHAUSTION")
        if di_spread < self.min_di_spread: blockers.append("DI_SPREAD_WEAK")
        if not aligned: blockers.append("TREND_ALIGNMENT_FAIL")
        if not sweep_ok: blockers.append("LIQUIDITY_SWEEP_MISSING")
        if not structure_ok: blockers.append("STRUCTURE_CONFIRMATION_MISSING")
        if vf["state"] not in ("EXPANSION", "NORMAL") or (vf["state"] == "EXHAUSTION"):
            blockers.append("VOLUME_CONFIRMATION_MISSING")
        if rf_signal != side: blockers.append("RF_MISMATCH")
        if rf_dist > self.rf_max_distance: blockers.append("RF_TOO_FAR")
        if pull["state"] in ("STRONG_PULLBACK", "REVERSAL"): blockers.append(pull["state"])
        if pull["state"] == "MEDIUM_PULLBACK":
            # Medium pullback is allowed only at a causal location with a
            # directional trigger candle; this is deliberately not a rejection.
            zone_near = False
            relevant_clusters = liq["equal_lows"] if side == "BUY" else liq["equal_highs"]
            relevant_swings = liq["swing_lows"] if side == "BUY" else liq["swing_highs"]
            for c in relevant_clusters:
                if abs(price - c["level"]) / price <= 0.006:
                    zone_near = True
                    break
            if not zone_near:
                for _, level in relevant_swings[-5:]:
                    if abs(price - level) <= 1.2 * atr:
                        zone_near = True
                        break
            if not zone_near:
                blockers.append("MEDIUM_PULLBACK_WITHOUT_LIQUIDITY_RETEST")
            if not (rejection or vf["aligned"] or mom["aligned"]):
                blockers.append("MEDIUM_PULLBACK_NO_RECONFIRMATION")

        # Score is evidence, not a substitute for the hard thesis.
        score = 0.0
        score += 12 if aligned else 0
        score += min(12, max(0, di_spread)) * 0.8
        score += 8 if 25 <= adx <= 35 else (5 if 35 < adx <= 45 else 0)
        score += 8 if vwap_aligned else (6 if vwap_reclaim else 0)
        score += 12 if sweep_ok else 0
        score += 8 if structure_ok else 0
        score += 10 if vf["state"] == "EXPANSION" else (6 if vf["state"] == "NORMAL" else 0)
        score += 7 if rejection else 0
        score += 7 if mom["aligned"] else 0
        score += 6 if mom["expansion"] else 0
        score += 5 if obx["aligned"] else 0
        score += min(10, target_attraction * 0.10)
        if pull["state"] == "WEAK_PULLBACK": score += 5
        elif pull["state"] == "MEDIUM_PULLBACK": score += 3
        if target and target["count"] >= 2: reasons.append(f"LIQUIDITY_TARGET:{target['level']:.8g}x{target['count']}")

        if aligned: reasons.append("EMA20/EMA50+PRICE_ALIGNED")
        if di_spread >= self.min_di_spread: reasons.append(f"DI_SPREAD={di_spread:.1f}")
        reasons.append(f"ADX={adx:.1f}")
        if vwap_aligned: reasons.append("VWAP_ALIGNED")
        elif vwap_reclaim: reasons.append("VWAP_RECLAIM")
        if sweep_ok: reasons.append(f"LIQUIDITY_SWEEP:{sweep_state}")
        if structure_ok: reasons.append("STRUCTURE_CONFIRMED")
        reasons.append(f"PULLBACK={pull['state']}")
        if vf["state"] == "EXPANSION": reasons.append("VOLUME_EXPANSION")
        if vf["aligned"]: reasons.append("AGGRESSIVE_FLOW_ALIGNED")
        if mom["aligned"]: reasons.append("MOMENTUM_ALIGNED")
        if rejection: reasons.append("REJECTION_CONFIRMATION")
        if obx["aligned"]: reasons.append("ORDERBOOK_ALIGNED")
        if rf_signal == side: reasons.append("RF_ALIGNED")

        sl, tp1, tp2, sl_meta = self._sl_tp(side, price, atr, liq, sweep_level, structure)
        if not sl_meta["valid"]:
            blockers.append("STRUCTURAL_SL_TOO_WIDE")

        approved = not blockers and score >= self.min_score
        if score < self.min_score:
            blockers.append(f"SCORE<{self.min_score:.0f}")
            approved = False

        classification = "TREND_CONTINUATION" if approved else "NO_TRADE"
        reason = "TREND_V29_APPROVED" if approved else ";".join(blockers[:4])
        metrics = {
            "symbol": symbol,
            "price": price, "atr": atr, "atr_pct": atr/price*100 if price else 0,
            "adx": adx, "adx_slope": float(adx_s.iloc[-1] - adx_s.iloc[-2]) if len(adx_s) >= 2 else 0,
            "di_plus": plus, "di_minus": minus, "di_spread": di_spread,
            "ema20": ema20, "ema50": ema50, "vwap": vwap,
            "vwap_aligned": vwap_aligned, "vwap_reclaim": vwap_reclaim,
            "rf_signal": rf_signal, "rf_distance": rf_dist,
            "sweep": sweep_state, "sweep_level": sweep_level,
            "pullback": pull, "volume_flow": vf, "momentum": mom, "orderbook": obx,
            "structure": structure, "liquidity": liq, "target_attraction": target_attraction,
            "sl_meta": sl_meta,
        }
        context = {
            "strategy_authority": "BARON_TREND_V29",
            "strategy_version": "v29",
            "trade_type": "TREND",
            "entry_type": "LIQUIDITY_PULLBACK_CONTINUATION",
            "market_regime": "TREND",
            "pullback_state": pull["state"],
            "liquidity_event": {"level": sweep_level, "quality": target_attraction, "state": sweep_state},
            "thesis": {"invalidation": sl, "side": side},
            "decision_packet": metrics,
            "reason": reasons,
        }
        return TrendDecision(approved, side, round(score, 2), classification, reason, reasons, blockers, metrics, sl, tp1, tp2, context)


__all__ = ["BaronTrendStrategyV29", "TrendDecision"]
