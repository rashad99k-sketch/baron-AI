import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.partition_ai import PartitionAI


def test_partition_10x_milestones_and_roe(tmp_path):
    ai = PartitionAI(str(tmp_path))
    tid = ai.begin_trade(symbol="BTC/USDT:USDT", side="BUY", entry_price=100.0, leverage=10, margin=20.0, qty=2, sl=98, tp1=101, tp2=102, score=80, trade_id="TRD-1", extra={"asset_class":"CRYPTO","component_scores":{"liquidity":90}})
    ai.observe(tid, price=101.0, roe_pct=10.0, indicators={"adx":30}, liquidity={"equal_lows":[{"level":99}]})
    ai.observe(tid, price=102.0, roe_pct=20.0)
    rec = ai.close_trade(tid, exit_price=102.0, pnl_pct=2.0, pnl_usdt=4.0, actual_roe_pct=20.0, exit_reason="TP2")
    assert rec["trade_id"] == "TRD-1"
    assert rec["mfe_pct"] >= 2.0
    assert rec["max_roe_pct"] >= 20.0
    assert "P1.0" in rec["milestones"] and "P2.0" in rec["milestones"]


def test_partition_news_keeps_underlying_class(tmp_path):
    ai = PartitionAI(str(tmp_path))
    tid = ai.begin_trade(symbol="BTC/USDT:USDT", side="BUY", entry_price=100.0, leverage=10,
                         trade_type="NEWS", classification="NEWS", trade_id="NEWS-1",
                         extra={"asset_class":"NEWS", "underlying_asset_class":"CRYPTO"})
    assert ai.active[tid]["asset_class"] == "NEWS"
    assert ai.active[tid]["underlying_asset_class"] == "CRYPTO"


def test_partition_sl_reversal_watch(tmp_path):
    ai = PartitionAI(str(tmp_path))
    tid = ai.begin_trade(symbol="ETH/USDT:USDT", side="BUY", entry_price=100.0, leverage=10,
                         margin=20.0, sl=98.0, tp1=101.0, tp2=102.0, trade_id="SL-1",
                         extra={"asset_class":"CRYPTO"})
    ai.close_trade(tid, exit_price=98.0, pnl_pct=-2.0, pnl_usdt=-4.0, actual_roe_pct=-20.0, exit_reason="STOP_LOSS")
    ai.observe_post_exit(symbol="ETH/USDT:USDT", price=101.0)
    assert ai.summary["sl_reversal"] == 1
