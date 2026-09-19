"""BARON execution action boundary.

The Brain decides *what* should happen. This service is the sole application
boundary for profit/protection actions; the preserved core exchange kernel
performs the actual venue operation and verification.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
import inspect
import threading
import time


class ExecutionAction(str, Enum):
    ENTER = "ENTER"
    TP1 = "TP1"
    MOVE_SL = "MOVE_SL"
    BREAKEVEN = "BREAKEVEN"
    TRAIL = "TRAIL"
    TP2 = "TP2"
    EXIT = "EXIT"
    FORCE_EXIT = "FORCE_EXIT"
    HOLD = "HOLD"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class ExecutionIntent:
    action: str
    symbol: str
    stage: str = "MANAGEMENT"
    reason: str = ""
    requested_qty: float = 0.0
    timestamp: float = 0.0

    def to_dict(self):
        return asdict(self)


class ExecutionService:
    """Single action gateway over the preserved BARON exchange kernel."""

    def __init__(self, core_engine):
        self.core = core_engine
        self._lock = threading.RLock()
        self.last_intent: ExecutionIntent | None = None

    def _intent(self, action, symbol, *, stage="MANAGEMENT", reason="", requested_qty=0.0):
        intent = ExecutionIntent(
            action=str(getattr(action, "value", action)).upper(),
            symbol=str(symbol or ""),
            stage=str(stage or "MANAGEMENT").upper(),
            reason=str(reason or ""),
            requested_qty=float(requested_qty or 0.0),
            timestamp=time.time(),
        )
        self.last_intent = intent
        return intent

    def open(self, side, amount, symbol, *, sl=0.0, tp1=0.0, tp2=0.0,
             score=0.0, reason="SERVICE", atr=0.0,
             trade_type="INSTITUTIONAL", entry_type="SERVICE",
             classification="SNIPER"):
        self._intent(ExecutionAction.ENTER, symbol, stage="ENTRY", reason=reason,
                     requested_qty=amount)
        price = self.core.get_ticker_safe(symbol)
        if not price:
            return False
        return bool(self.core.execute_entry(
            side, symbol, price, sl, tp1, tp2, score, reason, atr,
            trade_type, entry_type, classification
        ))

    def act(self, action, symbol=None, *, reason="MANAGEMENT", stage=None,
            close_price=None, stop=None):
        """Execute one already-decided action through the preserved kernel.

        No entry/exit decision is made here. The method only translates a
        decision into the existing strict exchange path and verifies the local
        post-condition exposed by that path.
        """
        symbol = symbol or getattr(self.core, "STATE", {}).get("current_symbol")
        if symbol and hasattr(self.core, "STATE") and self.core.STATE.get("current_symbol") not in (None, symbol):
            return False
        action_name = str(getattr(action, "value", action)).upper()
        self._intent(action_name, symbol, stage=stage or action_name, reason=reason,
                     requested_qty=(getattr(self.core, "STATE", {}) or {}).get("remaining_qty", 0.0))
        with self._lock:
            if action_name == ExecutionAction.TP1.value:
                ok = bool(self.core.close_partial(0.5, stage="TP1"))
                if ok:
                    state = getattr(self.core, "STATE", {})
                    state["tp1_execution_verified"] = True
                return ok
            if action_name in {
                ExecutionAction.TP2.value,
                ExecutionAction.EXIT.value,
                ExecutionAction.FORCE_EXIT.value,
            }:
                close_fn = self.core.close_position_full
                close_kwargs = {
                    "close_price": close_price,
                    "stage": stage or action_name,
                }
                # The preserved core close contract accepts these optional
                # keywords, but tests/legacy adapters may expose the historical
                # zero-argument callable. Adapt to the callable signature rather
                # than catching TypeError from inside the real close function.
                try:
                    params = inspect.signature(close_fn).parameters
                    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD
                                         for p in params.values())
                    if not accepts_kwargs:
                        close_kwargs = {k: v for k, v in close_kwargs.items() if k in params}
                except (TypeError, ValueError):
                    # Builtin/c-extension callables may not expose signatures;
                    # retain the full documented core contract in that case.
                    pass
                ok = bool(close_fn(**close_kwargs))
                # The strict core path owns the final CLOSED decision. Keep this
                # post-condition explicit for callers and dashboard telemetry.
                state = getattr(self.core, "STATE", {})
                if ok and not bool(state.get("open")):
                    state["close_verified"] = True
                return ok
            if action_name in {
                ExecutionAction.MOVE_SL.value,
                ExecutionAction.BREAKEVEN.value,
                ExecutionAction.TRAIL.value,
            }:
                if stop is None:
                    return False
                commit = getattr(self.core, "_protection_commit", None)
                if not callable(commit):
                    return False
                side = (getattr(self.core, "STATE", {}) or {}).get("side")
                qty = (getattr(self.core, "STATE", {}) or {}).get("remaining_qty", 0.0)
                result = commit(symbol, side, qty, float(stop), reason=reason)
                return str((result or {}).get("status", "")).upper() in {"PROTECTED", "PAPER_SYNTHETIC"}
            if action_name in {ExecutionAction.HOLD.value, ExecutionAction.RECOVERY.value}:
                return True
        return False

    def close(self, symbol=None, *, reason="MANAGEMENT"):
        return self.act(ExecutionAction.EXIT, symbol, reason=reason, stage="EXIT")
