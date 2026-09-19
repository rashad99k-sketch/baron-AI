import os
import unittest
from unittest.mock import patch


class BingXPositionModeRoutingTest(unittest.TestCase):
    def test_one_way_adds_both_and_reduce_only_for_close(self):
        import core.engine as E
        with patch.dict(os.environ, {"PAPER_MODE":"False", "BINGX_POSITION_MODE":"ONE_WAY"}, clear=False):
            E._BINGX_POSITION_MODE_CACHE.update(mode=None, ts=0.0)
            self.assertEqual(E.get_bingx_position_mode(), "ONE_WAY")
            self.assertEqual(E._order_position_params("BUY", closing=False), {"positionSide":"BOTH"})
            self.assertEqual(E._order_position_params("BUY", closing=True), {"positionSide":"BOTH", "reduceOnly":True})

    def test_hedge_never_sends_reduce_only(self):
        import core.engine as E
        with patch.dict(os.environ, {"PAPER_MODE":"False", "BINGX_POSITION_MODE":"HEDGE"}, clear=False):
            E._BINGX_POSITION_MODE_CACHE.update(mode=None, ts=0.0)
            self.assertEqual(E._order_position_params("BUY", closing=False), {"positionSide":"LONG"})
            self.assertEqual(E._order_position_params("SELL", closing=True), {"positionSide":"SHORT"})
            self.assertNotIn("reduceOnly", E._order_position_params("SELL", closing=True))

    def test_live_unknown_mode_fails_closed(self):
        import core.engine as E
        with patch.dict(os.environ, {"PAPER_MODE":"False"}, clear=False):
            E._BINGX_POSITION_MODE_CACHE.update(mode=None, ts=0.0)
            with patch.object(E, "MODE_LIVE", True), patch.object(E, "BingXSignedREST", None):
                with self.assertRaises(RuntimeError):
                    E._order_position_params("BUY", closing=True)


if __name__ == "__main__":
    unittest.main()
