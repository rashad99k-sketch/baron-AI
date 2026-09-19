import numpy as np
import pandas as pd

from core.institutional_entry_engine import InstitutionalEntryEngine


def make_df():
    values = np.concatenate([np.full(170, 100.0), np.linspace(100, 115, 70)])
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=len(values), freq="15min", tz="UTC"),
        "open": values,
        "high": values * 1.002,
        "low": values * 0.998,
        "close": values,
        "volume": np.full(len(values), 1000.0),
    })


def test_assessment_exposes_market_state_without_changing_entry_authority():
    engine = InstitutionalEntryEngine()
    df = make_df()
    result = engine.assess(
        df=df,
        side="BUY",
        price=float(df.close.iloc[-1]),
        atr=0.2,
        zone={"price": 114.0, "quality": 0.8},
        structure_ok=True,
        displacement_ok=True,
        rejection_ok=False,
    )
    assert "market_state" in result
    assert result["market_state"]["state"] in {
        "ACCUMULATION", "RE_ACCUMULATION", "MARKUP", "TREND_PULLBACK", "TRANSITION", "UNKNOWN"
    }
    assert result["decision"] in {"WAIT", "APPROVE", "REJECT"}


def test_recent_ema_cross_is_recorded_as_context_not_an_entry_trigger():
    engine = InstitutionalEntryEngine()
    df = make_df()
    result = engine.assess(
        df=df,
        side="BUY",
        price=float(df.close.iloc[-1]),
        atr=0.2,
        zone={},
        structure_ok=False,
        displacement_ok=False,
        rejection_ok=False,
    )
    assert result["direction"]["ema_cross"] in {"BULLISH_RECENT", "NONE"}
    assert result["direction"]["entry_trigger"] is False
    assert result["decision"] != "APPROVE"
