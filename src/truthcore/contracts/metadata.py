"""Contract metadata helpers for truth-core artifacts.

This module provides utilities for injecting and reading contract metadata
from artifact outputs.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from truthcore.contracts.registry import get_registry


@dataclass
class ContractMetadata:
    """Contract metadata for an artifact."""

    artifact_type: str
    contract_version: str
    truthcore_version: str
    engine_versions: dict[str, str]
    created_at: str
    schema: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "artifact_type": self.artifact_type,
            "contract_version": self.contract_version,
            "truthcore_version": self.truthcore_version,
            "engine_versions": self.engine_versions,
            "created_at": self.created_at,
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractMetadata:
        """Create from dictionary representation."""
        return cls(
            artifact_type=data["artifact_type"],
            contract_version=data["contract_version"],
            truthcore_version=data["truthcore_version"],
            engine_versions=data.get("engine_versions", {}),
            created_at=data["created_at"],
            schema=data["schema"],
        )


def get_truthcore_version() -> str:
    """Get the current truth-core version."""
    try:
        from truthcore import __version__
        return __version__
    except ImportError:
        return "unknown"


def normalize_timestamp(dt: datetime | None = None) -> str:
    """Normalize a timestamp to UTC ISO 8601 format.

    Args:
        dt: Datetime to normalize. If None, uses current UTC time.

    Returns:
        ISO 8601 formatted string in UTC (e.g., "2026-01-31T00:00:00Z")
    """
    if dt is None:
        dt = datetime.now(UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)

    # Format without microseconds, with Z suffix
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_metadata(
    artifact_type: str,
    contract_version: str,
    engine_versions: dict[str, str] | None = None,
    created_at: datetime | None = None,
) -> ContractMetadata:
    """Create contract metadata for an artifact.

    Args:
        artifact_type: Type of artifact (e.g., "verdict", "readiness")
        contract_version: Version of the contract (e.g., "2.0.0")
        engine_versions: Versions of engines used to produce artifact
        created_at: Creation timestamp (defaults to current UTC time)

    Returns:
        ContractMetadata instance
    """
    if engine_versions is None:
        engine_versions = {}

    # Build schema path
    registry = get_registry()
    schema_path = f"schemas/{artifact_type}/v{contract_version}/{artifact_type}.schema.json"

    # Verify version exists
    try:
        registry.get_schema(artifact_type, contract_version)
    except ValueError:
        # Schema doesn't exist yet, that's ok for new artifacts
        pass

    return ContractMetadata(
        artifact_type=artifact_type,
        contract_version=contract_version,
        truthcore_version=get_truthcore_version(),
        engine_versions=engine_versions,
        created_at=normalize_timestamp(created_at),
        schema=schema_path,
    )


def inject_metadata(
    artifact: dict[str, Any],
    metadata: ContractMetadata,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Inject contract metadata into an artifact.

    Args:
        artifact: The artifact dictionary to inject metadata into
        metadata: Contract metadata to inject
        replace_existing: If True, replace existing _contract field

    Returns:
        Artifact with metadata injected (returns new dict, doesn't modify original)
    """
    result = copy.deepcopy(artifact)

    if "_contract" in result and not replace_existing:
        raise ValueError("Artifact already has _contract metadata. Use replace_existing=True to overwrite.")

    result["_contract"] = metadata.to_dict()
    return result


def extract_metadata(artifact: dict[str, Any]) -> ContractMetadata | None:
    """Extract contract metadata from an artifact.

    Args:
        artifact: The artifact dictionary to extract metadata from

    Returns:
        ContractMetadata if present, None otherwise
    """
    if "_contract" not in artifact:
        return None

    try:
        return ContractMetadata.from_dict(artifact["_contract"])
    except (KeyError, TypeError):
        return None


def update_metadata(
    artifact: dict[str, Any],
    **updates: Any,
) -> dict[str, Any]:
    """Update specific fields in artifact metadata.

    Args:
        artifact: The artifact dictionary
        **updates: Fields to update (e.g., contract_version="2.0.0")

    Returns:
        Artifact with updated metadata
    """
    result = copy.deepcopy(artifact)

    if "_contract" not in result:
        raise ValueError("Artifact has no _contract metadata to update")

    for key, value in updates.items():
        if key in result["_contract"]:
            result["_contract"][key] = value
        else:
            raise ValueError(f"Unknown metadata field: {key}")

    return result


def remove_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    """Remove contract metadata from an artifact.

    Args:
        artifact: The artifact dictionary

    Returns:
        Artifact without _contract field
    """
    result = copy.deepcopy(artifact)
    result.pop("_contract", None)
    return result


def get_artifact_version(artifact: dict[str, Any]) -> str | None:
    """Get the contract version from an artifact.

    Args:
        artifact: The artifact dictionary

    Returns:
        Contract version string, or None if no metadata
    """
    metadata = extract_metadata(artifact)
    if metadata:
        return metadata.contract_version
    return None


def get_artifact_type(artifact: dict[str, Any]) -> str | None:
    """Get the artifact type from an artifact.

    Args:
        artifact: The artifact dictionary

    Returns:
        Artifact type string, or None if no metadata
    """
    metadata = extract_metadata(artifact)
    if metadata:
        return metadata.artifact_type
    return None


def has_metadata(artifact: dict[str, Any]) -> bool:
    """Check if an artifact has contract metadata.

    Args:
        artifact: The artifact dictionary

    Returns:
        True if _contract field exists and is valid
    """
    return extract_metadata(artifact) is not None


def ensure_metadata(
    artifact: dict[str, Any],
    artifact_type: str,
    contract_version: str,
    engine_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Ensure an artifact has contract metadata, adding it if missing.

    Args:
        artifact: The artifact dictionary
        artifact_type: Type of artifact
        contract_version: Contract version
        engine_versions: Engine versions used

    Returns:
        Artifact with metadata (adds if missing, preserves if present)
    """
    if has_metadata(artifact):
        return artifact

    metadata = create_metadata(
        artifact_type=artifact_type,
        contract_version=contract_version,
        engine_versions=engine_versions,
    )
    return inject_metadata(artifact, metadata)
