"""Change Impact Engine - analyze git diffs to determine what engines/invariants to run."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ImpactLevel(Enum):
    """Impact levels for changes."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(Enum):
    """Types of file changes."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    """Represents a single file change."""

    path: str
    change_type: ChangeType
    old_path: str | None = None
    diff_content: str | None = None
    impact_level: ImpactLevel = ImpactLevel.NONE
    affected_entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "old_path": self.old_path,
            "diff_content": self.diff_content,
            "impact_level": self.impact_level.value,
            "affected_entities": sorted(self.affected_entities),
        }


@dataclass
class EngineDecision:
    """Decision for a specific engine."""

    engine_id: str
    include: bool
    reason: str
    priority: int
    impact_level: ImpactLevel
    affected_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "include": self.include,
            "reason": self.reason,
            "priority": self.priority,
            "impact_level": self.impact_level.value,
            "affected_files": sorted(self.affected_files),
        }


@dataclass
class InvariantDecision:
    """Decision for a specific invariant rule."""

    rule_id: str
    include: bool
    reason: str
    impact_level: ImpactLevel
    affected_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "include": self.include,
            "reason": self.reason,
            "impact_level": self.impact_level.value,
            "affected_files": sorted(self.affected_files),
        }


@dataclass
class RunPlan:
    """Complete run plan generated from change analysis."""

    version: str
    timestamp: str
    source: str
    source_type: str
    impact_summary: dict[str, Any]
    engines: list[EngineDecision]
    invariants: list[InvariantDecision]
    exclusions: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    cache_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "source": self.source,
            "source_type": self.source_type,
            "cache_key": self.cache_key,
            "impact_summary": self.impact_summary,
            "engines": [e.to_dict() for e in self.engines],
            "invariants": [i.to_dict() for i in self.invariants],
            "exclusions": self.exclusions,
            "metadata": dict(sorted(self.metadata.items())),
        }

    def write(self, output_path: Path) -> None:
        """Write run plan to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=False)


class GitDiffParser:
    """Parse git diff output into structured file changes."""

    DIFF_HEADER_PATTERN = re.compile(r"^diff --git a/(.+) b/(.+)$")
    INDEX_PATTERN = re.compile(r"^index [a-f0-9]+\.\.[a-f0-9]+")
    NEW_FILE_PATTERN = re.compile(r"^new file mode")
    DELETED_FILE_PATTERN = re.compile(r"^deleted file mode")
    RENAME_PATTERN = re.compile(r"^rename from (.+) to (.+)$")
    HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    def __init__(self, diff_text: str | None = None, changed_files: list[str] | None = None):
        self.diff_text = diff_text or ""
        self.changed_files = changed_files or []
        self.changes: list[FileChange] = []

    def parse(self) -> list[FileChange]:
        """Parse diff text and/or changed files list."""
        if self.diff_text:
            self._parse_diff_text()
        
        if self.changed_files:
            self._parse_changed_files()
        
        return self.changes

    def _parse_diff_text(self) -> None:
        """Parse git diff text into file changes."""
        if not self.diff_text:
            return

        lines = self.diff_text.split("\n")
        current_change: FileChange | None = None
        current_diff_lines: list[str] = []

        for line in lines:
            # Check for diff header
            if match := self.DIFF_HEADER_PATTERN.match(line):
                # Save previous change
                if current_change:
                    current_change.diff_content = "\n".join(current_diff_lines)
                    self.changes.append(current_change)
                    current_diff_lines = []

                old_path, new_path = match.groups()
                change_type = ChangeType.MODIFIED
                current_change = FileChange(
                    path=new_path,
                    change_type=change_type,
                    old_path=old_path if old_path != new_path else None,
                )
                continue

            # Check for new file
            if self.NEW_FILE_PATTERN.match(line):
                if current_change:
                    current_change.change_type = ChangeType.ADDED
                continue

            # Check for deleted file
            if self.DELETED_FILE_PATTERN.match(line):
                if current_change:
                    current_change.change_type = ChangeType.DELETED
                continue

            # Check for rename
            if match := self.RENAME_PATTERN.match(line):
                if current_change:
                    current_change.old_path = match.group(1)
                    current_change.change_type = ChangeType.RENAMED
                continue

            # Accumulate diff content
            if current_change:
                current_diff_lines.append(line)

        # Save last change
        if current_change:
            current_change.diff_content = "\n".join(current_diff_lines)
            self.changes.append(current_change)

    def _parse_changed_files(self) -> None:
        """Parse simple changed files list."""
        existing_paths = {c.path for c in self.changes}
        
        for path in self.changed_files:
            if path not in existing_paths:
                self.changes.append(FileChange(
                    path=path,
                    change_type=ChangeType.MODIFIED,
                ))


class ImpactAnalyzer:
    """Analyze file changes to determine impact levels and affected entities."""

    # File patterns and their associated impact levels
    IMPACT_PATTERNS: dict[str, ImpactLevel] = {
        # Critical - security, core configs
        r"(\.env|secrets|credentials|private_key)": ImpactLevel.CRITICAL,
        r"(security|auth|crypto|encryption)": ImpactLevel.CRITICAL,
        # High - core logic, APIs, databases
        r"(api|endpoint|route|controller)": ImpactLevel.HIGH,
        r"(model|schema|migration)": ImpactLevel.HIGH,
        r"(engine|invariant|rule)": ImpactLevel.HIGH,
        r"(core|base|main|init)\.py$": ImpactLevel.HIGH,
        # Medium - adapters, utilities, tests
        r"(adapter|client|wrapper|util)": ImpactLevel.MEDIUM,
        r"(test|spec)\.py$": ImpactLevel.MEDIUM,
        r"_test\.py$": ImpactLevel.MEDIUM,
        # Low - docs, config files
        r"\.(md|rst|txt)$": ImpactLevel.LOW,
        r"(README|CHANGELOG|LICENSE)": ImpactLevel.LOW,
        r"\.(json|yaml|yml|toml)$": ImpactLevel.LOW,
    }

    # Entity extraction patterns
    ENTITY_PATTERNS: dict[str, list[str]] = {
        "file_path": [r"^(.+)$"],
        "route": [r"(?:@|\.)(route|get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)"],
        "component": [r"(?:class|def|function)\s+(\w+)[\s\(:]"],
        "api_endpoint": [r"(?:endpoint|url|path)\s*[=:]\s*['\"]([^'\"]+)"],
        "dependency": [r"(?:import|from|require)\s+([\w\.]+)"],
        "invariant_rule": [r"rule[:\s]+['\"](\w+)['\"]"],
    }

    def __init__(self, changes: list[FileChange]):
        self.changes = changes

    def analyze(self) -> list[FileChange]:
        """Analyze all changes and update impact levels and entities."""
        for change in self.changes:
            self._analyze_impact(change)
            self._extract_entities(change)
        return self.changes

    def _analyze_impact(self, change: FileChange) -> None:
        """Determine impact level for a file change."""
        path = change.path.lower()
        max_impact = ImpactLevel.NONE

        # Check patterns
        for pattern, level in self.IMPACT_PATTERNS.items():
            if re.search(pattern, path, re.IGNORECASE):
                if self._impact_value(level) > self._impact_value(max_impact):
                    max_impact = level

        # Special handling for change types
        if change.change_type == ChangeType.DELETED:
            # Deleted files always at least medium impact
            if self._impact_value(max_impact) < self._impact_value(ImpactLevel.MEDIUM):
                max_impact = ImpactLevel.MEDIUM
        elif change.change_type == ChangeType.ADDED:
            # New files with core patterns are high impact
            if max_impact in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]:
                pass  # Keep existing high impact

        change.impact_level = max_impact

    def _extract_entities(self, change: FileChange) -> None:
        """Extract affected entities from a file change."""
        entities: list[str] = []
        
        # Always include the file path
        entities.append(f"file_path:{change.path}")

        # Extract from diff content if available
        if change.diff_content:
            content = change.diff_content
            
            # Extract routes
            for match in re.finditer(
                r"(?:@|\.)(?:route|get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
                content
            ):
                entities.append(f"route:{match.group(1)}")
            
            # Extract components (classes/functions)
            for match in re.finditer(
                r"(?:class|def)\s+(\w+)",
                content
            ):
                entities.append(f"component:{match.group(1)}")
            
            # Extract dependencies
            for match in re.finditer(
                r"(?:import|from)\s+([\w\.]+)",
                content
            ):
                entities.append(f"dependency:{match.group(1)}")

        change.affected_entities = list(set(entities))

    def _impact_value(self, level: ImpactLevel) -> int:
        """Get numeric value for impact level comparison."""
        values = {
            ImpactLevel.NONE: 0,
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4,
        }
        return values.get(level, 0)


class EngineSelector:
    """Select which engines to run based on impact analysis."""

    # Engine definitions with their triggers
    ENGINE_DEFINITIONS: dict[str, dict[str, Any]] = {
        "readiness": {
            "description": "Readiness verification engine",
            "triggers": {
                "file_patterns": [r"\.(py|js|ts|jsx|tsx)$"],
                "entities": ["route:", "component:", "api_endpoint:"],
                "min_impact": ImpactLevel.LOW,
            },
            "priority": 1,
        },
        "reconciliation": {
            "description": "Financial/data reconciliation engine",
            "triggers": {
                "file_patterns": [r"(data|model|schema|migration)"],
                "entities": ["dependency:truthcore"],
                "min_impact": ImpactLevel.MEDIUM,
            },
            "priority": 2,
        },
        "agent_trace": {
            "description": "Agent execution trace analysis",
            "triggers": {
                "file_patterns": [r"(agent|trace|flow)"],
                "entities": ["component:Agent", "component:Trace"],
                "min_impact": ImpactLevel.LOW,
            },
            "priority": 3,
        },
        "knowledge": {
            "description": "Knowledge base indexing engine",
            "triggers": {
                "file_patterns": [r"\.(md|rst|txt)$"],
                "entities": ["invariant_rule:"],
                "min_impact": ImpactLevel.LOW,
            },
            "priority": 4,
        },
        "ui_geometry": {
            "description": "UI geometry and reachability verification",
            "triggers": {
                "file_patterns": [r"(ui|frontend|html|css|component)"],
                "entities": ["component:UI", "file_path:ui_facts"],
                "min_impact": ImpactLevel.LOW,
            },
            "priority": 5,
        },
        "security": {
            "description": "Security analysis engine",
            "triggers": {
                "file_patterns": [r".*"],  # All files
                "entities": ["dependency:crypto", "dependency:auth"],
                "min_impact": ImpactLevel.CRITICAL,
            },
            "priority": 0,  # Always run for critical changes
        },
    }

    INVARIANT_DEFINITIONS: dict[str, dict[str, Any]] = {
        "no_critical_errors": {
            "description": "No critical or high severity errors",
            "triggers": {
                "min_impact": ImpactLevel.MEDIUM,
                "applies_to": ["readiness", "agent_trace"],
            },
        },
        "api_contract_compliance": {
            "description": "API endpoints follow contract specifications",
            "triggers": {
                "entities": ["route:", "api_endpoint:"],
                "min_impact": ImpactLevel.MEDIUM,
                "applies_to": ["readiness"],
            },
        },
        "data_integrity": {
            "description": "Data reconciliation integrity checks",
            "triggers": {
                "file_patterns": [r"(data|model|schema)"],
                "min_impact": ImpactLevel.HIGH,
                "applies_to": ["reconciliation"],
            },
        },
        "agent_safety": {
            "description": "Agent execution safety constraints",
            "triggers": {
                "file_patterns": [r"agent"],
                "entities": ["component:Agent"],
                "min_impact": ImpactLevel.HIGH,
                "applies_to": ["agent_trace"],
            },
        },
        "determinism_check": {
            "description": "Verify deterministic outputs",
            "triggers": {
                "min_impact": ImpactLevel.MEDIUM,
                "applies_to": ["readiness", "reconciliation", "agent_trace"],
            },
        },
    }

    def __init__(self, changes: list[FileChange], profile: str | None = None):
        self.changes = changes
        self.profile = profile or "default"
        self.all_entities = self._collect_entities()
        self.max_impact = self._compute_max_impact()

    def _collect_entities(self) -> set[str]:
        """Collect all affected entities from changes."""
        entities: set[str] = set()
        for change in self.changes:
            entities.update(change.affected_entities)
        return entities

    def _compute_max_impact(self) -> ImpactLevel:
        """Compute maximum impact level across all changes."""
        max_level = ImpactLevel.NONE
        for change in self.changes:
            if self._impact_value(change.impact_level) > self._impact_value(max_level):
                max_level = change.impact_level
        return max_level

    def select_engines(self) -> list[EngineDecision]:
        """Select engines to run based on changes."""
        decisions: list[EngineDecision] = []
        
        for engine_id, definition in sorted(
            self.ENGINE_DEFINITIONS.items(),
            key=lambda x: x[1]["priority"]
        ):
            decision = self._evaluate_engine(engine_id, definition)
            decisions.append(decision)
        
        return decisions

    def select_invariants(self, selected_engines: list[str]) -> list[InvariantDecision]:
        """Select invariant rules to run based on changes and engines."""
        decisions: list[InvariantDecision] = []
        
        for rule_id, definition in self.INVARIANT_DEFINITIONS.items():
            decision = self._evaluate_invariant(rule_id, definition, selected_engines)
            decisions.append(decision)
        
        return decisions

    def _evaluate_engine(self, engine_id: str, definition: dict[str, Any]) -> EngineDecision:
        """Evaluate whether an engine should be included."""
        triggers = definition["triggers"]
        min_impact = triggers.get("min_impact", ImpactLevel.LOW)
        
        # Check if max impact meets minimum
        if self._impact_value(self.max_impact) < self._impact_value(min_impact):
            return EngineDecision(
                engine_id=engine_id,
                include=False,
                reason=f"Max impact ({self.max_impact.value}) below threshold ({min_impact.value})",
                priority=definition["priority"],
                impact_level=self.max_impact,
            )
        
        # Check file patterns
        file_patterns = triggers.get("file_patterns", [])
        matching_files: list[str] = []
        
        for change in self.changes:
            for pattern in file_patterns:
                if re.search(pattern, change.path, re.IGNORECASE):
                    matching_files.append(change.path)
                    break
        
        # Check entity patterns
        entity_patterns = triggers.get("entities", [])
        matching_entities: list[str] = []
        
        for entity in self.all_entities:
            for pattern in entity_patterns:
                if pattern in entity:
                    matching_entities.append(entity)
                    break
        
        # Decision logic
        if matching_files or matching_entities:
            affected = list(set(matching_files))
            return EngineDecision(
                engine_id=engine_id,
                include=True,
                reason=f"Matched {len(matching_files)} files, {len(matching_entities)} entities",
                priority=definition["priority"],
                impact_level=self.max_impact,
                affected_files=affected,
            )
        
        # Security engine always runs on critical changes
        if engine_id == "security" and self.max_impact == ImpactLevel.CRITICAL:
            return EngineDecision(
                engine_id=engine_id,
                include=True,
                reason="Critical impact changes detected - security scan required",
                priority=0,
                impact_level=ImpactLevel.CRITICAL,
            )
        
        return EngineDecision(
            engine_id=engine_id,
            include=False,
            reason="No matching patterns or entities",
            priority=definition["priority"],
            impact_level=self.max_impact,
        )

    def _evaluate_invariant(
        self,
        rule_id: str,
        definition: dict[str, Any],
        selected_engines: list[str],
    ) -> InvariantDecision:
        """Evaluate whether an invariant should be included."""
        triggers = definition["triggers"]
        min_impact = triggers.get("min_impact", ImpactLevel.LOW)
        applies_to = triggers.get("applies_to", [])
        
        # Check if applicable to selected engines
        applicable_engines = [e for e in selected_engines if e in applies_to]
        
        if not applicable_engines:
            return InvariantDecision(
                rule_id=rule_id,
                include=False,
                reason=f"Not applicable to selected engines ({', '.join(selected_engines)})",
                impact_level=self.max_impact,
            )
        
        # Check impact level
        if self._impact_value(self.max_impact) < self._impact_value(min_impact):
            return InvariantDecision(
                rule_id=rule_id,
                include=False,
                reason=f"Impact ({self.max_impact.value}) below threshold ({min_impact.value})",
                impact_level=self.max_impact,
            )
        
        # Check file patterns
        file_patterns = triggers.get("file_patterns", [])
        matching_files: list[str] = []
        
        for change in self.changes:
            for pattern in file_patterns:
                if re.search(pattern, change.path, re.IGNORECASE):
                    matching_files.append(change.path)
                    break
        
        # Check entity patterns
        entity_patterns = triggers.get("entities", [])
        matching_entities: list[str] = []
        
        for entity in self.all_entities:
            for pattern in entity_patterns:
                if pattern in entity:
                    matching_entities.append(entity)
                    break
        
        if matching_files or matching_entities:
            return InvariantDecision(
                rule_id=rule_id,
                include=True,
                reason=f"Applicable to engines: {', '.join(applicable_engines)}",
                impact_level=self.max_impact,
                affected_files=list(set(matching_files)),
            )
        
        return InvariantDecision(
            rule_id=rule_id,
            include=True,
            reason=f"Applicable to engines: {', '.join(applicable_engines)} (general coverage)",
            impact_level=self.max_impact,
        )

    def _impact_value(self, level: ImpactLevel) -> int:
        """Get numeric value for impact level comparison."""
        values = {
            ImpactLevel.NONE: 0,
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4,
        }
        return values.get(level, 0)


class ChangeImpactEngine:
    """Main engine for analyzing changes and generating run plans."""

    VERSION = "1.0.0"

    def __init__(self):
        self.changes: list[FileChange] = []
        self.plan: RunPlan | None = None

    def analyze(
        self,
        diff_text: str | None = None,
        changed_files: list[str] | None = None,
        profile: str | None = None,
        source: str | None = None,
    ) -> RunPlan:
        """Analyze changes and generate run plan.
        
        Args:
            diff_text: Git diff text to analyze
            changed_files: List of changed file paths
            profile: Execution profile to use
            source: Source identifier for the analysis
            
        Returns:
            RunPlan with selected engines and invariants
        """
        from truthcore.manifest import normalize_timestamp, hash_dict
        
        # Parse changes
        parser = GitDiffParser(diff_text, changed_files)
        self.changes = parser.parse()
        
        # Analyze impact
        analyzer = ImpactAnalyzer(self.changes)
        analyzer.analyze()
        
        # Select engines and invariants
        selector = EngineSelector(self.changes, profile)
        engine_decisions = selector.select_engines()
        
        # Get selected engine IDs for invariant selection
        selected_engines = [e.engine_id for e in engine_decisions if e.include]
        invariant_decisions = selector.select_invariants(selected_engines)
        
        # Generate exclusions with reasons
        exclusions = []
        for engine in engine_decisions:
            if not engine.include:
                exclusions.append({
                    "type": "engine",
                    "id": engine.engine_id,
                    "reason": engine.reason,
                })
        
        for invariant in invariant_decisions:
            if not invariant.include:
                exclusions.append({
                    "type": "invariant",
                    "id": invariant.rule_id,
                    "reason": invariant.reason,
                })
        
        # Compute impact summary
        impact_counts: dict[str, int] = {}
        for change in self.changes:
            level = change.impact_level.value
            impact_counts[level] = impact_counts.get(level, 0) + 1
        
        # Create run plan
        self.plan = RunPlan(
            version=self.VERSION,
            timestamp=normalize_timestamp(),
            source=source or "unknown",
            source_type="git_diff" if diff_text else "file_list",
            impact_summary={
                "total_changes": len(self.changes),
                "impact_distribution": impact_counts,
                "max_impact": selector.max_impact.value,
                "affected_entities_count": len(selector.all_entities),
            },
            engines=engine_decisions,
            invariants=invariant_decisions,
            exclusions=exclusions,
            metadata={
                "profile": profile or "default",
                "analyzer_version": self.VERSION,
            },
        )
        
        # Compute cache key
        plan_dict = self.plan.to_dict()
        self.plan.cache_key = hash_dict(plan_dict)
        
        return self.plan

    def load_diff_from_file(self, path: Path) -> str:
        """Load diff text from file."""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def load_changed_files_from_file(self, path: Path) -> list[str]:
        """Load changed files list from file."""
        with open(path, encoding="utf-8") as f:
            content = f.read()
            # Support both JSON arrays and newline-separated files
            if content.strip().startswith("["):
                return json.loads(content)
            return [line.strip() for line in content.split("\n") if line.strip()]
