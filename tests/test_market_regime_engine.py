import numpy as np
import pandas as pd

from core.market_regime_engine import MarketRegimeEngine


def frame(values, volume=None):
    values = np.asarray(values, dtype=float)
    if volume is None:
        volume = np.full(len(values), 1000.0)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(values), freq="15min", tz="UTC"),
        "open": values,
        "high": values * 1.001,
        "low": values * 0.999,
        "close": values,
        "volume": volume,
    })


def test_insufficient_history_is_unknown_and_deterministic():
    df = frame(np.linspace(100, 101, 80))
    result = MarketRegimeEngine().analyze(df)
    assert result.state == "UNKNOWN"
    assert result.data_quality == "INSUFFICIENT_HISTORY"
    assert result.confidence_score == 0.0


def test_bullish_markup_requires_more_than_an_ema_cross():
    values = np.concatenate([np.full(170, 100.0), np.linspace(100, 115, 70)])
    df = frame(values)
    engine = MarketRegimeEngine()

    cross_only = engine.analyze(df)
    assert cross_only.ema["cross_state"] in {"BULLISH_RECENT", "NONE"}
    assert cross_only.state != "MARKUP"

    confirmed = engine.analyze(
        df,
        structure={"direction": "BULLISH", "bos": True, "mss": True},
        liquidity={"direction": "BUY", "reclaimed": True, "quality": 0.8},
        vpa={"displacement": "BULLISH", "effort_result": "EFFICIENT"},
    )
    assert confirmed.state == "MARKUP"
    assert confirmed.side_bias == "BUY"
    assert confirmed.confidence_score > 0


def test_accumulation_is_first_class_and_requires_process_evidence():
    values = np.concatenate([
        np.linspace(100, 94, 40),
        np.full(120, 95.0),
        np.array([92.0, 96.0]),
        np.linspace(96, 97, 38),
    ])
    df = frame(values)
    result = MarketRegimeEngine().analyze(
        df,
        structure={"direction": "BULLISH", "mss": True, "bos": False},
        liquidity={"direction": "BUY", "sweep": True, "reclaimed": True, "quality": 0.9},
        vpa={"effort_result": "ABSORPTION", "absorption": True, "displacement": "NONE"},
    )
    assert result.accumulation["score"] >= 60
    assert result.state in {"ACCUMULATION", "MARKUP"}
    assert any("accumulation" in reason.lower() for reason in result.reasons)


def test_distribution_is_mirrored_and_does_not_require_a_full_ema_cross():
    values = np.concatenate([
        np.full(120, 105.0),
        np.linspace(105, 108, 20),
        np.array([111.0, 106.0]),
        np.linspace(106, 104, 68),
    ])
    df = frame(values)
    result = MarketRegimeEngine().analyze(
        df,
        structure={"direction": "BEARISH", "mss": True, "bos": False},
        liquidity={"direction": "SELL", "sweep": True, "reclaimed": True, "quality": 0.9},
        vpa={"effort_result": "ABSORPTION", "absorption": True, "displacement": "NONE"},
    )
    assert result.distribution["score"] >= 60
    assert result.state in {"DISTRIBUTION", "MARKDOWN"}
    assert any("distribution" in reason.lower() for reason in result.reasons)


def test_reaccumulation_and_redistribution_use_previous_regime_context():
    df_up = frame(np.concatenate([np.full(120, 100.0), np.linspace(100, 112, 80)]))
    reacc = MarketRegimeEngine().analyze(
        df_up,
        previous_state="MARKUP",
        structure={"direction": "BULLISH", "bos": False, "mss": True},
        liquidity={"direction": "BUY", "sweep": True, "reclaimed": True, "quality": 0.9},
        vpa={"effort_result": "ABSORPTION", "absorption": True},
    )
    assert reacc.state in {"RE_ACCUMULATION", "MARKUP"}

    df_down = frame(np.concatenate([np.full(120, 100.0), np.linspace(100, 88, 80)]))
    redist = MarketRegimeEngine().analyze(
        df_down,
        previous_state="MARKDOWN",
        structure={"direction": "BEARISH", "bos": False, "mss": True},
        liquidity={"direction": "SELL", "sweep": True, "reclaimed": True, "quality": 0.9},
        vpa={"effort_result": "ABSORPTION", "absorption": True},
    )
    assert redist.state in {"RE_DISTRIBUTION", "MARKDOWN"}


def test_vwap_is_explicit_value_context_and_not_a_trade_trigger():
    df = frame(np.concatenate([np.full(180, 100.0), np.linspace(100, 101, 60)]))
    result = MarketRegimeEngine().analyze(df)
    assert set(result.vwap) >= {"value", "side", "slope", "distance_atr", "reclaim", "rejection"}
    assert result.vwap["side"] in {"ABOVE", "BELOW", "AT"}
    assert result.state != "MARKUP"  # VWAP context alone cannot create a trend state.


def test_missing_microstructure_is_explicitly_unavailable():
    df = frame(np.linspace(100, 110, 220))
    result = MarketRegimeEngine().analyze(df)
    assert result.microstructure["data_quality"] == "UNAVAILABLE"
    assert result.microstructure["top_of_book_imbalance"] is None


def test_microstructure_uses_observable_depth_without_claiming_hidden_orders():
    df = frame(np.linspace(100, 110, 220))
    result = MarketRegimeEngine().analyze(
        df,
        depth={"bid_volume": 900.0, "ask_volume": 300.0, "spread": 0.02},
    )
    assert result.microstructure["data_quality"] == "FRESH"
    assert result.microstructure["top_of_book_imbalance"] == 0.5
    assert result.microstructure["spread"] == 0.02
