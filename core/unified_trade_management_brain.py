"""Unified trade-management decision authority for BARON.

The Brain is the only runtime component allowed to decide a management action.
It consumes already-computed market/position evidence and returns a declarative
Decision. It never calls an exchange API and never mutates exchange state.
Legacy intelligence classes remain import-compatible for historical tests and
research, but runtime execution must converge here before reaching
ExecutionService.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import time


@dataclass(frozen=True)
class BrainDecision:
    action: str
    reason: str = ""
    timestamp: float = 0.0
    stage: str = "MANAGEMENT"
    stop: float | None = None
    details: dict | None = None

    def to_dict(self):
        return {
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "stop": self.stop,
            "details": dict(self.details or {}),
            "authority": "UnifiedTradeManagementBrain",
        }


class UnifiedTradeManagementBrain:
    """Single decision authority for an already-open position.

    Priority is deliberately deterministic:
      1. emergency/confirmed thesis failure
      2. TP2 / TP1 target events
      3. confirmed stop hit
      4. evidence-based profit protection
      5. runner trailing
      6. protective SL ratchet
      7. HOLD

    The manager may calculate evidence, but it cannot independently execute an
    exit. All executable decisions pass through ``decide_action`` into the
    ExecutionService.
    """

    def __init__(self, legacy_brain=None):
        self.legacy = legacy_brain
        self.last_decision: BrainDecision | None = None
        self.current_trade_state = "UNKNOWN"

    @staticmethod
    def _decision(action, *, reason="", stage="MANAGEMENT", stop=None, details=None):
        return BrainDecision(
            action=str(getattr(action, "value", action)).upper(),
            reason=str(reason or ""),
            timestamp=time.time(),
            stage=str(stage or "MANAGEMENT").upper(),
            stop=float(stop) if stop is not None else None,
            details=dict(details or {}),
        )

    def evaluate(self, context: dict | None = None) -> BrainDecision:
        """Choose exactly one management action from a frozen evidence snapshot."""
        c = dict(context or {})
        side = str(c.get("side", "BUY")).upper()
        tp1_hit = bool(c.get("tp1_hit", False))
        roe = float(c.get("roe", 0.0) or 0.0)
        roe_valid = bool(c.get("roe_valid", True))

        # 1) Safety exits outrank profit events. If a stop/failure is observable
        # on the current mark, BARON must not partially close at a target merely
        # because the same candle also wicked through that target.
        if bool(c.get("force_exit", False)):
            d = self._decision("FORCE_EXIT", reason=str(c.get("force_exit_reason") or "forced management close"), stage="FORCE_EXIT")
        elif bool(c.get("confirmed_failure_exit", False)):
            d = self._decision("EXIT", reason=str(c.get("failure_reason") or "confirmed thesis failure"), stage="EXIT")
        elif bool(c.get("stop_hit", False)):
            d = self._decision("EXIT", reason=str(c.get("stop_reason") or "protective stop hit"), stage="EXIT")
        elif not tp1_hit and bool(c.get("tp1_touched", False)):
            d = self._decision("TP1", reason="canonical TP1 target touched", stage="TP1")
        elif tp1_hit and bool(c.get("tp2_touched", False)):
            d = self._decision("TP2", reason="canonical TP2 target touched", stage="TP2")
        elif bool(c.get("pre_tp1_protect", False)) and not tp1_hit and roe_valid and roe > 0:
            d = self._decision("BREAKEVEN", reason=str(c.get("protect_reason") or "profit protection before TP1"), stage="PROTECTION", stop=c.get("entry"))
        elif tp1_hit and bool(c.get("trail_hit", False)):
            d = self._decision("EXIT", reason=str(c.get("trail_reason") or "runner trailing stop hit"), stage="RUNNER_EXIT")
        elif bool(c.get("be_needed", False)) and roe_valid:
            d = self._decision("BREAKEVEN", reason=str(c.get("be_reason") or "breakeven ratchet"), stage="PROTECTION", stop=c.get("entry"))
        elif tp1_hit and bool(c.get("trail_update", False)) and c.get("trail_stop") is not None:
            d = self._decision("TRAIL", reason=str(c.get("trail_reason") or "runner trail update"), stage="TRAIL", stop=c.get("trail_stop"))
        elif c.get("candidate_sl") is not None and bool(c.get("candidate_sl_more_protective", False)):
            d = self._decision("MOVE_SL", reason=str(c.get("candidate_sl_reason") or "thesis/ATR protective ratchet"), stage="PROTECTION", stop=c.get("candidate_sl"))
        else:
            d = self._decision("HOLD", reason=str(c.get("hold_reason") or "no management action"), stage="HOLD")

        self.last_decision = d
        return d

    def decide_action(self, action, *, reason="", stage=None, stop=None, details=None):
        """Record an already-selected action for the execution boundary.

        Kept as the narrow compatibility bridge used by force-close/event paths.
        Normal live management should call ``evaluate`` first.
        """
        decision = self._decision(action, reason=reason, stage=stage or str(getattr(action, "value", action)), stop=stop, details=details)
        self.last_decision = decision
        return decision

    def update(self, smart: dict, momentum: dict, adx: float, regime: str, market_state: dict | None = None):
        """Update the display/state label without granting an execution bypass."""
        ms = dict(market_state or {})
        canonical = str(ms.get("state") or "").upper()
        mapping = {
            "ACCUMULATION": "ACCUMULATION",
            "RE_ACCUMULATION": "ACCUMULATION",
            "MARKUP": "EXPANSION",
            "TREND_PULLBACK": "HEALTHY_PULLBACK",
            "DISTRIBUTION": "DISTRIBUTION",
            "RE_DISTRIBUTION": "DISTRIBUTION",
            "MARKDOWN": "MARKDOWN",
            "TRANSITION": "TRANSITION",
            "UNKNOWN": "UNKNOWN",
        }
        if canonical in mapping:
            self.current_trade_state = mapping[canonical]
            return self.current_trade_state
        # Compatibility fallback only when the canonical market-state engine is
        # unavailable; legacy state machine is never allowed to override a valid
        # canonical state.
        if self.legacy is not None and hasattr(self.legacy, "update"):
            self.current_trade_state = self.legacy.update(smart, momentum, adx, regime)
        return self.current_trade_state

    def get_trail_multiplier(self) -> float:
        if self.current_trade_state == "MARKUP":
            return 3.5
        mapping = {
            "ACCUMULATION": 3.0, "EXPANSION": 3.5, "TREND_RIDE": 4.0,
            "HEALTHY_PULLBACK": 2.8, "DISTRIBUTION": 1.2, "MARKDOWN": 1.0,
            "TRANSITION": 1.8, "RANGE_CHOP": 1.5,
        }
        if self.current_trade_state in mapping:
            return mapping[self.current_trade_state]
        if self.legacy is not None and hasattr(self.legacy, "get_trail_multiplier"):
            return self.legacy.get_trail_multiplier()
        return 1.5

    def should_delay_tp1(self) -> bool:
        return self.current_trade_state in {"ACCUMULATION", "EXPANSION", "TREND_RIDE", "HEALTHY_PULLBACK"}

    def should_aggressive_profit_lock(self) -> bool:
        return self.current_trade_state in {"DISTRIBUTION", "MARKDOWN", "EXHAUSTION", "MOMENTUM_COLLAPSE", "PROFIT_DEFENSE", "LIQUIDITY_EXHAUSTION"}

    def should_hard_exit(self) -> bool:
        return self.current_trade_state in {"PANIC_EXIT", "MOMENTUM_COLLAPSE", "LIQUIDITY_EXHAUSTION"}

    def get_patience_level(self) -> str:
        if self.current_trade_state in {"ACCUMULATION", "EXPANSION", "TREND_RIDE", "HEALTHY_PULLBACK"}:
            return "HIGH"
        if self.current_trade_state in {"DISTRIBUTION", "MARKDOWN", "EXHAUSTION", "PROFIT_DEFENSE"}:
            return "LOW"
        return "MEDIUM"


__all__ = ["BrainDecision", "UnifiedTradeManagementBrain"]
