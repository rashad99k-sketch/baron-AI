import unittest
from unittest.mock import Mock

from execution.execution_service import ExecutionService, ExecutionAction


class ExecutionBoundaryTest(unittest.TestCase):
    def test_brain_action_routes_to_core_and_marks_verified_close(self):
        core = Mock()
        core.STATE = {"current_symbol":"BTC/USDT:USDT", "open":True, "remaining_qty":1.0}
        def _close(*args, **kwargs):
            core.STATE["open"] = False
            return True
        core.close_position_full.side_effect = _close
        svc = ExecutionService(core)
        self.assertTrue(svc.act(ExecutionAction.TP2, "BTC/USDT:USDT", reason="TP2"))
        core.close_position_full.assert_called_once()
        self.assertTrue(core.STATE.get("close_verified"))
        self.assertEqual(svc.last_intent.action, "TP2")

    def test_move_sl_requires_verified_protection_commit(self):
        core = Mock()
        core.STATE = {"current_symbol":"BTC/USDT:USDT", "remaining_qty":1.0, "side":"BUY"}
        core._protection_commit.return_value = {"status":"PROTECTED"}
        svc = ExecutionService(core)
        self.assertTrue(svc.act(ExecutionAction.MOVE_SL, "BTC/USDT:USDT", stop=100.0, reason="TRAIL"))


if __name__ == "__main__":
    unittest.main()

class LegacyCloseCallableCompatibilityTest(unittest.TestCase):
    def test_exit_supports_core_close_callable_without_optional_kwargs(self):
        class Core:
            STATE = {"current_symbol": "BTC/USDT:USDT", "open": True, "remaining_qty": 1.0}
            def close_position_full(self):
                self.STATE["open"] = False
                return True

        core = Core()
        svc = ExecutionService(core)
        self.assertTrue(svc.act(ExecutionAction.EXIT, "BTC/USDT:USDT", reason="REVERSAL"))
        self.assertFalse(core.STATE["open"])
        self.assertTrue(core.STATE.get("close_verified"))
