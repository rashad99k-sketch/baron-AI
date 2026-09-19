import unittest

from scanner import universe as U


class AssetClassificationFailClosedTest(unittest.TestCase):
    def test_usdt_suffix_does_not_imply_crypto(self):
        cls, src, conf = U.classify("NVDA-USDT/USDT:USDT", {})
        self.assertEqual(cls, "STOCK")
        self.assertEqual(src, "pattern")

    def test_unknown_is_explicit(self):
        cls, src, conf = U.classify("RANDOMINSTRUMENT-USDT/USDT:USDT", {})
        self.assertEqual(cls, "UNKNOWN")
        self.assertEqual(src, "unknown")
        self.assertEqual(conf, 0.0)

    def test_venue_prefix_metadata_wins(self):
        cls, src, conf = U.classify("NCSKNVDA2USD/USDT:USDT", {})
        self.assertEqual((cls, src), ("STOCK", "metadata"))

    def test_known_crypto_needs_more_than_usdt_suffix(self):
        cls, src, conf = U.classify("BTC/USDT:USDT", {})
        self.assertEqual(cls, "CRYPTO")
        self.assertEqual(src, "known_universe")


if __name__ == "__main__":
    unittest.main()
