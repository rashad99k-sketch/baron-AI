import os
import unittest
from unittest import mock


class NativeProtectionHedgeIsolationTest(unittest.TestCase):
    def test_long_and_short_protection_are_isolated_for_same_symbol(self):
        from portfolio.native_protection import NativeProtectionManager
        ex = mock.Mock()
        ex.create_order.side_effect = [
            {"id": "sl-long", "status": "open"},
            {"id": "sl-short", "status": "open"},
        ]
        ex.fetch_order.side_effect = [
            {"id": "sl-long", "status": "open"},
            {"id": "sl-short", "status": "open"},
        ]
        mgr = NativeProtectionManager(ex, lambda *a, **k: None)
        mgr.enabled = True
        self.assertEqual(mgr.place("BTC/USDT:USDT", "BUY", 1.0, 99.0, "LONG", "HEDGE")["status"], "PROTECTED")
        self.assertEqual(mgr.place("BTC/USDT:USDT", "SELL", 2.0, 101.0, "SHORT", "HEDGE")["status"], "PROTECTED")
        self.assertEqual(mgr.info("BTC/USDT:USDT", "LONG")["sl_order_id"], "sl-long")
        self.assertEqual(mgr.info("BTC/USDT:USDT", "SHORT")["sl_order_id"], "sl-short")
        self.assertTrue(mgr.cancel("BTC/USDT:USDT", "LONG"))
        self.assertIsNone(mgr.info("BTC/USDT:USDT", "LONG"))
        self.assertEqual(mgr.info("BTC/USDT:USDT", "SHORT")["sl_order_id"], "sl-short")


class NativeProtectionQuantityVerificationTest(unittest.TestCase):
    def test_ensure_native_protection_fails_closed_on_qty_mismatch(self):
        import core.engine as E
        saved = {
            "paper": E.PAPER_MODE,
            "live": E.MODE_LIVE,
            "np": E._NATIVE_PROTECTION,
            "status": E.STATE.get("protection_status"),
            "side": E.STATE.get("side"),
            "qty": E.STATE.get("remaining_qty"),
            "sl": E.STATE.get("synthetic_sl"),
        }
        class FakeNP:
            enabled = True
            def update(self, *args, **kwargs):
                return {"status": "PROTECTED", "sl_order_id": "sl-1"}
            def info(self, symbol, position_side=None):
                return {"sl_order_id": "sl-1", "qty": 0.5}
        try:
            E.PAPER_MODE = False
            E.MODE_LIVE = True
            E._NATIVE_PROTECTION = FakeNP()
            E.STATE.update({"side": "BUY", "remaining_qty": 1.0, "synthetic_sl": 99.0})
            with mock.patch.object(E, "get_bingx_position_mode", return_value="HEDGE"), \
                 mock.patch.object(E, "_verify_protection_qty", return_value=("MISMATCH", {"reason": "QTY_MISMATCH"})):
                result = E._ensure_native_protection("BTC/USDT:USDT")
            self.assertEqual(result.get("status"), "UNPROTECTED")
            self.assertEqual(E.STATE.get("protection_status"), "UNPROTECTED")
        finally:
            E.PAPER_MODE = saved["paper"]
            E.MODE_LIVE = saved["live"]
            E._NATIVE_PROTECTION = saved["np"]
            if saved["status"] is None:
                E.STATE.pop("protection_status", None)
            else:
                E.STATE["protection_status"] = saved["status"]
            E.STATE["side"] = saved["side"]
            E.STATE["remaining_qty"] = saved["qty"]
            E.STATE["synthetic_sl"] = saved["sl"]


class EntryFillTruthContractTest(unittest.TestCase):
    def test_authoritative_entry_fill_updates_initial_and_remaining_qty(self):
        import core.engine as E
        fn = getattr(E, "_adopt_authoritative_entry_fill", None)
        self.assertTrue(callable(fn))
        state = {"qty": 1.0, "qty_initial": 1.0, "remaining_qty": 1.0, "entry": 100.0}
        result = fn(state, {"filled": 0.73, "average": 101.25})
        self.assertTrue(result)
        self.assertAlmostEqual(state["qty"], 0.73)
        self.assertAlmostEqual(state["qty_initial"], 0.73)
        self.assertAlmostEqual(state["remaining_qty"], 0.73)
        self.assertAlmostEqual(state["entry"], 101.25)


class PostEntrySyncSafetyContractTest(unittest.TestCase):
    def test_unknown_post_entry_sync_is_not_accepted_as_active(self):
        import core.engine as E
        fn = getattr(E, "_post_entry_exchange_confirmation_ok", None)
        self.assertTrue(callable(fn))
        state = {"open": True, "remaining_qty": 1.0, "qty": 1.0}
        self.assertFalse(fn(state, None))

class ProtectionLegSelectionTest(unittest.TestCase):
    def test_protection_quantity_verification_queries_the_same_hedge_leg(self):
        import core.engine as E
        calls = []
        saved = {
            "paper": E.PAPER_MODE,
            "live": E.MODE_LIVE,
            "np": E._NATIVE_PROTECTION,
        }
        try:
            E.PAPER_MODE = False
            E.MODE_LIVE = True
            class FakeNP:
                def info(self, symbol, position_side=None):
                    return {"sl_order_id": "sl-long", "qty": 1.0}
            E._NATIVE_PROTECTION = FakeNP()
            def fake_fetch(symbol, position_side=None):
                calls.append(position_side)
                return ({"contracts": 1.0, "side": "long"}, "OK")
            with mock.patch.object(E, "get_bingx_position_mode", return_value="HEDGE"), \
                 mock.patch.object(E, "fetch_position_status", side_effect=fake_fetch):
                quality, _ = E._verify_protection_qty("BTC/USDT:USDT", "BUY", 1.0)
            self.assertEqual(quality, "MATCH")
            self.assertEqual(calls, ["LONG"])
        finally:
            E.PAPER_MODE = saved["paper"]
            E.MODE_LIVE = saved["live"]
            E._NATIVE_PROTECTION = saved["np"]
