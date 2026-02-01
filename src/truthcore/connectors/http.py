"""HTTP(S) artifact fetcher connector for truth-core."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from truthcore.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult


class HTTPConnector(BaseConnector):
    """Connector for fetching artifacts via HTTP(S).
    
    Downloads artifacts from a specific URL (no crawling).
    Supports single files or zip archives.
    
    Example source formats:
        https://example.com/path/to/artifact.json
        https://example.com/path/to/bundle.zip
    """
    
    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize HTTP connector.
        
        Args:
            config: Connector configuration
        """
        super().__init__(config)
    
    @property
    def name(self) -> str:
        return "http"
    
    @property
    def is_available(self) -> bool:
        return True
    
    def fetch(self, source: str, destination: Path) -> ConnectorResult:
        """Download artifact from HTTP(S) URL.
        
        Args:
            source: HTTP(S) URL to download
            destination: Destination directory for downloaded content
            
        Returns:
            ConnectorResult with status and file list
        """
        # Validate URL
        parsed = urlparse(source)
        if parsed.scheme not in ("http", "https"):
            return ConnectorResult(
                success=False,
                error=f"Invalid URL scheme: {parsed.scheme}. Only http/https supported."
            )
        
        # Block URLs with path traversal attempts
        if ".." in parsed.path or ".." in (parsed.query or ""):
            return ConnectorResult(
                success=False,
                error="URL contains path traversal attempt"
            )
        
        destination.mkdir(parents=True, exist_ok=True)
        
        try:
            req = Request(source)
            req.add_header("User-Agent", "truth-core/0.2.0")
            
            with urlopen(req, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
            
            # Check size limit
            if len(data) > self.config.max_size_bytes:
                return ConnectorResult(
                    success=False,
                    error=f"Downloaded content exceeds size limit ({self.config.max_size_bytes} bytes)"
                )
            
            # Determine if it's a zip file
            is_zip = (
                source.endswith(".zip") or
                content_type in ("application/zip", "application/x-zip-compressed")
            )
            
            if is_zip:
                return self._extract_zip(data, destination, source)
            else:
                return self._save_file(data, destination, source, parsed.path)
                
        except HTTPError as e:
            return ConnectorResult(success=False, error=f"HTTP error: {e.code}")
        except URLError as e:
            return ConnectorResult(success=False, error=f"Network error: {e.reason}")
        except Exception as e:
            return ConnectorResult(success=False, error=f"Error: {e}")
    
    def _extract_zip(self, data: bytes, destination: Path, source: str) -> ConnectorResult:
        """Extract zip file to destination.
        
        Args:
            data: Zip file data
            destination: Destination directory
            source: Original source URL
            
        Returns:
            ConnectorResult
        """
        files_extracted: list[str] = []
        total_size = 0
        errors: list[str] = []
        
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for member in zf.namelist():
                    # Skip directories
                    if member.endswith("/"):
                        continue
                    
                    # Validate path
                    if not self.validate_path(member):
                        errors.append(f"Skipped blocked file: {member}")
                        continue
                    
                    # Check file count
                    if len(files_extracted) >= self.config.max_files:
                        errors.append(f"Reached max file limit ({self.config.max_files})")
                        break
                    
                    # Get file info
                    info = zf.getinfo(member)
                    
                    # Check size limit
                    if not self.check_size_limit(total_size, info.file_size):
                        errors.append(f"Reached max size limit ({self.config.max_size_bytes} bytes)")
                        break
                    
                    # Extract file
                    dest_path = destination / member
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with zf.open(member) as src, open(dest_path, "wb") as dst:
                        file_data = src.read()
                        dst.write(file_data)
                    
                    files_extracted.append(member)
                    total_size += info.file_size
            
            return ConnectorResult(
                success=True,
                local_path=destination,
                files=files_extracted,
                metadata={
                    "source": source,
                    "type": "zip",
                    "files_extracted": len(files_extracted),
                    "total_bytes": total_size,
                    "errors": errors if errors else None,
                }
            )
            
        except zipfile.BadZipFile:
            return ConnectorResult(
                success=False,
                error="Downloaded file is not a valid ZIP archive"
            )
    
    def _save_file(
        self, data: bytes, destination: Path, source: str, path: str
    ) -> ConnectorResult:
        """Save single file to destination.
        
        Args:
            data: File data
            destination: Destination directory
            source: Original source URL
            path: URL path component
            
        Returns:
            ConnectorResult
        """
        # Get filename from path
        filename = Path(path).name
        if not filename:
            filename = "artifact"
        
        # Validate filename
        if not self.validate_path(filename):
            return ConnectorResult(
                success=False,
                error=f"File type blocked: {Path(filename).suffix}"
            )
        
        dest_file = destination / filename
        
        # Ensure no path traversal in filename
        if not dest_file.resolve().is_relative_to(destination.resolve()):
            return ConnectorResult(
                success=False,
                error="Filename contains path traversal attempt"
            )
        
        with open(dest_file, "wb") as f:
            f.write(data)
        
        return ConnectorResult(
            success=True,
            local_path=destination,
            files=[filename],
            metadata={
                "source": source,
                "type": "file",
                "files_extracted": 1,
                "total_bytes": len(data),
            }
        )
