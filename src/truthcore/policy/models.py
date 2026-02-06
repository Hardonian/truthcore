"""Policy data models and JSON Schema validation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

import yaml

from truthcore.security import safe_read_text
from truthcore.severity import Severity


class PolicyEffect(Enum):
    """Policy decision effect types."""

    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"


class PolicyPriority(Enum):
    """Priority levels for policy conflict resolution."""

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    DEFAULT = 4


@dataclass
class Matcher:
    """Pattern matcher for policy rules.

    Supports:
    - regex: Regular expression matching
    - contains: Substring matching
    - equals: Exact string matching
    - glob: Unix shell-style wildcards
    """

    type: Literal["regex", "contains", "equals", "glob"]
    pattern: str
    flags: list[str] = field(default_factory=list)
    _compiled_regex: re.Pattern | None = field(default=None, repr=False)

    def __post_init__(self):
        """Compile regex if needed."""
        if self.type == "regex" and self._compiled_regex is None:
            flags = 0
            for flag in self.flags:
                if flag == "i":
                    flags |= re.IGNORECASE
                elif flag == "m":
                    flags |= re.MULTILINE
                elif flag == "s":
                    flags |= re.DOTALL
            self._compiled_regex = re.compile(self.pattern, flags)

    def matches(self, value: str) -> bool:
        """Check if value matches the pattern."""
        if self.type == "regex":
            return bool(self._compiled_regex and self._compiled_regex.search(value))
        elif self.type == "contains":
            if "i" in self.flags:
                return self.pattern.lower() in value.lower()
            return self.pattern in value
        elif self.type == "equals":
            if "i" in self.flags:
                return self.pattern.lower() == value.lower()
            return self.pattern == value
        elif self.type == "glob":
            return fnmatch(value, self.pattern)
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "pattern": self.pattern,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Matcher:
        """Create from dictionary."""
        return cls(
            type=data["type"],
            pattern=data["pattern"],
            flags=data.get("flags", []),
        )


@dataclass
class Suppression:
    """Allowlist suppression for findings.

    Attributes:
        pattern: Pattern to match for suppression
        reason: Why this suppression exists
        expiry: Optional expiry date (ISO format)
        author: Who created the suppression
    """

    pattern: str
    reason: str
    expiry: str | None = None
    author: str | None = None

    def is_expired(self) -> bool:
        """Check if suppression has expired."""
        if not self.expiry:
            return False
        try:
            expiry_dt = datetime.fromisoformat(self.expiry)
            return datetime.now(UTC) > expiry_dt
        except ValueError:
            return False

    def matches(self, finding_target: str) -> bool:
        """Check if finding matches suppression pattern."""
        return fnmatch(finding_target, self.pattern)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern,
            "reason": self.reason,
            "expiry": self.expiry,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Suppression:
        """Create from dictionary."""
        return cls(
            pattern=data["pattern"],
            reason=data["reason"],
            expiry=data.get("expiry"),
            author=data.get("author"),
        )


@dataclass
class Threshold:
    """Threshold condition for rule evaluation.

    Attributes:
        count: Minimum number of matches required
        rate: Minimum rate (0.0-1.0) of matches required
        distinct: Minimum number of distinct values required
    """

    count: int | None = None
    rate: float | None = None
    distinct: int | None = None

    def evaluate(self, matches: list[Any]) -> bool:
        """Evaluate if matches meet threshold."""
        if self.count is not None and len(matches) < self.count:
            return False
        if self.distinct is not None and len(set(str(m) for m in matches)) < self.distinct:
            return False
        # Rate requires context (total count) - handled by caller
        return True

    def evaluate_with_rate(self, matches: list[Any], total: int) -> bool:
        """Evaluate with rate context."""
        if not self.evaluate(matches):
            return False
        if self.rate is not None:
            if total == 0:
                return self.rate == 0.0
            actual_rate = len(matches) / total
            if actual_rate < self.rate:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.count is not None:
            result["count"] = self.count
        if self.rate is not None:
            result["rate"] = self.rate
        if self.distinct is not None:
            result["distinct"] = self.distinct
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Threshold:
        """Create from dictionary."""
        return cls(
            count=data.get("count"),
            rate=data.get("rate"),
            distinct=data.get("distinct"),
        )


@dataclass
class PolicyRule:
    """A single policy rule.

    Attributes:
        id: Unique rule identifier
        description: Human-readable description
        severity: Severity level
        category: Rule category (security, privacy, etc.)
        target: What to target (files, logs, json_fields, findings, traces)
        matchers: List of matchers (OR logic between matchers)
        all_of: All must match (AND composition)
        any_of: Any can match (OR composition)
        not_match: Must NOT match (NOT composition)
        threshold: Threshold for triggering
        suppressions: List of suppressions
        suggestion: Remediation suggestion
        enabled: Whether rule is enabled
        metadata: Additional metadata
        effect: Policy effect (allow/deny/conditional)
        priority: Policy priority for conflict resolution
    """

    id: str
    description: str
    severity: Severity
    category: str
    target: Literal["files", "logs", "json_fields", "findings", "traces"]
    matchers: list[Matcher] = field(default_factory=list)
    all_of: list[PolicyRule] = field(default_factory=list)
    any_of: list[PolicyRule] = field(default_factory=list)
    not_match: PolicyRule | None = field(default=None)
    threshold: Threshold | None = None
    suppressions: list[Suppression] = field(default_factory=list)
    suggestion: str | None = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    effect: PolicyEffect = field(default=PolicyEffect.DENY)
    priority: PolicyPriority = field(default=PolicyPriority.MEDIUM)

    def __post_init__(self):
        """Ensure rule ID is normalized."""
        if not self.id:
            raise ValueError("Rule ID is required")

    def is_suppressed(self, finding_target: str) -> bool:
        """Check if finding is suppressed."""
        for suppression in self.suppressions:
            if not suppression.is_expired() and suppression.matches(finding_target):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category,
            "target": self.target,
            "enabled": self.enabled,
            "effect": self.effect.value,
            "priority": self.priority.name,
            "metadata": dict(sorted(self.metadata.items())),
        }
        if self.matchers:
            result["matchers"] = [m.to_dict() for m in self.matchers]
        if self.all_of:
            result["all_of"] = [r.to_dict() for r in self.all_of]
        if self.any_of:
            result["any_of"] = [r.to_dict() for r in self.any_of]
        if self.not_match:
            result["not_match"] = self.not_match.to_dict()
        if self.threshold:
            result["threshold"] = self.threshold.to_dict()
        if self.suppressions:
            result["suppressions"] = [s.to_dict() for s in self.suppressions]
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyRule:
        """Create from dictionary."""
        # Parse effect with backward compatibility (default to DENY)
        effect = PolicyEffect.DENY
        if "effect" in data:
            effect = PolicyEffect(data["effect"])

        # Parse priority with backward compatibility (default to MEDIUM)
        priority = PolicyPriority.MEDIUM
        if "priority" in data:
            priority = PolicyPriority[data["priority"]]

        rule = cls(
            id=data["id"],
            description=data["description"],
            severity=Severity(data["severity"]),
            category=data["category"],
            target=data["target"],
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
            suggestion=data.get("suggestion"),
            effect=effect,
            priority=priority,
        )
        if "matchers" in data:
            rule.matchers = [Matcher.from_dict(m) for m in data["matchers"]]
        if "all_of" in data:
            rule.all_of = [cls.from_dict(r) for r in data["all_of"]]
        if "any_of" in data:
            rule.any_of = [cls.from_dict(r) for r in data["any_of"]]
        if "not_match" in data:
            rule.not_match = cls.from_dict(data["not_match"])
        if "threshold" in data:
            rule.threshold = Threshold.from_dict(data["threshold"])
        if "suppressions" in data:
            rule.suppressions = [Suppression.from_dict(s) for s in data["suppressions"]]
        return rule


@dataclass
class PolicyPack:
    """A collection of policy rules.

    Attributes:
        name: Pack name
        description: Pack description
        version: Semantic version
        rules: List of rules
        metadata: Pack metadata
    """

    name: str
    description: str
    version: str
    rules: list[PolicyRule] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure pack has valid version."""
        if not self.version:
            self.version = "1.0.0"

    def get_enabled_rules(self) -> list[PolicyRule]:
        """Get all enabled rules."""
        return [r for r in self.rules if r.enabled]

    def get_rule(self, rule_id: str) -> PolicyRule | None:
        """Get rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def compute_hash(self) -> str:
        """Compute content hash for integrity."""
        content = str(sorted(self.to_dict().items()))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "metadata": dict(sorted(self.metadata.items())),
            "_hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyPack:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0.0"),
            rules=[PolicyRule.from_dict(r) for r in data.get("rules", [])],
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> PolicyPack:
        """Load pack from YAML file."""
        text = safe_read_text(path)
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid policy pack format in {path}")
        return cls.from_dict(data)

    def write_yaml(self, path: Path) -> None:
        """Write pack to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=True)
