# BARON Partition AI Merge — 2026-09-19

Merged the dedicated Partition AI forensic layer into the modular `baron_fix` project.

## Integration points
- `core/partition_ai.py` — forensic ledger/analytics layer
- `core/engine.py` — entry/partial/close hooks and evidence collection
- `portfolio/manager.py` — lifecycle observation + recovery capture
- `core/runtime.py` — post-SL observation service
- `docs/` — architecture and operating guide
- `archive/partition_reference/` — legacy monolithic Partition integration retained as reference only

## Non-negotiable architecture
Partition AI is observational only. The project does not add a second order-entry or position-management authority.

## Runtime validation status
Source compilation and targeted unit tests are required before deployment. A 2–3 hour live BingX run is not performed by the packaging step and must be executed in the user's runtime environment.
