"""Run pytest with a Python 3.11+ guard."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """Run pytest only when Python 3.11+ is available."""
    if sys.version_info < (3, 11):
        print("Truth Core tests require Python 3.11+; skipping.")
        return 0

    return subprocess.call([
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--strict-markers",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
