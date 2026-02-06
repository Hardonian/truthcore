"""Deterministic diff computation for replay verification.

Provides content-aware diffing that ignores specified fields and
normalizes values for deterministic comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truthcore.manifest import hash_dict


@dataclass
class DiffEntry:
    """A single diff entry representing a difference between two values.

    Attributes:
        path: JSON path to the differing field
        old_value: Value from the original/baseline
        new_value: Value from the new/comparison
        diff_type: Type of difference (added, removed, changed, normalized)
    """

    path: str
    old_value: Any
    new_value: Any
    diff_type: str  # 'changed', 'added', 'removed', 'normalized', 'allowed'


@dataclass
class DeterministicDiff:
    """Deterministic diff result with content-aware comparison.

    Attributes:
        identical: Whether the two documents are considered identical
        total_differences: Total number of differences found
        content_differences: Differences in content (not in allowlist)
        allowed_differences: Differences in allowed fields
        normalized_differences: Differences that were normalized away
        entries: List of all diff entries
    """

    identical: bool
    total_differences: int
    content_differences: int
    allowed_differences: int
    normalized_differences: int
    entries: list[DiffEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identical": self.identical,
            "total_differences": self.total_differences,
            "content_differences": self.content_differences,
            "allowed_differences": self.allowed_differences,
            "normalized_differences": self.normalized_differences,
            "entries": [
                {
                    "path": e.path,
                    "old_value": e.old_value,
                    "new_value": e.new_value,
                    "diff_type": e.diff_type,
                }
                for e in self.entries
            ],
        }

    def to_markdown(self) -> str:
        """Generate markdown report of differences."""
        if self.identical:
            return "# Diff Report\n\n✅ Documents are identical (content-wise)\n"

        lines = [
            "# Diff Report",
            "",
            f"**Status:** {'❌ DIFFERENCES FOUND' if self.content_differences > 0 else '✅ Equivalent (content-only)'}",
            "",
            "## Summary",
            "",
            f"- **Total Differences:** {self.total_differences}",
            f"- **Content Differences:** {self.content_differences}",
            f"- **Allowed Differences:** {self.allowed_differences}",
            f"- **Normalized Differences:** {self.normalized_differences}",
            "",
        ]

        if self.content_differences > 0:
            lines.extend(["## Content Differences", ""])
            for entry in self.entries:
                if entry.diff_type == "changed":
                    lines.append(f"### `{entry.path}`")
                    lines.append(f"- Old: `{json.dumps(entry.old_value)}`")
                    lines.append(f"- New: `{json.dumps(entry.new_value)}`")
                    lines.append("")

        if self.allowed_differences > 0:
            lines.extend(["## Allowed Differences", ""])
            for entry in self.entries:
                if entry.diff_type == "allowed":
                    lines.append(f"- `{entry.path}`: `{entry.old_value}` → `{entry.new_value}`")
            lines.append("")

        return "\n".join(lines)


class DiffComputer:
    """Computes deterministic diffs between JSON documents.

    This handles:
    - Field allowlists (fields that can differ)
    - Value normalization (timestamps, etc.)
    - Deep comparison of nested structures
    - Sorting of arrays for determinism
    """

    def __init__(
        self,
        allowlist: set[str] | None = None,
        normalize_timestamps: bool = True,
    ):
        self.allowlist = allowlist or set()
        self.normalize_timestamps = normalize_timestamps

    def compute(
        self,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        path_prefix: str = "$",
    ) -> DeterministicDiff:
        """Compute diff between two JSON documents.

        Args:
            old_data: Baseline/original document
            new_data: New/comparison document
            path_prefix: JSONPath prefix for this comparison

        Returns:
            DeterministicDiff with all differences
        """
        entries: list[DiffEntry] = []

        self._compare_objects(old_data, new_data, path_prefix, entries)

        # Count by type
        content_diffs = sum(1 for e in entries if e.diff_type == "changed")
        allowed_diffs = sum(1 for e in entries if e.diff_type == "allowed")
        normalized_diffs = sum(1 for e in entries if e.diff_type == "normalized")

        # Documents are identical if no content differences
        identical = content_diffs == 0

        return DeterministicDiff(
            identical=identical,
            total_differences=len(entries),
            content_differences=content_diffs,
            allowed_differences=allowed_diffs,
            normalized_differences=normalized_diffs,
            entries=entries,
        )

    def compute_files(
        self,
        old_file: Path,
        new_file: Path,
    ) -> DeterministicDiff:
        """Compute diff between two JSON files.

        Args:
            old_file: Path to baseline file
            new_file: Path to comparison file

        Returns:
            DeterministicDiff
        """
        with open(old_file, encoding="utf-8") as f:
            old_data = json.load(f)

        with open(new_file, encoding="utf-8") as f:
            new_data = json.load(f)

        return self.compute(old_data, new_data)

    def _compare_objects(
        self,
        old_obj: Any,
        new_obj: Any,
        path: str,
        entries: list[DiffEntry],
    ) -> None:
        """Recursively compare two objects."""
        # Handle type mismatches
        if type(old_obj) is not type(new_obj):
            self._add_entry(path, old_obj, new_obj, entries)
            return

        # Handle dictionaries
        if isinstance(old_obj, dict):
            self._compare_dicts(old_obj, new_obj, path, entries)
            return

        # Handle lists
        if isinstance(old_obj, list):
            self._compare_lists(old_obj, new_obj, path, entries)
            return

        # Handle primitive values
        if old_obj != new_obj:
            self._add_entry(path, old_obj, new_obj, entries)

    def _compare_dicts(
        self,
        old_dict: dict[str, Any],
        new_dict: dict[str, Any],
        path: str,
        entries: list[DiffEntry],
    ) -> None:
        """Compare two dictionaries."""
        old_keys = set(old_dict.keys())
        new_keys = set(new_dict.keys())

        # Check for removed keys
        for key in old_keys - new_keys:
            field_path = f"{path}.{key}"
            self._add_entry(field_path, old_dict[key], None, entries, diff_type="removed")

        # Check for added keys
        for key in new_keys - old_keys:
            field_path = f"{path}.{key}"
            self._add_entry(field_path, None, new_dict[key], entries, diff_type="added")

        # Compare common keys
        for key in old_keys & new_keys:
            field_path = f"{path}.{key}"

            # Check if this field is in the allowlist
            if key in self.allowlist or field_path in self.allowlist:
                if old_dict[key] != new_dict[key]:
                    entries.append(
                        DiffEntry(
                            path=field_path,
                            old_value=old_dict[key],
                            new_value=new_dict[key],
                            diff_type="allowed",
                        )
                    )
                continue

            self._compare_objects(old_dict[key], new_dict[key], field_path, entries)

    def _compare_lists(
        self,
        old_list: list[Any],
        new_list: list[Any],
        path: str,
        entries: list[DiffEntry],
    ) -> None:
        """Compare two lists.

        For determinism, we sort lists of dictionaries by a canonical key
        before comparison.
        """
        if len(old_list) != len(new_list):
            self._add_entry(path, old_list, new_list, entries)
            return

        # Try to sort for determinism if items are dicts with sortable keys
        old_sorted = self._sort_list(old_list)
        new_sorted = self._sort_list(new_list)

        for i, (old_item, new_item) in enumerate(zip(old_sorted, new_sorted, strict=True)):
            item_path = f"{path}[{i}]"
            self._compare_objects(old_item, new_item, item_path, entries)

    def _sort_list(self, lst: list[Any]) -> list[Any]:
        """Sort list for deterministic comparison.

        If items are dicts with 'id' or 'path' key, sort by that.
        Otherwise return as-is.
        """
        if not lst:
            return lst

        if isinstance(lst[0], dict):
            # Try to find a sort key
            for key in ["id", "path", "name", "finding_id", "rule_id"]:
                if all(key in item for item in lst):
                    return sorted(lst, key=lambda x: str(x[key]))

        return lst

    def _add_entry(
        self,
        path: str,
        old_value: Any,
        new_value: Any,
        entries: list[DiffEntry],
        diff_type: str | None = None,
    ) -> None:
        """Add a diff entry with appropriate type."""
        if diff_type:
            entries.append(
                DiffEntry(
                    path=path,
                    old_value=old_value,
                    new_value=new_value,
                    diff_type=diff_type,
                )
            )
            return

        # Determine diff type
        if self.normalize_timestamps and self._is_timestamp(old_value) and self._is_timestamp(new_value):
            # Both are timestamps - consider them normalized
            entries.append(
                DiffEntry(
                    path=path,
                    old_value=old_value,
                    new_value=new_value,
                    diff_type="normalized",
                )
            )
        else:
            entries.append(
                DiffEntry(
                    path=path,
                    old_value=old_value,
                    new_value=new_value,
                    diff_type="changed",
                )
            )

    def _is_timestamp(self, value: Any) -> bool:
        """Check if value looks like a timestamp."""
        if not isinstance(value, str):
            return False

        # ISO 8601 patterns
        import re

        iso_pattern = r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
        return bool(re.match(iso_pattern, value))


def compute_content_hash(data: dict[str, Any], allowlist: set[str] | None = None) -> str:
    """Compute a deterministic content hash, ignoring allowed fields.

    This creates a hash of the document content that excludes fields
    in the allowlist (like timestamps, run IDs, etc.).

    Args:
        data: Document to hash
        allowlist: Fields to ignore

    Returns:
        Hex digest of content hash
    """
    allowlist = allowlist or set()

    def clean_value(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: clean_value(v) for k, v in sorted(obj.items()) if k not in allowlist}
        elif isinstance(obj, list):
            return [clean_value(item) for item in obj]
        return obj

    cleaned = clean_value(data)
    return hash_dict(cleaned)
