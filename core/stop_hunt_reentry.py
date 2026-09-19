"""One-time thesis-continuity gate for stop-hunt re-entry."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def make_thesis_fingerprint(thesis: dict[str, Any] | None) -> str:
    payload = thesis or {}
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def evaluate_reentry(
    *,
    stop_classification: str,
    assessment: dict[str, Any] | None,
    reentries_used: int,
    thesis_fingerprint: str,
) -> dict[str, Any]:
    if int(reentries_used or 0) >= 1:
        return {"state": "INVALIDATED", "allowed": False, "reason": "MAX_REENTRY_USED"}
    if str(stop_classification).upper() != "STOP_HUNT":
        return {"state": "INVALIDATED", "allowed": False, "reason": "STOP_NOT_REARMABLE"}
    a = assessment or {}
    if str(a.get("decision", "")).upper() != "APPROVE":
        return {"state": "STOP_HUNT_REARM", "allowed": False, "reason": "FRESH_ASSESSMENT_NOT_APPROVED"}
    if str((a.get("entry_window") or "")).upper() not in {"EARLY", "CONFIRMED"}:
        return {"state": "STOP_HUNT_REARM", "allowed": False, "reason": "ENTRY_WINDOW_NOT_VALID"}
    event = a.get("liquidity_event") or {}
    if not (bool(event.get("detected")) and bool(event.get("reclaimed")) and float(event.get("quality", 0.0) or 0.0) >= 0.75):
        return {"state": "STOP_HUNT_REARM", "allowed": False, "reason": "FRESH_LIQUIDITY_CONFIRMATION_MISSING"}
    fresh_fp = str((a.get("thesis") or {}).get("fingerprint") or "")
    if not fresh_fp or fresh_fp != str(thesis_fingerprint):
        return {"state": "INVALIDATED", "allowed": False, "reason": "THESIS_FINGERPRINT_CHANGED"}
    return {
        "state": "REENTRY_READY",
        "allowed": True,
        "reason": "STOP_HUNT_REVALIDATED",
        "reentries_used_next": int(reentries_used or 0) + 1,
    }
