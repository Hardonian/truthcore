"""Canonical JSON serialization and stable hashing.

Provides deterministic JSON output and consistent hashing across platforms.

Design decisions:
- Hash algorithm: blake2b (fast, 16-byte digest by default)
- JSON: sorted keys, no whitespace, ASCII-only, null/bool/number normalization
- Arrays: preserved order (caller must sort where semantic ordering matters)
- Floats: finite values only; NaN/Inf raise errors to prevent silent corruption
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


class CanonicalJSONEncoder(json.JSONEncoder):
    """JSON encoder that produces canonical, deterministic output.

    Guarantees:
    - Sorted keys at all levels
    - No whitespace
    - ASCII-only output
    - Consistent float representation (rejects NaN/Inf)
    - None → null, True → true, False → false (standard JSON)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["sort_keys"] = True
        kwargs["separators"] = (",", ":")
        kwargs["ensure_ascii"] = True
        super().__init__(**kwargs)

    def default(self, o: Any) -> Any:
        """Handle non-serializable types."""
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "value"):
            return o.value
        return super().default(o)

    def encode(self, o: Any) -> str:
        """Encode with canonical formatting."""
        return super().encode(self._normalize(o))

    def _normalize(self, obj: Any) -> Any:
        """Recursively normalize values for canonical representation."""
        if obj is None or isinstance(obj, bool):
            return obj
        if isinstance(obj, float):
            if math.isnan(obj):
                raise ValueError(f"Cannot canonicalize NaN float: {obj}")
            # Infinity is a valid domain value (e.g., BLOCKER severity weight)
            # Represent as a stable string to ensure cross-platform consistency
            if math.isinf(obj):
                return "Infinity" if obj > 0 else "-Infinity"
            # Normalize -0.0 to 0.0
            if obj == 0.0:
                return 0.0
            return obj
        if isinstance(obj, int):
            return obj
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return {k: self._normalize(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [self._normalize(item) for item in obj]
        if hasattr(obj, "to_dict"):
            return self._normalize(obj.to_dict())
        if hasattr(obj, "value"):
            return obj.value
        return obj


# Singleton encoder instance
_encoder = CanonicalJSONEncoder()


def canonical_json(data: Any) -> str:
    """Produce canonical JSON string from data.

    Args:
        data: Any JSON-serializable data

    Returns:
        Canonical JSON string with sorted keys, no whitespace, ASCII-only

    Raises:
        ValueError: If data contains NaN or Infinity floats
    """
    return _encoder.encode(data)


def canonical_hash(data: Any, algorithm: str = "blake2b", digest_size: int = 16) -> str:
    """Compute deterministic hash of any data via canonical JSON.

    Args:
        data: JSON-serializable data
        algorithm: Hash algorithm (blake2b, sha256, sha3_256)
        digest_size: Digest size for blake2b (default 16 bytes = 32 hex chars)

    Returns:
        Hex digest string
    """
    canonical = canonical_json(data).encode("utf-8")

    if algorithm == "blake2b":
        hasher = hashlib.blake2b(digest_size=digest_size)
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha3_256":
        hasher = hashlib.sha3_256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hasher.update(canonical)
    return hasher.hexdigest()


def evidence_hash(evidence: dict[str, Any]) -> str:
    """Compute stable hash for an evidence packet.

    Uses canonical JSON + blake2b for cross-platform stability.

    Args:
        evidence: Evidence packet dictionary

    Returns:
        32-char hex digest (blake2b, 16 bytes)
    """
    return canonical_hash(evidence, algorithm="blake2b", digest_size=16)
