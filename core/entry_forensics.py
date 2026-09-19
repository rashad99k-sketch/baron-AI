"""Thesis-aware stop logic and post-stop classification for BARON."""
from __future__ import annotations

from typing import Any


def propose_dynamic_sl(
    *,
    side: str,
    entry: float,
    atr: float,
    invalidation: float,
    liquidity_level: float | None = None,
    liquidity_quality: float = 0.0,
    volatility_multiplier: float = 1.0,
) -> dict[str, Any]:
    side = str(side).upper()
    entry = float(entry)
    atr = max(float(atr or 0.0), 1e-9)
    invalidation = float(invalidation)
    quality = float(liquidity_quality or 0.0)
    # Buffer expands modestly with volatility, but stays bounded so the stop
    # cannot be widened indefinitely just to avoid a stop-out.
    buffer_atr = max(0.15, min(0.75, 0.20 * max(float(volatility_multiplier or 1.0), 0.5)))
    buffer = atr * buffer_atr
    if quality >= 0.75 and liquidity_level is not None:
        anchor = float(liquidity_level)
        basis = "LIQUIDITY_INVALIDATION"
    else:
        anchor = invalidation
        basis = "THESIS_INVALIDATION"
    if side == "BUY":
        sl = anchor - buffer
        sl = min(sl, entry - max(0.25 * atr, entry * 0.001))
    else:
        sl = anchor + buffer
        sl = max(sl, entry + max(0.25 * atr, entry * 0.001))
    return {
        "sl": float(sl),
        "basis": basis,
        "anchor": float(anchor),
        "buffer": float(buffer),
        "buffer_atr": float(buffer_atr),
    }


def ratchet_stop(side: str, previous_sl: float, proposed_sl: float) -> float:
    side = str(side).upper()
    previous_sl = float(previous_sl or 0.0)
    proposed_sl = float(proposed_sl)
    if previous_sl <= 0:
        return proposed_sl
    if side == "BUY":
        return max(previous_sl, proposed_sl)
    return min(previous_sl, proposed_sl)


def classify_stop_event(
    *,
    side: str,
    entry: float,
    stop_price: float,
    current_price: float,
    invalidation: float,
    ema200_intact: bool,
    structure_failed: bool,
    fresh_sweep: bool,
    reclaim: bool,
    volatility_spike: bool,
    entry_window: str = "UNKNOWN",
) -> dict[str, Any]:
    if entry_window == "LATE":
        classification = "LATE_ENTRY"
    elif volatility_spike:
        classification = "VOLATILITY_SPIKE"
    elif fresh_sweep and reclaim and ema200_intact and not structure_failed:
        classification = "STOP_HUNT"
    elif structure_failed or not ema200_intact:
        classification = "TRUE_FAILURE"
    elif entry_window in {"UNKNOWN", "FORMING"}:
        classification = "EARLY_ENTRY_ERROR"
    else:
        classification = "UNKNOWN"
    return {
        "classification": classification,
        "side": str(side).upper(),
        "entry": float(entry),
        "stop_price": float(stop_price),
        "current_price": float(current_price),
        "invalidation": float(invalidation),
        "ema200_intact": bool(ema200_intact),
        "structure_failed": bool(structure_failed),
        "fresh_sweep": bool(fresh_sweep),
        "reclaim": bool(reclaim),
        "volatility_spike": bool(volatility_spike),
        "entry_window": str(entry_window),
    }
