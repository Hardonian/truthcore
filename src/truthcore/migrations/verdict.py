"""Migration definitions for verdict artifacts."""

from __future__ import annotations

import copy
from typing import Any

from truthcore.migrations.engine import register_migration


def _migrate_v0_to_v1(artifact: dict[str, Any]) -> dict[str, Any]:
    """Migrate verdict from v0.0.0 (unversioned) to v1.0.0.

    Changes:
    - Add contract metadata (done by migration framework)
    - Ensure required fields exist with defaults
    """
    result = copy.deepcopy(artifact)

    # Ensure verdict field exists
    if "verdict" not in result:
        # If there's a 'result' field, use that
        if "result" in result:
            result["verdict"] = result.pop("result")
        else:
            result["verdict"] = "UNKNOWN"

    # Ensure score field exists
    if "score" not in result:
        result["score"] = 0.0

    # Ensure findings field exists
    if "findings" not in result:
        result["findings"] = []

    return result


def _migrate_v1_to_v1_1(artifact: dict[str, Any]) -> dict[str, Any]:
    """Migrate verdict from v1.0.0 to v1.1.0.

    Changes:
    - Add optional evidence_refs field (empty list by default)
    """
    result = copy.deepcopy(artifact)

    # Add evidence_refs if not present
    if "evidence_refs" not in result:
        result["evidence_refs"] = []

    return result


def _migrate_v1_1_to_v2(artifact: dict[str, Any]) -> dict[str, Any]:
    """Migrate verdict from v1.1.0 to v2.0.0.

    Changes (BREAKING):
    - Rename 'score' to 'value'
    - Add required 'confidence' field
    - Rename 'findings' to 'items'
    - Remove deprecated 'notes' field
    """
    result = copy.deepcopy(artifact)

    # Rename score to value
    if "score" in result:
        result["value"] = result.pop("score")
    else:
        result["value"] = 0.0

    # Add confidence field (calculate from score if needed)
    if "confidence" not in result:
        # Simple heuristic: higher score = higher confidence
        score = result.get("value", 0.0)
        result["confidence"] = min(1.0, abs(score) / 100.0) if score else 0.5

    # Rename findings to items
    if "findings" in result:
        result["items"] = result.pop("findings")
    else:
        result["items"] = []

    # Remove deprecated fields
    result.pop("notes", None)
    result.pop("legacy_notes", None)

    return result


# Register verdict migrations
register_migration(
    artifact_type="verdict",
    from_version="0.0.0",
    to_version="1.0.0",
    fn=_migrate_v0_to_v1,
    description="Add contract metadata and ensure required fields",
    breaking=False,
)

register_migration(
    artifact_type="verdict",
    from_version="1.0.0",
    to_version="1.1.0",
    fn=_migrate_v1_to_v1_1,
    description="Add optional evidence_refs field",
    breaking=False,
)

register_migration(
    artifact_type="verdict",
    from_version="1.1.0",
    to_version="2.0.0",
    fn=_migrate_v1_1_to_v2,
    description="Rename score to value, add confidence, rename findings to items",
    breaking=True,
)

# Reverse migrations (for downgrades)
register_migration(
    artifact_type="verdict",
    from_version="1.0.0",
    to_version="0.0.0",
    fn=lambda a: copy.deepcopy(a),  # Just strip metadata
    description="Remove contract metadata",
    breaking=True,
)

register_migration(
    artifact_type="verdict",
    from_version="1.1.0",
    to_version="1.0.0",
    fn=lambda a: copy.deepcopy(a),  # Just remove evidence_refs from metadata
    description="Remove evidence_refs field",
    breaking=False,
)

register_migration(
    artifact_type="verdict",
    from_version="2.0.0",
    to_version="1.1.0",
    fn=lambda a: {**copy.deepcopy(a), "score": a.get("value", 0.0), "findings": a.get("items", [])},
    description="Revert value to score, items to findings (lossy)",
    breaking=True,
)
