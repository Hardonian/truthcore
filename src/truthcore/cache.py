"""Content-addressed cache system for deterministic output reuse."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any

from truthcore.manifest import hash_dict


@dataclass
class CacheEntry:
    """A cached output entry."""
    cache_key: str
    output_dir: Path
    manifest: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert cache entry to dictionary."""
        return {
            "cache_key": self.cache_key,
            "output_dir": str(self.output_dir),
            "manifest": self.manifest,
            "timestamp": self.timestamp,
        }


class ContentAddressedCache:
    """Content-addressed cache for engine outputs.

    Cache keys are computed from:
    - Command name
    - Configuration hash
    - Input file content hashes
    - Engine version

    This ensures deterministic cache hits for identical inputs.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize cache.

        Args:
            cache_dir: Directory for cache storage. Defaults to .truthcache in current directory.
        """
        if cache_dir is None:
            cache_dir = Path(".truthcache")
        self.cache_dir = cache_dir.expanduser().resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create index file if not exists
        self.index_path = self.cache_dir / "index.json"
        self._index: dict[str, Any] | None = None
        self._index_dirty = False
        self._index_mtime: float | None = None
        self._load_index()

    def _load_index(self) -> dict[str, Any]:
        """Load cache index into memory with caching."""
        if self._index is None:
            if self.index_path.exists():
                with open(self.index_path, encoding="utf-8") as f:
                    self._index = json.load(f)
                self._index_mtime = self.index_path.stat().st_mtime
            else:
                self._index = {"version": "1.0", "entries": {}}
                self._index_mtime = None
        return self._index  # type: ignore[return-value]

    def _save_index(self, index: dict[str, Any]) -> None:
        """Save cache index."""
        # Ensure cache directory exists before saving
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, sort_keys=True)
        self._index_dirty = False
        self._index_mtime = self.index_path.stat().st_mtime

    def _get_cached_index(self) -> dict[str, Any]:
        """Get cached index, loading from disk if needed."""
        if self._index is None:
            return self._load_index()
        return self._index

    def _refresh_index_if_stale(self) -> None:
        """Refresh index if another instance updated it on disk."""
        if not self.index_path.exists():
            return
        if self._index_dirty:
            return
        current_mtime = self.index_path.stat().st_mtime
        if self._index_mtime is None or current_mtime > self._index_mtime:
            self._index = None
            self._load_index()

    def sync_index(self) -> None:
        """Sync in-memory index to disk if dirty."""
        if self._index_dirty and self._index is not None:
            self._save_index(self._index)

    def compute_cache_key(
        self,
        command: str,
        config: dict[str, Any],
        input_hashes: list[str],
        engine_version: str,
    ) -> str:
        """Compute deterministic cache key."""
        key_data = {
            "command": command,
            "config": config,
            "inputs": sorted(input_hashes),  # Sort for determinism
            "engine_version": engine_version,
        }
        return hash_dict(key_data)

    def get(self, cache_key: str) -> Path | None:
        """Get cached output directory if exists.

        Returns:
            Path to cached output directory, or None if not in cache.
        """
        self._refresh_index_if_stale()
        index = self._get_cached_index()

        if cache_key in index["entries"]:
            cache_path = self.cache_dir / cache_key

            if cache_path.exists():
                return cache_path
            else:
                # Stale index entry, remove it
                del index["entries"][cache_key]
                self._index_dirty = True
                self.sync_index()

        return None

    def put(
        self,
        cache_key: str,
        output_dir: Path,
        manifest: dict[str, Any],
    ) -> Path:
        """Store output in cache.

        Args:
            cache_key: Computed cache key
            output_dir: Directory containing outputs to cache
            manifest: Run manifest for this execution

        Returns:
            Path to cached directory
        """
        cache_path = self.cache_dir / cache_key

        # Remove existing cache entry if present
        if cache_path.exists():
            shutil.rmtree(cache_path)

        # Copy outputs to cache
        shutil.copytree(output_dir, cache_path, dirs_exist_ok=True)

        # Update index (in-memory first, then sync to disk)
        index = self._get_cached_index()
        from datetime import datetime
        # Use file count from source dir to avoid re-walking cache
        file_count = sum(1 for _ in output_dir.rglob("*") if _.is_file())
        index["entries"][cache_key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "manifest_hash": hash_dict(manifest),
            "output_files": file_count,
        }
        self._index_dirty = True
        self.sync_index()

        return cache_path

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared.
        """
        index = self._get_cached_index()
        count = len(index["entries"])

        # Remove all cached directories
        for key in index["entries"]:
            cache_path = self.cache_dir / key
            if cache_path.exists():
                shutil.rmtree(cache_path)

        # Reset index
        index["entries"] = {}
        self._index_dirty = True
        self.sync_index()

        return count

    def compact(self, max_age_days: int = 30) -> int:
        """Remove old cache entries.

        Args:
            max_age_days: Maximum age in days for entries to keep

        Returns:
            Number of entries removed.
        """
        from datetime import datetime, timedelta

        index = self._get_cached_index()
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        to_remove: list[str] = []
        for key, entry in index["entries"].items():
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time < cutoff:
                to_remove.append(key)

        for key in to_remove:
            cache_path = self.cache_dir / key
            if cache_path.exists():
                shutil.rmtree(cache_path)
            del index["entries"][key]

        if to_remove:
            self._index_dirty = True
            self.sync_index()
        return len(to_remove)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics (alias for get_stats)."""
        return self.get_stats()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics using cached index."""
        index = self._get_cached_index()

        total_size = 0
        for key in index["entries"]:
            cache_path = self.cache_dir / key
            if cache_path.exists():
                total_size += sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())

        return {
            "entries": len(index["entries"]),
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }


class JsonTtlCache:
    """Lightweight JSON cache with TTL stored on disk for cross-instance reuse."""

    def __init__(self, cache_dir: Path, namespace: str) -> None:
        self.cache_dir = cache_dir / namespace
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str, now: float) -> dict[str, Any] | None:
        """Return cached payload if present and not expired."""
        entry_path = self._entry_path(cache_key)
        if not entry_path.exists():
            return None
        try:
            with open(entry_path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            entry_path.unlink(missing_ok=True)
            return None
        expires_at = payload.get("expires_at")
        if expires_at is None or expires_at <= now:
            entry_path.unlink(missing_ok=True)
            return None
        return payload.get("data")

    def put(self, cache_key: str, data: dict[str, Any], expires_at: float) -> None:
        """Persist cached payload to disk."""
        entry_path = self._entry_path(cache_key)
        with open(entry_path, "w", encoding="utf-8") as f:
            json.dump({"expires_at": expires_at, "data": data}, f, indent=2, sort_keys=True)
