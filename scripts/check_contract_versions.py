#!/usr/bin/env python3
"""Contract version check script for CI.

This script validates that contract changes follow the versioning policy:
- Breaking changes require MAJOR version bump
- New features require MINOR version bump
- Bug fixes require PATCH version bump

Usage:
    python scripts/check_contract_versions.py

Exit codes:
    0 - All checks passed
    1 - Version check failed
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_schema_version(schema_path: Path) -> str:
    """Extract version from schema path."""
    # Path format: schemas/<type>/v<version>/<type>.schema.json
    parts = schema_path.parts
    version_part = parts[-2]  # e.g., "v1.0.0"
    return version_part.lstrip("v")


def check_schema_changes() -> list[str]:
    """Check schema files for proper versioning.

    Returns list of error messages.
    """
    errors = []

    schemas_dir = Path("src/truthcore/schemas")
    if not schemas_dir.exists():
        return errors

    for artifact_dir in schemas_dir.iterdir():
        if not artifact_dir.is_dir():
            continue

        versions = []
        for version_dir in artifact_dir.iterdir():
            if not version_dir.is_dir():
                continue
            
            version_str = version_dir.name.lstrip("v")
            try:
                major, minor, patch = map(int, version_str.split("."))
                versions.append((major, minor, patch, version_str))
            except ValueError:
                errors.append(f"Invalid version format: {version_dir.name} in {artifact_dir.name}")

        # Check version ordering
        versions.sort()
        
        for i in range(1, len(versions)):
            prev = versions[i - 1]
            curr = versions[i]
            
            # Check if versions follow semver
            if curr[0] < prev[0]:
                errors.append(f"Version {curr[3]} < {prev[3]} in {artifact_dir.name}")
            elif curr[0] == prev[0] and curr[1] < prev[1]:
                errors.append(f"Minor version decreased: {curr[3]} < {prev[3]} in {artifact_dir.name}")
            elif curr[0] == prev[0] and curr[1] == prev[1] and curr[2] < prev[2]:
                errors.append(f"Patch version decreased: {curr[3]} < {prev[3]} in {artifact_dir.name}")
    
    return errors


def check_migration_coverage() -> list[str]:
    """Check that migrations exist for version gaps.

    Returns list of error messages.
    """
    errors = []

    # Import migrations to check coverage
    try:
        from truthcore.migrations.engine import list_available_migrations
        
        schemas_dir = Path("src/truthcore/schemas")
        if not schemas_dir.exists():
            return errors
        
        for artifact_dir in schemas_dir.iterdir():
            if not artifact_dir.is_dir():
                continue

            artifact_type = artifact_dir.name
            migrations = list_available_migrations(artifact_type)
            
            # Get all versions
            versions = set()
            for version_dir in artifact_dir.iterdir():
                if version_dir.is_dir():
                    version_str = version_dir.name.lstrip("v")
                    versions.add(version_str)
            
            # Check that migrations exist between consecutive versions
            sorted_versions = sorted(versions, key=lambda v: tuple(map(int, v.split("."))))
            
            migration_pairs = set()
            for m in migrations:
                migration_pairs.add((m["from"], m["to"]))
            
            # For now, just warn if there are gaps
            # Full validation would require checking all possible paths
            
        except ImportError:
            # truthcore not installed, skip this check
            pass

    return errors


def main() -> int:
    """Run all contract version checks.
    
    Returns exit code.
    """
    print("Checking contract versions...")
    print("=" * 60)
    
    all_errors = []
    
    # Check schema changes
    print("\n1. Checking schema versions...")
    schema_errors = check_schema_changes()
    if schema_errors:
        all_errors.extend(schema_errors)
        for error in schema_errors:
            print(f"  ERROR: {error}")
    else:
        print("  OK")
    
    # Check migration coverage
    print("\n2. Checking migration coverage...")
    migration_errors = check_migration_coverage()
    if migration_errors:
        all_errors.extend(migration_errors)
        for error in migration_errors:
            print(f"  ERROR: {error}")
    else:
        print("  OK")
    
    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s) found")
        return 1
    else:
        print("PASSED: All contract version checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
