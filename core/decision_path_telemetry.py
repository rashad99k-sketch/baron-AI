"""Read-only Decision Path telemetry for BARON.

This module records the evidence visible at each pipeline hand-off without
changing strategy thresholds, scores, gates, or execution behaviour.

Primary artifact:
    runtime/decision_path_trace.jsonl

The trace is intentionally append-only and best-effort. A telemetry failure
must never affect trading decisions.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()


def _path() -> Path:
    return Path(os.getenv("DECISION_PATH_TRACE_PATH", "runtime/decision_path_trace.jsonl"))


def _num(value: Any, digits: int = 6):
    try:
        if value is None:
            return None
        v = float(value)
        if not (v == v) or abs(v) == float("inf"):
            return None
        return round(v, digits)
    except Exception:
        return None


def _bool(value: Any):
    return None if value is None else bool(value)


def _liquidity_snapshot(df, price: float, atr: float) -> dict[str, Any]:
    """Describe EQH/EQL from confirmed swing points plus legacy cluster flags.

    This is telemetry only. It does not alter the production liquidity detector.
    Confirmed swings require five bars on each side, so the latest five bars are
    not treated as confirmed swings by this telemetry map.
    """
    out = {
        "legacy_eqh": None,
        "legacy_eql": None,
        "swing_eqh": False,
        "swing_eql": False,
        "eqh_levels": [],
        "eql_levels": [],
        "eqh_touches": 0,
        "eql_touches": 0,
        "nearest_eqh": None,
        "nearest_eql": None,
        "eqh_distance_pct": None,
        "eql_distance_pct": None,
        "eqh_distance_atr": None,
        "eql_distance_atr": None,
        "high_pool": [],
        "low_pool": [],
    }
    try:
        import core.engine as E
        legacy = E.detect_liquidity_cluster(df, lb=20, tol=0.001)
        out["legacy_eqh"], out["legacy_eql"] = bool(legacy[0]), bool(legacy[1])
        sh, sl = E.swing_points(df, lb=5)
        highs = [float(x[1]) for x in sh[-5:]]
        lows = [float(x[1]) for x in sl[-5:]]

        def clusters(values, tolerance=0.0015):
            groups = []
            for v in values:
                placed = False
                for g in groups:
                    mean = sum(g) / len(g)
                    if abs(v - mean) / max(abs(mean), 1e-12) < tolerance:
                        g.append(v)
                        placed = True
                        break
                if not placed:
                    groups.append([v])
            return [g for g in groups if len(g) >= 2]

        eqh_groups = clusters(highs)
        eql_groups = clusters(lows)
        out["swing_eqh"] = bool(eqh_groups)
        out["swing_eql"] = bool(eql_groups)
        out["eqh_levels"] = [
            {"level": _num(sum(g) / len(g)), "touches": len(g),
             "spread_pct": _num((max(g) - min(g)) / max(abs(sum(g) / len(g)), 1e-12), 6)}
            for g in eqh_groups
        ]
        out["eql_levels"] = [
            {"level": _num(sum(g) / len(g)), "touches": len(g),
             "spread_pct": _num((max(g) - min(g)) / max(abs(sum(g) / len(g)), 1e-12), 6)}
            for g in eql_groups
        ]
        out["eqh_touches"] = max([x["touches"] for x in out["eqh_levels"]] or [0])
        out["eql_touches"] = max([x["touches"] for x in out["eql_levels"]] or [0])

        if out["eqh_levels"]:
            levels = [x["level"] for x in out["eqh_levels"]]
            above = [x for x in levels if x >= price]
            nearest = min(above or levels, key=lambda x: abs(x - price))
            out["nearest_eqh"] = _num(nearest)
            out["eqh_distance_pct"] = _num((nearest - price) / price if price else None)
            out["eqh_distance_atr"] = _num(abs(nearest - price) / atr if atr else None)
        if out["eql_levels"]:
            levels = [x["level"] for x in out["eql_levels"]]
            below = [x for x in levels if x <= price]
            nearest = min(below or levels, key=lambda x: abs(x - price))
            out["nearest_eql"] = _num(nearest)
            out["eql_distance_pct"] = _num((price - nearest) / price if price else None)
            out["eql_distance_atr"] = _num(abs(price - nearest) / atr if atr else None)

        pools = E.build_liquidity_pools(df)
        out["high_pool"] = [_num(x) for x in (pools.get("high_pools") or [])[-5:]]
        out["low_pool"] = [_num(x) for x in (pools.get("low_pools") or [])[-5:]]
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def market_snapshot(df, side: str = "", atr: float | None = None,
                    price: float | None = None,
                    indicators: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a forensic snapshot using the same production indicator helpers."""
    snap: dict[str, Any] = {"side": str(side or "").upper()}
    try:
        if df is None or len(df) == 0:
            return snap
        import core.engine as E
        px = float(df["close"].iloc[-1] if price is None else price)
        a = float(atr if atr is not None else E.compute_atr(df).iloc[-1])
        adx, plus_di, minus_di = E.compute_adx(df, 14, return_di=True)
        adx_v = float(adx.iloc[-1])
        plus_v = float(plus_di.iloc[-1])
        minus_v = float(minus_di.iloc[-1])
        ema50 = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(df["close"].ewm(span=200, adjust=False).mean().iloc[-1])
        vwap = E.compute_vwap(df)
        vwap_v = float(vwap.iloc[-1])
        snap.update({
            "price": _num(px),
            "atr": _num(a),
            "ema50": _num(ema50),
            "ema200": _num(ema200),
            "price_above_ema50": px > ema50,
            "price_above_ema200": px > ema200,
            "ema50_ema200_bias": (
                "BULLISH" if ema50 > ema200 and px > ema200
                else "BEARISH" if ema50 < ema200 and px < ema200
                else "TRANSITION"
            ),
            "vwap": _num(vwap_v),
            "vwap_side": "ABOVE" if px > vwap_v else "BELOW" if px < vwap_v else "AT",
            "vwap_distance_pct": _num((px - vwap_v) / vwap_v if vwap_v else 0.0),
            "adx": _num(adx_v),
            "di_plus": _num(plus_v),
            "di_minus": _num(minus_v),
            "di_spread": _num(plus_v - minus_v),
            "di_bias": "BUY" if plus_v > minus_v else "SELL" if minus_v > plus_v else "NEUTRAL",
            "candle_count": len(df),
        })
        ts = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
        snap["candle_timestamp"] = str(ts) if ts is not None else None
        snap["liquidity"] = _liquidity_snapshot(df, px, a)
        if isinstance(indicators, dict):
            snap["caller_indicators"] = indicators
    except Exception as exc:
        snap["error"] = f"{type(exc).__name__}: {exc}"
    return snap


def emit(*, trace_id: str, symbol: str, stage: str, decision: str,
         side: str = "", reason: str = "", authority: str = "",
         source: str = "", snapshot: dict[str, Any] | None = None,
         fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one telemetry event. Any failure is swallowed by design."""
    record = {
        "ts": round(time.time(), 6),
        "trace_id": str(trace_id),
        "symbol": str(symbol or ""),
        "side": str(side or "").upper(),
        "stage": str(stage or ""),
        "decision": str(decision or ""),
        "reason": str(reason or "")[:500],
        "authority": str(authority or ""),
        "source": str(source or ""),
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "fields": fields if isinstance(fields, dict) else {},
    }
    # A per-event digest makes accidental line corruption detectable without
    # imposing the hash-chain semantics of the existing decision journal.
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    record["event_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    try:
        path = _path()
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass
    return record
