"""Replay bundle format for deterministic replay and simulation.

A replay bundle captures all inputs, configuration, and outputs from a run,
enabling deterministic replay and counterfactual simulation.

Bundle structure:
    bundle/
        run_manifest.json       # Original run manifest
        inputs/                 # Raw inputs used
        config/                 # Profiles, thresholds, policy packs
        outputs/                # Previous outputs for comparison
        evidence.manifest.json  # Provenance manifest (optional with sig)
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.provenance.manifest import EvidenceManifest
from truthcore.provenance.verifier import BundleVerifier, VerificationResult
from truthcore.security import SecurityLimits, check_path_safety

# Fields that are allowed to differ between replay and original
# These are typically timestamps, run IDs, or other non-content metadata
DEFAULT_ALLOWLIST = {
    "run_id",
    "timestamp",
    "duration_ms",
    "cache_key",
    "cache_path",
    "cache_hit",
}


@dataclass
class ReplayBundle:
    """A replay bundle containing all artifacts needed for replay/simulation.

    Attributes:
        bundle_dir: Path to the bundle directory
        manifest: The run manifest from the original run
        inputs_dir: Path to inputs subdirectory
        config_dir: Path to config subdirectory
        outputs_dir: Path to outputs subdirectory
        evidence_manifest: Optional evidence manifest for verification
        allowlist: Set of fields allowed to differ during replay comparison
    """

    bundle_dir: Path
    manifest: RunManifest
    inputs_dir: Path
    config_dir: Path
    outputs_dir: Path
    evidence_manifest: EvidenceManifest | None = None
    allowlist: set[str] = field(default_factory=lambda: DEFAULT_ALLOWLIST.copy())

    @classmethod
    def load(cls, bundle_dir: Path) -> ReplayBundle:
        """Load a replay bundle from directory.

        Args:
            bundle_dir: Path to bundle directory

        Returns:
            Loaded ReplayBundle

        Raises:
            FileNotFoundError: If required files missing
            ValueError: If bundle structure invalid
        """
        bundle_dir = Path(bundle_dir).resolve()

        if not bundle_dir.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_dir}")

        # Load run manifest
        manifest_path = bundle_dir / "run_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing run_manifest.json in bundle: {bundle_dir}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        # Convert dict back to RunManifest
        manifest = RunManifest(
            run_id=manifest_data["run_id"],
            command=manifest_data["command"],
            timestamp=manifest_data["timestamp"],
            truthcore_version=manifest_data["truthcore_version"],
            truthcore_git_sha=manifest_data.get("truthcore_git_sha"),
            config_hash=manifest_data["config"]["hash"],
            config_path=manifest_data["config"].get("path"),
            profile=manifest_data["config"].get("profile"),
            input_directory=manifest_data["inputs"].get("directory"),
            cache_hit=manifest_data["cache"].get("hit", False),
            cache_key=manifest_data["cache"].get("key"),
            cache_path=manifest_data["cache"].get("path"),
            duration_ms=manifest_data["execution"].get("duration_ms", 0),
            exit_code=manifest_data["execution"].get("exit_code", 0),
            metadata=manifest_data.get("metadata", {}),
        )

        # Load input files info
        for file_info in manifest_data["inputs"].get("files", []):
            from truthcore.manifest import InputFileInfo
            manifest.input_files.append(InputFileInfo(
                path=file_info["path"],
                size=file_info["size"],
                content_hash=file_info["content_hash"],
                modified_time=file_info["modified_time"],
            ))

        # Load evidence manifest if present
        evidence_manifest = None
        evidence_path = bundle_dir / "evidence.manifest.json"
        if evidence_path.exists():
            evidence_manifest = EvidenceManifest.from_json(evidence_path)

        return cls(
            bundle_dir=bundle_dir,
            manifest=manifest,
            inputs_dir=bundle_dir / "inputs",
            config_dir=bundle_dir / "config",
            outputs_dir=bundle_dir / "outputs",
            evidence_manifest=evidence_manifest,
        )

    def verify_integrity(self, public_key: bytes | None = None) -> VerificationResult:
        """Verify bundle integrity using evidence manifest.

        Args:
            public_key: Optional public key for signature verification

        Returns:
            VerificationResult with details
        """
        if not self.evidence_manifest:
            # No evidence manifest, can't verify
            return VerificationResult(
                valid=True,  # Assume valid if no manifest
                manifest_valid=True,
                signature_valid=None,
            )

        verifier = BundleVerifier(public_key=public_key)
        return verifier.verify(
            self.bundle_dir,
            manifest_path=self.bundle_dir / "evidence.manifest.json",
            signature_path=self.bundle_dir / "evidence.sig",
        )

    def get_config_files(self) -> list[Path]:
        """Get all configuration files in the bundle.

        Returns:
            List of paths to config files
        """
        if not self.config_dir.exists():
            return []

        files = []
        for pattern in ["*.json", "*.yaml", "*.yml"]:
            files.extend(self.config_dir.glob(pattern))
        return sorted(files)

    def get_input_files(self) -> list[Path]:
        """Get all input files in the bundle.

        Returns:
            List of paths to input files
        """
        if not self.inputs_dir.exists():
            return []

        files = []
        for f in self.inputs_dir.rglob("*"):
            if f.is_file():
                files.append(f)
        return sorted(files)

    def get_output_files(self) -> list[Path]:
        """Get all output files in the bundle.

        Returns:
            List of paths to output files
        """
        if not self.outputs_dir.exists():
            return []

        files = []
        for f in self.outputs_dir.rglob("*"):
            if f.is_file() and f.name not in ("evidence.manifest.json", "evidence.sig"):
                files.append(f)
        return sorted(files)

    def to_dict(self) -> dict[str, Any]:
        """Convert bundle info to dictionary."""
        return {
            "bundle_dir": str(self.bundle_dir),
            "run_id": self.manifest.run_id,
            "command": self.manifest.command,
            "timestamp": self.manifest.timestamp,
            "truthcore_version": self.manifest.truthcore_version,
            "has_inputs": self.inputs_dir.exists(),
            "has_config": self.config_dir.exists(),
            "has_outputs": self.outputs_dir.exists(),
            "has_evidence_manifest": self.evidence_manifest is not None,
            "input_count": len(self.get_input_files()),
            "config_count": len(self.get_config_files()),
            "output_count": len(self.get_output_files()),
        }


class BundleExporter:
    """Exports run results into a replay bundle format.

    This captures all inputs, configuration, and outputs needed for
    deterministic replay and counterfactual simulation.
    """

    def __init__(self, limits: SecurityLimits | None = None):
        self.limits = limits or SecurityLimits()

    def export(
        self,
        run_dir: Path,
        original_inputs_dir: Path | None,
        out_bundle_dir: Path,
        profile: str | None = None,
        mode: str | None = None,
        copy_inputs: bool = True,
    ) -> ReplayBundle:
        """Export a run directory into a replay bundle.

        Args:
            run_dir: Directory containing run outputs (with run_manifest.json)
            original_inputs_dir: Original inputs directory (if separate from run_dir)
            out_bundle_dir: Output directory for the bundle
            profile: Profile used for the run
            mode: Mode used for the run
            copy_inputs: Whether to copy input files (True) or just reference them

        Returns:
            The created ReplayBundle

        Raises:
            FileNotFoundError: If run_dir missing required files
            SecurityError: If path safety checks fail
        """
        run_dir = Path(run_dir).resolve()
        out_bundle_dir = Path(out_bundle_dir).resolve()

        # Validate paths
        check_path_safety(run_dir)
        if original_inputs_dir:
            check_path_safety(original_inputs_dir)

        # Load run manifest
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No run_manifest.json found in {run_dir}")

        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)

        # Create bundle directory structure
        out_bundle_dir.mkdir(parents=True, exist_ok=True)

        inputs_dir = out_bundle_dir / "inputs"
        config_dir = out_bundle_dir / "config"
        outputs_dir = out_bundle_dir / "outputs"

        # Copy run manifest
        shutil.copy2(manifest_path, out_bundle_dir / "run_manifest.json")

        # Copy evidence manifest and signature if present
        evidence_path = run_dir / "evidence.manifest.json"
        if evidence_path.exists():
            shutil.copy2(evidence_path, out_bundle_dir / "evidence.manifest.json")

        sig_path = run_dir / "evidence.sig"
        if sig_path.exists():
            shutil.copy2(sig_path, out_bundle_dir / "evidence.sig")

        # Copy outputs
        if run_dir.exists():
            outputs_dir.mkdir(parents=True, exist_ok=True)
            for item in run_dir.iterdir():
                if item.is_file():
                    # Skip manifests (already copied to root)
                    if item.name in ("run_manifest.json", "evidence.manifest.json", "evidence.sig"):
                        continue
                    shutil.copy2(item, outputs_dir / item.name)
                elif item.is_dir() and item.name not in ("inputs", "config", "outputs"):
                    # Copy subdirectories
                    shutil.copytree(item, outputs_dir / item.name, dirs_exist_ok=True)

        # Copy or reference inputs
        inputs_source = original_inputs_dir or manifest_data["inputs"].get("directory")
        if inputs_source and copy_inputs:
            inputs_source = Path(inputs_source).resolve()
            if inputs_source.exists():
                inputs_dir.mkdir(parents=True, exist_ok=True)

                # Copy all input files
                for file_info in manifest_data["inputs"].get("files", []):
                    src_path = inputs_source / file_info["path"]
                    if src_path.exists():
                        dst_path = inputs_dir / file_info["path"]
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)

        # Extract/copy configuration
        config_dir.mkdir(parents=True, exist_ok=True)

        # Look for config files in outputs
        for config_file in ["thresholds.json", "policy_pack.yaml", "rules.json", "invariants.yaml"]:
            src = run_dir / config_file
            if src.exists():
                shutil.copy2(src, config_dir / config_file)

        # Also check for profile-specific configs
        if profile:
            for config_file in [f"profile_{profile}.json", f"profile_{profile}.yaml"]:
                src = run_dir / config_file
                if src.exists():
                    shutil.copy2(src, config_dir / config_file)

        # Write bundle metadata
        bundle_meta = {
            "exported_at": normalize_timestamp(),
            "run_dir": str(run_dir),
            "original_inputs_dir": str(original_inputs_dir) if original_inputs_dir else None,
            "profile": profile,
            "mode": mode,
        }

        with open(out_bundle_dir / "bundle_meta.json", "w", encoding="utf-8") as f:
            json.dump(bundle_meta, f, indent=2, sort_keys=True)

        # Load and return the bundle
        return ReplayBundle.load(out_bundle_dir)
