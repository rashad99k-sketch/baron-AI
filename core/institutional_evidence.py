"""Institutional-style market evidence for BARON.

Pure, deterministic, closed-candle analysis.  This module never places orders,
sizes positions, mutates exchange state, or decides BUY/SELL by itself.

The intent is to combine the strongest reusable ideas from the supplied
reference projects into one explainable evidence packet:
  - liquidity sweep / stop-run detection
  - causal order-block context
  - market-structure shift
  - premium/discount location
  - VWAP + EMA50/EMA200 context
  - ADX/DMI + ATR volatility
  - RSI + MACD momentum context
  - effort-vs-result / VPA
  - accumulation/distribution context
  - temporal sequence validation

A sequence can be incomplete; incomplete evidence is explicitly represented and
never converted into a false confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple
import math

import numpy as np
import pandas as pd


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _side(side: str) -> str:
    s = str(side or "").upper()
    return "BUY" if s in {"BUY", "LONG"} else "SELL" if s in {"SELL", "SHORT"} else ""


def _ema(series: pd.Series, period: int) -> float:
    if len(series) < max(2, min(period, len(series))):
        return 0.0
    return _f(series.ewm(span=period, adjust=False).mean().iloc[-1])


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / (loss + 1e-12)
    return _f((100 - 100 / (1 + rs)).iloc[-1], 50.0)


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    if len(series) < slow + signal:
        return 0.0, 0.0, 0.0
    ef = series.ewm(span=fast, adjust=False).mean()
    es = series.ewm(span=slow, adjust=False).mean()
    line = ef - es
    sig = line.ewm(span=signal, adjust=False).mean()
    return _f(line.iloc[-1]), _f(sig.iloc[-1]), _f((line - sig).iloc[-1])


def _adx(df: pd.DataFrame, period: int = 14) -> Tuple[float, float, float, float]:
    if len(df) < period * 2:
        return 0.0, 0.0, 0.0, 0.0
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    prev = c.shift()
    tr = pd.concat([(h - l).abs(), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period, min_periods=period).mean()
    pdi = 100 * plus_dm.rolling(period, min_periods=period).sum() / (atr * period + 1e-12)
    mdi = 100 * minus_dm.rolling(period, min_periods=period).sum() / (atr * period + 1e-12)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-12)
    adx = dx.rolling(period, min_periods=period).mean()
    cur = _f(adx.iloc[-1])
    prev4 = _f(adx.iloc[-4]) if len(adx) >= 4 else cur
    return cur, _f(pdi.iloc[-1]), _f(mdi.iloc[-1]), cur - prev4


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    prev = df["close"].shift()
    tr = pd.concat([(df["high"] - df["low"]).abs(), (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return _f(tr.rolling(period, min_periods=period).mean().iloc[-1])


def _vwap(df: pd.DataFrame, period: int = 30) -> float:
    p = (df["high"] + df["low"] + df["close"]) / 3.0
    x = df.tail(period)
    v = x["volume"].astype(float)
    den = _f(v.sum())
    return _f((p.tail(len(x)) * v).sum() / den) if den > 0 else _f(p.iloc[-1])


def _swing_levels(df: pd.DataFrame, window: int = 2):
    highs, lows = [], []
    if len(df) < window * 2 + 3:
        return highs, lows
    for i in range(window, len(df) - window):
        hi = _f(df["high"].iloc[i])
        lo = _f(df["low"].iloc[i])
        if hi >= _f(df["high"].iloc[i-window:i+window+1].max()):
            highs.append((i, hi))
        if lo <= _f(df["low"].iloc[i-window:i+window+1].min()):
            lows.append((i, lo))
    return highs, lows


def _detect_sweep(df: pd.DataFrame, side: str, lookback: int = 10) -> Dict[str, Any]:
    s = _side(side)
    highs, lows = _swing_levels(df, 2)
    out = {"detected": False, "type": "NONE", "bar": -1, "level": 0.0, "age": 999,
           "reclaimed": False, "quality": "NONE"}
    if not s or not highs or not lows:
        return out
    start = max(1, len(df) - lookback)
    last_close = _f(df["close"].iloc[-1])
    for i in range(len(df) - 1, start - 1, -1):
        row = df.iloc[i]
        if s == "BUY":
            prior_lows = [v for j, v in lows if j < i]
            if prior_lows:
                level = prior_lows[-1]
                if _f(row["low"]) < level:
                    reclaimed = last_close > level
                    wick = (_f(row["close"]) - _f(row["low"])) / max(_f(row["high"]) - _f(row["low"]), 1e-12)
                    out.update({"detected": True, "type": "SELL_SIDE_SWEEP", "bar": i,
                                "level": level, "age": len(df)-1-i, "reclaimed": reclaimed,
                                "quality": "STRONG" if reclaimed and wick >= 0.45 else "WEAK"})
                    return out
        else:
            prior_highs = [v for j, v in highs if j < i]
            if prior_highs:
                level = prior_highs[-1]
                if _f(row["high"]) > level:
                    reclaimed = last_close < level
                    wick = (_f(row["high"]) - _f(row["close"])) / max(_f(row["high"]) - _f(row["low"]), 1e-12)
                    out.update({"detected": True, "type": "BUY_SIDE_SWEEP", "bar": i,
                                "level": level, "age": len(df)-1-i, "reclaimed": reclaimed,
                                "quality": "STRONG" if reclaimed and wick >= 0.45 else "WEAK"})
                    return out
    return out


def _structure(df: pd.DataFrame, side: str) -> Dict[str, Any]:
    s = _side(side)
    highs, lows = _swing_levels(df, 2)
    out = {"direction": "NEUTRAL", "bos": False, "mss": False, "shift": "NONE", "level": 0.0}
    if len(highs) < 2 or len(lows) < 2 or not s:
        return out
    ph, lh = highs[-2][1], highs[-1][1]
    pl, ll = lows[-2][1], lows[-1][1]
    close = _f(df["close"].iloc[-1])
    bull = close > ph or (lh > ph and ll > pl)
    bear = close < pl or (lh < ph and ll < pl)
    if bull and not bear:
        out["direction"] = "BULLISH"
        out["bos"] = close > ph
        out["mss"] = lh > ph and ll > pl
        out["shift"] = "BULLISH_MSS" if out["mss"] else "BULLISH_BOS" if out["bos"] else "NONE"
        out["level"] = ph
    elif bear and not bull:
        out["direction"] = "BEARISH"
        out["bos"] = close < pl
        out["mss"] = lh < ph and ll < pl
        out["shift"] = "BEARISH_MSS" if out["mss"] else "BEARISH_BOS" if out["bos"] else "NONE"
        out["level"] = pl
    return out


def _premium_discount(df: pd.DataFrame) -> Dict[str, Any]:
    hi = _f(df["high"].tail(50).max())
    lo = _f(df["low"].tail(50).min())
    mid = (hi + lo) / 2.0 if hi and lo else 0.0
    px = _f(df["close"].iloc[-1])
    if not mid:
        return {"state": "UNKNOWN", "mid": 0.0, "high": hi, "low": lo, "position_pct": 50.0}
    pct = (px - lo) / max(hi - lo, 1e-12) * 100.0
    state = "DISCOUNT" if pct <= 45 else "PREMIUM" if pct >= 55 else "EQUILIBRIUM"
    return {"state": state, "mid": mid, "high": hi, "low": lo, "position_pct": round(max(0.0, min(100.0, pct)), 2)}


def _vpa(df: pd.DataFrame, side: str, atr: float) -> Dict[str, Any]:
    if len(df) < 20:
        return {"available": False, "score": 0.0, "classification": "UNAVAILABLE"}
    s = _side(side)
    vol_base = _f(df["volume"].tail(11).iloc[:-1].mean(), 1.0)
    row = df.iloc[-1]
    vr = _f(row["volume"]) / max(vol_base, 1e-12)
    rng = max(_f(row["high"]) - _f(row["low"]), 1e-12)
    body = abs(_f(row["close"]) - _f(row["open"]))
    eff = body / rng
    directional = (s == "BUY" and row["close"] > row["open"]) or (s == "SELL" and row["close"] < row["open"])
    score = 50.0 + (10 if directional else 0) + (15 if vr >= 1.5 and directional and eff >= 0.55 else 0)
    result_atr = body / max(atr, 1e-12)
    if result_atr >= 0.75:
        score += 12
    adverse = bool((not directional) and vr >= 1.6 and eff >= 0.55)
    if adverse:
        score -= 22
    score = max(0.0, min(100.0, score))
    cls = "ADVERSE_ATTACK" if adverse else "CONFIRMED" if score >= 65 else "NEUTRAL"
    return {"available": True, "score": round(score, 2), "classification": cls,
            "confirmation": bool(score >= 65 and not adverse), "adverse": adverse,
            "volume_ratio": round(vr, 3), "effort_result": round(eff * 100, 2),
            "body_atr": round(result_atr, 3)}


def _find_causal_ob(df: pd.DataFrame, side: str, atr: float, max_bars: int = 40) -> Dict[str, Any]:
    s = _side(side)
    n = len(df)
    best = None
    if not s or n < 8 or atr <= 0:
        return {"present": False, "quality": 0.0, "origin_bar": -1, "low": 0.0, "high": 0.0}
    start = max(1, n - max_bars)
    for i in range(start, n - 2):
        c = df.iloc[i]
        body = abs(_f(c["close"]) - _f(c["open"]))
        rng = max(_f(c["high"]) - _f(c["low"]), 1e-12)
        if body / rng > 0.78:
            continue
        opposite = (s == "BUY" and c["close"] < c["open"]) or (s == "SELL" and c["close"] > c["open"])
        if not opposite:
            continue
        fut = df.iloc[i+1:min(n, i+5)]
        if fut.empty:
            continue
        if s == "BUY":
            displacement = (_f(fut["close"].max()) - _f(c["high"])) / atr
            zl, zh = _f(c["low"]), _f(c["open"])
        else:
            displacement = (_f(c["low"]) - _f(fut["close"].min())) / atr
            zl, zh = _f(c["open"]), _f(c["high"])
        if displacement < 0.6:
            continue
        touches = 0
        broken = False
        for _, r in df.iloc[i+1:].iterrows():
            low, high, close = _f(r["low"]), _f(r["high"]), _f(r["close"])
            if high >= min(zl, zh) and low <= max(zl, zh):
                touches += 1
            if s == "BUY" and close < min(zl, zh) - atr * 0.15:
                broken = True
            if s == "SELL" and close > max(zl, zh) + atr * 0.15:
                broken = True
        if broken:
            continue
        vol_base = _f(df["volume"].iloc[max(0, i-10):i].mean(), 1.0)
        vol_ratio = _f(fut["volume"].max()) / max(vol_base, 1e-12)
        freshness = max(0, n - 1 - i)
        quality = 50 + min(25, max(0, displacement - 0.6) * 20) + min(15, max(0, vol_ratio - 1) * 10)
        quality += 10 if touches <= 1 else 4 if touches <= 2 else -10
        quality += 8 if freshness <= 10 else 4 if freshness <= 20 else -8
        item = {"present": True, "quality": max(0, min(100, quality)), "origin_bar": i,
                "low": min(zl, zh), "high": max(zl, zh), "mid": (zl+zh)/2,
                "displacement_atr": displacement, "volume_ratio": vol_ratio,
                "touches": touches, "freshness_bars": freshness, "broken": False}
        if best is None or item["quality"] > best["quality"]:
            best = item
    return best or {"present": False, "quality": 0.0, "origin_bar": -1, "low": 0.0, "high": 0.0}


def _sequence(sweep: Dict[str, Any], ob: Dict[str, Any], structure: Dict[str, Any], vpa: Dict[str, Any], price: float, side: str) -> Dict[str, Any]:
    s = _side(side)
    flags = {
        "sweep": bool(sweep.get("detected")),
        "displacement": bool(ob.get("present") and ob.get("displacement_atr", 0) >= 0.75),
        "structure": bool((s == "BUY" and structure.get("direction") == "BULLISH") or (s == "SELL" and structure.get("direction") == "BEARISH")),
        "order_block": bool(ob.get("present")),
        "retest_context": bool(ob.get("present") and ob.get("high", 0) >= price >= ob.get("low", 0)),
        "vpa": bool(vpa.get("confirmation")),
    }
    if flags["sweep"] and flags["displacement"] and flags["structure"] and flags["order_block"] and flags["retest_context"]:
        state = "FULL_INSTITUTIONAL_SEQUENCE"
    elif flags["sweep"] and flags["displacement"] and flags["structure"]:
        state = "LIQUIDITY_STRUCTURE_CONFIRMED"
    elif flags["sweep"] and flags["order_block"]:
        state = "LIQUIDITY_THEN_ZONE"
    elif flags["structure"] and flags["order_block"]:
        state = "STRUCTURE_WITH_ZONE"
    elif flags["sweep"]:
        state = "LIQUIDITY_ONLY"
    elif flags["order_block"]:
        state = "ZONE_ONLY"
    else:
        state = "NO_INSTITUTIONAL_SEQUENCE"
    ordered = [k for k,v in flags.items() if v]
    return {"state": state, "flags": flags, "evidence_count": len(ordered),
            "ordered_evidence": ordered,
            "valid_for_entry": state in {"FULL_INSTITUTIONAL_SEQUENCE", "LIQUIDITY_STRUCTURE_CONFIRMED"},
            "no_lookahead": True}


def analyze_institutional_evidence(df: pd.DataFrame, side: str, *, atr: Optional[float] = None,
                                   ob_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a deterministic institutional evidence packet from closed candles."""
    s = _side(side)
    required = {"open", "high", "low", "close", "volume"}
    if not s or not isinstance(df, pd.DataFrame) or len(df) < 40 or not required.issubset(df.columns):
        return {"available": False, "reason": "INSUFFICIENT_DATA", "side": s}
    x = df.copy()
    a = _f(atr) or _atr(x)
    px = _f(x["close"].iloc[-1])
    vwap = _vwap(x)
    ema50 = _ema(x["close"], 50)
    ema200 = _ema(x["close"], 200) if len(x) >= 200 else 0.0
    adx, pdi, mdi, adx_slope = _adx(x)
    rsi = _rsi(x["close"])
    macd, macd_signal, macd_hist = _macd(x["close"])
    sweep = _detect_sweep(x, s)
    structure = _structure(x, s)
    pdx = _premium_discount(x)
    ob = dict(ob_hint or {}) if ob_hint else _find_causal_ob(x, s, a)
    vpa = _vpa(x, s, a)

    trend_aligned = bool((s == "BUY" and px > vwap and px > ema50 and (not ema200 or ema50 > ema200) and pdi >= mdi)
                         or (s == "SELL" and px < vwap and px < ema50 and (not ema200 or ema50 < ema200) and mdi >= pdi))
    pd_aligned = bool((s == "BUY" and pdx["state"] == "DISCOUNT") or (s == "SELL" and pdx["state"] == "PREMIUM"))
    momentum_aligned = bool((s == "BUY" and rsi >= 45 and macd_hist >= 0) or (s == "SELL" and rsi <= 55 and macd_hist <= 0))
    sequence = _sequence(sweep, ob, structure, vpa, px, s)

    accumulation_distribution = "NEUTRAL"
    if sweep.get("detected") and vpa.get("confirmation"):
        if s == "BUY" and pdx["state"] == "DISCOUNT":
            accumulation_distribution = "ACCUMULATION"
        elif s == "SELL" and pdx["state"] == "PREMIUM":
            accumulation_distribution = "DISTRIBUTION"
    if vpa.get("adverse"):
        accumulation_distribution = "DISTRIBUTION_RISK" if s == "BUY" else "ACCUMULATION_RISK"

    confluence = 0.0
    confluence += 25 if sweep.get("detected") and sweep.get("reclaimed") else 0
    confluence += 20 if sequence["flags"]["structure"] else 0
    confluence += 20 if ob.get("present") and ob.get("quality", 0) >= 65 else 0
    confluence += 15 if pd_aligned else 0
    confluence += 10 if trend_aligned else 0
    confluence += 10 if momentum_aligned else 0
    if vpa.get("confirmation"):
        confluence += 10
    if vpa.get("adverse"):
        confluence -= 20
    if accumulation_distribution in {"DISTRIBUTION_RISK", "ACCUMULATION_RISK"}:
        confluence -= 15
    confluence = max(0.0, min(100.0, confluence))

    return {
        "available": True, "side": s, "price": px, "atr": a,
        "confluence_score": round(confluence, 2),
        "sweep": sweep, "structure": structure, "order_block": ob,
        "premium_discount": pdx, "vpa": vpa,
        "accumulation_distribution": accumulation_distribution,
        "indicators": {
            "vwap": vwap, "ema50": ema50, "ema200": ema200,
            "adx": adx, "pdi": pdi, "mdi": mdi, "adx_slope": adx_slope,
            "rsi": rsi, "macd": macd, "macd_signal": macd_signal, "macd_hist": macd_hist,
        },
        "trend_aligned": trend_aligned,
        "pd_aligned": pd_aligned,
        "momentum_aligned": momentum_aligned,
        "sequence": sequence,
        "early_move": "EARLY" if sequence["state"] in {"LIQUIDITY_ONLY", "LIQUIDITY_THEN_ZONE"} else "DEVELOPING" if sequence["state"] in {"STRUCTURE_WITH_ZONE", "LIQUIDITY_STRUCTURE_CONFIRMED"} else "LATE" if sequence["state"] == "FULL_INSTITUTIONAL_SEQUENCE" and ob.get("freshness_bars", 999) > 15 else "NEUTRAL",
        "no_lookahead": True,
    }
