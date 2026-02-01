"""Tests for contract versioning system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from truthcore.contracts import (
    create_metadata,
    ensure_metadata,
    extract_metadata,
    get_registry,
    has_metadata,
    inject_metadata,
    validate_artifact,
    validate_artifact_or_raise,
)
from truthcore.contracts.compat import (
    check_compat_possible,
    convert_to_version,
)
from truthcore.contracts.validate import (
    ValidationError,
)
from truthcore.migrations.engine import migrate


class TestContractMetadata:
    """Test contract metadata functionality."""

    def test_create_metadata(self):
        """Test creating contract metadata."""
        metadata = create_metadata(
            artifact_type="verdict",
            contract_version="2.0.0",
            engine_versions={"readiness": "1.0.0"},
        )

        assert metadata.artifact_type == "verdict"
        assert metadata.contract_version == "2.0.0"
        assert metadata.engine_versions == {"readiness": "1.0.0"}
        assert metadata.schema == "schemas/verdict/v2.0.0/verdict.schema.json"

    def test_inject_and_extract_metadata(self):
        """Test injecting and extracting metadata from artifacts."""
        artifact = {"verdict": "PASS", "value": 95.0}
        metadata = create_metadata(
            artifact_type="verdict",
            contract_version="2.0.0",
        )

        # Inject metadata
        with_metadata = inject_metadata(artifact, metadata)

        # Verify structure
        assert "_contract" in with_metadata
        assert with_metadata["verdict"] == "PASS"

        # Extract metadata
        extracted = extract_metadata(with_metadata)
        assert extracted is not None
        assert extracted.artifact_type == "verdict"
        assert extracted.contract_version == "2.0.0"

    def test_has_metadata(self):
        """Test checking if artifact has metadata."""
        artifact_without = {"verdict": "PASS"}
        assert not has_metadata(artifact_without)

        artifact_with = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
        }
        assert has_metadata(artifact_with)

    def test_ensure_metadata(self):
        """Test ensuring metadata is present."""
        artifact = {"verdict": "PASS"}

        result = ensure_metadata(
            artifact,
            artifact_type="verdict",
            contract_version="1.0.0",
        )

        assert has_metadata(result)
        extracted = extract_metadata(result)
        assert extracted.artifact_type == "verdict"


class TestContractRegistry:
    """Test contract registry."""

    def test_get_registry(self):
        """Test getting the global registry."""
        registry = get_registry()
        assert registry is not None

        # Should return same instance
        registry2 = get_registry()
        assert registry is registry2

    def test_list_artifact_types(self):
        """Test listing registered artifact types."""
        registry = get_registry()
        types = registry.list_artifact_types()

        # Should have at least verdict and readiness
        assert "verdict" in types
        assert "readiness" in types

    def test_get_schema(self):
        """Test getting schema for an artifact type."""
        registry = get_registry()
        schema_ref = registry.get_schema("verdict", "1.0.0")

        assert schema_ref is not None
        assert schema_ref.artifact_type == "verdict"

        # Should be able to load the schema
        schema = schema_ref.load()
        assert "properties" in schema

    def test_is_supported(self):
        """Test checking if a version is supported."""
        registry = get_registry()

        # Verdict 1.0.0 should be supported
        assert registry.is_supported("verdict", "1.0.0")

        # Verdict 2.0.0 should be supported
        assert registry.is_supported("verdict", "2.0.0")

        # Unknown version should not be supported
        assert not registry.is_supported("verdict", "99.0.0")


class TestContractValidation:
    """Test contract validation."""

    def test_validate_valid_artifact(self):
        """Test validating a valid artifact."""
        artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [],
        }

        errors = validate_artifact(artifact)
        assert len(errors) == 0

    def test_validate_invalid_artifact(self):
        """Test validating an invalid artifact."""
        artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            # Missing required fields
        }

        errors = validate_artifact(artifact)
        assert len(errors) > 0

    def test_validate_artifact_or_raise(self):
        """Test validation that raises on error."""
        artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [],
        }

        # Should not raise
        validate_artifact_or_raise(artifact)

        # Invalid artifact should raise
        invalid_artifact = {"_contract": artifact["_contract"]}
        with pytest.raises(ValidationError):
            validate_artifact_or_raise(invalid_artifact)


class TestContractMigrations:
    """Test contract migrations."""

    def test_migrate_v1_to_v2(self):
        """Test migrating verdict from v1 to v2."""
        v1_artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [
                {"id": "1", "severity": "LOW", "message": "Test"}
            ],
        }

        result = migrate(v1_artifact, "1.0.0", "2.0.0")

        # Check version updated
        metadata = extract_metadata(result)
        assert metadata.contract_version == "2.0.0"

        # Check fields migrated
        assert "value" in result  # renamed from score
        assert "items" in result  # renamed from findings
        assert "confidence" in result  # new field
        assert result["value"] == 95.0
        assert result["confidence"] > 0

    def test_migrate_same_version(self):
        """Test migrating to same version returns copy."""
        artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [],
        }

        result = migrate(artifact, "1.0.0", "1.0.0")
        assert result == artifact


class TestContractCompat:
    """Test compatibility mode."""

    def test_check_compat_possible(self):
        """Test checking if compat conversion is possible."""
        v1_artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [],
        }

        possible, reason = check_compat_possible(v1_artifact, "2.0.0")
        assert possible is True
        assert "Migration path found" in reason

    def test_convert_to_version(self):
        """Test converting to a specific version."""
        v1_artifact = {
            "_contract": {
                "artifact_type": "verdict",
                "contract_version": "1.0.0",
                "truthcore_version": "0.2.0",
                "engine_versions": {},
                "created_at": "2026-01-31T00:00:00Z",
                "schema": "schemas/verdict/v1.0.0/verdict.schema.json",
            },
            "verdict": "PASS",
            "score": 95.0,
            "findings": [],
        }

        result = convert_to_version(v1_artifact, "2.0.0")

        metadata = extract_metadata(result)
        assert metadata.contract_version == "2.0.0"

        # Should validate against v2 schema
        errors = validate_artifact(result, "verdict", "2.0.0")
        assert len(errors) == 0


class TestContractFixtures:
    """Test with fixture files."""

    def test_load_and_validate_v1_fixture(self):
        """Test loading and validating v1 fixture."""
        fixture_path = Path("tests/fixtures/contracts/verdict_v1.json")
        if not fixture_path.exists():
            pytest.skip("Fixture not found")

        with open(fixture_path) as f:
            artifact = json.load(f)

        errors = validate_artifact(artifact)
        assert len(errors) == 0

    def test_load_and_validate_v2_fixture(self):
        """Test loading and validating v2 fixture."""
        fixture_path = Path("tests/fixtures/contracts/verdict_v2.json")
        if not fixture_path.exists():
            pytest.skip("Fixture not found")

        with open(fixture_path) as f:
            artifact = json.load(f)

        errors = validate_artifact(artifact)
        assert len(errors) == 0
