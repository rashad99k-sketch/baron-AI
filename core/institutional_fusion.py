"""BARON institutional setup fusion (advisory/read-only).

This module does not place orders and does not replace the Unified Trade
Management Brain.  It converts the existing scanner/evidence outputs into one
explainable setup fingerprint for ranking, dashboard display, and post-trade
research.
"""
from __future__ import annotations
from typing import Any, Dict


def _num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x else default
    except Exception:
        return default


def _bool(v: Any) -> bool:
    return bool(v)


def build_institutional_fusion(entry: Dict[str, Any]) -> Dict[str, Any]:
    side = str(entry.get("side") or "").upper()
    smart = entry.get("smart_money") or {}
    momentum = entry.get("momentum") or {}
    formation = entry.get("early_formation") or {}
    vpa = entry.get("vpa") or {}
    forecast = entry.get("forecast_evidence") or {}
    narrative = entry.get("narrative") or {}
    inst = entry.get("institutional_ob_analysis") or {}
    by_side = entry.get("institutional_ob_by_side") or {}
    winning_ob = by_side.get(side) or {}
    opposing_ob = by_side.get("SELL" if side == "BUY" else "BUY") or {}
    msb = entry.get("msb") or {}
    pd = (inst.get("premium_discount") or {}) if isinstance(inst, dict) else {}

    sweep = _bool(narrative.get("sweep")) or str((entry.get("institutional_ob_analysis") or {}).get("direction", "")).upper() == side and _bool((entry.get("institutional_ob_analysis") or {}).get("sweep", {}).get("detected"))
    structure = _bool(narrative.get("choch_bos")) or _bool(entry.get("msb_active")) or str((inst.get("structure") or {}).get("direction", "")).upper() in {"BULLISH", "BEARISH"}
    ob_present = str(winning_ob.get("grade", "")).upper() in {"A", "A+", "B", "VALID", "FRESH"} or bool(entry.get("zone"))
    ob_conflict = _bool(entry.get("institutional_ob_conflict")) or str(inst.get("decision", "")).upper() == "BLOCK_OPPOSING_OB"
    vpa_confirmed = _bool(entry.get("vpa_confirmed")) or _bool(vpa.get("confirmation")) or _bool(winning_ob.get("vpa_confirmed"))
    vpa_adverse = _bool(entry.get("vpa_adverse")) or _bool(vpa.get("adverse")) or _bool(winning_ob.get("vpa_adverse"))
    flow_aligned = str(smart.get("institutional_bias", "NEUTRAL")).upper() == side or str(momentum.get("flow_bias", "NEUTRAL")).upper() == side
    formation_eligible = _bool(formation.get("eligible"))
    early_phase = str(formation.get("phase", entry.get("move_maturity", "UNKNOWN"))).upper() in {"PRE_EXPANSION", "EARLY_EXPANSION"}
    forecast_quality = str(forecast.get("quality", "UNAVAILABLE")).upper()
    forecast_consensus = _num(forecast.get("directional_consensus"))
    forecast_side_aligned = forecast_quality != "UNAVAILABLE" and ((side == "BUY" and forecast_consensus >= 0.58) or (side == "SELL" and forecast_consensus >= 0.58))
    forecast_uncertain = _num(forecast.get("uncertainty"), 1.0) >= 0.65
    pd_state = str(pd.get("state", "UNKNOWN")).upper()
    location_aligned = (side == "BUY" and pd_state == "DISCOUNT") or (side == "SELL" and pd_state == "PREMIUM")

    # This is an evidence score, not a win probability and never an execution gate.
    dimensions = {
        "liquidity": 100.0 if sweep else _num(entry.get("liq_score"), 0.0),
        "structure": 100.0 if structure else _num(entry.get("struct_score"), 0.0),
        "zone": min(100.0, max(0.0, _num(winning_ob.get("score"), _num(entry.get("ob_score"), 0.0)))),
        "vpa": 100.0 if vpa_confirmed else _num(vpa.get("score"), 0.0),
        "flow": 100.0 if flow_aligned else 0.0,
        "formation": _num(formation.get("score"), 0.0),
        "location": 100.0 if location_aligned else 35.0 if pd_state != "UNKNOWN" else 0.0,
        "forecast": 100.0 if forecast_side_aligned and not forecast_uncertain else 55.0 if forecast_quality != "UNAVAILABLE" else 0.0,
    }
    weights = {"liquidity": .18, "structure": .18, "zone": .18, "vpa": .12, "flow": .10, "formation": .10, "location": .08, "forecast": .06}
    available = [k for k, v in dimensions.items() if v > 0 or k in {"liquidity", "structure", "zone"}]
    weighted = sum(dimensions[k] * weights[k] for k in available)
    coverage = min(100.0, len(available) / len(dimensions) * 100.0)

    contradictions = []
    if ob_conflict:
        contradictions.append("OPPOSING_ZONE_CONFLICT")
    if vpa_adverse:
        contradictions.append("VPA_ADVERSE")
    if forecast_quality != "UNAVAILABLE" and not forecast_side_aligned and not forecast_uncertain:
        contradictions.append("FORECAST_COUNTER")
    if _num(entry.get("news_risk"), 0.0) >= 80:
        contradictions.append("NEWS_RISK")
    if str(entry.get("data_quality", "OK")).upper() in {"STALE", "ERROR", "PROVIDER_FAILURE", "DATA_UNAVAILABLE"}:
        contradictions.append("DATA_QUALITY")

    if contradictions and ("OPPOSING_ZONE_CONFLICT" in contradictions or "DATA_QUALITY" in contradictions):
        state = "CONFLICTED"
    elif vpa_adverse:
        state = "CONFLICTED"
    elif formation_eligible and early_phase and len(contradictions) == 0:
        state = "EARLY_MOVE"
    elif sweep and structure and ob_present and vpa_confirmed and len(contradictions) == 0:
        state = "CONFIRMED"
    elif ob_present or structure or sweep:
        state = "FORMING"
    else:
        state = "WATCH"

    explosive_candidate = bool(
        formation_eligible and early_phase and
        _num(formation.get("score"), 0.0) >= 55 and
        (sweep or _bool(formation.get("liquidity_building")) or flow_aligned) and
        not contradictions
    )

    return {
        "version": "institutional-fusion-v1",
        "advisory_only": True,
        "side": side,
        "state": state,
        "evidence_score": round(max(0.0, min(100.0, weighted)), 2),
        "evidence_coverage": round(coverage, 1),
        "explosive_candidate": explosive_candidate,
        "location": {
            "premium_discount": pd_state,
            "aligned": location_aligned,
            "role": "LOWER_VALUE_LONG" if side == "BUY" and location_aligned else "UPPER_VALUE_SHORT" if side == "SELL" and location_aligned else "NEUTRAL_LOCATION",
        },
        "sequence": {
            "liquidity_sweep": sweep,
            "structure_shift": structure,
            "causal_zone": ob_present,
            "retest": _bool(narrative.get("retest")) or str(entry.get("entry_timing", "")).upper() in {"RETEST_ENTRY", "MICRO_PULLBACK_ENTRY"},
            "vpa_confirmation": vpa_confirmed,
        },
        "dimensions": {k: round(v, 1) for k, v in dimensions.items()},
        "contradictions": contradictions,
        "forecast": {
            "quality": forecast_quality,
            "consensus": round(forecast_consensus, 3),
            "uncertainty": round(_num(forecast.get("uncertainty"), 1.0), 3),
            "aligned": forecast_side_aligned,
        },
        "zone": {
            "grade": str(winning_ob.get("grade", entry.get("ob_grade", "NONE"))).upper(),
            "score": round(_num(winning_ob.get("score"), _num(entry.get("ob_score"), 0.0)), 1),
            "freshness": winning_ob.get("freshness"),
            "touches": winning_ob.get("touches"),
            "displacement_atr": round(_num(winning_ob.get("displacement_atr")), 3),
        },
    }
