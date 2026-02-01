"""Compatibility mode for truth-core artifacts.

This module provides utilities for converting artifacts to different
contract versions for backward compatibility.
"""

from __future__ import annotations

import copy
from typing import Any

from truthcore.contracts.metadata import (
    create_metadata,
    extract_metadata,
    inject_metadata,
    update_metadata,
)
from truthcore.contracts.registry import get_registry
from truthcore.contracts.validate import ValidationError, validate_artifact_or_raise
from truthcore.migrations.engine import MigrationNotFoundError, find_migration_chain, migrate


class CompatError(Exception):
    """Error raised when compatibility conversion fails."""
    pass


class BreakingChangeError(CompatError):
    """Error raised when requested compat version requires breaking changes."""
    pass


class UnsupportedVersionError(CompatError):
    """Error raised when requested version is not supported."""
    pass


def check_compat_possible(
    artifact: dict[str, Any],
    target_version: str,
) -> tuple[bool, str]:
    """Check if compatibility conversion is possible.
    
    Args:
        artifact: The artifact to convert
        target_version: Target contract version
    
    Returns:
        Tuple of (is_possible, reason)
    """
    # Extract current version
    metadata = extract_metadata(artifact)
    if metadata is None:
        return False, "Artifact has no contract metadata"
    
    current_version = metadata.contract_version
    artifact_type = metadata.artifact_type
    
    # Check if versions are the same
    if current_version == target_version:
        return True, "Already at target version"
    
    # Check if target version is supported
    registry = get_registry()
    if not registry.is_supported(artifact_type, target_version):
        return False, f"Version {target_version} is not supported for {artifact_type}"
    
    # Check if migration exists
    try:
        # Try to find migration path
        find_migration_chain(artifact_type, current_version, target_version)
        return True, "Migration path found"
    except MigrationNotFoundError as e:
        return False, str(e)


def convert_to_version(
    artifact: dict[str, Any],
    target_version: str,
    validate: bool = True,
) -> dict[str, Any]:
    """Convert an artifact to a specific contract version.
    
    Args:
        artifact: The artifact to convert
        target_version: Target contract version
        validate: If True, validate output against target schema
    
    Returns:
        Converted artifact
    
    Raises:
        CompatError: If conversion fails
        BreakingChangeError: If conversion requires breaking changes
        UnsupportedVersionError: If target version is not supported
    """
    # Extract metadata
    metadata = extract_metadata(artifact)
    if metadata is None:
        raise CompatError("Artifact has no contract metadata")
    
    current_version = metadata.contract_version
    artifact_type = metadata.artifact_type
    
    # If already at target version, return copy
    if current_version == target_version:
        return copy.deepcopy(artifact)
    
    # Check if target version is supported
    registry = get_registry()
    if not registry.is_supported(artifact_type, target_version):
        raise UnsupportedVersionError(
            f"Version {target_version} is not supported for {artifact_type}. "
            f"Supported versions: {registry.get_supported_versions(artifact_type)}"
        )
    
    # Check if migration is possible
    possible, reason = check_compat_possible(artifact, target_version)
    if not possible:
        raise BreakingChangeError(
            f"Cannot convert to version {target_version}: {reason}. "
            "This may require consumer code updates. "
            "Consider using the latest contract version or upgrading your consumer code."
        )
    
    # Perform migration
    try:
        result = migrate(artifact, current_version, target_version)
    except MigrationNotFoundError as e:
        raise BreakingChangeError(
            f"No migration path from {current_version} to {target_version}: {e}"
        )
    
    # Update metadata to reflect new version
    result = update_metadata(result, contract_version=target_version)
    
    # Validate if requested
    if validate:
        try:
            validate_artifact_or_raise(result, artifact_type, target_version)
        except ValidationError as e:
            raise CompatError(
                f"Converted artifact failed validation: {e}"
            )
    
    return result


def convert_directory(
    input_dir: str,
    output_dir: str,
    target_version: str,
    artifact_types: list[str] | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Convert all artifacts in a directory to a target version.
    
    Args:
        input_dir: Input directory containing artifacts
        output_dir: Output directory for converted artifacts
        target_version: Target contract version
        artifact_types: If provided, only convert these artifact types
        validate: If True, validate outputs
    
    Returns:
        Summary dict with conversion results
    """
    import json
    from pathlib import Path
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {
        "converted": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }
    
    # Find all JSON files
    for json_file in input_path.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                artifact = json.load(f)
            
            # Check if this is an artifact with metadata
            metadata = extract_metadata(artifact)
            if metadata is None:
                results["skipped"] += 1
                continue
            
            # Filter by artifact type if specified
            if artifact_types and metadata.artifact_type not in artifact_types:
                results["skipped"] += 1
                continue
            
            # Check if already at target version
            if metadata.contract_version == target_version:
                # Just copy file
                with open(output_path / json_file.name, "w", encoding="utf-8") as f:
                    json.dump(artifact, f, indent=2)
                results["skipped"] += 1
                continue
            
            # Convert
            converted = convert_to_version(artifact, target_version, validate)
            
            # Write output
            with open(output_path / json_file.name, "w", encoding="utf-8") as f:
                json.dump(converted, f, indent=2)
            
            results["converted"] += 1
            
        except CompatError as e:
            results["failed"] += 1
            results["errors"].append(f"{json_file.name}: {e}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{json_file.name}: {type(e).__name__}: {e}")
    
    return results


def get_compat_versions(artifact_type: str) -> list[str]:
    """Get list of versions available for compat mode.
    
    Args:
        artifact_type: The artifact type
    
    Returns:
        List of supported version strings
    """
    registry = get_registry()
    try:
        return registry.get_supported_versions(artifact_type)
    except ValueError:
        return []


def add_contract_metadata_if_missing(
    artifact: dict[str, Any],
    artifact_type: str,
    contract_version: str,
    engine_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Add contract metadata to an artifact if it doesn't have any.
    
    This is useful for migrating legacy (unversioned) artifacts.
    
    Args:
        artifact: The artifact
        artifact_type: Artifact type
        contract_version: Contract version (typically "0.0.0" for legacy)
        engine_versions: Engine versions
    
    Returns:
        Artifact with metadata added
    """
    metadata = extract_metadata(artifact)
    if metadata is not None:
        return copy.deepcopy(artifact)
    
    new_metadata = create_metadata(
        artifact_type=artifact_type,
        contract_version=contract_version,
        engine_versions=engine_versions,
    )
    return inject_metadata(artifact, new_metadata)
