"""Migrations module for truth-core.

This module provides artifact migration between contract versions.
"""

# Import migration definitions to register them
from truthcore.migrations import verdict
from truthcore.migrations.engine import (
    Migration,
    MigrationNotFoundError,
    find_migration_chain,
    get_migration_info,
    list_available_migrations,
    migrate,
    register_migration,
)

__all__ = [
    "Migration",
    "MigrationNotFoundError",
    "find_migration_chain",
    "get_migration_info",
    "list_available_migrations",
    "migrate",
    "register_migration",
]
