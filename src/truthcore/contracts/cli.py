"""CLI commands for contract management.

Provides commands for:
- Listing contracts
- Validating artifacts
- Migrating artifacts
- Converting to compat versions
- Comparing contracts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from truthcore.contracts.compat import (
    CompatError,
    convert_directory,
)
from truthcore.contracts.metadata import extract_metadata
from truthcore.contracts.registry import get_registry
from truthcore.contracts.validate import ValidationError, validate_artifact
from truthcore.migrations.engine import get_migration_info, list_available_migrations, migrate


@click.group(name="contracts", help="Contract and schema management commands")
def contracts_cli():
    """Contract management CLI group."""
    pass


@contracts_cli.command(name="list", help="List all registered contracts and versions")
def list_contracts():
    """List all artifact types and their versions."""
    registry = get_registry()

    click.echo("Registered Contracts:")
    click.echo("=" * 60)

    for artifact_type in registry.list_artifact_types():
        registration = registry.get(artifact_type)
        click.echo(f"\n{artifact_type}")
        click.echo(f"  Description: {registration.description}")
        click.echo(f"  Current: {registration.current_version}")
        click.echo(f"  Supported: {', '.join(str(v) for v in registration.supported_versions)}")
        click.echo(f"  All versions: {', '.join(registration.list_versions())}")


@contracts_cli.command(name="validate", help="Validate an artifact against its schema")
@click.option("--file", "file_path", type=click.Path(exists=True), help="Path to artifact file")
@click.option(
    "--inputs", "inputs_dir",
    type=click.Path(exists=True, file_okay=False),
    help="Directory with artifacts to validate",
)
@click.option("--strict", is_flag=True, help="Fail on additional properties not in schema")
@click.option("--artifact-type", help="Artifact type (inferred from metadata if not provided)")
@click.option("--version", help="Contract version (inferred from metadata if not provided)")
def validate_contract(
    file_path: str | None,
    inputs_dir: str | None,
    strict: bool,
    artifact_type: str | None,
    version: str | None,
):
    """Validate one or more artifacts."""
    if file_path:
        # Validate single file
        try:
            with open(file_path, encoding="utf-8") as f:
                artifact = json.load(f)

            errors = validate_artifact(artifact, artifact_type, version, strict)

            if errors:
                click.echo(f"Validation failed for {file_path}:", err=True)
                for error in errors:
                    click.echo(f"  - {error}", err=True)
                sys.exit(1)
            else:
                # Show metadata
                metadata = extract_metadata(artifact)
                if metadata:
                    click.echo(f"Valid: {file_path}")
                    click.echo(f"  Type: {metadata.artifact_type}")
                    click.echo(f"  Version: {metadata.contract_version}")
                else:
                    click.echo(f"Valid (no metadata): {file_path}")

        except ValidationError as e:
            click.echo(f"Validation error: {e}", err=True)
            sys.exit(1)
        except json.JSONDecodeError as e:
            click.echo(f"Invalid JSON: {e}", err=True)
            sys.exit(1)

    elif inputs_dir:
        # Validate all files in directory
        input_path = Path(inputs_dir)
        all_valid = True

        for json_file in input_path.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    artifact = json.load(f)

                errors = validate_artifact(artifact, artifact_type, version, strict)

                if errors:
                    click.echo(f"Invalid: {json_file.name}", err=True)
                    for error in errors:
                        click.echo(f"  - {error}", err=True)
                    all_valid = False
                else:
                    click.echo(f"Valid: {json_file.name}")

            except Exception as e:
                click.echo(f"Error validating {json_file.name}: {e}", err=True)
                all_valid = False

        if not all_valid:
            sys.exit(1)
    else:
        click.echo("Error: Provide --file or --inputs", err=True)
        sys.exit(1)


@contracts_cli.command(name="migrate", help="Migrate an artifact to a different version")
@click.option("--file", "file_path", type=click.Path(exists=True), required=True, help="Path to artifact file")
@click.option("--to", "target_version", required=True, help="Target contract version")
@click.option("--out", "output_path", type=click.Path(), required=True, help="Output file path")
@click.option("--validate/--no-validate", default=True, help="Validate output after migration")
def migrate_contract(
    file_path: str,
    target_version: str,
    output_path: str,
    validate: bool,
):
    """Migrate an artifact to a target contract version."""
    try:
        with open(file_path, encoding="utf-8") as f:
            artifact = json.load(f)

        # Extract current metadata
        metadata = extract_metadata(artifact)
        if metadata is None:
            click.echo("Error: Artifact has no contract metadata", err=True)
            sys.exit(1)

        click.echo(f"Migrating {metadata.artifact_type} from {metadata.contract_version} to {target_version}...")

        # Perform migration
        result = migrate(artifact, metadata.contract_version, target_version)

        # Validate if requested
        if validate:
            errors = validate_artifact(result, metadata.artifact_type, target_version)
            if errors:
                click.echo("Validation failed after migration:", err=True)
                for error in errors:
                    click.echo(f"  - {error}", err=True)
                sys.exit(1)

        # Write output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        click.echo(f"Migrated artifact written to: {output_path}")

    except Exception as e:
        click.echo(f"Migration failed: {e}", err=True)
        sys.exit(1)


@contracts_cli.command(name="compat", help="Convert artifacts to a target version (batch)")
@click.option(
    "--inputs", "input_dir",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Input directory",
)
@click.option("--target-version", required=True, help="Target contract version")
@click.option("--out", "output_dir", type=click.Path(), required=True, help="Output directory")
@click.option("--artifact-type", multiple=True, help="Filter by artifact type (can be used multiple times)")
@click.option("--validate/--no-validate", default=True, help="Validate outputs")
def compat_contract(
    input_dir: str,
    target_version: str,
    output_dir: str,
    artifact_type: tuple[str, ...],
    validate: bool,
):
    """Convert all artifacts in a directory to a target version."""
    try:
        click.echo(f"Converting artifacts from {input_dir} to version {target_version}...")

        artifact_types = list(artifact_type) if artifact_type else None

        results = convert_directory(
            input_dir,
            output_dir,
            target_version,
            artifact_types,
            validate,
        )

        click.echo("\nResults:")
        click.echo(f"  Converted: {results['converted']}")
        click.echo(f"  Skipped: {results['skipped']}")
        click.echo(f"  Failed: {results['failed']}")

        if results['errors']:
            click.echo("\nErrors:")
            for error in results['errors']:
                click.echo(f"  - {error}")

        if results['failed'] > 0:
            sys.exit(1)

    except CompatError as e:
        click.echo(f"Compat conversion failed: {e}", err=True)
        sys.exit(1)


@contracts_cli.command(name="diff", help="Compare two contract versions")
@click.option("--old", "old_file", type=click.Path(exists=True), required=True, help="Old artifact file")
@click.option("--new", "new_file", type=click.Path(exists=True), required=True, help="New artifact file")
def diff_contracts(old_file: str, new_file: str):
    """Compare two artifacts and show differences."""
    try:
        with open(old_file, encoding="utf-8") as f:
            old_artifact = json.load(f)
        with open(new_file, encoding="utf-8") as f:
            new_artifact = json.load(f)

        old_meta = extract_metadata(old_artifact)
        new_meta = extract_metadata(new_artifact)

        if old_meta and new_meta:
            click.echo(f"Comparing {old_meta.artifact_type} contracts:")
            click.echo(f"  Old: {old_meta.contract_version}")
            click.echo(f"  New: {new_meta.contract_version}")

        # Get migration info
        if old_meta and new_meta and old_meta.artifact_type == new_meta.artifact_type:
            info = get_migration_info(
                old_meta.artifact_type,
                old_meta.contract_version,
                new_meta.contract_version,
            )

            if info.get("possible"):
                click.echo("\nMigration path:")
                click.echo(f"  Steps: {info['steps']}")
                click.echo(f"  Breaking: {'Yes' if info['breaking'] else 'No'}")

                if info.get("migrations"):
                    click.echo("\nMigration steps:")
                    for m in info["migrations"]:
                        click.echo(f"  {m['from']} -> {m['to']}: {m['description']}")
                        if m['breaking']:
                            click.echo("    [BREAKING]")
            else:
                click.echo(f"\nNo migration path available: {info.get('error')}")

        # Show field differences
        old_fields = set(old_artifact.keys())
        new_fields = set(new_artifact.keys())

        added = new_fields - old_fields
        removed = old_fields - new_fields

        if added:
            click.echo(f"\nFields added: {', '.join(added)}")
        if removed:
            click.echo(f"Fields removed: {', '.join(removed)}")

        if not added and not removed:
            click.echo("\nNo field differences detected")

    except Exception as e:
        click.echo(f"Comparison failed: {e}", err=True)
        sys.exit(1)


@contracts_cli.command(name="migrations", help="List available migrations for an artifact type")
@click.option("--artifact-type", required=True, help="Artifact type")
def list_migrations(artifact_type: str):
    """List all available migrations for an artifact type."""
    try:
        migrations = list_available_migrations(artifact_type)

        if not migrations:
            click.echo(f"No migrations registered for {artifact_type}")
            return

        click.echo(f"Available migrations for {artifact_type}:")
        click.echo("=" * 60)

        for m in migrations:
            breaking_marker = " [BREAKING]" if m['breaking'] else ""
            click.echo(f"\n{m['from']} -> {m['to']}{breaking_marker}")
            click.echo(f"  {m['description']}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
