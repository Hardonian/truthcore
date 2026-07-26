#!/usr/bin/env python3
"""Emit a safe, machine-readable local Truth Core status snapshot."""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
print(json.dumps({
    "schema_version": "1.0",
    "product": "truthcore",
    "scope": "local_repository",
    "status": "ready" if (root / "src" / "truthcore").is_dir() else "degraded",
    "python": platform.python_version(),
    "truthcore_api_key_configured": bool(os.environ.get("TRUTHCORE_API_KEY")),
    "cache_enabled": os.environ.get("TRUTHCORE_CACHE_ENABLED", "1"),
    "paths": {"root": str(root), "schemas": str(root / "src" / "truthcore" / "schemas")},
    "claims": {"hosted": False, "customer_proof": False, "revenue_proof": False},
}, sort_keys=True))
