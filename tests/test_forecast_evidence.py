import os, sys, unittest
import numpy as np
import pandas as pd
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
from core.forecast_evidence import analyze_forecast_evidence


def frame(n=120, drift=0.0008):
    rng=np.random.default_rng(23)
    r=rng.normal(drift,0.003,n)
    close=100*np.cumprod(1+r)
    open_=np.r_[100.0, close[:-1]]
    high=np.maximum(open_,close)*(1+rng.uniform(0.0002,0.001,n))
    low=np.minimum(open_,close)*(1-rng.uniform(0.0002,0.001,n))
    vol=rng.uniform(900,1200,n)
    return pd.DataFrame({"open":open_,"high":high,"low":low,"close":close,"volume":vol})

class TestForecastEvidence(unittest.TestCase):
    def test_insufficient_data_fails_closed(self):
        out=analyze_forecast_evidence(frame(20),"BUY")
        self.assertFalse(out["available"])
        self.assertEqual(out["quality"],"UNAVAILABLE")

    def test_packet_contains_uncertainty_and_paths(self):
        out=analyze_forecast_evidence(frame(),"BUY")
        self.assertTrue(out["available"])
        self.assertIn("uncertainty",out)
        self.assertIn("directional_consensus",out)
        self.assertIn("dispersion_atr",out)
        self.assertTrue(0 <= out["uncertainty"] <= 1)
        self.assertTrue(0 <= out["directional_consensus"] <= 1)
        self.assertTrue(out["no_lookahead"])

    def test_does_not_mutate_input(self):
        df=frame(); before=df.copy(deep=True)
        analyze_forecast_evidence(df,"SELL")
        pd.testing.assert_frame_equal(df,before)

    def test_deterministic_for_same_frame(self):
        df=frame()
        a=analyze_forecast_evidence(df,"BUY")
        b=analyze_forecast_evidence(df,"BUY")
        self.assertEqual(a,b)

if __name__ == '__main__': unittest.main()
