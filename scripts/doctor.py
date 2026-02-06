#!/usr/bin/env python3
"""Doctor script for truth-core development environment.

Verifies environment variables, node/python versions, build prerequisites,
and checks for secret leakage patterns.

Usage:
    python scripts/doctor.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
INFO = "\033[36mINFO\033[0m"

# Patterns that indicate secret leakage in log/output files
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-._~+/]+=*"),
    re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
    re.compile(r"(?i)TRUTHCORE_API_KEY=[^\s]{8,}"),
    re.compile(r"(?i)TRUTHCORE_SIGNING_KEY_PATH=.+\.pem"),
]


def header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_python_version() -> list[str]:
    """Check Python version meets requirements."""
    errors: list[str] = []
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 11):
        errors.append(f"Python >= 3.11 required, found {major}.{minor}. Install Python 3.11+.")
    else:
        print(f"    Python {major}.{minor} [{PASS}]")
    return errors


def check_node_version() -> list[str]:
    """Check Node.js version meets requirements."""
    errors: list[str] = []
    node = shutil.which("node")
    if not node:
        errors.append("Node.js not found. Install Node.js >= 18: https://nodejs.org/")
        return errors

    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        version_str = result.stdout.strip().lstrip("v")
        major = int(version_str.split(".")[0])
        if major < 18:
            errors.append(f"Node.js >= 18 required, found {version_str}. Update Node.js.")
        else:
            print(f"    Node.js {version_str} [{PASS}]")
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        errors.append("Could not determine Node.js version.")
    return errors


def check_pnpm() -> list[str]:
    """Check pnpm is available."""
    errors: list[str] = []
    pnpm = shutil.which("pnpm")
    if not pnpm:
        errors.append("pnpm not found. Install: npm install -g pnpm")
        return errors

    try:
        result = subprocess.run(
            ["pnpm", "--version"], capture_output=True, text=True, timeout=10
        )
        version_str = result.stdout.strip()
        print(f"    pnpm {version_str} [{PASS}]")
    except subprocess.TimeoutExpired:
        errors.append("Could not determine pnpm version.")
    return errors


def check_python_packages() -> list[str]:
    """Check required Python packages are installed."""
    errors: list[str] = []
    # Map of package name -> import name (when they differ)
    required = {
        "click": "click",
        "pydantic": "pydantic",
        "pyyaml": "yaml",
        "rich": "rich",
        "structlog": "structlog",
        "jsonschema": "jsonschema",
    }

    for pkg, import_name in required.items():
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {import_name}; print(getattr({import_name}, '__version__', 'ok'))"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                errors.append(f"Python package '{pkg}' not installed. Run: pip install -e '.[dev]'")
        except subprocess.TimeoutExpired:
            errors.append(f"Timeout checking package '{pkg}'")
    if not errors:
        print(f"    Required Python packages [{PASS}]")
    return errors


def check_truthcore_installed() -> list[str]:
    """Check truthcore is installed in development mode."""
    errors: list[str] = []
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import truthcore; print(truthcore.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append("truthcore not installed. Run: pip install -e '.[dev]'")
        else:
            print(f"    truthcore {result.stdout.strip()} [{PASS}]")
    except subprocess.TimeoutExpired:
        errors.append("Timeout checking truthcore installation.")
    return errors


def check_node_modules() -> list[str]:
    """Check that node_modules are installed."""
    errors: list[str] = []
    ts_sdk_modules = ROOT / "packages" / "ts-contract-sdk" / "node_modules"
    if not ts_sdk_modules.exists():
        errors.append(
            "node_modules not installed for ts-contract-sdk. Run: pnpm install"
        )
    else:
        print(f"    node_modules present [{PASS}]")
    return errors


def check_build_prerequisites() -> list[str]:
    """Check build tools are available."""
    errors: list[str] = []
    tools = {
        "git": "Install git: https://git-scm.com/",
        "ruff": "Install ruff: pip install ruff",
    }

    for tool, remedy in tools.items():
        if not shutil.which(tool):
            errors.append(f"'{tool}' not found. {remedy}")

    if not errors:
        print(f"    Build tools (git, ruff) [{PASS}]")
    return errors


def check_env_vars() -> list[str]:
    """Check environment configuration."""
    errors: list[str] = []

    env_example = ROOT / ".env.example"
    env_file = ROOT / ".env"

    if env_example.exists() and not env_file.exists():
        print(f"    [{INFO}] No .env file found. Copy .env.example to .env for local config.")

    # Check for dangerous env vars that should not be set in CI
    dangerous_vars = [
        "TRUTHCORE_API_KEY",
        "TRUTHCORE_SIGNING_KEY_PATH",
    ]

    for var in dangerous_vars:
        val = os.environ.get(var, "")
        if val and val not in ("", "your-api-key-here"):
            # This is informational, not an error in dev
            print(f"    [{WARN}] {var} is set. Ensure it is not committed to source.")

    print(f"    Environment variables [{PASS}]")
    return errors


def check_secret_leakage() -> list[str]:
    """Scan source files for potential secret leakage patterns."""
    errors: list[str] = []

    scan_dirs = [
        ROOT / "src",
        ROOT / "tests",
        ROOT / "scripts",
        ROOT / "contracts",
    ]

    scan_extensions = {".py", ".ts", ".js", ".json", ".yaml", ".yml", ".sh"}

    # Files that are expected to contain secret-like patterns (detection rules,
    # test fixtures, and this script's own pattern definitions).
    excluded_files = {
        "scripts/doctor.py",
        "tests/test_policy.py",
        "src/truthcore/policy/packs/security.yaml",
        "src/truthcore/server.py",
    }

    files_scanned = 0

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for fpath in scan_dir.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.suffix not in scan_extensions:
                continue
            if "__pycache__" in str(fpath) or "node_modules" in str(fpath):
                continue

            rel_path = str(fpath.relative_to(ROOT))
            if rel_path in excluded_files:
                continue

            files_scanned += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern in SECRET_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    for match in matches:
                        match_str = match if isinstance(match, str) else str(match)
                        if any(
                            safe in match_str.lower()
                            for safe in ["example", "test", "your-", "placeholder", "xxx"]
                        ):
                            continue
                        errors.append(
                            f"Potential secret in {rel_path}: matches pattern "
                            f"'{pattern.pattern[:40]}...'"
                        )
                        break  # One report per file per pattern

    if not errors:
        print(f"    Secret scan ({files_scanned} files) [{PASS}]")
    return errors


def check_contract_kit_present() -> list[str]:
    """Verify the contract kit directory exists with required files."""
    errors: list[str] = []
    required_files = [
        "contracts.version.json",
        "config.schema.json",
        "module_manifest.schema.json",
        "evidence_packet.schema.json",
        "structured_log_event.schema.json",
        "error_envelope.schema.json",
    ]

    contracts_dir = ROOT / "contracts"
    if not contracts_dir.exists():
        errors.append("contracts/ directory missing. Run the contract kit setup.")
        return errors

    for fname in required_files:
        if not (contracts_dir / fname).exists():
            errors.append(f"contracts/{fname} missing.")

    if not errors:
        print(f"    Contract kit files [{PASS}]")
    return errors


def main() -> int:
    """Run all doctor checks."""
    header("Truth Core Doctor")
    all_errors: list[str] = []

    sections = [
        ("Runtime Versions", [check_python_version, check_node_version, check_pnpm]),
        ("Dependencies", [check_python_packages, check_truthcore_installed, check_node_modules]),
        ("Build Prerequisites", [check_build_prerequisites]),
        ("Environment", [check_env_vars]),
        ("Contract Kit", [check_contract_kit_present]),
        ("Security Scan", [check_secret_leakage]),
    ]

    for section_name, checks in sections:
        print(f"\n  {section_name}:")
        for check_fn in checks:
            try:
                errors = check_fn()
            except Exception as e:
                errors = [f"Check failed unexpectedly: {e}"]
            if errors:
                for err in errors:
                    print(f"    [{FAIL}] {err}")
                all_errors.extend(errors)

    header("Summary")
    if all_errors:
        print(f"\n  {FAIL}: {len(all_errors)} issue(s) found")
        print("\n  Remediation:")
        for err in all_errors:
            print(f"    - {err}")
        return 1
    else:
        print(f"\n  {PASS}: All checks passed. Environment is healthy.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
