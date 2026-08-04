
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

INTERVAL_SECONDS = max(30, int(os.getenv("ATLAS_INTERVAL_SECONDS", "60")))
SCAN_COMMAND = [sys.executable, "background_scan.py"]
_shutdown = False


def _request_shutdown(signum, frame) -> None:
    global _shutdown
    _shutdown = True
    print(f"[worker] Shutdown signal received: {signum}", flush=True)


signal.signal(signal.SIGTERM, _request_shutdown)
signal.signal(signal.SIGINT, _request_shutdown)


def run_scan() -> int:
    started = datetime.now(timezone.utc).isoformat()
    print(f"[worker] Starting ATLAS scan at {started}", flush=True)

    completed = subprocess.run(
        SCAN_COMMAND,
        env=os.environ.copy(),
        check=False,
    )

    print(
        f"[worker] Scan finished with exit code {completed.returncode}",
        flush=True,
    )
    return completed.returncode


def main() -> None:
    print(
        f"[worker] ATLAS 60s worker online. "
        f"Target start-to-start interval: {INTERVAL_SECONDS}s",
        flush=True,
    )

    consecutive_failures = 0

    while not _shutdown:
        cycle_started = time.monotonic()
        exit_code = run_scan()

        if exit_code == 0:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            print(
                f"[worker] Scan failure #{consecutive_failures}. "
                "Worker remains alive and will retry.",
                flush=True,
            )

        elapsed = time.monotonic() - cycle_started
        sleep_seconds = max(1.0, INTERVAL_SECONDS - elapsed)

        print(
            f"[worker] Cycle took {elapsed:.1f}s. "
            f"Next scan in {sleep_seconds:.1f}s.",
            flush=True,
        )

        deadline = time.monotonic() + sleep_seconds
        while not _shutdown and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))

    print("[worker] ATLAS worker stopped cleanly.", flush=True)


if __name__ == "__main__":
    main()
