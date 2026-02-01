"""Contracts module for truth-core.

This module provides contract versioning, validation, and migration support.
"""

from truthcore.contracts.metadata import (
    ContractMetadata,
    create_metadata,
    ensure_metadata,
    extract_metadata,
    has_metadata,
    inject_metadata,
)
from truthcore.contracts.registry import (
    ContractRegistry,
    ContractVersion,
    SchemaRef,
    get_registry,
)
from truthcore.contracts.validate import (
    ValidationError,
    validate_artifact,
    validate_artifact_or_raise,
    validate_file,
)

__all__ = [
    "ContractMetadata",
    "ContractRegistry",
    "ContractVersion",
    "SchemaRef",
    "ValidationError",
    "create_metadata",
    "ensure_metadata",
    "extract_metadata",
    "get_registry",
    "has_metadata",
    "inject_metadata",
    "validate_artifact",
    "validate_artifact_or_raise",
    "validate_file",
]
