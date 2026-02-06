"""Parquet history store for high-performance historical data storage.

Provides optional Parquet-based storage for history data while keeping
JSON as the canonical interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any

# Parquet is optional - only import if available
PYARROW_AVAILABLE = find_spec("pyarrow") is not None


class ParquetStore:
    """Parquet-based history store for performance.

    This is an internal optimization layer. JSON remains the canonical
    interface for all outputs.
    """

    def __init__(self, store_dir: Path) -> None:
        """Initialize store.

        Args:
            store_dir: Directory for parquet files
        """
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._available = PYARROW_AVAILABLE

    @property
    def available(self) -> bool:
        """Check if parquet support is available."""
        return self._available

    def write_findings(
        self,
        findings: list[dict[str, Any]],
        run_id: str,
        timestamp: str,
    ) -> Path | None:
        """Write findings to parquet.

        Returns:
            Path to parquet file, or None if parquet not available
        """
        if not self.available:
            return None

        # Convert to Arrow table
        if not findings:
            return None

        # Add metadata columns
        rows = []
        for finding in findings:
            row = finding.copy()
            row["_run_id"] = run_id
            row["_timestamp"] = timestamp
            rows.append(row)

        # Create table and write
        try:
            import pandas as pd

            df = pd.DataFrame(rows)
            path = self.store_dir / f"findings_{run_id}.parquet"
            df.to_parquet(path, index=False, compression="zstd")
            return path
        except Exception:
            return None

    def read_findings_history(
        self,
        since: datetime | None = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        """Read historical findings.

        Args:
            since: Only read records after this time
            limit: Maximum records to return

        Returns:
            List of finding records
        """
        if not self.available:
            return []

        import pandas as pd

        all_findings: list[dict[str, Any]] = []

        for parquet_file in sorted(self.store_dir.glob("findings_*.parquet")):
            try:
                df = pd.read_parquet(parquet_file)

                # Filter by time if requested
                if since is not None:
                    df["_ts"] = pd.to_datetime(df["_timestamp"])
                    df = df[df["_ts"] >= since]

                records = df.to_dict("records")
                all_findings.extend(records)

                if len(all_findings) >= limit:
                    break
            except Exception:
                continue

        return all_findings[:limit]

    def compact(self, retention_days: int = 90) -> dict[str, int]:
        """Compact old history files.

        Args:
            retention_days: Keep records from last N days

        Returns:
            Statistics about compaction
        """
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        stats = {"removed": 0, "kept": 0, "bytes_freed": 0}

        for parquet_file in self.store_dir.glob("*.parquet"):
            # Check file modification time
            mtime = datetime.fromtimestamp(parquet_file.stat().st_mtime, tz=UTC)

            if mtime < cutoff:
                size = parquet_file.stat().st_size
                parquet_file.unlink()
                stats["removed"] += 1
                stats["bytes_freed"] += size
            else:
                stats["kept"] += 1

        return stats

    def stats(self) -> dict[str, Any]:
        """Get store statistics."""
        total_size = 0
        file_count = 0

        for parquet_file in self.store_dir.glob("*.parquet"):
            total_size += parquet_file.stat().st_size
            file_count += 1

        return {
            "available": self.available,
            "store_dir": str(self.store_dir),
            "file_count": file_count,
            "total_size_bytes": total_size,
        }


@dataclass
class CompactionPolicy:
    """Policy for history compaction."""

    retention_days: int = 90
    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    compress_after_days: int = 7


class HistoryCompactor:
    """Manages compaction of historical data."""

    def __init__(
        self,
        store: ParquetStore,
        policy: CompactionPolicy | None = None,
    ) -> None:
        self.store = store
        self.policy = policy or CompactionPolicy()

    def compact(self, dry_run: bool = False) -> dict[str, Any]:
        """Run compaction.

        Args:
            dry_run: If True, only report what would be done

        Returns:
            Compaction statistics
        """
        if not self.store.available:
            return {"error": "Parquet not available"}

        if dry_run:
            # Just return stats without removing
            return {
                "dry_run": True,
                "policy": {
                    "retention_days": self.policy.retention_days,
                },
                "current_stats": self.store.stats(),
            }

        # Perform compaction
        stats = self.store.compact(self.policy.retention_days)

        return {
            "compacted": True,
            "stats": stats,
        }
