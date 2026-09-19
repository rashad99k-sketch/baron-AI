"""Lightweight probabilistic forecast evidence for BARON.

This is deliberately NOT a trading model and never places orders.  It adapts
ideas from financial time-series foundation models into a dependency-free
runtime layer: multi-horizon path estimation, bootstrap-style path dispersion,
ATR normalization, and explicit uncertainty.  It is intended to be an
additional evidence provider for BARON's existing decision authority.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import math
import numpy as np
import pandas as pd


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    prev = df["close"].shift(1)
    tr = pd.concat([
        (df["high"] - df["low"]).abs(),
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return _f(tr.rolling(period, min_periods=period).mean().iloc[-1])


@dataclass(frozen=True)
class ForecastEvidence:
    available: bool
    side: str
    horizons: tuple
    expected_move_atr: float
    directional_consensus: float
    uncertainty: float
    dispersion_atr: float
    regime: str
    quality: str
    no_lookahead: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _regime(df: pd.DataFrame, atr: float) -> str:
    close = df["close"]
    fast = float(close.ewm(span=min(20, len(close)), adjust=False).mean().iloc[-1])
    slow = float(close.ewm(span=min(50, len(close)), adjust=False).mean().iloc[-1])
    recent = float(close.iloc[-1] - close.iloc[-min(12, len(close))])
    norm = recent / max(atr * max(1, min(12, len(close)) * 0.5), 1e-12)
    if abs(fast - slow) <= atr * 0.15 and abs(norm) < 0.6:
        return "RANGE_OR_COMPRESSION"
    if abs(norm) >= 1.2:
        return "EXPANSION"
    return "TREND_UP" if fast > slow else "TREND_DOWN"


def _returns(close: pd.Series, lookback: int = 32) -> np.ndarray:
    x = close.astype(float).pct_change().dropna().tail(lookback).to_numpy(dtype=float)
    return x[np.isfinite(x)] if len(x) else np.array([], dtype=float)


def analyze_forecast_evidence(
    df: pd.DataFrame,
    side: str,
    *,
    atr: Optional[float] = None,
    horizons: tuple[int, ...] = (1, 2, 4),
    paths: int = 32,
) -> Dict[str, Any]:
    """Return bounded, deterministic forecast evidence from closed candles.

    The path ensemble is generated from historical returns only.  It is a
    resilience-safe proxy for a probabilistic foundation model when the heavy
    Kronos dependency is not installed.  It must never be interpreted as a
    guaranteed future price or probability of profit.
    """
    side = str(side or "").upper()
    req = {"open", "high", "low", "close", "volume"}
    if side not in {"BUY", "SELL"} or not isinstance(df, pd.DataFrame) or len(df) < 40 or not req.issubset(df.columns):
        return ForecastEvidence(False, side, tuple(horizons), 0.0, 0.0, 1.0, 0.0, "UNKNOWN", "UNAVAILABLE").to_dict()

    x = df[["open", "high", "low", "close", "volume"]].copy(deep=True)
    a = _f(atr) or _atr(x)
    if a <= 0:
        return ForecastEvidence(False, side, tuple(horizons), 0.0, 0.0, 1.0, 0.0, "UNKNOWN", "UNAVAILABLE").to_dict()

    r = _returns(x["close"], 36)
    if len(r) < 12:
        return ForecastEvidence(False, side, tuple(horizons), 0.0, 0.0, 1.0, 0.0, "UNKNOWN", "UNAVAILABLE").to_dict()

    # Deterministic seed from the observed frame; no future data is used.
    last_ts = str(x.index[-1])
    seed = (hash((last_ts, len(x), round(float(x["close"].iloc[-1]), 8))) & 0xFFFFFFFF)
    rng = np.random.default_rng(seed)

    horizons = tuple(sorted({max(1, int(h)) for h in horizons}))[:6]
    path_count = max(8, min(128, int(paths)))
    last = _f(x["close"].iloc[-1])
    candidates = []
    for _ in range(path_count):
        idx = rng.integers(0, len(r), size=max(horizons))
        sampled = r[idx]
        prices = last * np.cumprod(1.0 + sampled)
        candidates.append(prices)
    paths_arr = np.asarray(candidates, dtype=float)
    terminal_idx = [h - 1 for h in horizons]
    terminal = paths_arr[:, terminal_idx]
    mean_terminal = terminal.mean(axis=0)
    baseline = max(last, 1e-12)
    signed_moves = (mean_terminal - baseline) / a
    side_sign = 1.0 if side == "BUY" else -1.0
    expected_move = float(signed_moves[-1] * side_sign)

    # Consensus = fraction of terminal paths moving in the requested direction.
    directional = (terminal[:, -1] - baseline) * side_sign
    consensus = float(np.mean(directional > 0.0))
    disp_atr = float(np.std(terminal[:, -1] - baseline) / a)
    uncertainty = min(1.0, disp_atr / max(abs(expected_move) + 1.0, 1.0))

    regime = _regime(x, a)
    quality = "HIGH" if consensus >= 0.68 and uncertainty <= 0.45 else "MEDIUM" if consensus >= 0.58 else "LOW"

    return ForecastEvidence(
        True, side, horizons, round(expected_move, 4), round(consensus, 4),
        round(uncertainty, 4), round(disp_atr, 4), regime, quality,
    ).to_dict()
