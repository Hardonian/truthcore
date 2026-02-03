"""Local filesystem connector for truth-core."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from truthcore.connectors.base import BaseConnector, ConnectorResult


class LocalConnector(BaseConnector):
    """Connector for local filesystem inputs.

    This connector copies files from a local source directory
    to the destination, applying validation and size limits.
    """

    @property
    def name(self) -> str:
        """Return connector name."""
        return "local"

    @property
    def is_available(self) -> bool:
        """Return whether local connector is available (always True)."""
        return True

    def fetch(self, source: str, destination: Path) -> ConnectorResult:
        """Copy files from local source to destination.

        Args:
            source: Source directory path
            destination: Destination directory path

        Returns:
            ConnectorResult with status and file list
        """
        source_path = Path(source).resolve()

        if not source_path.exists():
            return ConnectorResult(
                success=False,
                error=f"Source path does not exist: {source}"
            )

        destination.mkdir(parents=True, exist_ok=True)

        files_copied: list[str] = []
        total_size = 0
        file_count = 0
        errors: list[str] = []

        try:
            if source_path.is_file():
                # Single file
                if not self.validate_path(str(source_path)):
                    return ConnectorResult(
                        success=False,
                        error=f"File type blocked: {source_path.suffix}"
                    )

                file_size = source_path.stat().st_size
                if not self.check_size_limit(0, file_size):
                    return ConnectorResult(
                        success=False,
                        error=f"File exceeds size limit: {file_size} bytes"
                    )

                dest_file = destination / source_path.name
                shutil.copy2(source_path, dest_file)
                files_copied.append(source_path.name)
                total_size = file_size
                file_count = 1
            else:
                # Directory - walk and copy
                for src_file in source_path.rglob("*"):
                    if not src_file.is_file():
                        continue

                    # Check file count limit
                    if file_count >= self.config.max_files:
                        errors.append(f"Reached max file limit ({self.config.max_files})")
                        break

                    # Validate path
                    rel_path = src_file.relative_to(source_path)
                    if not self.validate_path(str(rel_path)):
                        continue

                    file_size = src_file.stat().st_size

                    # Check size limit
                    if not self.check_size_limit(total_size, file_size):
                        errors.append(f"Reached max size limit ({self.config.max_size_bytes} bytes)")
                        break

                    # Copy file
                    dest_file = destination / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)

                    files_copied.append(str(rel_path))
                    total_size += file_size
                    file_count += 1

            return ConnectorResult(
                success=True,
                local_path=destination,
                files=files_copied,
                metadata={
                    "source": str(source_path),
                    "files_copied": file_count,
                    "total_bytes": total_size,
                    "errors": errors if errors else None,
                }
            )

        except Exception as e:
            return ConnectorResult(
                success=False,
                local_path=destination if destination.exists() else None,
                files=files_copied,
                error=str(e)
            )

    def fetch_from_config(self, config: dict[str, Any], destination: Path) -> ConnectorResult:
        """Fetch using a configuration dict.

        Args:
            config: Configuration with 'path' key
            destination: Destination directory

        Returns:
            ConnectorResult
        """
        source = config.get("path")
        if not source:
            return ConnectorResult(
                success=False,
                error="Config missing 'path' key"
            )
        return self.fetch(source, destination)
