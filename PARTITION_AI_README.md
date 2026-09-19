# BARON Partition AI — Integrated Release

This release merges Partition AI into the modular BARON V29 project.

**Run the normal BARON entry point only. Do not run the legacy reference file in `archive/partition_reference/`.**

Partition AI is an observability-only layer. It records trade evidence; it never opens, closes, sizes, moves stops, changes the 6-position capacity rule, or changes the News slot rule.

Runtime output: `runtime/partition_ai/`

Key files:
- `trade_ledger.jsonl`
- `trade_snapshots.jsonl`
- `partial_close_events.jsonl`
- `post_exit_watch.jsonl`
- `forensic_summary.json`

Configuration is in `.env.example`:
- `PARTITION_AI_ENABLED=True`
- `PARTITION_SNAPSHOT_INTERVAL_SEC=15`
- `PARTITION_POST_EXIT_WATCH_SECONDS=1800`
- `PARTITION_POST_EXIT_POLL_SEC=15`
- `PARTITION_POST_EXIT_MAX_WATCHERS=12`

At 10x leverage, Partition stores price move and ROE separately. A +1% favorable price move is approximately +10% theoretical ROE before fees/funding/slippage.

For News trades it records the event payload, mapped symbol/asset class, expected direction, reaction direction, causality, and the resulting trade path.
