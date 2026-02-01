"""Deterministic scanners for policy rules.

All scanners use only local regex - no external services or network calls.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truthcore.findings import Finding, Location
from truthcore.policy.models import Matcher, PolicyRule, Severity
from truthcore.security import safe_read_text, SecurityLimits


@dataclass
class ScanContext:
    """Context for a scan operation."""

    input_dir: Path
    current_file: Path | None = None
    file_count: int = 0
    byte_count: int = 0
    limits: SecurityLimits = field(default_factory=SecurityLimits)
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyScanner(ABC):
    """Base class for policy scanners."""

    def __init__(self, context: ScanContext) -> None:
        self.context = context
        self.findings: list[Finding] = []

    @abstractmethod
    def scan(self, rule: PolicyRule) -> list[Finding]:
        """Scan for findings based on rule."""
        pass

    def add_finding(
        self,
        rule: PolicyRule,
        target: str,
        location: Location,
        message: str,
        excerpt: str | None = None,
    ) -> None:
        """Add a finding."""
        # Check suppression
        if rule.is_suppressed(target):
            return

        # Create finding
        excerpt_hash = None
        if excerpt:
            excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()[:32]

        finding = Finding(
            rule_id=rule.id,
            severity=rule.severity.to_finding_severity(),
            target=target,
            location=location,
            message=message,
            excerpt=excerpt[:200] if excerpt else None,  # Limit excerpt length
            excerpt_hash=excerpt_hash,
            suggestion=rule.suggestion,
            metadata={"category": rule.category, **rule.metadata},
        )
        self.findings.append(finding)

    def _match_content(self, content: str, matchers: list[Matcher]) -> list[tuple[str, int]]:
        """Find all matches in content.

        Returns:
            List of (match_text, position) tuples
        """
        matches = []
        for matcher in matchers:
            if matcher.type == "regex":
                for m in matcher._compiled_regex.finditer(content):
                    matches.append((m.group(0), m.start()))
            elif matcher.type == "contains":
                pattern = matcher.pattern
                start = 0
                while True:
                    idx = content.find(pattern, start)
                    if idx == -1:
                        break
                    matches.append((pattern, idx))
                    start = idx + 1
            elif matcher.type == "equals":
                if matcher.matches(content):
                    matches.append((content, 0))
            elif matcher.type == "glob":
                # Glob is path-based, skip for content
                pass
        return matches

    def _get_line_number(self, content: str, byte_offset: int) -> int:
        """Get line number for byte offset."""
        return content[:byte_offset].count("\n") + 1


class SecretScanner(PolicyScanner):
    """Scanner for secret-like patterns.

    Uses regex only - no external secret detection services.
    """

    # Common secret patterns (deterministic, no external calls)
    SECRET_PATTERNS = {
        "api_key": re.compile(
            r'(?i)(api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?'
        ),
        "bearer_token": re.compile(
            r'(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})'
        ),
        "private_key": re.compile(
            r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'
        ),
        "aws_access_key": re.compile(
            r'AKIA[0-9A-Z]{16}'
        ),
        "aws_secret_key": re.compile(
            r'(?i)aws[_-]?secret[_-]?access[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?'
        ),
        "github_token": re.compile(
            r'gh[pousr]_[A-Za-z0-9_]{36,}'
        ),
        "slack_token": re.compile(
            r'xox[baprs]-[0-9a-zA-Z]{10,}'
        ),
        "jwt_token": re.compile(
            r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'
        ),
        "generic_secret": re.compile(
            r'(?i)(password|passwd|pwd|secret|token)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9!@#$%^&*]{8,})["\']?'
        ),
    }

    def scan(self, rule: PolicyRule) -> list[Finding]:
        """Scan for secrets."""
        self.findings = []

        # Walk files
        for file_path in sorted(self.context.input_dir.rglob("*")):
            if not file_path.is_file():
                continue

            # Skip binary files
            if self._is_binary(file_path):
                continue

            # Skip very large files
            try:
                stat = file_path.stat()
                if stat.st_size > self.context.limits.max_file_size:
                    continue
            except OSError:
                continue

            try:
                content = safe_read_text(file_path, self.context.limits)
            except Exception:
                continue

            rel_path = str(file_path.relative_to(self.context.input_dir))

            # Check matchers if defined
            if rule.matchers:
                for matcher in rule.matchers:
                    if matcher.type == "regex":
                        for match in matcher._compiled_regex.finditer(content):
                            line = self._get_line_number(content, match.start())
                            self.add_finding(
                                rule,
                                f"file:{rel_path}",
                                Location(path=rel_path, line=line, byte_offset=match.start()),
                                f"Pattern match: {matcher.pattern[:50]}",
                                match.group(0)[:100],
                            )
            else:
                # Use built-in secret patterns
                for pattern_name, pattern_regex in self.SECRET_PATTERNS.items():
                    for match in pattern_regex.finditer(content):
                        line = self._get_line_number(content, match.start())
                        # Redact the actual secret value
                        excerpt = match.group(0)
                        # Replace potential secret with hash
                        secret_hash = hashlib.sha256(excerpt.encode()).hexdigest()[:16]
                        redacted_excerpt = f"[{pattern_name}:{secret_hash}]"

                        self.add_finding(
                            rule,
                            f"file:{rel_path}",
                            Location(path=rel_path, line=line, byte_offset=match.start()),
                            f"Potential secret detected: {pattern_name}",
                            redacted_excerpt,
                        )

        # Apply threshold
        if rule.threshold:
            if not rule.threshold.evaluate(self.findings):
                # Threshold not met, clear findings
                self.findings = []

        return self.findings

    def _is_binary(self, path: Path) -> bool:
        """Check if file is binary."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return True


class PIIScanner(PolicyScanner):
    """Scanner for PII patterns.

    Uses regex heuristics only - deterministic, no external services.
    """

    # PII patterns (heuristics only)
    PII_PATTERNS = {
        "email": re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ),
        "phone_us": re.compile(
            r'\b(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
        ),
        "ssn_like": re.compile(
            r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'
        ),
        "credit_card": re.compile(
            r'\b(?:\d{4}[-.\s]?){3}\d{4}\b'
        ),
        "ip_address": re.compile(
            r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ),
    }

    # Allowlist patterns (common false positives)
    ALLOWLIST = [
        r'example\.com',
        r'test@example',
        r'localhost',
        r'0\.0\.0\.0',
        r'127\.0\.0\.1',
        r'192\.168\.\d+\.\d+',
        r'10\.\d+\.\d+\.\d+',
        r'172\.(?:1[6-9]|2[0-9]|3[01])\.\d+\.\d+',
    ]

    def __init__(self, context: ScanContext) -> None:
        super().__init__(context)
        self._allowlist_regex = re.compile("|".join(f"(?:{p})" for p in self.ALLOWLIST))

    def scan(self, rule: PolicyRule) -> list[Finding]:
        """Scan for PII."""
        self.findings = []

        for file_path in sorted(self.context.input_dir.rglob("*")):
            if not file_path.is_file():
                continue

            if self._is_binary(file_path):
                continue

            try:
                stat = file_path.stat()
                if stat.st_size > self.context.limits.max_file_size:
                    continue
            except OSError:
                continue

            try:
                content = safe_read_text(file_path, self.context.limits)
            except Exception:
                continue

            rel_path = str(file_path.relative_to(self.context.input_dir))

            # Check matchers if defined
            if rule.matchers:
                for matcher in rule.matchers:
                    if matcher.type == "regex":
                        for match in matcher._compiled_regex.finditer(content):
                            matched_text = match.group(0)
                            if self._is_allowlisted(matched_text):
                                continue
                            line = self._get_line_number(content, match.start())
                            self.add_finding(
                                rule,
                                f"file:{rel_path}",
                                Location(path=rel_path, line=line, byte_offset=match.start()),
                                f"PII pattern match: {matcher.pattern[:50]}",
                                matched_text[:100],
                            )
            else:
                # Use built-in PII patterns
                for pattern_name, pattern_regex in self.PII_PATTERNS.items():
                    for match in pattern_regex.finditer(content):
                        matched_text = match.group(0)
                        if self._is_allowlisted(matched_text):
                            continue
                        line = self._get_line_number(content, match.start())
                        self.add_finding(
                            rule,
                            f"file:{rel_path}",
                            Location(path=rel_path, line=line, byte_offset=match.start()),
                            f"Potential PII detected: {pattern_name}",
                            matched_text[:100],
                        )

        if rule.threshold:
            if not rule.threshold.evaluate(self.findings):
                self.findings = []

        return self.findings

    def _is_allowlisted(self, text: str) -> bool:
        """Check if text matches allowlist."""
        return bool(self._allowlist_regex.search(text))

    def _is_binary(self, path: Path) -> bool:
        """Check if file is binary."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return True


class ConfigScanner(PolicyScanner):
    """Scanner for unsafe configuration patterns."""

    # Unsafe config patterns
    UNSAFE_PATTERNS = {
        "debug_true": re.compile(
            r'(?i)debug\s*[=:]\s*(true|yes|1|on)\b'
        ),
        "disable_ssl_verify": re.compile(
            r'(?i)(ssl[_-]?verify|verify[_-]?ssl)\s*[=:]\s*(false|no|0|off)\b'
        ),
        "permissive_cors": re.compile(
            r'(?i)(access[_-]?control[_-]?allow[_-]?origin)\s*[=:]\s*\*'
        ),
        "weak_crypto": re.compile(
            r'(?i)(md5|sha1|des|rc4)\b'
        ),
        "hardcoded_password": re.compile(
            r'(?i)password\s*[=:]\s*["\'][^"\']+["\']'
        ),
        "wildcard_permission": re.compile(
            r'(?i)(permission|allow|grant)\s*[=:]\s*["\']?\*["\']?'
        ),
    }

    def scan(self, rule: PolicyRule) -> list[Finding]:
        """Scan for unsafe configs."""
        self.findings = []

        config_extensions = {".yaml", ".yml", ".json", ".toml", ".ini", ".conf", ".properties"}

        for file_path in sorted(self.context.input_dir.rglob("*")):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in config_extensions:
                continue

            try:
                stat = file_path.stat()
                if stat.st_size > self.context.limits.max_file_size:
                    continue
            except OSError:
                continue

            try:
                content = safe_read_text(file_path, self.context.limits)
            except Exception:
                continue

            rel_path = str(file_path.relative_to(self.context.input_dir))

            # Parse based on file type for better accuracy
            is_prod_file = "prod" in rel_path.lower() or "production" in rel_path.lower()

            # Check matchers if defined
            if rule.matchers:
                for matcher in rule.matchers:
                    if matcher.type == "regex":
                        for match in matcher._compiled_regex.finditer(content):
                            line = self._get_line_number(content, match.start())
                            self.add_finding(
                                rule,
                                f"config:{rel_path}",
                                Location(path=rel_path, line=line, byte_offset=match.start()),
                                f"Config pattern match: {matcher.pattern[:50]}",
                                match.group(0)[:100],
                            )
            else:
                # Use built-in unsafe patterns
                for pattern_name, pattern_regex in self.UNSAFE_PATTERNS.items():
                    for match in pattern_regex.finditer(content):
                        line = self._get_line_number(content, match.start())
                        # Extra severity for prod files with debug enabled
                        if pattern_name == "debug_true" and is_prod_file:
                            msg = f"CRITICAL: debug=true in production config ({rel_path})"
                        else:
                            msg = f"Unsafe config pattern: {pattern_name}"

                        self.add_finding(
                            rule,
                            f"config:{rel_path}",
                            Location(path=rel_path, line=line, byte_offset=match.start()),
                            msg,
                            match.group(0)[:100],
                        )

            # Additional JSON/YAML parsing for structured checks
            if file_path.suffix.lower() in (".json", ".yaml", ".yml"):
                self._check_structured_config(file_path, rel_path, rule)

        if rule.threshold:
            if not rule.threshold.evaluate(self.findings):
                self.findings = []

        return self.findings

    def _check_structured_config(self, file_path: Path, rel_path: str, rule: PolicyRule) -> None:
        """Check structured config files for specific patterns."""
        try:
            if file_path.suffix.lower() == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._check_config_dict(data, rel_path, rule, [])
            else:
                import yaml
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._check_config_dict(data, rel_path, rule, [])
        except Exception:
            pass

    def _check_config_dict(
        self, data: Any, rel_path: str, rule: PolicyRule, path: list[str]
    ) -> None:
        """Recursively check config dictionary."""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = path + [key]
                key_path = ".".join(current_path)

                # Check for unsafe values
                if isinstance(value, bool):
                    if key.lower() in ("debug", "debug_mode") and value:
                        self.add_finding(
                            rule,
                            f"config:{rel_path}",
                            Location(path=rel_path),
                            f"debug=true found at {key_path}",
                            f"{key_path}: true",
                        )
                    elif key.lower() in ("verify_ssl", "ssl_verify") and not value:
                        self.add_finding(
                            rule,
                            f"config:{rel_path}",
                            Location(path=rel_path),
                            f"SSL verification disabled at {key_path}",
                            f"{key_path}: false",
                        )

                # Recurse
                self._check_config_dict(value, rel_path, rule, current_path)


class ArtifactScanner(PolicyScanner):
    """Scanner for artifact hygiene issues."""

    def __init__(self, context: ScanContext) -> None:
        super().__init__(context)
        self.oversized_files: list[tuple[Path, int]] = []
        self.suspicious_binaries: list[Path] = []

    def scan(self, rule: PolicyRule) -> list[Finding]:
        """Scan for artifact hygiene issues."""
        self.findings = []

        # Check for oversized files
        max_size = rule.metadata.get("max_file_size_mb", 10) * 1024 * 1024

        # Check for path traversal attempts in filenames
        traversal_patterns = re.compile(r'\.\.[\\/]|%2e%2e|[\\/]\.\.[\\/]')

        file_count = 0
        for file_path in sorted(self.context.input_dir.rglob("*")):
            if not file_path.is_file():
                continue

            file_count += 1
            rel_path = str(file_path.relative_to(self.context.input_dir))

            # Check for path traversal in filename
            if traversal_patterns.search(rel_path):
                self.add_finding(
                    rule,
                    f"file:{rel_path}",
                    Location(path=rel_path),
                    "Path traversal pattern detected in filename",
                    rel_path[:100],
                )
                continue

            # Check file size
            try:
                stat = file_path.stat()
                if stat.st_size > max_size:
                    self.add_finding(
                        rule,
                        f"file:{rel_path}",
                        Location(path=rel_path),
                        f"Oversized file: {stat.st_size / 1024 / 1024:.1f} MB (max: {max_size / 1024 / 1024:.1f} MB)",
                        f"Size: {stat.st_size} bytes",
                    )
            except OSError:
                continue

            # Check for suspicious binary content
            if self._is_suspicious_binary(file_path):
                self.add_finding(
                    rule,
                    f"file:{rel_path}",
                    Location(path=rel_path),
                    "Suspicious binary payload detected",
                    "Binary content",
                )

        # Check total file count
        max_files = rule.metadata.get("max_file_count", 10000)
        if file_count > max_files:
            self.add_finding(
                rule,
                f"directory:{self.context.input_dir}",
                Location(path=str(self.context.input_dir)),
                f"Too many files: {file_count} (max: {max_files})",
                f"File count: {file_count}",
            )

        if rule.threshold:
            if not rule.threshold.evaluate(self.findings):
                self.findings = []

        return self.findings

    def _is_suspicious_binary(self, path: Path) -> bool:
        """Check if binary file has suspicious characteristics."""
        try:
            with open(path, "rb") as f:
                header = f.read(256)

            # Check for executable headers in non-executable files
            if path.suffix not in (".exe", ".dll", ".so", ".dylib", ".bin"):
                # ELF header
                if header.startswith(b"\x7fELF"):
                    return True
                # Mach-O header
                if header[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    return True
                # Windows executable
                if header[:2] == b"MZ":
                    return True

            return False
        except Exception:
            return False
