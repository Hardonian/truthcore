"""Bundle verification for tamper detection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from truthcore.provenance.manifest import EvidenceManifest, ManifestEntry
from truthcore.provenance.signing import Signature, Signer, VerificationError
from truthcore.security import SecurityLimits, SecurityError, check_path_safety


@dataclass
class VerificationResult:
    """Result of bundle verification."""

    valid: bool
    manifest_valid: bool
    signature_valid: bool | None = None
    files_checked: int = 0
    files_valid: int = 0
    files_tampered: list[dict[str, Any]] = field(default_factory=list)
    files_missing: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "manifest_valid": self.manifest_valid,
            "signature_valid": self.signature_valid,
            "files_checked": self.files_checked,
            "files_valid": self.files_valid,
            "files_tampered": self.files_tampered,
            "files_missing": self.files_missing,
            "files_added": self.files_added,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }

    def write_json(self, path: Path) -> None:
        """Write to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    def write_markdown(self, path: Path) -> None:
        """Write to Markdown file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown())

    def _generate_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Bundle Verification Report",
            "",
            f"**Status:** {'✅ VALID' if self.valid else '❌ INVALID'}",
            f"**Timestamp:** {self.timestamp}",
            "",
            "## Summary",
            "",
            f"- **Manifest Valid:** {'✅ Yes' if self.manifest_valid else '❌ No'}",
        ]

        if self.signature_valid is not None:
            lines.append(f"- **Signature Valid:** {'✅ Yes' if self.signature_valid else '❌ No'}")

        lines.extend([
            f"- **Files Checked:** {self.files_checked}",
            f"- **Files Valid:** {self.files_valid}",
            f"- **Files Tampered:** {len(self.files_tampered)}",
            f"- **Files Missing:** {len(self.files_missing)}",
            f"- **Files Added:** {len(self.files_added)}",
            "",
        ])

        if self.files_tampered:
            lines.extend(["## Tampered Files", ""])
            for item in self.files_tampered:
                lines.append(f"- **{item['path']}**")
                lines.append(f"  - Expected: `{item['expected_hash']}`")
                lines.append(f"  - Actual: `{item['actual_hash']}`")
            lines.append("")

        if self.files_missing:
            lines.extend(["## Missing Files", ""])
            for path in self.files_missing:
                lines.append(f"- `{path}`")
            lines.append("")

        if self.files_added:
            lines.extend(["## Added Files (Not in Manifest)", ""])
            for path in self.files_added:
                lines.append(f"- `{path}`")
            lines.append("")

        if self.errors:
            lines.extend(["## Errors", ""])
            for error in self.errors:
                lines.append(f"- {error}")
            lines.append("")

        return "\n".join(lines)


class BundleVerifier:
    """Verifier for evidence bundles."""

    def __init__(
        self,
        public_key: bytes | None = None,
        limits: SecurityLimits | None = None,
    ) -> None:
        self.public_key = public_key
        self.limits = limits or SecurityLimits()
        self._signer = Signer(public_key=public_key) if public_key else None

    def verify(
        self,
        bundle_dir: Path,
        manifest_path: Path | None = None,
        signature_path: Path | None = None,
    ) -> VerificationResult:
        """Verify a bundle.

        Args:
            bundle_dir: Directory containing the bundle
            manifest_path: Path to evidence.manifest.json (default: bundle_dir/evidence.manifest.json)
            signature_path: Path to signature file (default: bundle_dir/evidence.sig)

        Returns:
            VerificationResult
        """
        result = VerificationResult(valid=False, manifest_valid=False)

        # Default paths
        if manifest_path is None:
            manifest_path = bundle_dir / "evidence.manifest.json"
        if signature_path is None:
            signature_path = bundle_dir / "evidence.sig"

        # Validate bundle directory
        try:
            check_path_safety(bundle_dir)
        except SecurityError as e:
            result.errors.append(f"Invalid bundle directory: {e}")
            return result

        # Load manifest
        try:
            manifest = EvidenceManifest.from_json(manifest_path)
        except FileNotFoundError:
            result.errors.append(f"Manifest not found: {manifest_path}")
            return result
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid manifest JSON: {e}")
            return result
        except Exception as e:
            result.errors.append(f"Error loading manifest: {e}")
            return result

        # Verify manifest integrity
        try:
            stored_hash = manifest.compute_manifest_hash()
            manifest_dict = manifest.to_dict()
            if manifest_dict.get("manifest_hash") != stored_hash:
                result.errors.append("Manifest hash mismatch - manifest may be corrupted")
                return result
            result.manifest_valid = True
        except Exception as e:
            result.errors.append(f"Error computing manifest hash: {e}")
            return result

        # Verify signature if present and keys available
        if signature_path.exists() and self._signer:
            try:
                with open(signature_path, "rb") as f:
                    sig_bytes = f.read()
                signature = Signature.from_bytes(sig_bytes)

                # Load manifest content
                with open(manifest_path, "rb") as f:
                    manifest_content = f.read()

                # Verify
                if self._signer.verify(manifest_content, signature):
                    result.signature_valid = True
                else:
                    result.signature_valid = False
                    result.errors.append("Signature verification failed")
            except VerificationError as e:
                result.signature_valid = False
                result.errors.append(f"Signature verification error: {e}")
            except Exception as e:
                result.signature_valid = None
                result.errors.append(f"Error reading signature: {e}")
        elif signature_path.exists():
            result.signature_valid = None
            result.errors.append("Signature present but no public key provided for verification")

        # Verify all files in manifest
        current_files = set()
        for entry in manifest.entries:
            result.files_checked += 1
            file_path = bundle_dir / entry.path

            # Track for detecting added files
            current_files.add(entry.path)

            # Check file exists
            if not file_path.exists():
                result.files_missing.append(entry.path)
                continue

            # Check file hash
            try:
                import hashlib

                hasher = hashlib.sha256()
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                actual_hash = hasher.hexdigest()

                if actual_hash == entry.sha256:
                    result.files_valid += 1
                else:
                    result.files_tampered.append({
                        "path": entry.path,
                        "expected_hash": entry.sha256,
                        "actual_hash": actual_hash,
                    })
            except Exception as e:
                result.errors.append(f"Error checking {entry.path}: {e}")

        # Check for added files (files in bundle but not in manifest)
        for file_path in bundle_dir.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = str(file_path.relative_to(bundle_dir)).replace("\\", "/")

            # Skip manifest and signature files
            if rel_path in ("evidence.manifest.json", "evidence.sig"):
                continue

            if rel_path not in current_files:
                result.files_added.append(rel_path)

        # Determine overall validity
        result.valid = (
            result.manifest_valid
            and result.files_valid == result.files_checked
            and not result.files_missing
            and not result.files_tampered
            and (result.signature_valid is not False)  # Invalid only if explicitly false
        )

        return result

    def verify_and_report(
        self,
        bundle_dir: Path,
        output_dir: Path,
        manifest_path: Path | None = None,
        signature_path: Path | None = None,
    ) -> tuple[VerificationResult, dict[str, Path]]:
        """Verify and write reports.

        Returns:
            Tuple of (result, report_paths)
        """
        result = self.verify(bundle_dir, manifest_path, signature_path)

        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        # Write JSON report
        json_path = output_dir / "verification_report.json"
        result.write_json(json_path)
        paths["json"] = json_path

        # Write Markdown report
        md_path = output_dir / "verification_report.md"
        result.write_markdown(md_path)
        paths["markdown"] = md_path

        return result, paths
