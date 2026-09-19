# BARON Windows Dependency Bootstrap — 2026-09-16

## Root cause observed
The Windows launcher used a single pip command with a 180-second subprocess ceiling. The screenshot shows the package downloads completing, followed by `pip install` timing out during the collected-package installation phase. This can be caused by Windows Defender/antivirus scanning, proxy/TLS overhead, or pip unpack/install work; the launcher should not classify this as a trading-code failure.

## Fix
- Runtime and development dependencies are separated.
- `pytest` is no longer installed during normal bot startup.
- Runtime installation prefers wheels (`--only-binary=:all:`).
- The first attempt reuses the normal pip cache.
- Recovery purges the cache once and installs only the still-missing distributions individually.
- Each pip subprocess has a hard upper bound (default 600 seconds) and a network timeout (default 45 seconds).
- A second isolated attempt can reuse the cache after a clean-cache failure.
- Imports are verified after installation.
- `BARON_PIP_TIMEOUT` and `BARON_PIP_CONNECT_TIMEOUT` may be overridden when a controlled environment needs different limits.

## What this does not do
It does not disable antivirus/proxy protection, silently ignore a failed installation, or run the bot with missing runtime dependencies. A failed dependency remains a hard startup error.

## Manual developer setup
After the bot starts successfully, development/test dependencies can be installed with:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```
