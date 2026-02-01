"""Run manifest system for reproducibility and provenance tracking."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from truthcore import __version__


def get_git_sha() -> str | None:
    """Get git SHA if available."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except Exception:
        pass
    return None


def normalize_timestamp(ts: datetime | str | None = None) -> str:
    """Generate normalized ISO timestamp in UTC.
    
    All timestamps are converted to UTC and formatted consistently.
    """
    if ts is None:
        ts = datetime.now(timezone.utc)
    elif isinstance(ts, str):
        # Parse and re-format to ensure consistency
        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    
    # Ensure UTC
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    
    # Format: 2026-01-31T10:00:00Z (no microseconds, always UTC)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_file(path: Path, algorithm: str = "blake2b", digest_size: int = 16) -> str:
    """Compute content hash of a file.
    
    Args:
        path: Path to file
        algorithm: Hash algorithm (blake2b, sha256, sha3_256)
        digest_size: Size of digest (for blake2b)
    
    Returns:
        Hex digest of file content
    """
    if algorithm == "blake2b":
        hasher = hashlib.blake2b(digest_size=digest_size)
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha3_256":
        hasher = hashlib.sha3_256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    # Read in chunks to handle large files
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def hash_content(content: bytes | str, algorithm: str = "blake2b", digest_size: int = 16) -> str:
    """Compute hash of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    if algorithm == "blake2b":
        hasher = hashlib.blake2b(digest_size=digest_size)
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha3_256":
        hasher = hashlib.sha3_256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    hasher.update(content)
    return hasher.hexdigest()


def hash_dict(data: dict[str, Any], algorithm: str = "blake2b", digest_size: int = 16) -> str:
    """Compute deterministic hash of a dictionary.
    
    Uses canonical JSON representation with sorted keys.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hash_content(canonical.encode("utf-8"), algorithm, digest_size)


@dataclass
class InputFileInfo:
    """Information about an input file."""
    path: str
    size: int
    content_hash: str
    modified_time: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "content_hash": self.content_hash,
            "modified_time": normalize_timestamp(self.modified_time) if isinstance(self.modified_time, str) else self.modified_time,
        }


@dataclass
class RunManifest:
    """Manifest capturing all provenance information for a run.
    
    This enables reproducibility by recording:
    - Software versions
    - Configuration
    - Input files with content hashes
    - Environment
    - Cache status
    """
    
    # Run identification (required)
    run_id: str  # Unique run identifier
    command: str  # CLI command invoked
    timestamp: str  # ISO timestamp (normalized UTC)
    
    # Software versions (required)
    truthcore_version: str
    truthcore_git_sha: str | None
    config_hash: str  # Configuration
    
    # Optional fields with defaults
    engine_versions: dict[str, str] = field(default_factory=lambda: {})
    config_path: str | None = None
    profile: str | None = None
    input_files: list[InputFileInfo] = field(default_factory=lambda: [])
    input_directory: str | None = None
    python_version: str = field(default_factory=lambda: sys.version)
    python_implementation: str = field(default_factory=lambda: platform.python_implementation())
    os_name: str = field(default_factory=lambda: platform.system())
    os_release: str = field(default_factory=lambda: platform.release())
    cpu_arch: str = field(default_factory=lambda: platform.machine())
    timezone: str = field(default_factory=lambda: datetime.now().astimezone().tzname() or "UTC")
    
    # Cache status
    cache_hit: bool = False
    cache_key: str | None = None
    cache_path: str | None = None
    
    # Execution
    duration_ms: int = 0
    exit_code: int = 0
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=lambda: {})
    
    def __post_init__(self):
        """Normalize timestamp after initialization."""
        if not self.timestamp.endswith('Z'):
            self.timestamp = normalize_timestamp(self.timestamp)
    
    @classmethod
    def create(
        cls,
        command: str,
        config: dict[str, Any],
        input_dir: Path | None = None,
        input_files: list[Path] | None = None,
        profile: str | None = None,
        cache_hit: bool = False,
        cache_key: str | None = None,
    ) -> "RunManifest":
        """Create a new run manifest."""
        import uuid
        
        # Generate run ID from timestamp + random component
        now = datetime.now(timezone.utc)
        run_id = f"{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # Hash config
        config_hash = hash_dict(config)
        
        # Collect input file info
        file_infos: list[InputFileInfo] = []
        
        if input_files:
            for path in sorted(input_files):  # Sort for determinism
                if path.exists():
                    stat = path.stat()
                    file_infos.append(InputFileInfo(
                        path=str(path),
                        size=stat.st_size,
                        content_hash=hash_file(path),
                        modified_time=normalize_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                    ))
        
        elif input_dir:
            # Scan directory for relevant files
            for path in sorted(input_dir.rglob("*")):
                if path.is_file() and not any(part.startswith('.') for part in path.parts):
                    stat = path.stat()
                    file_infos.append(InputFileInfo(
                        path=str(path.relative_to(input_dir)),
                        size=stat.st_size,
                        content_hash=hash_file(path),
                        modified_time=normalize_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                    ))
        
        return cls(
            run_id=run_id,
            command=command,
            timestamp=normalize_timestamp(now),
            truthcore_version=__version__,
            truthcore_git_sha=get_git_sha(),
            config_hash=config_hash,
            profile=profile,
            input_files=file_infos,
            input_directory=str(input_dir) if input_dir else None,
            cache_hit=cache_hit,
            cache_key=cache_key,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with stable sorting."""
        return {
            "run_id": self.run_id,
            "command": self.command,
            "timestamp": self.timestamp,
            "truthcore_version": self.truthcore_version,
            "truthcore_git_sha": self.truthcore_git_sha,
            "engine_versions": dict(sorted(self.engine_versions.items())),
            "config": {
                "hash": self.config_hash,
                "path": self.config_path,
                "profile": self.profile,
            },
            "inputs": {
                "directory": self.input_directory,
                "files": [f.to_dict() for f in sorted(self.input_files, key=lambda x: x.path)],
            },
            "environment": {
                "python_version": self.python_version,
                "python_implementation": self.python_implementation,
                "os": {
                    "name": self.os_name,
                    "release": self.os_release,
                },
                "cpu_arch": self.cpu_arch,
                "timezone": self.timezone,
            },
            "cache": {
                "hit": self.cache_hit,
                "key": self.cache_key,
                "path": self.cache_path,
            },
            "execution": {
                "duration_ms": self.duration_ms,
                "exit_code": self.exit_code,
            },
            "metadata": dict(sorted(self.metadata.items())),
        }
    
    def write(self, output_dir: Path) -> Path:
        """Write manifest to output directory."""
        manifest_path = output_dir / "run_manifest.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True, ensure_ascii=True)
        
        return manifest_path
    
    def compute_cache_key(self) -> str:
        """Compute cache key from manifest content.
        
        This combines command, config hash, and input hashes.
        """
        key_data = {
            "command": self.command,
            "config_hash": self.config_hash,
            "input_hashes": [f.content_hash for f in self.input_files],
            "truthcore_version": self.truthcore_version,
        }
        return hash_dict(key_data)
