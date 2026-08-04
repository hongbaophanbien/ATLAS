from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone


INTERVAL_SECONDS = max(60, int(os.getenv("ATLAS_INTERVAL_SECONDS", "60")))


def run_once() -> int:
    started = datetime.now(timezone.utc)
    print(f"[ATLAS] scan started {started.isoformat()}", flush=True)
    result = subprocess.run(
        [sys.executable, "background_scan.py"],
        check=False,
    )
    finished = datetime.now(timezone.utc)
    print(
        f"[ATLAS] scan finished {finished.isoformat()} "
        f"exit={result.returncode}",
        flush=True,
    )
    return result.returncode


def main() -> None:
    while True:
        cycle_start = time.monotonic()
        code = run_once()

        # Keep retrying each minute; never overwrite a valid snapshot with an empty one.
        elapsed = time.monotonic() - cycle_start
        sleep_for = max(1.0, INTERVAL_SECONDS - elapsed)
        if code != 0:
            sleep_for = min(20.0, sleep_for)

        print(f"[ATLAS] next cycle in {sleep_for:.1f}s", flush=True)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
