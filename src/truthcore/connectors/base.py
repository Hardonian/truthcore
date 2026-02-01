"""Base connector interface for truth-core input sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ConnectorResult:
    """Result from fetching inputs via a connector.
    
    Attributes:
        success: Whether the fetch was successful
        local_path: Path to the fetched inputs directory
        files: List of files that were fetched
        metadata: Additional metadata about the fetch
        error: Error message if fetch failed
    """
    success: bool
    local_path: Path | None = None
    files: list[str] = None  # type: ignore[assignment]
    metadata: dict[str, Any] = None  # type: ignore[assignment]
    error: str | None = None
    
    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConnectorConfig:
    """Base configuration for connectors.
    
    Attributes:
        max_size_bytes: Maximum total size of inputs to fetch (default 100MB)
        max_files: Maximum number of files to fetch (default 1000)
        allowed_extensions: List of allowed file extensions (None = all)
        blocked_extensions: List of blocked file extensions
        sanitize_paths: Whether to sanitize paths for security
    """
    max_size_bytes: int = 100 * 1024 * 1024  # 100MB
    max_files: int = 1000
    allowed_extensions: list[str] | None = None
    blocked_extensions: list[str] = None  # type: ignore[assignment]
    sanitize_paths: bool = True
    
    def __post_init__(self):
        if self.blocked_extensions is None:
            # Block dangerous extensions
            self.blocked_extensions = [
                ".exe", ".dll", ".bat", ".cmd", ".sh", ".bin",
                ".so", ".dylib", ".app", ".msi", ".dmg", ".pkg",
            ]


class BaseConnector(ABC):
    """Abstract base class for input connectors.
    
    Connectors fetch inputs from various sources and normalize them
    into a local directory ready for the judge to consume.
    """
    
    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize connector with configuration.
        
        Args:
            config: Connector configuration
        """
        self.config = config or ConnectorConfig()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return connector name."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this connector is available (dependencies, auth, etc)."""
        pass
    
    @abstractmethod
    def fetch(self, source: str, destination: Path) -> ConnectorResult:
        """Fetch inputs from source and place in destination.
        
        Args:
            source: Source specification (URL, path, etc)
            destination: Local directory to place inputs
            
        Returns:
            ConnectorResult with status and metadata
        """
        pass
    
    def validate_path(self, path: str) -> bool:
        """Validate that a path is safe and within limits.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid and safe
        """
        if not self.config.sanitize_paths:
            return True
            
        # Check for path traversal attempts
        normalized = Path(path).resolve()
        
        # Block absolute paths that could escape
        if path.startswith('/') or path.startswith('\\'):
            if '..' in path:
                return False
                
        # Check extension
        if self.config.blocked_extensions:
            ext = Path(path).suffix.lower()
            if ext in self.config.blocked_extensions:
                return False
                
        if self.config.allowed_extensions:
            ext = Path(path).suffix.lower()
            if ext not in self.config.allowed_extensions:
                return False
                
        return True
    
    def check_size_limit(self, current_size: int, new_file_size: int) -> bool:
        """Check if adding a file would exceed size limit.
        
        Args:
            current_size: Current total size in bytes
            new_file_size: Size of file to add
            
        Returns:
            True if within limits
        """
        return (current_size + new_file_size) <= self.config.max_size_bytes
