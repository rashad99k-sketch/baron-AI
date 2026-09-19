import json
from pathlib import Path

from core.adaptive_trade_intelligence import AdaptiveTradeIntelligence


def _state(tid, score=80):
    return {
        "trade_id": tid,
        "current_symbol": "BTC/USDT:USDT",
        "side": "BUY",
        "asset_class": "CRYPTO",
        "trade_type": "REVERSAL",
        "entry_type": "EXECUTION_QUEUE",
        "market_regime": "TREND_UP",
        "move_maturity": "FIRST",
        "institutional_stage": "FULL_INSTITUTIONAL_SEQUENCE",
        "early_formation": {"verdict": "FIRST"},
        "ob_grade": "A+",
        "trade_score": score,
        "position_setup_snapshot": {
            "side": "BUY",
            "zone_type": "ORDER_BLOCK",
            "ob_grade": "A+",
            "structure_shift": "bullish_shift",
            "liquidity_event": "LIQUIDITY_SWEEP",
            "zone": {"type": "ORDER_BLOCK"},
            "vpa": {"state": "EXPANSION"},
            "institutional_evidence": {"institutional_bias": "ACCUMULATION"},
            "adx": 31,
        },
        "forecast_evidence": {"quality": "HIGH", "regime": "TREND_UP", "uncertainty": 0.2},
    }


def test_records_and_labels(tmp_path):
    mem = AdaptiveTradeIntelligence(tmp_path / "ati.jsonl", min_samples=3)
    st = _state("T1")
    out = mem.record_outcome(st, 2.0, 12.0, "WIN", peak_roe=35.0)
    assert out["saved"] is True
    assert out["label"] == "EXPLOSIVE_WIN"
    assert mem.record_outcome(st, 2.0, 12.0, "WIN", peak_roe=35.0)["saved"] is False
    assert mem.summary()["total_trades"] == 1
    assert json.loads(Path(tmp_path / "ati.jsonl").read_text().splitlines()[0])["label"] == "EXPLOSIVE_WIN"


def test_learning_is_advisory_until_min_samples(tmp_path):
    mem = AdaptiveTradeIntelligence(tmp_path / "ati.jsonl", min_samples=3)
    assert mem.assess_entry(_state("NEW"))["available"] is False
    for i in range(3):
        mem.record_outcome(_state(f"T{i}"), 1.0, 6.0, "WIN", peak_roe=18.0)
    assessment = mem.assess_entry(_state("NEW"))
    assert assessment["available"] is True
    assert assessment["label"] == "HISTORICALLY_STRONG"
    assert assessment["authority"] == "ADVISORY_ONLY"


def test_weak_entry_is_recorded_without_mutating_strategy(tmp_path):
    mem = AdaptiveTradeIntelligence(tmp_path / "ati.jsonl", min_samples=3)
    st = _state("WEAK", score=40)
    out = mem.record_outcome(st, -1.0, -5.0, "LOSS", peak_roe=2.0)
    assert out["label"] == "WEAK_ENTRY"
    assert st["trade_score"] == 40
    assert mem.summary()["labels"]["WEAK_ENTRY"] == 1
