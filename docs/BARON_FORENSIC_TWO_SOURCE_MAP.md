# BARON Two-Source Forensic Map

BARON now has two complementary evidence sources:

### Source A — Strategy/Architecture Forensics
The V29/trend integration, trade lifecycle, decision-path telemetry and outcome-memory modules describe what the system was designed to evaluate and what the execution path decided.

### Source B — Partition AI Trade Forensics
Partition AI records what was actually present around each real lifecycle event and what happened after the position was opened or closed.

The intended investigation flow is:

`Strategy hypothesis -> execution decision -> real position -> live indicator/liquidity evolution -> MFE/MAE -> TP/SL outcome -> post-SL behavior -> cross-trade pattern`

The two sources must be compared before any strategy rule is changed. Partition AI is not allowed to self-modify live strategy parameters.
