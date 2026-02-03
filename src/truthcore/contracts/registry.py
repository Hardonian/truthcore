"""Contract registry for truth-core artifact versioning.

This module provides the central registry for artifact types, versions,
schemas, and migration paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContractVersion:
    """Represents a specific contract version."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: ContractVersion) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: ContractVersion) -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: ContractVersion) -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: ContractVersion) -> bool:
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    @classmethod
    def parse(cls, version: str) -> ContractVersion:
        """Parse a version string into a ContractVersion."""
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}. Expected MAJOR.MINOR.PATCH")
        return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))

    def is_compatible_with(self, other: ContractVersion) -> bool:
        """Check if this version is backward compatible with another.

        Returns True if self can be used where other is expected.
        """
        # Same major version and self is >= other
        return self.major == other.major and self >= other

    def bump_major(self) -> ContractVersion:
        """Return a new version with bumped major."""
        return ContractVersion(major=self.major + 1, minor=0, patch=0)

    def bump_minor(self) -> ContractVersion:
        """Return a new version with bumped minor."""
        return ContractVersion(major=self.major, minor=self.minor + 1, patch=0)

    def bump_patch(self) -> ContractVersion:
        """Return a new version with bumped patch."""
        return ContractVersion(major=self.major, minor=self.minor, patch=self.patch + 1)


@dataclass(frozen=True)
class SchemaRef:
    """Reference to a schema file."""

    artifact_type: str
    version: ContractVersion
    path: Path

    def load(self) -> dict[str, Any]:
        """Load and return the schema as a dictionary."""
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)


@dataclass
class ArtifactTypeRegistration:
    """Registration for an artifact type."""

    artifact_type: str
    versions: dict[str, SchemaRef]
    description: str
    current_version: ContractVersion
    supported_versions: list[ContractVersion]

    def get_schema(self, version: str | ContractVersion) -> SchemaRef:
        """Get schema reference for a specific version."""
        if isinstance(version, ContractVersion):
            version = str(version)
        if version not in self.versions:
            raise ValueError(f"Unknown version {version} for {self.artifact_type}")
        return self.versions[version]

    def list_versions(self) -> list[str]:
        """List all registered versions."""
        return sorted(self.versions.keys())


class ContractRegistry:
    """Central registry for all truth-core contracts."""

    def __init__(self, schemas_dir: Path | None = None):
        self._registry: dict[str, ArtifactTypeRegistration] = {}
        self._legacy_mappings: dict[str, tuple[str, str]] = {}

        if schemas_dir is None:
            # Default to package schemas directory
            package_dir = Path(__file__).parent.parent
            schemas_dir = package_dir / "schemas"

        self.schemas_dir = schemas_dir
        self._load_schemas()

    def _load_schemas(self) -> None:
        """Load all schemas from the schemas directory."""
        if not self.schemas_dir.exists():
            return

        for artifact_dir in self.schemas_dir.iterdir():
            if not artifact_dir.is_dir():
                continue

            artifact_type = artifact_dir.name
            versions: dict[str, SchemaRef] = {}
            version_list: list[ContractVersion] = []

            for version_dir in artifact_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                version_str = version_dir.name.lstrip("v")
                try:
                    version = ContractVersion.parse(version_str)
                except ValueError:
                    continue

                # Find schema file
                schema_file = version_dir / f"{artifact_type}.schema.json"
                if not schema_file.exists():
                    # Try alternative naming
                    schema_file = version_dir / "schema.json"

                if schema_file.exists():
                    schema_ref = SchemaRef(
                        artifact_type=artifact_type,
                        version=version,
                        path=schema_file
                    )
                    versions[version_str] = schema_ref
                    version_list.append(version)

            if versions:
                # Sort versions to determine current
                version_list.sort()
                current = version_list[-1]

                # Determine supported versions (last 2 major)
                supported_majors = sorted(set(v.major for v in version_list))[-2:]
                supported = [v for v in version_list if v.major in supported_majors]

                registration = ArtifactTypeRegistration(
                    artifact_type=artifact_type,
                    versions=versions,
                    description=self._get_description(artifact_type),
                    current_version=current,
                    supported_versions=supported
                )
                self._registry[artifact_type] = registration

                # Register legacy mapping
                self._legacy_mappings[f"schemas/{artifact_type}.schema.json"] = (
                    artifact_type, str(current)
                )

    def _get_description(self, artifact_type: str) -> str:
        """Get description for an artifact type."""
        descriptions = {
            "verdict": "Aggregated judgment from multiple engines",
            "readiness": "Readiness check results",
            "invariants": "Invariant rule evaluations",
            "policy_findings": "Policy-as-code scan results",
            "provenance_manifest": "Signed provenance manifest",
            "agent_trace_report": "Agent trace analysis report",
            "reconciliation_table": "Reconciliation truth table",
            "knowledge_index": "Knowledge graph index",
            "intel_scorecard": "Intelligence analysis scorecard",
        }
        return descriptions.get(artifact_type, f"{artifact_type} artifact")

    def register(self, registration: ArtifactTypeRegistration) -> None:
        """Register an artifact type."""
        self._registry[registration.artifact_type] = registration

    def get(self, artifact_type: str) -> ArtifactTypeRegistration:
        """Get registration for an artifact type."""
        if artifact_type not in self._registry:
            raise ValueError(f"Unknown artifact type: {artifact_type}")
        return self._registry[artifact_type]

    def list_artifact_types(self) -> list[str]:
        """List all registered artifact types."""
        return sorted(self._registry.keys())

    def get_schema(self, artifact_type: str, version: str | None = None) -> SchemaRef:
        """Get schema for an artifact type and version.

        If version is None, returns the current version.
        """
        registration = self.get(artifact_type)
        if version is None:
            version = str(registration.current_version)
        return registration.get_schema(version)

    def resolve_legacy_path(self, path: str) -> tuple[str, str]:
        """Resolve a legacy schema path to (artifact_type, version)."""
        if path in self._legacy_mappings:
            return self._legacy_mappings[path]
        raise ValueError(f"Unknown legacy path: {path}")

    def is_supported(self, artifact_type: str, version: str) -> bool:
        """Check if a version is supported for an artifact type."""
        try:
            registration = self.get(artifact_type)
            ver = ContractVersion.parse(version)
            return ver in registration.supported_versions
        except (ValueError, KeyError):
            return False

    def get_supported_versions(self, artifact_type: str) -> list[str]:
        """Get list of supported versions for an artifact type."""
        registration = self.get(artifact_type)
        return [str(v) for v in registration.supported_versions]


# Global registry instance
_registry: ContractRegistry | None = None


def get_registry() -> ContractRegistry:
    """Get the global contract registry."""
    global _registry
    if _registry is None:
        _registry = ContractRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None
