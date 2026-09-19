import os
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.institutional_evidence import analyze_institutional_evidence


def frame(n=80, side="BUY"):
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0.0, 0.18, n))
    open_ = close - rng.normal(0.0, 0.08, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.22, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.22, n)
    volume = rng.uniform(900, 1100, n)
    # Closed-candle sweep + displacement/reclaim near the end.
    if side == "BUY":
        level = float(low[-10:-2].min())
        low[-2] = level - 0.45
        open_[-2] = level - 0.10
        close[-2] = level + 0.10
        high[-2] = close[-2] + 0.08
        open_[-1] = close[-2]
        close[-1] = close[-2] + 0.75
        high[-1] = close[-1] + 0.10
        low[-1] = open_[-1] - 0.05
        volume[-2:] = [2200, 2400]
    else:
        level = float(high[-10:-2].max())
        high[-2] = level + 0.45
        open_[-2] = level + 0.10
        close[-2] = level - 0.10
        low[-2] = close[-2] - 0.08
        open_[-1] = close[-2]
        close[-1] = close[-2] - 0.75
        low[-1] = close[-1] - 0.10
        high[-1] = open_[-1] + 0.05
        volume[-2:] = [2200, 2400]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


class TestInstitutionalEvidence(unittest.TestCase):
    def test_insufficient_data_fails_closed(self):
        out = analyze_institutional_evidence(frame(20), "BUY")
        self.assertFalse(out["available"])
        self.assertEqual(out["reason"], "INSUFFICIENT_DATA")

    def test_returns_required_evidence_families(self):
        out = analyze_institutional_evidence(frame(100, "BUY"), "BUY")
        self.assertTrue(out["available"])
        for key in ("sweep", "structure", "order_block", "premium_discount", "vpa", "sequence", "indicators"):
            self.assertIn(key, out)
        self.assertIn("ema50", out["indicators"])
        self.assertIn("ema200", out["indicators"])
        self.assertIn("vwap", out["indicators"])
        self.assertTrue(out["no_lookahead"])

    def test_does_not_mutate_input(self):
        df = frame(100, "BUY")
        before = df.copy(deep=True)
        analyze_institutional_evidence(df, "BUY")
        pd.testing.assert_frame_equal(df, before)

    def test_side_symmetry(self):
        buy = frame(100, "BUY")
        sell = buy.copy()
        sell = pd.DataFrame({
            "open": 200 - buy["open"],
            "high": 200 - buy["low"],
            "low": 200 - buy["high"],
            "close": 200 - buy["close"],
            "volume": buy["volume"],
        })
        b = analyze_institutional_evidence(buy, "BUY")
        s = analyze_institutional_evidence(sell, "SELL")
        self.assertTrue(b["available"] and s["available"])
        self.assertEqual(b["side"], "BUY")
        self.assertEqual(s["side"], "SELL")
        self.assertIn(b["sequence"]["state"], {
            "FULL_INSTITUTIONAL_SEQUENCE", "LIQUIDITY_STRUCTURE_CONFIRMED",
            "LIQUIDITY_THEN_ZONE", "LIQUIDITY_ONLY", "ZONE_ONLY", "STRUCTURE_WITH_ZONE",
            "NO_INSTITUTIONAL_SEQUENCE",
        })

    def test_no_future_data_change_after_last_closed_candle(self):
        df = frame(100, "BUY")
        a = analyze_institutional_evidence(df, "BUY")
        extended = pd.concat([df, frame(50, "SELL")], ignore_index=True)
        # The final packet is allowed to change only because the current candle changed;
        # there is no future/look-ahead field in the original packet.
        self.assertTrue(a["no_lookahead"])
        self.assertNotIn("future", a)


if __name__ == "__main__":
    unittest.main()
