"""Migration engine for truth-core artifacts.

This module provides the migration infrastructure for converting artifacts
between contract versions.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from truthcore.contracts.metadata import update_metadata
from truthcore.contracts.registry import ContractVersion


# Type alias for migration functions
MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class Migration:
    """Represents a single migration between versions."""
    
    artifact_type: str
    from_version: str
    to_version: str
    fn: MigrationFn
    description: str
    breaking: bool = False


class MigrationNotFoundError(Exception):
    """Error raised when a migration cannot be found."""
    pass


class MigrationCycleError(Exception):
    """Error raised when a migration cycle is detected."""
    pass


class MigrationRegistry:
    """Registry for all migrations."""
    
    def __init__(self):
        self._migrations: dict[str, dict[tuple[str, str], Migration]] = {}
    
    def register(self, migration: Migration) -> None:
        """Register a migration."""
        artifact_type = migration.artifact_type
        if artifact_type not in self._migrations:
            self._migrations[artifact_type] = {}
        
        key = (migration.from_version, migration.to_version)
        self._migrations[artifact_type][key] = migration
    
    def get(
        self,
        artifact_type: str,
        from_version: str,
        to_version: str,
    ) -> Migration | None:
        """Get a specific migration."""
        if artifact_type not in self._migrations:
            return None
        
        key = (from_version, to_version)
        return self._migrations[artifact_type].get(key)
    
    def list_migrations(self, artifact_type: str) -> list[Migration]:
        """List all migrations for an artifact type."""
        if artifact_type not in self._migrations:
            return []
        return list(self._migrations[artifact_type].values())
    
    def list_versions(self, artifact_type: str) -> list[str]:
        """List all versions reachable via migrations for an artifact type."""
        migrations = self.list_migrations(artifact_type)
        versions: set[str] = set()
        for m in migrations:
            versions.add(m.from_version)
            versions.add(m.to_version)
        return sorted(versions)


# Global registry
_migration_registry = MigrationRegistry()


def register_migration(
    artifact_type: str,
    from_version: str,
    to_version: str,
    fn: MigrationFn,
    description: str = "",
    breaking: bool = False,
) -> None:
    """Register a migration function.
    
    Args:
        artifact_type: Type of artifact this migration applies to
        from_version: Source version (e.g., "1.0.0")
        to_version: Target version (e.g., "2.0.0")
        fn: Migration function that takes and returns an artifact dict
        description: Human-readable description of the migration
        breaking: Whether this is a breaking change
    """
    migration = Migration(
        artifact_type=artifact_type,
        from_version=from_version,
        to_version=to_version,
        fn=fn,
        description=description,
        breaking=breaking,
    )
    _migration_registry.register(migration)


def _parse_version(version: str) -> ContractVersion:
    """Parse a version string."""
    return ContractVersion.parse(version)


def find_migration_chain(
    artifact_type: str,
    from_version: str,
    to_version: str,
) -> list[Migration]:
    """Find a chain of migrations from one version to another.
    
    Uses BFS to find shortest path.
    
    Args:
        artifact_type: Type of artifact
        from_version: Starting version
        to_version: Target version
    
    Returns:
        List of migrations to apply in order
    
    Raises:
        MigrationNotFoundError: If no path exists
    """
    from_version_parsed = _parse_version(from_version)
    to_version_parsed = _parse_version(to_version)
    
    # Determine direction
    ascending = to_version_parsed > from_version_parsed
    
    # BFS
    visited: set[str] = set()
    queue: list[tuple[str, list[Migration]]] = [(from_version, [])]
    
    while queue:
        current, path = queue.pop(0)
        
        if current == to_version:
            return path
        
        if current in visited:
            continue
        visited.add(current)
        
        # Find next possible migrations
        migrations = _migration_registry.list_migrations(artifact_type)
        for migration in migrations:
            if ascending:
                if migration.from_version == current:
                    queue.append((migration.to_version, path + [migration]))
            else:
                if migration.to_version == current:
                    queue.append((migration.from_version, path + [migration]))
    
    raise MigrationNotFoundError(
        f"No migration path from {from_version} to {to_version} for {artifact_type}"
    )


def migrate(
    artifact: dict[str, Any],
    from_version: str,
    to_version: str,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    """Migrate an artifact from one version to another.
    
    Args:
        artifact: The artifact to migrate
        from_version: Current version of the artifact
        to_version: Target version
        artifact_type: Artifact type (inferred from metadata if not provided)
    
    Returns:
        Migrated artifact
    
    Raises:
        MigrationNotFoundError: If no migration path exists
    """
    # Extract artifact type if not provided
    if artifact_type is None:
        from truthcore.contracts.metadata import extract_metadata
        metadata = extract_metadata(artifact)
        if metadata:
            artifact_type = metadata.artifact_type
        else:
            raise ValueError("artifact_type required when artifact has no metadata")
    
    # If already at target version, return copy
    if from_version == to_version:
        return copy.deepcopy(artifact)
    
    # Find migration chain
    chain = find_migration_chain(artifact_type, from_version, to_version)
    
    # Apply migrations
    result = copy.deepcopy(artifact)
    for migration in chain:
        result = migration.fn(result)
    
    # Update metadata
    result = update_metadata(result, contract_version=to_version)
    
    return result


def get_migration_info(
    artifact_type: str,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    """Get information about a migration path.
    
    Args:
        artifact_type: Type of artifact
        from_version: Starting version
        to_version: Target version
    
    Returns:
        Dict with migration information
    """
    try:
        chain = _find_migration_chain(artifact_type, from_version, to_version)
        return {
            "possible": True,
            "steps": len(chain),
            "breaking": any(m.breaking for m in chain),
            "migrations": [
                {
                    "from": m.from_version,
                    "to": m.to_version,
                    "description": m.description,
                    "breaking": m.breaking,
                }
                for m in chain
            ],
        }
    except MigrationNotFoundError as e:
        return {
            "possible": False,
            "error": str(e),
        }


def list_available_migrations(artifact_type: str) -> list[dict[str, Any]]:
    """List all available migrations for an artifact type.
    
    Args:
        artifact_type: Type of artifact
    
    Returns:
        List of migration information dicts
    """
    migrations = _migration_registry.list_migrations(artifact_type)
    return [
        {
            "from": m.from_version,
            "to": m.to_version,
            "description": m.description,
            "breaking": m.breaking,
        }
        for m in migrations
    ]
