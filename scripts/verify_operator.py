#!/usr/bin/env python3
"""Run the non-destructive operator verification contract."""
from __future__ import annotations

import os
import subprocess
import sys

commands = [
    [sys.executable, "scripts/status.py"],
    [sys.executable, "scripts/doctor.py"],
    [sys.executable, "scripts/contracts_check.py"],
]
env = {**os.environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src")}
for command in commands:
    print(f"==> {' '.join(command)}")
    result = subprocess.run(command, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
