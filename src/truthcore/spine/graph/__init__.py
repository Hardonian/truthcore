"""Content-addressed graph storage for TruthCore Spine.

Provides DAG storage with lineage tracking and deterministic replay support.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from truthcore.spine.primitives import Assertion, Evidence


class GraphStore:
    """Content-addressed storage for assertions and evidence.

    Uses a directory structure with hash prefixes for efficient
    file system storage and lookup.
    """

    def __init__(self, base_path: str | Path = ".truthcore/spine"):
        self.base_path = Path(base_path)
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        dirs = ["assertions", "evidence", "beliefs", "decisions", "overrides", "meanings", "contradictions", "indices"]
        for d in dirs:
            (self.base_path / d).mkdir(parents=True, exist_ok=True)

    def _hash_path(self, hash_id: str, subdir: str) -> Path:
        """Get storage path for a hash ID."""
        prefix = hash_id[:2]
        return self.base_path / subdir / prefix / f"{hash_id}.json"

    def _id_path(self, id_str: str, subdir: str) -> Path:
        """Get storage path for an ID string."""
        # For IDs that aren't hashes (like assertion_id), use full string
        if len(id_str) >= 2:
            prefix = id_str[:2]
            return self.base_path / subdir / prefix / f"{id_str}.json"
        return self.base_path / subdir / f"{id_str}.json"

    def store_assertion(self, assertion: Assertion) -> Path:
        """Store an assertion."""
        path = self._hash_path(assertion.assertion_id, "assertions")
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(assertion.to_dict(), f, indent=2, sort_keys=True)

        # Update index
        self._update_index("by_timestamp", assertion.timestamp, assertion.assertion_id)
        self._update_index("by_source", assertion.source, assertion.assertion_id)

        return path

    def get_assertion(self, assertion_id: str) -> Assertion | None:
        """Retrieve an assertion by ID."""
        path = self._hash_path(assertion_id, "assertions")
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return Assertion.from_dict(data)

    def assertion_exists(self, assertion_id: str) -> bool:
        """Check if an assertion exists without loading it."""
        path = self._hash_path(assertion_id, "assertions")
        return path.exists()

    def store_evidence(self, evidence: Evidence) -> Path:
        """Store evidence."""
        path = self._hash_path(evidence.evidence_id, "evidence")
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(evidence.to_dict(), f, indent=2, sort_keys=True)

        return path

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        """Retrieve evidence by ID."""
        path = self._hash_path(evidence_id, "evidence")
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return Evidence.from_dict(data)

    def get_evidence_batch(self, evidence_ids: list[str]) -> dict[str, Evidence]:
        """Retrieve multiple evidence items efficiently."""
        result = {}
        for eid in evidence_ids:
            ev = self.get_evidence(eid)
            if ev:
                result[eid] = ev
        return result

    def list_assertions(self, since: str | None = None, source: str | None = None) -> list[str]:
        """List assertion IDs with optional filtering."""
        assertion_dir = self.base_path / "assertions"
        if not assertion_dir.exists():
            return []

        ids = []
        for prefix_dir in assertion_dir.iterdir():
            if prefix_dir.is_dir():
                for f in prefix_dir.glob("*.json"):
                    assertion_id = f.stem

                    # Apply filters
                    if since or source:
                        assertion = self.get_assertion(assertion_id)
                        if not assertion:
                            continue
                        if since and assertion.timestamp < since:
                            continue
                        if source and assertion.source != source:
                            continue

                    ids.append(assertion_id)

        return sorted(ids)

    def get_lineage(self, assertion_id: str, max_depth: int = 10) -> AssertionLineage:
        """Get lineage for an assertion (upstream evidence and assertions)."""
        return AssertionLineage.compute(self, assertion_id, max_depth)

    def _update_index(self, index_name: str, key: str, value: str) -> None:
        """Update an index file."""
        index_path = self.base_path / "indices" / f"{index_name}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        index_data = {}
        if index_path.exists():
            with open(index_path, encoding="utf-8") as f:
                index_data = json.load(f)

        if key not in index_data:
            index_data[key] = []
        if value not in index_data[key]:
            index_data[key].append(value)

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, sort_keys=True)

    def get_index(self, index_name: str) -> dict[str, list[str]]:
        """Get an index by name."""
        index_path = self.base_path / "indices" / f"{index_name}.json"
        if not index_path.exists():
            return {}

        with open(index_path, encoding="utf-8") as f:
            return json.load(f)

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        stats = {
            "base_path": str(self.base_path),
            "assertions": 0,
            "evidence": 0,
            "total_size_bytes": 0,
        }

        for subdir in ["assertions", "evidence", "beliefs", "decisions", "overrides", "meanings"]:
            dir_path = self.base_path / subdir
            if dir_path.exists():
                count = 0
                size = 0
                for f in dir_path.rglob("*.json"):
                    count += 1
                    size += f.stat().st_size
                stats[subdir] = count
                stats["total_size_bytes"] += size

        return stats


class AssertionLineage:
    """Provenance chain for an assertion."""

    def __init__(
        self,
        root_assertion: Assertion,
        upstream_assertions: list[Assertion],
        evidence_chain: list[Evidence],
        transformations: list[str],
        depth: int,
    ):
        self.root_assertion = root_assertion
        self.upstream_assertions = upstream_assertions
        self.evidence_chain = evidence_chain
        self.transformations = transformations
        self.depth = depth

    @classmethod
    def compute(cls, store: GraphStore, assertion_id: str, max_depth: int = 10) -> AssertionLineage:
        """Compute lineage for an assertion."""
        root = store.get_assertion(assertion_id)
        if not root:
            raise ValueError(f"Assertion not found: {assertion_id}")

        upstream_assertions = []
        evidence_chain = []
        transformations = []
        visited = {assertion_id}
        queue = [(root, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Collect evidence
            for evidence_id in current.evidence_ids:
                evidence = store.get_evidence(evidence_id)
                if evidence and evidence not in evidence_chain:
                    evidence_chain.append(evidence)

            # Note transformation
            if current.claim_type.value in ["derived", "inferred"]:
                transformations.append(f"{current.source}: {current.claim_type.value}")

            # TODO: Follow upstream assertions (when we have assertion-to-assertion links)
            # For now, evidence is the upstream

        return cls(
            root_assertion=root,
            upstream_assertions=upstream_assertions,
            evidence_chain=evidence_chain,
            transformations=transformations,
            depth=len(visited) - 1,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "root_assertion": self.root_assertion.to_dict(),
            "upstream_assertions": [a.to_dict() for a in self.upstream_assertions],
            "evidence_chain": [e.to_dict() for e in self.evidence_chain],
            "transformations": self.transformations,
            "depth": self.depth,
        }
