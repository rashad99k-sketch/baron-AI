"""BARON Partition AI — Trade Forensics & Learning Ledger.

Observability-only layer. It does not make entry/exit decisions and does not mutate
BARON strategy rules. It records entry fingerprints, live milestones, MFE/MAE,
exit causes, liquidity context, and post-SL reversal evidence.
"""
from __future__ import annotations
import json, math, os, threading, time, uuid
from collections import defaultdict
from datetime import datetime, timezone

LEVERAGE_DEFAULT = 10.0
POST_EXIT_WATCH_SECONDS = float(os.getenv("PARTITION_POST_EXIT_WATCH_SECONDS", "1800"))
SNAPSHOT_INTERVAL = float(os.getenv("PARTITION_SNAPSHOT_INTERVAL", "10"))
MILESTONES = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0)
LOSS_MILESTONES = (-0.5, -1.0, -1.5, -2.0, -3.0, -5.0)

class PartitionAI:
    def __init__(self, root=None):
        self.root = root or os.getenv("PARTITION_AI_DIR", os.path.join("runtime", "partition_ai"))
        os.makedirs(self.root, exist_ok=True)
        self.ledger = os.path.join(self.root, "trade_ledger.jsonl")
        self.snapshots = os.path.join(self.root, "trade_snapshots.jsonl")
        self.post_exit = os.path.join(self.root, "post_exit_watch.jsonl")
        self.summary_path = os.path.join(self.root, "forensic_summary.json")
        self._lock = threading.RLock()
        self.active = {}
        self.watchers = {}
        self.summary = {"version": 2, "updated_at": None, "trades": 0, "wins": 0,
                        "losses": 0, "by_asset_class": {}, "by_exit_class": {},
                        "milestones": defaultdict(int), "sl_reversal": 0}
        self._load_summary()

    def _load_summary(self):
        try:
            with open(self.summary_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            self.summary.update(old)
            self.summary["milestones"] = defaultdict(int, self.summary.get("milestones", {}))
        except Exception:
            pass

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _json_safe(v):
        if isinstance(v, dict): return {str(k): PartitionAI._json_safe(x) for k,x in v.items()}
        if isinstance(v, (list, tuple)): return [PartitionAI._json_safe(x) for x in v]
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
        try: json.dumps(v); return v
        except Exception: return str(v)

    def _append(self, path, obj):
        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self._json_safe(obj), ensure_ascii=False, separators=(",", ":")) + "\n")

    def _flush_summary(self):
        with self._lock:
            self.summary["updated_at"] = self._now()
            data = dict(self.summary)
            data["milestones"] = dict(self.summary["milestones"])
            tmp = self.summary_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._json_safe(data), f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.summary_path)

    @staticmethod
    def asset_class(symbol, explicit=None):
        if explicit: return str(explicit).upper()
        s = str(symbol or "").upper()
        if any(x in s for x in ("XAU", "XAG", "GOLD", "SILVER")): return "METAL"
        if any(x in s for x in ("USOIL", "OIL", "WTI", "BRENT")): return "ENERGY"
        if any(x in s for x in ("US500", "SPX", "SP500", "NAS100", "NDX", "US30", "DJI", "UK100", "DAX")): return "INDEX"
        if any(x in s for x in ("NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META", "GOOG", "NFLX")): return "STOCK"
        if ":USDT" in s or "/USDT" in s or "BTC" in s or "ETH" in s: return "CRYPTO"
        return "UNKNOWN"

    @staticmethod
    def price_move(entry, price, side):
        if not entry or not price: return 0.0
        return ((price-entry)/entry*100.0) if side == "BUY" else ((entry-price)/entry*100.0)

    def begin_trade(self, *, symbol, side, entry_price, score=0, reason="", trade_type="", entry_type="",
                    classification="", leverage=10, margin=None, qty=None, sl=None, tp1=None, tp2=None,
                    indicators=None, liquidity=None, volume=None, structure=None, momentum=None,
                    smart_money=None, news=None, extra=None, trade_id=None):
        tid = str(trade_id or f"BARON-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:10].upper()}")
        ex = extra or {}
        explicit_class = ex.get("asset_class")
        underlying_class = ex.get("underlying_asset_class") or self.asset_class(symbol, explicit_class if str(explicit_class or "").upper() != "NEWS" else None)
        rec = {
            "trade_id": tid, "phase": "ENTRY", "created_at": self._now(), "entry_time": self._now(),
            "symbol": symbol, "asset_class": self.asset_class(symbol, explicit_class),
            "underlying_asset_class": str(underlying_class or "UNKNOWN").upper(),
            "side": side, "entry_price": float(entry_price), "leverage": float(leverage or LEVERAGE_DEFAULT),
            "score": float(score or 0), "reason": reason, "trade_type": trade_type, "entry_type": entry_type,
            "classification": classification, "qty": qty, "margin": margin, "sl": sl, "tp1": tp1, "tp2": tp2,
            "indicators": indicators or {}, "liquidity": liquidity or {}, "volume": volume or {},
            "structure": structure or {}, "momentum": momentum or {}, "smart_money": smart_money or {},
            "news": news or {}, "milestones": {}, "mfe_pct": 0.0, "mae_pct": 0.0,
            "max_roe_pct": 0.0, "min_roe_pct": 0.0, "snapshot_count": 0, "snapshots": 0,
        }
        with self._lock: self.active[tid] = rec
        self._append(self.ledger, rec)
        return tid

    def observe(self, trade_id, *, price, roe_pct=None, indicators=None, liquidity=None, volume=None,
                structure=None, momentum=None, smart_money=None, news=None, extra=None, timestamp=None):
        with self._lock:
            rec = self.active.get(trade_id)
            if not rec: return None
            move = self.price_move(rec["entry_price"], float(price), rec["side"])
            lev = rec["leverage"] or LEVERAGE_DEFAULT
            theoretical_roe = move * lev
            actual_roe = float(roe_pct) if roe_pct is not None else theoretical_roe
            rec["mfe_pct"] = max(rec["mfe_pct"], move)
            rec["mae_pct"] = min(rec["mae_pct"], move)
            rec["max_roe_pct"] = max(rec["max_roe_pct"], actual_roe)
            rec["min_roe_pct"] = min(rec["min_roe_pct"], actual_roe)
            rec["snapshot_count"] += 1
            for m in MILESTONES:
                if move >= m and f"P{m}" not in rec["milestones"]:
                    key = f"P{m}"
                    rec["milestones"][key] = {"time": self._now(), "price": float(price), "roe_pct": actual_roe}
                    self.summary["milestones"][key] += 1
            for m in LOSS_MILESTONES:
                if move <= m and f"N{abs(m)}" not in rec["milestones"]:
                    key = f"N{abs(m)}"
                    rec["milestones"][key] = {"time": self._now(), "price": float(price), "roe_pct": actual_roe}
                    self.summary["milestones"][key] += 1
            snap = {"trade_id": trade_id, "time": timestamp or self._now(), "price": float(price),
                    "price_move_pct": move, "roe_pct_actual_or_theoretical": actual_roe,
                    "indicators": indicators or {}, "liquidity": liquidity or {}, "volume": volume or {},
                    "structure": structure or {}, "momentum": momentum or {}, "smart_money": smart_money or {},
                    "news": news or {}, "extra": extra or {}}
            self._append(self.snapshots, snap)
            return snap

    def record_partial_close(self, trade_id, *, stage, qty, price, pnl_usdt=0.0, pnl_pct=0.0, roe_pct=None):
        with self._lock:
            rec = self.active.get(trade_id)
            if not rec:
                return None
            event = {
                "trade_id": trade_id, "time": self._now(), "phase": "PARTIAL_CLOSE",
                "stage": str(stage).upper(), "qty": float(qty or 0.0), "price": float(price or 0.0),
                "pnl_usdt": float(pnl_usdt or 0.0), "pnl_pct": float(pnl_pct or 0.0),
                "roe_pct": float(roe_pct) if roe_pct is not None else float(pnl_pct or 0.0) * float(rec.get("leverage") or LEVERAGE_DEFAULT),
            }
            rec.setdefault("partial_closes", []).append(event)
            self._append(os.path.join(self.root, "partial_close_events.jsonl"), event)
            self._append(self.ledger, {"trade_id": trade_id, "phase": "PARTIAL_CLOSE", **event})
            return event

    def close_trade(self, trade_id, *, exit_price, pnl_pct, pnl_usdt=0, exit_reason="UNKNOWN",
                    actual_roe_pct=None, indicators=None, liquidity=None, volume=None, structure=None,
                    momentum=None, smart_money=None, news=None, extra=None):
        with self._lock:
            rec = self.active.pop(trade_id, None)
            if not rec: return None
            exit_move = self.price_move(rec["entry_price"], float(exit_price), rec["side"])
            result = "WIN" if float(pnl_pct) > 0 else "LOSS"
            exit_class = self._classify_exit(rec, float(pnl_pct), exit_reason, extra or {})
            rec.update({"phase":"EXIT", "exit_time":self._now(), "exit_price":float(exit_price),
                        "pnl_pct":float(pnl_pct), "pnl_usdt":float(pnl_usdt or 0), "result":result,
                        "exit_reason":exit_reason, "exit_classification":exit_class,
                        "exit_price_move_pct":exit_move, "actual_roe_pct":actual_roe_pct,
                        "exit_indicators":indicators or {}, "exit_liquidity":liquidity or {},
                        "exit_volume":volume or {}, "exit_structure":structure or {},
                        "exit_momentum":momentum or {}, "exit_smart_money":smart_money or {},
                        "exit_news":news or {}, "extra":extra or {}})
            self._append(self.ledger, rec)
            self.summary["trades"] += 1
            self.summary["wins" if result == "WIN" else "losses"] += 1
            ac = rec["asset_class"]; self.summary["by_asset_class"].setdefault(ac, {"trades":0,"wins":0,"losses":0})
            self.summary["by_asset_class"][ac]["trades"] += 1; self.summary["by_asset_class"][ac]["wins" if result=="WIN" else "losses"] += 1
            uac = rec.get("underlying_asset_class") or "UNKNOWN"
            self.summary["by_underlying_asset_class"] = self.summary.setdefault("by_underlying_asset_class", {})
            self.summary["by_underlying_asset_class"].setdefault(uac, {"trades":0,"wins":0,"losses":0})
            self.summary["by_underlying_asset_class"][uac]["trades"] += 1; self.summary["by_underlying_asset_class"][uac]["wins" if result=="WIN" else "losses"] += 1
            self.summary["by_exit_class"].setdefault(exit_class, 0); self.summary["by_exit_class"][exit_class] += 1
            if float(pnl_pct) < 0 and ("SL" in str(exit_reason).upper() or "STOP" in str(exit_reason).upper()):
                self.watchers[trade_id] = {"trade": rec, "started": time.time(), "until": time.time()+POST_EXIT_WATCH_SECONDS,
                                           "stop_price": rec.get("sl"), "max_reclaim_pct": 0.0,
                        "entry_recovered": False, "tp1_reached": False, "tp2_reached": False,
                        "post_sl_reversal_recorded": False}
            self._flush_summary()
            return rec

    @staticmethod
    def _classify_exit(rec, pnl, reason, extra):
        r = str(reason or "").upper()
        e = {str(k).lower(): v for k,v in extra.items()}
        if pnl >= 0: return "PROFITABLE_EXIT"
        if "SL" in r or "STOP" in r:
            if e.get("post_sl_reversal") is True: return "SL_LIQUIDITY_SWEEP_REVERSAL"
            if e.get("late_entry") is True: return "LATE_ENTRY"
            if e.get("structure_failure") is True: return "TRUE_THESIS_FAILURE_STRUCTURE"
            if e.get("momentum_failure") is True: return "MOMENTUM_FAILURE"
            return "STOP_LOSS_PENDING_FORENSICS"
        return "LOSS_OTHER"

    def observe_post_exit(self, *, symbol, price, timestamp=None):
        now = time.time(); closed=[]
        with self._lock:
            for tid, w in list(self.watchers.items()):
                rec=w["trade"]
                if rec["symbol"] != symbol: continue
                move=self.price_move(rec["entry_price"], float(price), rec["side"])
                stop=rec.get("sl")
                reclaim=False
                if stop:
                    if rec["side"]=="BUY": reclaim=float(price) > float(stop) and move > 0
                    else: reclaim=float(price) < float(stop) and move > 0
                w["max_reclaim_pct"] = max(w["max_reclaim_pct"], move)
                event={"trade_id":tid,"symbol":symbol,"time":timestamp or self._now(),"price":float(price),
                       "original_entry":rec["entry_price"],"original_sl":stop,"post_exit_move_pct":move,
                       "reclaimed_stop_zone":reclaim,"max_reclaim_pct":w["max_reclaim_pct"]}
                self._append(self.post_exit,event)
                if move > 0:
                    if not w["entry_recovered"] and ((rec["side"] == "BUY" and float(price) >= rec["entry_price"]) or (rec["side"] == "SELL" and float(price) <= rec["entry_price"])):
                        w["entry_recovered"] = True
                    tp1 = rec.get("tp1")
                    tp2 = rec.get("tp2")
                    if tp1:
                        w["tp1_reached"] = w["tp1_reached"] or ((rec["side"] == "BUY" and float(price) >= float(tp1)) or (rec["side"] == "SELL" and float(price) <= float(tp1)))
                    if tp2:
                        w["tp2_reached"] = w["tp2_reached"] or ((rec["side"] == "BUY" and float(price) >= float(tp2)) or (rec["side"] == "SELL" and float(price) <= float(tp2)))
                event["entry_recovered"] = w["entry_recovered"]
                event["tp1_reached"] = w["tp1_reached"]
                event["tp2_reached"] = w["tp2_reached"]
                event["stop_distance_pct"] = (abs(float(rec.get("entry_price") or 0) - float(stop)) / float(rec.get("entry_price") or 1) * 100.0) if stop else None
                if reclaim and move >= 0.5 and not w["post_sl_reversal_recorded"]:
                    rec["post_sl_reversal"] = True
                    rec["post_sl_reversal_move_pct"] = move
                    w["post_sl_reversal_recorded"] = True
                    self.summary["sl_reversal"] += 1
                    self._append(self.ledger, {"trade_id":tid,"phase":"POST_EXIT_CLASSIFICATION","classification":"SL_LIQUIDITY_SWEEP_REVERSAL","recovered_entry":w["entry_recovered"],"tp1_reached":w["tp1_reached"],"tp2_reached":w["tp2_reached"],"time":self._now()})
                if now >= w["until"]:
                    closed.append(tid)
            for tid in closed: self.watchers.pop(tid,None)
            if closed: self._flush_summary()

    def watched_symbols(self):
        with self._lock:
            return [w["trade"]["symbol"] for w in self.watchers.values()]

    def status(self):
        with self._lock:
            return {"active_trades":len(self.active),"post_exit_watchers":len(self.watchers),"summary":self._json_safe(self.summary)}

GLOBAL_PARTITION_AI = PartitionAI()
partition_ai = GLOBAL_PARTITION_AI
