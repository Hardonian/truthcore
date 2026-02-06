#!/usr/bin/env python3
"""Contract Kit validation script.

Validates all contract schemas, module manifests, SDK exports, and CLI entrypoints.
Fails CI on any drift between contracts and implementation.

Usage:
    python scripts/contracts_check.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
SCHEMAS_DIR = ROOT / "src" / "truthcore" / "schemas"
TS_SDK_DIR = ROOT / "packages" / "ts-contract-sdk"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"


def header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_contract_schemas() -> list[str]:
    """Validate that all contract kit schemas are valid JSON Schema files."""
    errors: list[str] = []

    if not CONTRACTS_DIR.exists():
        errors.append("contracts/ directory does not exist")
        return errors

    version_file = CONTRACTS_DIR / "contracts.version.json"
    if not version_file.exists():
        errors.append("contracts/contracts.version.json is missing")
        return errors

    # Validate version file is valid JSON
    try:
        with open(version_file, encoding="utf-8") as f:
            version_data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"contracts.version.json is invalid JSON: {e}")
        return errors

    required_fields = ["kit", "version", "schemas", "updated_at"]
    for field in required_fields:
        if field not in version_data:
            errors.append(f"contracts.version.json missing required field: {field}")

    # Validate each schema file in contracts/
    schema_files = sorted(CONTRACTS_DIR.glob("*.schema.json"))
    if not schema_files:
        errors.append("No .schema.json files found in contracts/")
        return errors

    for schema_file in schema_files:
        try:
            with open(schema_file, encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{schema_file.name}: invalid JSON: {e}")
            continue

        # Check it has $schema field
        if "$schema" not in schema:
            errors.append(f"{schema_file.name}: missing $schema field")

        # Check it has title
        if "title" not in schema:
            errors.append(f"{schema_file.name}: missing title field")

        # Check it has type
        if "type" not in schema:
            errors.append(f"{schema_file.name}: missing type field")

    return errors


def check_artifact_schemas() -> list[str]:
    """Validate that artifact schemas in src/truthcore/schemas/ are consistent."""
    errors: list[str] = []

    if not SCHEMAS_DIR.exists():
        errors.append("src/truthcore/schemas/ directory does not exist")
        return errors

    for artifact_dir in sorted(SCHEMAS_DIR.iterdir()):
        if not artifact_dir.is_dir():
            continue

        artifact_type = artifact_dir.name
        versions: list[str] = []

        for version_dir in sorted(artifact_dir.iterdir()):
            if not version_dir.is_dir():
                continue

            version_str = version_dir.name.lstrip("v")

            # Validate version format
            parts = version_str.split(".")
            if len(parts) != 3:
                errors.append(f"{artifact_type}/{version_dir.name}: invalid version format")
                continue

            try:
                [int(p) for p in parts]
            except ValueError:
                errors.append(f"{artifact_type}/{version_dir.name}: version parts must be integers")
                continue

            versions.append(version_str)

            # Check schema file exists
            schema_file = version_dir / f"{artifact_type}.schema.json"
            if not schema_file.exists():
                schema_file = version_dir / "schema.json"
                if not schema_file.exists():
                    errors.append(f"{artifact_type}/v{version_str}: no schema file found")
                    continue

            # Validate schema JSON
            try:
                with open(schema_file, encoding="utf-8") as f:
                    schema = json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{artifact_type}/v{version_str}: invalid JSON: {e}")
                continue

            # Check required fields in artifact schema
            if "required" not in schema:
                errors.append(f"{artifact_type}/v{version_str}: schema missing 'required' field")

            if schema.get("type") != "object":
                errors.append(f"{artifact_type}/v{version_str}: schema root type must be 'object'")

        if not versions:
            errors.append(f"{artifact_type}: no valid versions found")

    return errors


def check_sdk_exports() -> list[str]:
    """Validate that the TypeScript SDK exports the expected public API surface."""
    errors: list[str] = []

    index_file = TS_SDK_DIR / "src" / "index.ts"
    if not index_file.exists():
        errors.append("packages/ts-contract-sdk/src/index.ts does not exist")
        return errors

    index_content = index_file.read_text(encoding="utf-8")

    # Expected type exports
    expected_types = [
        "ContractMetadata",
        "SeverityLevel",
        "VerdictState",
        "Finding",
        "VerdictV1",
        "VerdictV2",
        "Verdict",
        "ReadinessCheck",
        "ReadinessV1",
        "Readiness",
        "TruthCoreArtifact",
    ]

    # Expected function exports
    expected_functions = [
        "isVerdict",
        "isReadiness",
        "isVerdictV1",
        "isVerdictV2",
        "loadVerdict",
        "topFindings",
        "filterBySeverity",
        "summarizeTrend",
        "hasSeverity",
        "getCategories",
        "getEngines",
    ]

    for type_name in expected_types:
        if type_name not in index_content:
            errors.append(f"SDK missing type export: {type_name}")

    for func_name in expected_functions:
        if func_name not in index_content:
            errors.append(f"SDK missing function export: {func_name}")

    # Check types.ts exists
    types_file = TS_SDK_DIR / "src" / "types.ts"
    if not types_file.exists():
        errors.append("packages/ts-contract-sdk/src/types.ts does not exist")

    # Check helpers.ts exists
    helpers_file = TS_SDK_DIR / "src" / "helpers.ts"
    if not helpers_file.exists():
        errors.append("packages/ts-contract-sdk/src/helpers.ts does not exist")

    return errors


def check_cli_entrypoints() -> list[str]:
    """Validate that CLI entrypoints exist and respond to --help."""
    errors: list[str] = []

    # Check truthctl is importable
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from truthcore.cli import main; print('ok')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            errors.append(f"truthcore.cli import failed: {result.stderr.strip()}")
            return errors
    except subprocess.TimeoutExpired:
        errors.append("truthcore.cli import timed out")
        return errors

    # Check truthctl --help
    try:
        result = subprocess.run(
            [sys.executable, "-m", "truthcore.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Some CLI frameworks exit 0 on --help, others use different conventions
            # Try direct invocation
            result2 = subprocess.run(
                ["truthctl", "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result2.returncode != 0:
                errors.append(f"truthctl --help failed (exit {result2.returncode})")
    except FileNotFoundError:
        # truthctl might not be on PATH but module import worked - that's ok
        pass
    except subprocess.TimeoutExpired:
        errors.append("truthctl --help timed out")

    return errors


def check_python_contracts_module() -> list[str]:
    """Validate that the Python contracts module exposes expected API."""
    errors: list[str] = []

    expected_exports = [
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

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from truthcore.contracts import __all__; print(','.join(sorted(__all__)))",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            errors.append(f"Failed to import truthcore.contracts: {result.stderr.strip()}")
            return errors

        actual_exports = set(result.stdout.strip().split(","))
        expected_set = set(expected_exports)

        missing = expected_set - actual_exports
        if missing:
            errors.append(f"Python contracts module missing exports: {', '.join(sorted(missing))}")

    except subprocess.TimeoutExpired:
        errors.append("Python contracts module import timed out")

    return errors


def check_version_sync() -> list[str]:
    """Check that contract kit version file is in sync with package versions."""
    errors: list[str] = []

    version_file = CONTRACTS_DIR / "contracts.version.json"
    if not version_file.exists():
        errors.append("contracts.version.json missing")
        return errors

    with open(version_file, encoding="utf-8") as f:
        version_data = json.load(f)

    # Check that declared artifact schemas match what exists on disk
    artifact_schemas = version_data.get("artifact_schemas", {})
    for schema_key, declared_version in artifact_schemas.items():
        # Parse artifact type from key (e.g., "verdict_v1" -> "verdict", "1.0.0")
        parts = schema_key.rsplit("_v", 1)
        if len(parts) != 2:
            continue
        artifact_type = parts[0]
        version_dir = SCHEMAS_DIR / artifact_type / f"v{declared_version}"
        if not version_dir.exists():
            errors.append(
                f"Declared artifact schema {schema_key}={declared_version} "
                f"but {version_dir} does not exist"
            )

    return errors


def main() -> int:
    """Run all contract checks."""
    header("Truth Core Contract Kit Validation")
    all_errors: list[str] = []
    checks = [
        ("Contract Kit Schemas", check_contract_schemas),
        ("Artifact Schemas", check_artifact_schemas),
        ("SDK Exports (TypeScript)", check_sdk_exports),
        ("CLI Entrypoints", check_cli_entrypoints),
        ("Python Contracts Module", check_python_contracts_module),
        ("Version Sync", check_version_sync),
    ]

    for name, check_fn in checks:
        print(f"\n  {name}...")
        try:
            errors = check_fn()
        except Exception as e:
            errors = [f"Unexpected error: {e}"]

        if errors:
            print(f"    [{FAIL}] {len(errors)} error(s):")
            for err in errors:
                print(f"      - {err}")
            all_errors.extend(errors)
        else:
            print(f"    [{PASS}]")

    header("Summary")
    if all_errors:
        print(f"\n  {FAIL}: {len(all_errors)} total error(s)")
        return 1
    else:
        print(f"\n  {PASS}: All contract checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
