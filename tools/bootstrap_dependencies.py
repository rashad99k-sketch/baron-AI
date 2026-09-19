"""Robust Windows dependency bootstrap for BARON.

Design goals:
- install only runtime dependencies during normal startup (pytest is dev-only)
- avoid a single resolver/install failure taking down the launcher
- prefer wheels and reuse a healthy pip cache on the first attempt
- retry the failed distribution independently with a clean cache
- keep every pip subprocess bounded; never wait forever
- verify imports after installation
"""
from __future__ import annotations

import importlib.util
import os
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQ = ROOT / "requirements-runtime.txt"
DEV_REQ = ROOT / "requirements-dev.txt"

IMPORT_TO_DIST = {
    "ccxt": "ccxt",
    "pandas": "pandas",
    "numpy": "numpy",
    "flask": "Flask",
    "requests": "requests",
    "dotenv": "python-dotenv",
}

# A first-time Windows install can legitimately take several minutes while
# Defender/proxy software scans wheels.  This is still a hard upper bound.
INSTALL_TIMEOUT = int(os.getenv("BARON_PIP_TIMEOUT", "600"))
CONNECT_TIMEOUT = int(os.getenv("BARON_PIP_CONNECT_TIMEOUT", "45"))


def missing() -> list[str]:
    return [dist for mod, dist in IMPORT_TO_DIST.items() if importlib.util.find_spec(mod) is None]


def run_pip(args: list[str], label: str, *, timeout: int = INSTALL_TIMEOUT) -> bool:
    cmd = [sys.executable, "-m", "pip", *args]
    print(f"[SETUP] {label}", flush=True)
    env = os.environ.copy()
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("PIP_NO_INPUT", "1")
    env.setdefault("PIP_PROGRESS_BAR", "off")
    try:
        cp = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout, check=False)
        if cp.returncode != 0:
            print(f"[SETUP] {label} returned exit code {cp.returncode}.", flush=True)
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"[SETUP] {label} timed out after {timeout}s.", flush=True)
        return False
    except OSError as exc:
        print(f"[SETUP] {label} failed: {type(exc).__name__}: {exc}", flush=True)
        return False


def install_dist(dist: str, *, clean: bool = False) -> bool:
    cache_args = ["--no-cache-dir"] if clean else []
    args = [
        "install",
        "--prefer-binary",
        "--only-binary=:all:",
        "--retries", "2",
        "--timeout", str(CONNECT_TIMEOUT),
        *cache_args,
        dist,
    ]
    return run_pip(args, f"install {dist}")


def install_requirements_file(req: Path, label: str) -> bool:
    return run_pip([
        "install", "--prefer-binary", "--only-binary=:all:",
        "--retries", "2", "--timeout", str(CONNECT_TIMEOUT),
        "-r", str(req)
    ], label)


def install_dev_dependencies() -> bool:
    """Install test/development dependencies only when the release gate requests them."""
    if not DEV_REQ.exists():
        print(f"[ERROR] Missing {DEV_REQ.name}.", flush=True)
        return False
    if importlib.util.find_spec("pytest") is not None:
        print("[SETUP] Development dependency pytest already available.", flush=True)
        return True
    if install_requirements_file(DEV_REQ, "development requirements install") and importlib.util.find_spec("pytest") is not None:
        print("[SETUP] Development dependencies installed and verified.", flush=True)
        return True
    # Same bounded recovery path used for runtime dependencies, but scoped to the
    # actual missing dev package. This avoids the old 'pytest not found' cascade.
    run_pip(["cache", "purge"], "clean pip cache for dev recovery", timeout=120)
    if install_dist("pytest", clean=True) and importlib.util.find_spec("pytest") is not None:
        print("[SETUP] pytest recovery completed and import verified.", flush=True)
        return True
    if install_dist("pytest", clean=False) and importlib.util.find_spec("pytest") is not None:
        print("[SETUP] pytest recovery completed and import verified.", flush=True)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--dev", action="store_true", help="also install and verify development/test dependencies")
    args = parser.parse_args()
    if not RUNTIME_REQ.exists():
        print(f"[ERROR] Missing {RUNTIME_REQ.name}.", flush=True)
        return 1

    miss = missing()
    if not miss:
        print("[SETUP] Runtime dependencies already available.", flush=True)
        if args.dev and not install_dev_dependencies():
            print("[ERROR] Development/test dependency bootstrap failed (pytest is required for the release gate).", flush=True)
            return 1
        return 0

    print(f"[SETUP] Missing runtime dependencies: {', '.join(miss)}", flush=True)

    # Install the complete runtime set first. This lets pip resolve compatible
    # dependency versions once instead of repeatedly resolving the graph.
    if run_pip([
        "install", "--prefer-binary", "--only-binary=:all:",
        "--retries", "2", "--timeout", str(CONNECT_TIMEOUT),
        "-r", str(RUNTIME_REQ)
    ], "runtime requirements install"):
        remaining = missing()
        if not remaining:
            print("[SETUP] Runtime dependency installation completed.", flush=True)
            if args.dev and not install_dev_dependencies():
                print("[ERROR] Development/test dependency bootstrap failed (pytest is required for the release gate).", flush=True)
                return 1
            return 0
        print(f"[SETUP] Imports still missing after bulk install: {', '.join(remaining)}", flush=True)

    # Recovery: clear the cache once, then isolate the failing distributions.
    # We recompute missing() because the bulk attempt may have installed most
    # packages successfully before the failing package timed out.
    run_pip(["cache", "purge"], "clean pip cache", timeout=120)
    remaining = missing()
    for dist in remaining:
        if not install_dist(dist, clean=True):
            # A second isolated attempt is useful when an antivirus/proxy kills
            # a long install; it remains bounded and uses the normal cache path.
            if not install_dist(dist, clean=False):
                print(f"[ERROR] Could not install {dist} after isolated retries.", flush=True)
                print("[ERROR] Check proxy/antivirus access to PyPI and rerun the launcher.", flush=True)
                return 1

    remaining = missing()
    if remaining:
        print(f"[ERROR] Runtime dependencies still missing: {', '.join(remaining)}", flush=True)
        return 1

    print("[SETUP] Dependency recovery completed and imports verified.", flush=True)
    if args.dev and not install_dev_dependencies():
        print("[ERROR] Development/test dependency bootstrap failed (pytest is required for the release gate).", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
