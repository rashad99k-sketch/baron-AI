import pandas as pd
from core.institutional_fusion import build_institutional_fusion


def _entry():
    return {
        "side": "BUY",
        "smart_money": {"institutional_bias": "BUY"},
        "momentum": {"flow_bias": "BUY"},
        "early_formation": {"eligible": True, "phase": "PRE_EXPANSION", "score": 72, "liquidity_building": 70},
        "vpa": {"confirmation": True, "adverse": False, "score": 78},
        "narrative": {"sweep": True, "choch_bos": True, "retest": True},
        "institutional_ob_analysis": {"premium_discount": {"state": "DISCOUNT"}, "decision": "CONTINUE_TO_INSTITUTIONAL_GATES"},
        "institutional_ob_by_side": {"BUY": {"grade": "A", "score": 88, "freshness": 3, "touches": 0, "displacement_atr": 1.8, "vpa_confirmed": True}},
        "forecast_evidence": {"quality": "HIGH", "directional_consensus": 0.75, "uncertainty": 0.25},
        "data_quality": "OK",
        "news_risk": 10,
    }


def test_fusion_is_advisory_and_detects_early_move():
    out = build_institutional_fusion(_entry())
    assert out["advisory_only"] is True
    assert out["state"] in {"EARLY_MOVE", "CONFIRMED"}
    assert out["explosive_candidate"] is True
    assert out["location"]["role"] == "LOWER_VALUE_LONG"
    assert out["contradictions"] == []


def test_fusion_marks_conflict_without_authority_change():
    e = _entry()
    e["institutional_ob_analysis"]["decision"] = "BLOCK_OPPOSING_OB"
    e["institutional_ob_conflict"] = True
    out = build_institutional_fusion(e)
    assert out["state"] == "CONFLICTED"
    assert "OPPOSING_ZONE_CONFLICT" in out["contradictions"]
    assert out["advisory_only"] is True
