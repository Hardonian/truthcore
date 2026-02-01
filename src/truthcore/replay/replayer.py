"""Deterministic replay engine for re-running verdicts.

Replays a previous run using stored inputs and configuration, then
compares outputs to verify deterministic behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.replay.bundle import DEFAULT_ALLOWLIST, ReplayBundle
from truthcore.replay.diff import DeterministicDiff, DiffComputer
from truthcore.verdict.aggregator import aggregate_verdict


@dataclass
class FileDiffResult:
    """Diff result for a single file."""
    file_name: str
    original_path: Path
    replayed_path: Path
    diff: DeterministicDiff


@dataclass
class ReplayResult:
    """Result of a replay operation.
    
    Attributes:
        success: Whether replay completed successfully
        bundle: The replay bundle used
        output_dir: Directory containing replay outputs
        file_diffs: List of per-file diffs
        identical: Whether all outputs are identical (content-wise)
        allowlist: Fields that were allowed to differ
        timestamp: When replay occurred
        errors: Any errors encountered
    """
    success: bool
    bundle: ReplayBundle
    output_dir: Path
    file_diffs: list[FileDiffResult] = field(default_factory=list)
    identical: bool = True
    allowlist: set[str] = field(default_factory=lambda: DEFAULT_ALLOWLIST.copy())
    timestamp: str = field(default_factory=lambda: normalize_timestamp())
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "timestamp": self.timestamp,
            "bundle": self.bundle.to_dict(),
            "output_dir": str(self.output_dir),
            "identical": self.identical,
            "total_files_compared": len(self.file_diffs),
            "files_identical": sum(1 for d in self.file_diffs if d.diff.identical),
            "files_different": sum(1 for d in self.file_diffs if not d.diff.identical),
            "allowlist": sorted(self.allowlist),
            "file_diffs": [
                {
                    "file": d.file_name,
                    "identical": d.diff.identical,
                    "content_differences": d.diff.content_differences,
                    "allowed_differences": d.diff.allowed_differences,
                }
                for d in self.file_diffs
            ],
            "errors": self.errors,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        status = "✅ PASS" if self.success and self.identical else "❌ FAIL"

        lines = [
            "# Replay Report",
            "",
            f"**Status:** {status}",
            f"**Timestamp:** {self.timestamp}",
            f"**Bundle:** `{self.bundle.bundle_dir}`",
            "",
            "## Summary",
            "",
            f"- **Files Compared:** {len(self.file_diffs)}",
            f"- **Identical:** {sum(1 for d in self.file_diffs if d.diff.identical)}",
            f"- **Different:** {sum(1 for d in self.file_diffs if not d.diff.identical)}",
            "",
        ]

        if self.allowlist:
            lines.extend([
                "## Allowed Differences",
                "",
                "The following fields are allowed to differ:",
                "",
            ])
            for field in sorted(self.allowlist):
                lines.append(f"- `{field}`")
            lines.append("")

        # Show file details
        different_files = [d for d in self.file_diffs if not d.diff.identical]
        if different_files:
            lines.extend(["## Files with Differences", ""])
            for fd in different_files:
                lines.append(f"### {fd.file_name}")
                lines.append(f"- Content differences: {fd.diff.content_differences}")
                lines.append(f"- Allowed differences: {fd.diff.allowed_differences}")
                lines.append("")

                # Show first few content differences
                content_entries = [e for e in fd.diff.entries if e.diff_type == "changed"][:5]
                if content_entries:
                    lines.append("**Differences:**")
                    for entry in content_entries:
                        lines.append(f"- `{entry.path}`: `{entry.old_value}` → `{entry.new_value}`")
                    lines.append("")

        if self.errors:
            lines.extend(["## Errors", ""])
            for error in self.errors:
                lines.append(f"- ❌ {error}")
            lines.append("")

        return "\n".join(lines)


class ReplayEngine:
    """Engine for deterministic replay of truth-core runs.
    
    This re-runs a previous verdict using the same inputs and configuration,
    then compares the results to verify deterministic behavior.
    """

    def __init__(
        self,
        allowlist: set[str] | None = None,
        strict: bool = False,
    ):
        """Initialize replay engine.
        
        Args:
            allowlist: Fields allowed to differ between runs
            strict: If True, any differences (even allowed) cause failure
        """
        self.allowlist = allowlist or DEFAULT_ALLOWLIST.copy()
        self.strict = strict
        self.diff_computer = DiffComputer(allowlist=self.allowlist)

    def replay(
        self,
        bundle: ReplayBundle,
        output_dir: Path,
        mode: str | None = None,
        profile: str | None = None,
    ) -> ReplayResult:
        """Replay a bundle and compare results.
        
        Args:
            bundle: The replay bundle to replay
            output_dir: Directory for replay outputs
            mode: Override mode (uses bundle mode if None)
            profile: Override profile (uses bundle profile if None)
            
        Returns:
            ReplayResult with comparison details
        """
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        result = ReplayResult(
            success=True,
            bundle=bundle,
            output_dir=output_dir,
            allowlist=self.allowlist.copy(),
        )

        try:
            # Determine mode and profile
            replay_mode = mode or bundle.manifest.profile or "pr"
            replay_profile = profile or bundle.manifest.profile or "default"

            # Run the verdict aggregation using bundle inputs
            self._run_verdict(bundle, output_dir, replay_mode, replay_profile)

            # Compare outputs
            self._compare_outputs(bundle, output_dir, result)

            # Determine overall success
            if self.strict:
                result.identical = all(d.diff.identical for d in result.file_diffs)
            else:
                result.identical = all(
                    d.diff.content_differences == 0 for d in result.file_diffs
                )

            result.success = result.identical

        except Exception as e:
            result.success = False
            result.identical = False
            result.errors.append(str(e))

        return result

    def _run_verdict(
        self,
        bundle: ReplayBundle,
        output_dir: Path,
        mode: str,
        profile: str,
    ) -> None:
        """Run verdict aggregation using bundle inputs."""
        # Collect input files from bundle
        input_files: list[Path] = []

        # Add findings from bundle outputs
        for output_file in bundle.get_output_files():
            if output_file.suffix == ".json":
                input_files.append(output_file)

        # Also check inputs directory
        for input_file in bundle.get_input_files():
            if input_file.suffix == ".json":
                input_files.append(input_file)

        if not input_files:
            raise ValueError("No input files found in bundle")

        # Run aggregation
        verdict_result = aggregate_verdict(
            input_paths=input_files,
            mode=mode,
            profile=profile,
        )

        # Write outputs
        verdict_result.write_json(output_dir / "verdict.json")
        verdict_result.write_markdown(output_dir / "verdict.md")

        # Create a new run manifest for the replay
        replay_manifest = RunManifest.create(
            command="replay",
            config={
                "original_run_id": bundle.manifest.run_id,
                "mode": mode,
                "profile": profile,
            },
            input_dir=bundle.inputs_dir if bundle.inputs_dir.exists() else None,
            profile=profile,
        )
        replay_manifest.write(output_dir)

    def _compare_outputs(
        self,
        bundle: ReplayBundle,
        replay_dir: Path,
        result: ReplayResult,
    ) -> None:
        """Compare original outputs with replayed outputs."""
        original_files = {f.name: f for f in bundle.get_output_files()}
        replayed_files = {f.name: f for f in replay_dir.iterdir() if f.is_file()}

        # Compare each file that exists in both
        for file_name in original_files:
            if file_name not in replayed_files:
                result.errors.append(f"Missing replayed file: {file_name}")
                continue

            original_path = original_files[file_name]
            replayed_path = replayed_files[file_name]

            # Only compare JSON files
            if not file_name.endswith(".json"):
                continue

            try:
                diff = self.diff_computer.compute_files(original_path, replayed_path)

                result.file_diffs.append(FileDiffResult(
                    file_name=file_name,
                    original_path=original_path,
                    replayed_path=replayed_path,
                    diff=diff,
                ))
            except Exception as e:
                result.errors.append(f"Error comparing {file_name}: {e}")


class ReplayReporter:
    """Generates reports from replay results."""

    def write_reports(
        self,
        result: ReplayResult,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Write replay reports.
        
        Args:
            result: Replay result to report
            output_dir: Directory for report files
            
        Returns:
            Dict of report type to path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        # Write JSON report
        json_path = output_dir / "replay_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, sort_keys=True)
        paths["json"] = json_path

        # Write Markdown report
        md_path = output_dir / "replay_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result.to_markdown())
        paths["markdown"] = md_path

        return paths
