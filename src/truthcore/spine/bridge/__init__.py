"""Integration bridge between TruthCore and Spine.

Connects existing TruthCore engines to the Spine for recording
assertions, evidence, and decisions.
"""

from __future__ import annotations

from typing import Any

from truthcore.spine.graph import GraphStore
from truthcore.spine.ingest import IngestionBridge
from truthcore.spine.primitives import Decision as SpineDecision
from truthcore.spine.primitives import DecisionType
from truthcore.spine.primitives import Override as SpineOverride


class SpineBridge:
    """High-level bridge for integrating TruthCore with Spine.

    Records findings, verdicts, and overrides as spine primitives.
    """

    def __init__(self, store: GraphStore | None = None, enabled: bool = False):
        self.enabled = enabled
        self.store = store
        self.ingestion = IngestionBridge(store, enabled=enabled)

    def record_finding(self, finding: Any) -> bool:
        """Record a finding from any TruthCore engine."""
        if not self.enabled:
            return False
        return self.ingestion.record_finding(finding)

    def record_verdict(self, verdict: Any, actor: str = "system") -> bool:
        """Record a verdict as a decision."""
        if not self.enabled:
            return False
        return self.ingestion.record_verdict(verdict, actor)

    def record_override(
        self,
        original: str,
        override: str,
        actor: str,
        rationale: str,
        authority_scope: str = "default",
        expires_at: str | None = None,
    ) -> bool:
        """Record a human override."""
        if not self.enabled:
            return False

        # First ingest as signal
        self.ingestion.record_override(original, override, actor, rationale)

        # Also store as formal Override record
        if self.store and expires_at:
            from datetime import UTC, datetime
            override_record = SpineOverride(
                override_id=f"override_{original}_{datetime.now(UTC).isoformat()}",
                original_decision=original,
                override_decision=override,
                actor=actor,
                authority_scope=authority_scope,
                rationale=rationale,
                expires_at=expires_at,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._store_override(override_record)

        return True

    def _store_override(self, override: SpineOverride) -> None:
        """Store override record."""
        import json
        from datetime import datetime

        # Store in overrides directory
        ts = datetime.fromisoformat(override.created_at.replace('Z', '+00:00'))
        override_dir = self.store.base_path / "overrides" / f"{ts.year}" / f"{ts.month:02d}-{ts.day:02d}"
        override_dir.mkdir(parents=True, exist_ok=True)

        path = override_dir / f"{override.override_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(override.to_dict(), f, indent=2, sort_keys=True)

    def shutdown(self) -> None:
        """Shutdown the bridge."""
        if self.ingestion:
            self.ingestion.shutdown()


class SpineConfig:
    """Configuration for Spine integration."""

    def __init__(
        self,
        enabled: bool = False,
        storage_path: str = ".truthcore/spine",
        assertions: bool = True,
        beliefs: bool = True,
        decisions: bool = True,
        overrides: bool = True,
    ):
        self.enabled = enabled
        self.storage_path = storage_path
        self.assertions = assertions
        self.beliefs = beliefs
        self.decisions = decisions
        self.overrides = overrides

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpineConfig:
        """Create config from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            storage_path=data.get("storage_path", ".truthcore/spine"),
            assertions=data.get("assertions", True),
            beliefs=data.get("beliefs", True),
            decisions=data.get("decisions", True),
            overrides=data.get("overrides", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "storage_path": self.storage_path,
            "assertions": self.assertions,
            "beliefs": self.beliefs,
            "decisions": self.decisions,
            "overrides": self.overrides,
        }
