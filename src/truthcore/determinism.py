"""Determinism mode for reproducible, stable outputs.

Provides a global determinism flag and fixed-value providers for all
nondeterministic sources: timestamps, UUIDs, random bytes, git SHAs.

Usage in tests:
    with determinism_mode():
        # All timestamps, UUIDs, run IDs are now fixed and stable
        manifest = RunManifest.create(...)

Usage as a flag:
    set_determinism_mode(True)
    assert is_deterministic()
"""

from __future__ import annotations

import contextlib
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

# Thread-local state for determinism mode
_state = threading.local()

# Fixed values used in determinism mode
FIXED_TIMESTAMP = "2025-01-01T00:00:00Z"
FIXED_TIMESTAMP_DT = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
FIXED_UUID_HEX = "00000000000000000000000000000000"
FIXED_RUN_ID = "20250101000000-00000000"
FIXED_GIT_SHA = "000000000000"
FIXED_REQUEST_ID = "00000000-0000-0000-0000-000000000000"
FIXED_RANDOM_HEX = "0000000000000000"


def is_deterministic() -> bool:
    """Check if determinism mode is active."""
    return getattr(_state, "deterministic", False)


def set_determinism_mode(enabled: bool = True) -> None:
    """Set determinism mode globally (thread-local).

    Args:
        enabled: Whether to enable determinism mode
    """
    _state.deterministic = enabled


@contextlib.contextmanager
def determinism_mode() -> Generator[None, None, None]:
    """Context manager to enable determinism mode.

    Within this context, all nondeterministic sources return fixed values.
    """
    prev = getattr(_state, "deterministic", False)
    _state.deterministic = True
    try:
        yield
    finally:
        _state.deterministic = prev


def stable_now() -> datetime:
    """Return current time, or fixed time in determinism mode."""
    if is_deterministic():
        return FIXED_TIMESTAMP_DT
    return datetime.now(UTC)


def stable_timestamp() -> str:
    """Return normalized ISO timestamp, fixed in determinism mode."""
    if is_deterministic():
        return FIXED_TIMESTAMP
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_uuid_hex() -> str:
    """Return UUID hex string, fixed in determinism mode."""
    if is_deterministic():
        return FIXED_UUID_HEX
    import uuid
    return uuid.uuid4().hex


def stable_run_id() -> str:
    """Return a stable run ID, fixed in determinism mode."""
    if is_deterministic():
        return FIXED_RUN_ID
    import uuid
    now = datetime.now(UTC)
    return f"{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def stable_git_sha() -> str | None:
    """Return git SHA, fixed in determinism mode."""
    if is_deterministic():
        return FIXED_GIT_SHA
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return None


def stable_random_hex(n: int = 8) -> str:
    """Return random hex string, fixed in determinism mode."""
    if is_deterministic():
        return "0" * (n * 2)
    import secrets
    return secrets.token_hex(n)


def stable_isoformat() -> str:
    """Return ISO format timestamp, fixed in determinism mode."""
    if is_deterministic():
        return FIXED_TIMESTAMP_DT.isoformat()
    return datetime.now(UTC).isoformat()
