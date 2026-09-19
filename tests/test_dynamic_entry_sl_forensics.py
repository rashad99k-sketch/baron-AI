import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.entry_forensics import classify_stop_event, propose_dynamic_sl, ratchet_stop


def test_dynamic_sl_anchors_to_liquidity_invalidation_with_adaptive_buffer():
    proposal = propose_dynamic_sl(
        side="BUY",
        entry=100.0,
        atr=1.0,
        invalidation=98.8,
        liquidity_level=99.0,
        liquidity_quality=0.9,
        volatility_multiplier=1.25,
    )
    assert proposal["basis"] == "LIQUIDITY_INVALIDATION"
    assert proposal["sl"] < 99.0
    assert proposal["buffer"] > 0


def test_ratchet_stop_never_loosens_for_buy_or_sell():
    assert ratchet_stop("BUY", 100.0, 101.0) == 101.0
    assert ratchet_stop("BUY", 101.0, 100.5) == 101.0
    assert ratchet_stop("SELL", 100.0, 99.0) == 99.0
    assert ratchet_stop("SELL", 99.0, 99.5) == 99.0


def test_stop_forensics_distinguishes_true_failure_from_stop_hunt():
    true_failure = classify_stop_event(
        side="BUY", entry=100.0, stop_price=98.5, current_price=98.2,
        invalidation=98.5, ema200_intact=False, structure_failed=True,
        fresh_sweep=False, reclaim=False, volatility_spike=False,
    )
    assert true_failure["classification"] == "TRUE_FAILURE"

    stop_hunt = classify_stop_event(
        side="BUY", entry=100.0, stop_price=98.5, current_price=99.2,
        invalidation=98.5, ema200_intact=True, structure_failed=False,
        fresh_sweep=True, reclaim=True, volatility_spike=False,
    )
    assert stop_hunt["classification"] == "STOP_HUNT"


def test_stop_forensics_marks_late_or_volatility_errors():
    late = classify_stop_event(
        side="BUY", entry=100.0, stop_price=96.0, current_price=96.2,
        invalidation=98.5, ema200_intact=True, structure_failed=False,
        fresh_sweep=False, reclaim=False, volatility_spike=False,
        entry_window="LATE",
    )
    assert late["classification"] == "LATE_ENTRY"

    spike = classify_stop_event(
        side="SELL", entry=100.0, stop_price=101.5, current_price=101.7,
        invalidation=101.0, ema200_intact=True, structure_failed=False,
        fresh_sweep=False, reclaim=False, volatility_spike=True,
        entry_window="EARLY",
    )
    assert spike["classification"] == "VOLATILITY_SPIKE"
