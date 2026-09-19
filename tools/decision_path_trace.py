"""CLI reader for BARON Decision Path telemetry.

Examples:
    python tools/decision_path_trace.py --symbol BTC/USDT:USDT
    python tools/decision_path_trace.py --symbol BTC/USDT:USDT TIA/USDT:USDT
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def load(path: str, symbols: set[str] | None = None):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if symbols and row.get("symbol") not in symbols:
            continue
        rows.append(row)
    rows.sort(key=lambda r: (r.get("symbol", ""), r.get("ts", 0)))
    return rows


def compact(row):
    snap = row.get("snapshot") or {}
    liq = snap.get("liquidity") or {}
    fields = row.get("fields") or {}
    return {
        "time": row.get("ts"),
        "stage": row.get("stage"),
        "decision": row.get("decision"),
        "side": row.get("side"),
        "reason": row.get("reason"),
        "authority": row.get("authority"),
        "source": row.get("source"),
        "price": snap.get("price"),
        "ema50": snap.get("ema50"),
        "ema200": snap.get("ema200"),
        "vwap": snap.get("vwap"),
        "vwap_side": snap.get("vwap_side"),
        "adx": snap.get("adx"),
        "di_plus": snap.get("di_plus"),
        "di_minus": snap.get("di_minus"),
        "di_spread": snap.get("di_spread"),
        "eqh": bool(liq.get("legacy_eqh") or liq.get("swing_eqh")),
        "eql": bool(liq.get("legacy_eql") or liq.get("swing_eql")),
        "nearest_eqh": liq.get("nearest_eqh"),
        "nearest_eql": liq.get("nearest_eql"),
        "eqh_distance_atr": liq.get("eqh_distance_atr"),
        "eql_distance_atr": liq.get("eql_distance_atr"),
        "selected_score": fields.get("selected_watch_score", fields.get("priority_score", fields.get("score"))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.getenv("DECISION_PATH_TRACE_PATH", "runtime/decision_path_trace.jsonl"))
    ap.add_argument("--symbol", nargs="*", default=[])
    args = ap.parse_args()
    rows = load(args.path, set(args.symbol) if args.symbol else None)
    if not rows:
        print("No decision-path telemetry found.")
        return 0
    for row in rows:
        print(json.dumps(compact(row), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
