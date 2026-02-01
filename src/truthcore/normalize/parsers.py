"""Normalization Toolkit - Log Parser Helpers.

Provides deterministic parsers for common tool outputs.
All parsers produce normalized, structured data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Pattern

from truthcore.normalize.text import TextNormalizer, TextNormalizationConfig


class ParserError(Exception):
    """Error during log parsing."""
    pass


class SeverityLevel(Enum):
    """Standardized severity levels."""

    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ParsedFinding:
    """A parsed finding from log output."""

    tool: str
    severity: SeverityLevel
    message: str
    location: str | None = None
    rule_id: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool": self.tool,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "rule_id": self.rule_id,
            "category": self.category,
            "metadata": self.metadata,
        }


class BaseLogParser:
    """Base class for log parsers."""

    def __init__(self, tool_name: str):
        """Initialize parser.
        
        Args:
            tool_name: Name of the tool being parsed
        """
        self.tool_name = tool_name
        self._normalizer = TextNormalizer(TextNormalizationConfig(trim_final=True))

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse log content and return findings.
        
        Args:
            content: Log content to parse
            
        Returns:
            List of parsed findings
        """
        raise NotImplementedError("Subclasses must implement parse()")

    def parse_file(self, path: Path) -> list[ParsedFinding]:
        """Parse a log file.
        
        Args:
            path: Path to log file
            
        Returns:
            List of parsed findings
        """
        content = path.read_text(encoding="utf-8")
        return self.parse(content)

    def _infer_severity(self, text: str) -> SeverityLevel:
        """Infer severity from text content (deterministic rules)."""
        text_upper = text.upper()

        # Blocker patterns
        if any(p in text_upper for p in ["BLOCKER", "FATAL", "CRITICAL", "PANIC", "ABORT"]):
            return SeverityLevel.BLOCKER

        # High patterns
        if any(p in text_upper for p in ["ERROR", "HIGH", "FAILED", "FAILURE", "EXCEPTION"]):
            return SeverityLevel.HIGH

        # Medium patterns
        if any(p in text_upper for p in ["WARNING", "WARN", "MEDIUM", "MODERATE"]):
            return SeverityLevel.MEDIUM

        # Low patterns
        if any(p in text_upper for p in ["NOTICE", "LOW", "MINOR", "STYLE", "HINT"]):
            return SeverityLevel.LOW

        # Info patterns
        if any(p in text_upper for p in ["INFO", "DEBUG", "LOG", "NOTE", "SUCCESS"]):
            return SeverityLevel.INFO

        return SeverityLevel.UNKNOWN


class RegexLogParser(BaseLogParser):
    """Generic regex-based log parser."""

    def __init__(
        self,
        tool_name: str,
        pattern: str | Pattern[str],
        severity_map: dict[str, SeverityLevel] | None = None,
    ):
        """Initialize with regex pattern.
        
        Args:
            tool_name: Name of the tool
            pattern: Regex pattern with named groups
            severity_map: Map of captured severity values to SeverityLevel
        """
        super().__init__(tool_name)
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.severity_map = severity_map or {}

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse using regex pattern."""
        findings = []

        for match in self.pattern.finditer(content):
            groups = match.groupdict()

            # Extract severity
            severity_str = groups.get("severity", "").upper()
            severity = self.severity_map.get(severity_str)
            if severity is None:
                severity = self._infer_severity(severity_str or groups.get("message", ""))

            finding = ParsedFinding(
                tool=self.tool_name,
                severity=severity,
                message=groups.get("message", "").strip(),
                location=groups.get("file") or groups.get("location"),
                rule_id=groups.get("rule") or groups.get("rule_id") or groups.get("code"),
                category=groups.get("category"),
                metadata={k: v for k, v in groups.items() if k not in (
                    "severity", "message", "file", "location", "rule", "rule_id", "code", "category"
                )},
            )
            findings.append(finding)

        return findings


class BlockParser(BaseLogParser):
    """Parser that extracts blocks/sections from logs."""

    def __init__(
        self,
        tool_name: str,
        block_start: str,
        block_end: str | None = None,
        severity_infer: bool = True,
    ):
        """Initialize block parser.
        
        Args:
            tool_name: Name of the tool
            block_start: Pattern indicating start of block
            block_end: Pattern indicating end of block (None = next block_start)
            severity_infer: Whether to infer severity from block content
        """
        super().__init__(tool_name)
        self.block_start = block_start
        self.block_end = block_end
        self.severity_infer = severity_infer

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse content into blocks."""
        findings = []
        blocks = self._extract_blocks(content)

        for block in blocks:
            severity = SeverityLevel.UNKNOWN
            if self.severity_infer:
                severity = self._infer_severity(block)

            finding = ParsedFinding(
                tool=self.tool_name,
                severity=severity,
                message=block.strip()[:500],  # Limit message length
                metadata={"full_block": block},
            )
            findings.append(finding)

        return findings

    def _extract_blocks(self, content: str) -> list[str]:
        """Extract blocks from content."""
        lines = content.split("\n")
        blocks = []
        current_block = []
        in_block = False

        for line in lines:
            if self.block_start in line:
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                in_block = True
                current_block.append(line)
            elif self.block_end and self.block_end in line:
                current_block.append(line)
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                in_block = False
            elif in_block:
                current_block.append(line)

        if current_block:
            blocks.append("\n".join(current_block))

        return blocks


# ============================================================================
# Specific Tool Parsers
# ============================================================================

class ESLintJSONParser(BaseLogParser):
    """Parser for ESLint JSON output."""

    def __init__(self):
        super().__init__("eslint")

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse ESLint JSON output."""
        findings = []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return findings

        for file_result in data:
            file_path = file_result.get("filePath", "")

            for msg in file_result.get("messages", []):
                severity_map = {2: SeverityLevel.HIGH, 1: SeverityLevel.LOW}
                severity = severity_map.get(msg.get("severity", 0), SeverityLevel.UNKNOWN)

                finding = ParsedFinding(
                    tool="eslint",
                    severity=severity,
                    message=msg.get("message", ""),
                    location=f"{file_path}:{msg.get('line', 0)}:{msg.get('column', 0)}",
                    rule_id=msg.get("ruleId"),
                    category=msg.get("severity") == 2 and "error" or "warning",
                    metadata={
                        "fixable": msg.get("fix") is not None,
                        "end_line": msg.get("endLine"),
                        "end_column": msg.get("endColumn"),
                    },
                )
                findings.append(finding)

        return findings


class ESLintTextParser(RegexLogParser):
    """Parser for ESLint text output."""

    # Pattern: file:line:column: severity message [rule]
    PATTERN = r"(?P<file>[^:]+):(?P<line>\d+):(?P<column>\d+):\s*(?P<severity>error|warning)\s+(?P<message>.+?)(?:\s*\[(?P<rule>[^\]]+)\])?(?=\n|$)"

    def __init__(self):
        severity_map = {
            "ERROR": SeverityLevel.HIGH,
            "WARNING": SeverityLevel.LOW,
        }
        super().__init__("eslint", self.PATTERN, severity_map)

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse ESLint text output."""
        findings = []

        for match in self.pattern.finditer(content):
            groups = match.groupdict()

            severity_str = groups.get("severity", "").upper()
            severity = self.severity_map.get(severity_str, SeverityLevel.UNKNOWN)

            finding = ParsedFinding(
                tool="eslint",
                severity=severity,
                message=groups.get("message", "").strip(),
                location=f"{groups.get('file')}:{groups.get('line')}:{groups.get('column')}",
                rule_id=groups.get("rule"),
                category=severity_str.lower(),
            )
            findings.append(finding)

        return findings


class TypeScriptCompilerParser(RegexLogParser):
    """Parser for TypeScript compiler (tsc) output."""

    # Pattern: file(line,column): error TS####: message
    PATTERN = r"(?P<file>[^(]+)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>error|warning)\s+(?P<code>TS\d+):\s*(?P<message>.+?)(?=\n|$)"

    def __init__(self):
        severity_map = {
            "ERROR": SeverityLevel.HIGH,
            "WARNING": SeverityLevel.LOW,
        }
        super().__init__("tsc", self.PATTERN, severity_map)

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse tsc output."""
        findings = []

        for match in self.pattern.finditer(content):
            groups = match.groupdict()

            severity_str = groups.get("severity", "").upper()
            severity = self.severity_map.get(severity_str, SeverityLevel.UNKNOWN)

            file_path = groups.get("file", "").strip() if groups.get("file") else ""
            finding = ParsedFinding(
                tool="tsc",
                severity=severity,
                message=groups.get("message", "").strip(),
                location=f"{file_path}:{groups.get('line')}:{groups.get('column')}",
                rule_id=groups.get("code"),
                category="type_error" if severity_str == "ERROR" else "type_warning",
            )
            findings.append(finding)

        return findings


class BuildLogParser(RegexLogParser):
    """Generic build log parser."""

    # Pattern: [timestamp] severity: message
    PATTERN = r"(?:\[?[^\]]*\]?\s*)?(?P<severity>ERROR|WARN|WARNING|INFO|DEBUG|FAIL|FAILURE|SUCCESS)[:\s]+(?P<message>.+?)(?=\n|$)"

    def __init__(self, tool_name: str = "build"):
        severity_map = {
            "ERROR": SeverityLevel.HIGH,
            "FAIL": SeverityLevel.HIGH,
            "FAILURE": SeverityLevel.HIGH,
            "WARN": SeverityLevel.MEDIUM,
            "WARNING": SeverityLevel.MEDIUM,
            "INFO": SeverityLevel.INFO,
            "DEBUG": SeverityLevel.LOW,
            "SUCCESS": SeverityLevel.INFO,
        }
        super().__init__(tool_name, self.PATTERN, severity_map)

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse build log with multiline support."""
        findings = []

        for match in self.pattern.finditer(content, re.MULTILINE):
            groups = match.groupdict()

            severity_str = groups.get("severity", "").upper()
            severity = self.severity_map.get(severity_str, SeverityLevel.UNKNOWN)

            finding = ParsedFinding(
                tool=self.tool_name,
                severity=severity,
                message=groups.get("message", "").strip(),
                rule_id=None,
                category=None,
            )
            findings.append(finding)

        return findings


class PlaywrightJSONParser(BaseLogParser):
    """Parser for Playwright JSON report."""

    def __init__(self):
        super().__init__("playwright")

    def parse(self, content: str) -> list[ParsedFinding]:
        """Parse Playwright JSON report."""
        findings = []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return findings

        # Parse suites recursively
        suites = data.get("suites", [])
        for suite in suites:
            findings.extend(self._parse_suite(suite))

        return findings

    def _parse_suite(self, suite: dict, path: str = "") -> list[ParsedFinding]:
        """Recursively parse test suite."""
        findings = []

        suite_title = suite.get("title", "")
        current_path = f"{path}/{suite_title}" if path else suite_title

        # Parse specs (tests)
        for spec in suite.get("specs", []):
            findings.extend(self._parse_spec(spec, current_path))

        # Parse nested suites
        for nested_suite in suite.get("suites", []):
            findings.extend(self._parse_suite(nested_suite, current_path))

        return findings

    def _parse_spec(self, spec: dict, path: str) -> list[ParsedFinding]:
        """Parse a test spec."""
        findings = []

        spec_title = spec.get("title", "")
        tests = spec.get("tests", [])

        for test in tests:
            results = test.get("results", [])

            for result in results:
                status = result.get("status", "").lower()

                if status in ("failed", "timedout"):
                    errors = result.get("errors", [])
                    for error in errors:
                        finding = ParsedFinding(
                            tool="playwright",
                            severity=SeverityLevel.HIGH,
                            message=error.get("message", "Test failed"),
                            location=f"{path}/{spec_title}",
                            metadata={
                                "status": status,
                                "duration": result.get("duration"),
                                "retry": result.get("retry"),
                                "stack": error.get("stack", "")[:1000],  # Limit stack trace
                            },
                        )
                        findings.append(finding)

                elif status == "skipped":
                    finding = ParsedFinding(
                        tool="playwright",
                        severity=SeverityLevel.LOW,
                        message=f"Test skipped: {spec_title}",
                        location=path,
                        metadata={"status": "skipped"},
                    )
                    findings.append(finding)

        return findings


# ============================================================================
# Parser Registry
# ============================================================================

# Factory functions for creating parsers
PARSER_REGISTRY: dict[str, Callable[[], BaseLogParser]] = {
    "eslint-json": lambda: ESLintJSONParser(),
    "eslint-text": lambda: ESLintTextParser(),
    "tsc": lambda: TypeScriptCompilerParser(),
    "playwright-json": lambda: PlaywrightJSONParser(),
    "build": lambda: BuildLogParser(),
}


def get_parser(tool_name: str) -> BaseLogParser | None:
    """Get a parser by tool name.
    
    Args:
        tool_name: Name of the tool/parser
        
    Returns:
        Parser instance or None if not found
        
    Example:
        >>> parser = get_parser("eslint-json")
        >>> findings = parser.parse_file(Path("eslint-output.json"))
    """
    factory = PARSER_REGISTRY.get(tool_name)
    if factory:
        return factory()
    return None


def register_parser(name: str, factory: Callable[[], BaseLogParser]) -> None:
    """Register a custom parser.
    
    Args:
        name: Name to register under
        factory: Factory function that returns a parser instance
    """
    PARSER_REGISTRY[name] = factory


def parse_with(tool_name: str, content: str) -> list[ParsedFinding]:
    """Parse content with a registered parser.
    
    Args:
        tool_name: Name of the parser to use
        content: Content to parse
        
    Returns:
        List of findings
        
    Raises:
        ValueError: If parser not found
    """
    parser = get_parser(tool_name)
    if parser is None:
        raise ValueError(f"Unknown parser: {tool_name}")
    return parser.parse(content)


def infer_severity(text: str) -> SeverityLevel:
    """Infer severity from text (deterministic rules).
    
    Args:
        text: Text to analyze
        
    Returns:
        Inferred severity level
    """
    parser = BaseLogParser("infer")
    return parser._infer_severity(text)
