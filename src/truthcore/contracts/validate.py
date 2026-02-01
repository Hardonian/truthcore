"""Contract validation for truth-core artifacts.

This module provides validation of artifacts against their declared schemas.
"""

from __future__ import annotations

import json
from typing import Any

from truthcore.contracts.metadata import extract_metadata, has_metadata
from truthcore.contracts.registry import get_registry


class ValidationError(Exception):
    """Error raised when artifact validation fails."""
    
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class SchemaNotFoundError(ValidationError):
    """Error raised when a schema cannot be found."""
    pass


class ContractVersionError(ValidationError):
    """Error raised when contract version is invalid or unsupported."""
    pass


def _validate_type(value: Any, expected_type: str, path: str) -> list[str]:
    """Validate a value against an expected type.
    
    Returns list of error messages.
    """
    errors = []
    
    type_validators = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
        "null": lambda v: v is None,
    }
    
    if expected_type in type_validators:
        if not type_validators[expected_type](value):
            errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
    
    return errors


def _validate_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    """Validate a value against a schema fragment.
    
    Returns list of error messages.
    """
    errors = []
    
    # Check type
    if "type" in schema:
        expected_type = schema["type"]
        if isinstance(expected_type, list):
            # Union type - value must match at least one
            type_matched = any(
                not _validate_type(value, t, path) for t in expected_type
            )
            if not type_matched:
                errors.append(f"{path}: expected one of {expected_type}, got {type(value).__name__}")
        else:
            errors.extend(_validate_type(value, expected_type, path))
    
    # Check enum
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value must be one of {schema['enum']}")
    
    # Check object properties
    if schema.get("type") == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional_properties = schema.get("additionalProperties", True)
        
        # Check required properties
        for prop in required:
            if prop not in value:
                errors.append(f"{path}: missing required property '{prop}'")
        
        # Validate properties
        for prop, prop_value in value.items():
            prop_path = f"{path}.{prop}" if path else prop
            
            if prop in properties:
                errors.extend(_validate_value(prop_value, properties[prop], prop_path))
            elif not additional_properties:
                errors.append(f"{prop_path}: additional property not allowed")
    
    # Check array items
    if schema.get("type") == "array" and isinstance(value, list):
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(value):
                item_path = f"{path}[{i}]"
                errors.extend(_validate_value(item, items_schema, item_path))
        
        # Check minItems/maxItems
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: array must have at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: array must have at most {schema['maxItems']} items")
    
    # Check string constraints
    if schema.get("type") == "string" and isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string must be at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string must be at most {schema['maxLength']} characters")
        if "pattern" in schema:
            import re
            if not re.match(schema["pattern"], value):
                errors.append(f"{path}: string does not match pattern {schema['pattern']}")
    
    # Check numeric constraints
    if schema.get("type") in ("integer", "number") and isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value must be <= {schema['maximum']}")
    
    return errors


def validate_artifact(
    artifact: dict[str, Any],
    artifact_type: str | None = None,
    version: str | None = None,
    strict: bool = False,
) -> list[str]:
    """Validate an artifact against its schema.
    
    Args:
        artifact: The artifact to validate
        artifact_type: Artifact type (inferred from metadata if not provided)
        version: Contract version (inferred from metadata if not provided)
        strict: If True, fail on additional properties not in schema
    
    Returns:
        List of validation error messages (empty if valid)
    
    Raises:
        SchemaNotFoundError: If the schema cannot be found
        ContractVersionError: If contract metadata is missing/invalid
    """
    errors = []
    
    # Extract metadata if available
    if artifact_type is None or version is None:
        metadata = extract_metadata(artifact)
        if metadata is None:
            raise ContractVersionError(
                "Artifact has no contract metadata. "
                "Provide artifact_type and version explicitly, or add metadata."
            )
        
        if artifact_type is None:
            artifact_type = metadata.artifact_type
        if version is None:
            version = metadata.contract_version
    
    # Load schema
    try:
        registry = get_registry()
        schema_ref = registry.get_schema(artifact_type, version)
        schema = schema_ref.load()
    except ValueError as e:
        raise SchemaNotFoundError(f"Schema not found for {artifact_type} v{version}: {e}")
    except FileNotFoundError as e:
        raise SchemaNotFoundError(f"Schema file not found: {e}")
    
    # Validate root type
    if "type" in schema:
        errors.extend(_validate_type(artifact, schema["type"], "<root>"))
    
    # Validate against schema
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required properties (including _contract if present)
        for prop in required:
            if prop not in artifact:
                errors.append(f"<root>: missing required property '{prop}'")
        
        # Validate all properties
        for prop, value in artifact.items():
            if prop in properties:
                prop_schema = properties[prop]
                if strict and prop_schema.get("type") == "object":
                    prop_schema = {**prop_schema, "additionalProperties": False}
                errors.extend(_validate_value(value, prop_schema, prop))
            elif schema.get("additionalProperties") is False:
                errors.append(f"<root>: additional property '{prop}' not allowed")
    
    return errors


def validate_artifact_or_raise(
    artifact: dict[str, Any],
    artifact_type: str | None = None,
    version: str | None = None,
    strict: bool = False,
) -> None:
    """Validate an artifact and raise an exception if invalid.
    
    Args:
        artifact: The artifact to validate
        artifact_type: Artifact type (inferred from metadata if not provided)
        version: Contract version (inferred from metadata if not provided)
        strict: If True, fail on additional properties not in schema
    
    Raises:
        ValidationError: If validation fails
    """
    errors = validate_artifact(artifact, artifact_type, version, strict)
    if errors:
        raise ValidationError(f"Validation failed with {len(errors)} errors", errors)


def is_valid(
    artifact: dict[str, Any],
    artifact_type: str | None = None,
    version: str | None = None,
    strict: bool = False,
) -> bool:
    """Check if an artifact is valid.
    
    Args:
        artifact: The artifact to check
        artifact_type: Artifact type (inferred from metadata if not provided)
        version: Contract version (inferred from metadata if not provided)
        strict: If True, fail on additional properties not in schema
    
    Returns:
        True if valid, False otherwise
    """
    try:
        errors = validate_artifact(artifact, artifact_type, version, strict)
        return len(errors) == 0
    except (ValidationError, SchemaNotFoundError, ContractVersionError):
        return False


def validate_file(
    file_path: str,
    artifact_type: str | None = None,
    version: str | None = None,
    strict: bool = False,
) -> list[str]:
    """Validate an artifact file.
    
    Args:
        file_path: Path to the artifact file
        artifact_type: Artifact type (inferred from metadata if not provided)
        version: Contract version (inferred from metadata if not provided)
        strict: If True, fail on additional properties not in schema
    
    Returns:
        List of validation error messages
    """
    with open(file_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    
    return validate_artifact(artifact, artifact_type, version, strict)
