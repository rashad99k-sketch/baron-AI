"""Explicit exchange reconciliation helpers."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class ReconciliationResult:
    state: str
    symbol: str = ""
    internal_qty: float = 0.0
    exchange_qty: float = 0.0
    order_state: str = "UNKNOWN"
    fill_state: str = "UNKNOWN"
    differences: list[str] = field(default_factory=list)
    requested_qty: float = 0.0
    executed_qty: float = 0.0
    protection_state: str = "UNKNOWN"
    verified_zero: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "state": self.state,
            "symbol": self.symbol,
            "internal_qty": self.internal_qty,
            "exchange_qty": self.exchange_qty,
            "order_state": self.order_state,
            "fill_state": self.fill_state,
            "differences": list(self.differences),
            "requested_qty": self.requested_qty,
            "executed_qty": self.executed_qty,
            "protection_state": self.protection_state,
            "verified_zero": self.verified_zero,
            "timestamp": self.timestamp,
        }


class ExchangeReconciliation:
    """Small deterministic comparator; venue reads are injected by the caller."""

    STATES = {"SYNCED", "DRIFT", "RECOVERING", "UNKNOWN", "DATA_UNAVAILABLE", "PROVIDER_FAILURE"}

    @staticmethod
    def compare(symbol, internal_qty, exchange_qty, *, order_state="UNKNOWN", fill_state="UNKNOWN",
                data_available=True, provider_ok=True, requested_qty=0.0, executed_qty=0.0,
                protection_state="UNKNOWN"):
        requested_qty = float(requested_qty or 0.0)
        executed_qty = float(executed_qty or 0.0)
        verified_zero = float(exchange_qty or 0.0) == 0.0 and str(fill_state).upper() == "VERIFIED"
        if not provider_ok:
            return ReconciliationResult("PROVIDER_FAILURE", symbol, internal_qty, exchange_qty, order_state, fill_state,
                                        requested_qty=requested_qty, executed_qty=executed_qty,
                                        protection_state=str(protection_state), verified_zero=False)
        if not data_available:
            return ReconciliationResult("DATA_UNAVAILABLE", symbol, internal_qty, exchange_qty, order_state, fill_state,
                                        requested_qty=requested_qty, executed_qty=executed_qty,
                                        protection_state=str(protection_state), verified_zero=False)
        diff = abs(float(internal_qty or 0.0) - float(exchange_qty or 0.0))
        state = "SYNCED" if diff <= 1e-12 else "DRIFT"
        differences = [] if state == "SYNCED" else ["quantity_mismatch"]
        if requested_qty > 0 and executed_qty > requested_qty + 1e-12:
            differences.append("executed_qty_exceeds_requested")
        return ReconciliationResult(state, symbol, internal_qty, exchange_qty, order_state, fill_state, differences,
                                    requested_qty, executed_qty, str(protection_state), verified_zero)
