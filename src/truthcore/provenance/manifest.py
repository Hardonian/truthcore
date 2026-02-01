"""Evidence manifest generator for tamper detection."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass, field

from pathlib import Path
from typing import Any

from truthcore import __version__
from truthcore.manifest import normalize_timestamp
from truthcore.security import SecurityLimits, SecurityError, check_path_safety


@dataclass
class ManifestEntry:
    """Entry for a single file in the evidence manifest."""

    path: str
    sha256: str
    size: int
    content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
        }
        if self.content_type:
            result["content_type"] = self.content_type
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestEntry:
        """Create from dictionary."""
        return cls(
            path=data["path"],
            sha256=data["sha256"],
            size=data["size"],
            content_type=data.get("content_type"),
        )

    @classmethod
    def from_file(
        cls,
        file_path: Path,
        base_dir: Path,
        limits: SecurityLimits | None = None,
    ) -> ManifestEntry:
        """Create entry from file.

        Args:
            file_path: Path to the file
            base_dir: Base directory for computing relative path
            limits: Security limits

        Returns:
            ManifestEntry

        Raises:
            SecurityError: If file too large or unsafe path
        """
        limits = limits or SecurityLimits()

        # Check path safety
        safe_path = check_path_safety(file_path, base_dir)

        # Check file size
        stat = safe_path.stat()
        if stat.st_size > limits.max_file_size:
            raise SecurityError(
                f"File too large: {file_path} ({stat.st_size} bytes > {limits.max_file_size})"
            )

        # Compute relative path
        rel_path = str(file_path.relative_to(base_dir)).replace("\\", "/")

        # Compute SHA-256
        sha256_hash = hashlib.sha256()
        with open(safe_path, "rb") as f:
            while chunk := f.read(8192):
                sha256_hash.update(chunk)

        # Guess content type
        content_type, _ = mimetypes.guess_type(str(file_path))

        return cls(
            path=rel_path,
            sha256=sha256_hash.hexdigest(),
            size=stat.st_size,
            content_type=content_type,
        )


@dataclass
class EvidenceManifest:
    """Evidence manifest for tamper detection.

    Records:
    - All files in output directory with SHA-256 hashes
    - Run manifest hash
    - Config hash
    - Engine versions
    - Timestamp
    """

    version: str = "1.0.0"
    timestamp: str = field(default_factory=lambda: normalize_timestamp())
    entries: list[ManifestEntry] = field(default_factory=lambda: list())
    run_manifest_hash: str | None = None
    config_hash: str | None = None
    engine_versions: dict[str, str] = field(default_factory=lambda: dict())
    truthcore_version: str = field(default_factory=lambda: __version__)
    metadata: dict[str, Any] = field(default_factory=lambda: dict())

    def add_entry(self, entry: ManifestEntry) -> None:
        """Add an entry to the manifest."""
        self.entries.append(entry)

    def compute_manifest_hash(self) -> str:
        """Compute deterministic hash of the manifest content."""
        # Sort entries by path for determinism
        sorted_entries = sorted(self.entries, key=lambda e: e.path)

        content = {
            "version": self.version,
            "timestamp": self.timestamp,
            "entries": [e.to_dict() for e in sorted_entries],
            "run_manifest_hash": self.run_manifest_hash,
            "config_hash": self.config_hash,
            "engine_versions": dict(sorted(self.engine_versions.items())),
            "truthcore_version": self.truthcore_version,
            "metadata": dict(sorted(self.metadata.items())),
        }

        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "manifest_hash": self.compute_manifest_hash(),
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in sorted(self.entries, key=lambda e: e.path)],
            "run_manifest_hash": self.run_manifest_hash,
            "config_hash": self.config_hash,
            "engine_versions": dict(sorted(self.engine_versions.items())),
            "truthcore_version": self.truthcore_version,
            "metadata": dict(sorted(self.metadata.items())),
        }

    def write_json(self, path: Path) -> None:
        """Write manifest to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceManifest:
        """Create from dictionary."""
        manifest = cls(
            version=data.get("version", "1.0.0"),
            timestamp=data.get("timestamp", normalize_timestamp()),
            run_manifest_hash=data.get("run_manifest_hash"),
            config_hash=data.get("config_hash"),
            engine_versions=data.get("engine_versions", {}),
            truthcore_version=data.get("truthcore_version", __version__),
            metadata=data.get("metadata", {}),
        )
        for entry_data in data.get("entries", []):
            manifest.add_entry(ManifestEntry.from_dict(entry_data))
        return manifest

    @classmethod
    def from_json(cls, path: Path) -> EvidenceManifest:
        """Load manifest from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def generate(
        cls,
        bundle_dir: Path,
        run_manifest_hash: str | None = None,
        config_hash: str | None = None,
        engine_versions: dict[str, str] | None = None,
        limits: SecurityLimits | None = None,
        max_files: int = 10000,
    ) -> EvidenceManifest:
        """Generate manifest from bundle directory.

        Args:
            bundle_dir: Directory to scan
            run_manifest_hash: Hash of run_manifest.json if available
            config_hash: Hash of configuration
            engine_versions: Dictionary of engine versions
            limits: Security limits for file reading
            max_files: Maximum number of files to process

        Returns:
            EvidenceManifest

        Raises:
            SecurityError: If path traversal detected or too many files
        """
        limits = limits or SecurityLimits()

        # Validate bundle directory is safe
        try:
            check_path_safety(bundle_dir)
        except SecurityError as e:
            raise SecurityError(f"Invalid bundle directory: {e}") from e

        manifest = cls(
            run_manifest_hash=run_manifest_hash,
            config_hash=config_hash,
            engine_versions=engine_versions or {},
            metadata={
                "source_dir": str(bundle_dir),
                "generated_at": normalize_timestamp(),
            },
        )

        # Walk directory
        file_count = 0
        for file_path in sorted(bundle_dir.rglob("*")):
            if not file_path.is_file():
                continue

            file_count += 1
            if file_count > max_files:
                raise SecurityError(
                    f"Too many files in bundle: {file_count} > {max_files}"
                )

            # Skip signature files (to avoid circular dependency)
            if file_path.name in ("evidence.sig", "evidence.manifest.json"):
                continue

            try:
                entry = ManifestEntry.from_file(file_path, bundle_dir, limits)
                manifest.add_entry(entry)
            except SecurityError:
                # Skip files that fail security checks
                continue

        return manifest
