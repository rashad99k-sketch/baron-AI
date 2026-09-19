"""BARON Adaptive Trade Intelligence.

A deterministic, local learning memory for trade outcomes.  It learns which
*observed setup fingerprints* have historically produced strong/explosive
outcomes and which entry conditions have repeatedly been weak.

Important: this module is advisory research memory.  It never changes live
strategy thresholds, places orders, changes leverage, or overrides the
UnifiedTradeManagementBrain.  Any future rule promotion must be validated
separately before production use.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _num(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _bucket(value: Any, cuts: Iterable[float], labels: Iterable[str]) -> str:
    x = _num(value)
    for cut, label in zip(cuts, labels):
        if x < cut:
            return str(label)
    labels = list(labels)
    return str(labels[-1]) if labels else "UNKNOWN"


class AdaptiveTradeIntelligence:
    """Persistent outcome memory + conservative setup-pattern learning."""

    VERSION = "ATI-1.0"

    def __init__(self, path: str | os.PathLike[str] | None = None, min_samples: int = 5):
        self.path = Path(path or os.getenv("ADAPTIVE_TRADE_MEMORY_PATH", "runtime/adaptive_trade_intelligence.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.min_samples = max(3, int(os.getenv("ADAPTIVE_MIN_SAMPLES", str(min_samples))))
        self._lock = threading.RLock()
        self._records: List[Dict[str, Any]] = []
        self._ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    tid = str(rec.get("trade_id") or "")
                    if tid and tid in self._ids:
                        continue
                    if tid:
                        self._ids.add(tid)
                    self._records.append(rec)
            self._records = self._records[-5000:]
        except Exception:
            self._records = []
            self._ids = set()

    @staticmethod
    def fingerprint(state: Dict[str, Any] | None) -> Dict[str, Any]:
        s = state if isinstance(state, dict) else {}
        setup = s.get("position_setup_snapshot") if isinstance(s.get("position_setup_snapshot"), dict) else {}
        zone = setup.get("zone") if isinstance(setup.get("zone"), dict) else {}
        ob = setup.get("order_block") if isinstance(setup.get("order_block"), dict) else {}
        vpa = setup.get("vpa") if isinstance(setup.get("vpa"), dict) else s.get("vpa", {})
        inst = setup.get("institutional_evidence") if isinstance(setup.get("institutional_evidence"), dict) else s.get("institutional_evidence", {})
        forecast = s.get("forecast_evidence") if isinstance(s.get("forecast_evidence"), dict) else {}
        early = s.get("early_formation") if isinstance(s.get("early_formation"), dict) else {}
        return {
            "side": str(s.get("side") or setup.get("side") or "UNKNOWN").upper(),
            "asset_class": str(s.get("asset_class") or "UNKNOWN").upper(),
            "market_regime": str(s.get("market_regime") or s.get("regime") or "UNKNOWN"),
            "market_session": str(s.get("session_label") or s.get("market_session", {}).get("state") if isinstance(s.get("market_session"), dict) else "UNKNOWN"),
            "trade_type": str(s.get("trade_type") or "UNKNOWN"),
            "entry_type": str(s.get("entry_type") or "UNKNOWN"),
            "institutional_stage": str(s.get("institutional_stage") or "UNKNOWN"),
            "move_maturity": str(s.get("move_maturity") or "UNKNOWN"),
            "formation_verdict": str(early.get("verdict") or "UNKNOWN"),
            "zone_type": str(setup.get("zone_type") or zone.get("type") or "UNKNOWN"),
            "ob_grade": str(s.get("ob_grade") or setup.get("ob_grade") or ob.get("grade") or "NONE"),
            "structure_shift": str(setup.get("structure_shift") or "UNKNOWN"),
            "liquidity_event": str(setup.get("liquidity_event") or "UNKNOWN"),
            "vpa_state": str(vpa.get("state") or vpa.get("classification") or vpa.get("verdict") or "UNKNOWN"),
            "institutional_bias": str(inst.get("institutional_bias") or inst.get("bias") or "UNKNOWN"),
            "forecast_quality": str(forecast.get("quality") or "UNAVAILABLE"),
            "forecast_regime": str(forecast.get("regime") or "UNKNOWN"),
            "score_band": _bucket(s.get("trade_score", s.get("score", 0)), (50, 65, 75, 85), ("LOW", "MEDIUM", "GOOD", "STRONG", "ELITE")),
            "adx_band": _bucket(setup.get("adx", s.get("adx_live", 0)), (18, 22, 28, 35), ("CHOP", "EMERGING", "TREND", "STRONG", "EXTREME")),
            "forecast_uncertainty_band": _bucket(forecast.get("uncertainty", 1.0), (0.25, 0.45, 0.65), ("LOW", "MODERATE", "HIGH", "VERY_HIGH")),
        }

    @staticmethod
    def classify_outcome(pnl_pct: float, peak_roe: float, entry_score: float = 0.0) -> str:
        strong_roe = _num(os.getenv("ATI_STRONG_PEAK_ROE", "15"), 15)
        explosive_roe = _num(os.getenv("ATI_EXPLOSIVE_PEAK_ROE", "30"), 30)
        strong_pnl = _num(os.getenv("ATI_STRONG_REALIZED_PCT", "5"), 5)
        explosive_pnl = _num(os.getenv("ATI_EXPLOSIVE_REALIZED_PCT", "10"), 10)
        weak_score = _num(os.getenv("ATI_WEAK_ENTRY_SCORE", "60"), 60)
        p, peak, score = _num(pnl_pct), _num(peak_roe), _num(entry_score)
        if p >= explosive_pnl and peak >= explosive_roe:
            return "EXPLOSIVE_WIN"
        if p >= strong_pnl and peak >= strong_roe:
            return "STRONG_WIN"
        if p > 0:
            return "PROFITABLE"
        if score < weak_score and p <= 0:
            return "WEAK_ENTRY"
        return "LOSS"

    def assess_entry(self, state: Dict[str, Any] | None) -> Dict[str, Any]:
        """Return an advisory historical similarity assessment."""
        fp = self.fingerprint(state)
        with self._lock:
            rows = list(self._records)
        relevant = [r for r in rows if isinstance(r.get("fingerprint"), dict)]
        exact = [r for r in relevant if r.get("fingerprint") == fp]
        strong = [r for r in exact if r.get("label") in {"STRONG_WIN", "EXPLOSIVE_WIN"}]
        weak = [r for r in exact if r.get("label") in {"WEAK_ENTRY", "LOSS"}]
        if len(exact) < self.min_samples:
            return {
                "available": False, "label": "LEARNING", "confidence": 0.0,
                "samples": len(exact), "strong_samples": len(strong), "weak_samples": len(weak),
                "message": f"Learning this setup ({len(exact)}/{self.min_samples} samples). No historical edge applied.",
                "fingerprint": fp,
                "authority": "ADVISORY_ONLY",
            }
        win_rate = len(strong) / len(exact)
        weak_rate = len(weak) / len(exact)
        confidence = min(100.0, 100.0 * min(1.0, len(exact) / max(self.min_samples * 3, 1)) * abs(win_rate - weak_rate + 0.5))
        if win_rate >= 0.65 and win_rate > weak_rate:
            label, msg = "HISTORICALLY_STRONG", "Historical matches are predominantly strong; keep this setup under observation."
        elif weak_rate >= 0.55:
            label, msg = "HISTORICALLY_WEAK", "Historical matches are frequently weak/loss-making; treat this setup with extra skepticism."
        else:
            label, msg = "MIXED", "Historical matches are mixed; no edge is strong enough to influence execution."
        return {
            "available": True, "label": label, "confidence": round(confidence, 1),
            "samples": len(exact), "strong_samples": len(strong), "weak_samples": len(weak),
            "win_rate": round(win_rate * 100, 1), "weak_rate": round(weak_rate * 100, 1),
            "message": msg, "fingerprint": fp, "authority": "ADVISORY_ONLY",
        }

    def record_outcome(self, state: Dict[str, Any] | None, pnl_usdt: float, pnl_pct: float,
                       result: str, peak_roe: float = 0.0, drawdown_from_peak: float = 0.0,
                       exit_reason: str = "UNKNOWN") -> Dict[str, Any]:
        s = state if isinstance(state, dict) else {}
        tid = str(s.get("trade_id") or "").strip()
        if not tid:
            return {"saved": False, "reason": "missing_trade_id"}
        fp = self.fingerprint(s)
        label = self.classify_outcome(pnl_pct, peak_roe, _num(s.get("trade_score", 0)))
        rec = {
            "version": self.VERSION, "recorded_at": time.time(), "trade_id": tid,
            "symbol": s.get("current_symbol") or s.get("symbol"), "side": s.get("side"),
            "result": str(result), "label": label, "pnl_usdt": _num(pnl_usdt), "pnl_pct": _num(pnl_pct),
            "peak_roe": _num(peak_roe), "drawdown_from_peak": _num(drawdown_from_peak),
            "exit_reason": str(exit_reason or "UNKNOWN"), "fingerprint": fp,
        }
        with self._lock:
            if tid in self._ids:
                return {"saved": False, "reason": "duplicate_trade_id", "label": label}
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True, default=str) + "\n")
                self._ids.add(tid)
                self._records.append(rec)
                self._records = self._records[-5000:]
            except Exception as exc:
                return {"saved": False, "reason": f"write_error:{type(exc).__name__}", "label": label}
        return {"saved": True, "label": label, "trade_id": tid}

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            rows = list(self._records)
        total = len(rows)
        labels = {k: sum(1 for r in rows if r.get("label") == k) for k in ("EXPLOSIVE_WIN", "STRONG_WIN", "PROFITABLE", "WEAK_ENTRY", "LOSS")}
        winners = [r for r in rows if r.get("label") in {"EXPLOSIVE_WIN", "STRONG_WIN"}]
        avg_win = sum(_num(r.get("pnl_pct")) for r in winners) / len(winners) if winners else 0.0
        avg_peak = sum(_num(r.get("peak_roe")) for r in winners) / len(winners) if winners else 0.0
        return {
            "version": self.VERSION, "learning_enabled": True, "auto_rule_mutation": False,
            "total_trades": total, "labels": labels,
            "strong_or_explosive": len(winners),
            "explosive_rate": round(labels["EXPLOSIVE_WIN"] / total * 100, 1) if total else 0.0,
            "avg_strong_realized_pct": round(avg_win, 3),
            "avg_strong_peak_roe": round(avg_peak, 3),
            "min_samples": self.min_samples,
            "status": "LEARNING" if total < self.min_samples else "ACTIVE",
        }

    def playbook(self, limit: int = 12) -> List[Dict[str, Any]]:
        with self._lock:
            rows = list(self._records)
        strong = [r for r in rows if r.get("label") in {"EXPLOSIVE_WIN", "STRONG_WIN"}]
        groups: Dict[str, Dict[str, Any]] = {}
        for r in strong:
            fp = r.get("fingerprint") or {}
            # Compact, interpretable pattern key; avoids pretending the system
            # discovered a causal law from a tiny sample.
            key_fields = ("side", "market_regime", "move_maturity", "formation_verdict", "ob_grade", "liquidity_event", "structure_shift", "vpa_state", "forecast_quality")
            key = "|".join(f"{k}={fp.get(k, 'UNKNOWN')}" for k in key_fields)
            g = groups.setdefault(key, {"pattern": {k: fp.get(k, "UNKNOWN") for k in key_fields}, "samples": 0, "explosive": 0, "pnl_sum": 0.0, "peak_sum": 0.0})
            g["samples"] += 1
            g["explosive"] += 1 if r.get("label") == "EXPLOSIVE_WIN" else 0
            g["pnl_sum"] += _num(r.get("pnl_pct"))
            g["peak_sum"] += _num(r.get("peak_roe"))
        out = []
        for g in groups.values():
            if g["samples"] < self.min_samples:
                continue
            out.append({
                "pattern": g["pattern"], "samples": g["samples"],
                "explosive_count": g["explosive"],
                "explosive_share": round(g["explosive"] / g["samples"] * 100, 1),
                "avg_realized_pct": round(g["pnl_sum"] / g["samples"], 3),
                "avg_peak_roe": round(g["peak_sum"] / g["samples"], 3),
                "confidence": round(min(95.0, 50.0 + g["samples"] * 5.0), 1),
                "promotion": "RESEARCH_ONLY",
            })
        return sorted(out, key=lambda x: (x["explosive_share"], x["samples"], x["avg_realized_pct"]), reverse=True)[:max(1, int(limit))]

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(reversed(self._records[-max(1, int(limit)):]))


GLOBAL_ADAPTIVE_TRADE_INTELLIGENCE = AdaptiveTradeIntelligence()
