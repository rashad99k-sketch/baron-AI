from execution.reconciliation import ExchangeReconciliation
from portfolio.native_protection import NativeProtectionManager


def test_reconciliation_keeps_requested_and_executed_quantity_distinct():
    result = ExchangeReconciliation.compare(
        "BTC/USDT:USDT", 0.5, 0.5,
        order_state="FILLED", fill_state="VERIFIED",
        requested_qty=0.6, executed_qty=0.5,
        protection_state="VERIFIED",
    )
    data = result.to_dict()
    assert result.state == "SYNCED"
    assert data["requested_qty"] == 0.6
    assert data["executed_qty"] == 0.5
    assert data["protection_state"] == "VERIFIED"
    assert data["verified_zero"] is False


def test_reconciliation_can_prove_zero_position_only_from_exchange_quantity():
    result = ExchangeReconciliation.compare(
        "BTC/USDT:USDT", 0.0, 0.0,
        order_state="FILLED", fill_state="VERIFIED",
        requested_qty=0.5, executed_qty=0.5,
    )
    assert result.to_dict()["verified_zero"] is True


def test_native_conditional_protection_does_not_send_client_order_id():
    manager = NativeProtectionManager(exchange=None)
    params = manager._params("BUY", "LONG", 100.0, client_order_id="baron-test", position_mode="HEDGE")
    assert "clientOrderId" not in params
    assert params["positionSide"] == "LONG"
    assert "reduceOnly" not in params


def test_native_one_way_protection_uses_both_and_reduce_only():
    manager = NativeProtectionManager(exchange=None)
    params = manager._params("BUY", "LONG", 100.0, client_order_id="baron-test", position_mode="ONE_WAY")
    assert "clientOrderId" not in params
    assert params["positionSide"] == "BOTH"
    assert params["reduceOnly"] is True
