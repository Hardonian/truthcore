"""Safe memoization keyed by evidence hash.

Provides deterministic caching for expensive operations (e.g., verdict
computation, rule evaluation) keyed by the canonical hash of the input data.

Thread-safe via a simple lock. Cache can be cleared between runs.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from truthcore.canonical import canonical_hash

T = TypeVar("T")

_cache: dict[str, Any] = {}
_lock = threading.Lock()
_hits = 0
_misses = 0


def memoize_by_hash(data: dict[str, Any], compute: Callable[[], T]) -> T:
    """Return cached result if evidence hash matches, else compute and cache.

    Args:
        data: Input data (hashed to create cache key)
        compute: Callable that produces the result if cache miss

    Returns:
        Cached or freshly computed result
    """
    global _hits, _misses
    key = canonical_hash(data)
    with _lock:
        if key in _cache:
            _hits += 1
            return _cache[key]
    result = compute()
    with _lock:
        _cache[key] = result
        _misses += 1
    return result


def clear_memo_cache() -> None:
    """Clear the memoization cache."""
    global _hits, _misses
    with _lock:
        _cache.clear()
        _hits = 0
        _misses = 0


def memo_stats() -> dict[str, int]:
    """Get cache statistics."""
    with _lock:
        return {
            "entries": len(_cache),
            "hits": _hits,
            "misses": _misses,
        }
