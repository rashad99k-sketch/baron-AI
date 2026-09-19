import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.stop_hunt_reentry import evaluate_reentry, make_thesis_fingerprint


def approved_assessment(fp):
    return {
        "decision": "APPROVE",
        "setup_type": "LIQUIDITY_REVERSAL",
        "entry_window": "EARLY",
        "liquidity_event": {"detected": True, "reclaimed": True, "quality": 0.85},
        "thesis": {"fingerprint": fp},
    }


def test_true_failure_is_never_rearmed():
    result = evaluate_reentry(
        stop_classification="TRUE_FAILURE",
        assessment=approved_assessment("same"),
        reentries_used=0,
        thesis_fingerprint="same",
    )
    assert result["state"] == "INVALIDATED"
    assert result["allowed"] is False


def test_stop_hunt_can_rearm_once_with_fresh_confirmation():
    result = evaluate_reentry(
        stop_classification="STOP_HUNT",
        assessment=approved_assessment("same"),
        reentries_used=0,
        thesis_fingerprint="same",
    )
    assert result["state"] == "REENTRY_READY"
    assert result["allowed"] is True


def test_second_reentry_is_blocked_even_after_new_confirmation():
    result = evaluate_reentry(
        stop_classification="STOP_HUNT",
        assessment=approved_assessment("same"),
        reentries_used=1,
        thesis_fingerprint="same",
    )
    assert result["state"] == "INVALIDATED"
    assert result["allowed"] is False


def test_reentry_requires_same_thesis_fingerprint():
    fp = make_thesis_fingerprint({"zone": 100, "side": "BUY", "setup": "LIQUIDITY_REVERSAL"})
    result = evaluate_reentry(
        stop_classification="STOP_HUNT",
        assessment=approved_assessment("different"),
        reentries_used=0,
        thesis_fingerprint=fp,
    )
    assert result["state"] == "INVALIDATED"
    assert result["allowed"] is False
