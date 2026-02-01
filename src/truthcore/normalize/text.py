"""Normalization Toolkit - Canonical Text Normalization.

Provides deterministic text normalization to make inputs boring and consistent.
All operations are stable, platform-agnostic, and suitable for content hashing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any


@dataclass(frozen=True)
class TextNormalizationConfig:
    """Configuration for text normalization.
    
    All settings default to safe, deterministic values.
    """

    # Whitespace handling
    collapse_whitespace: bool = True
    trim_lines: bool = True
    trim_final: bool = True

    # Newline handling
    newline_style: str = "lf"  # "lf", "crlf", "native"

    # Timestamp redaction (for stable hashing)
    redact_timestamps: bool = False
    timestamp_patterns: tuple[str, ...] = (
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
        r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}",
        r"\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}",
        r"\[?\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]?",
    )
    timestamp_replacement: str = "[TIMESTAMP]"

    # Path normalization
    normalize_paths: bool = True
    path_separator: str = "/"  # Normalize to forward slashes

    # Line ending
    ensure_trailing_newline: bool = False

    def __post_init__(self):
        """Validate configuration."""
        if self.newline_style not in ("lf", "crlf", "native"):
            raise ValueError(f"Invalid newline_style: {self.newline_style}")


class TextNormalizer:
    """Deterministic text normalizer.
    
    Normalizes text to a canonical form suitable for content hashing
    and comparison. All operations are deterministic and stable.
    """

    # Pre-compiled patterns for performance
    _whitespace_pattern: Pattern[str] = re.compile(r"[ \t]+")
    _blank_line_pattern: Pattern[str] = re.compile(r"\n\s*\n")

    def __init__(self, config: TextNormalizationConfig | None = None):
        """Initialize with configuration.
        
        Args:
            config: Normalization configuration (uses defaults if None)
        """
        self.config = config or TextNormalizationConfig()
        self._timestamp_patterns: list[Pattern[str]] = [
            re.compile(p) for p in self.config.timestamp_patterns
        ]

    def normalize(self, text: str) -> str:
        """Normalize text to canonical form.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text in canonical form
            
        Example:
            >>> normalizer = TextNormalizer()
            >>> normalizer.normalize("  hello   world  \\n")
            'hello world'
        """
        result = text

        # Normalize newlines first
        result = self._normalize_newlines(result)

        # Redact timestamps if configured
        if self.config.redact_timestamps:
            result = self._redact_timestamps(result)

        # Normalize paths
        if self.config.normalize_paths:
            result = self._normalize_paths(result)

        # Collapse whitespace
        if self.config.collapse_whitespace:
            result = self._collapse_whitespace(result)

        # Trim lines
        if self.config.trim_lines:
            result = self._trim_lines(result)

        # Final trim
        if self.config.trim_final:
            result = result.strip()

        # Ensure trailing newline if configured
        if self.config.ensure_trailing_newline and not result.endswith("\n"):
            result += "\n"

        return result

    def normalize_lines(self, lines: list[str]) -> list[str]:
        """Normalize a list of lines.
        
        Args:
            lines: List of text lines
            
        Returns:
            List of normalized lines (empty lines removed if collapsing)
        """
        normalized = [self.normalize(line) for line in lines]

        if self.config.collapse_whitespace:
            # Remove empty lines that resulted from normalization
            normalized = [line for line in normalized if line]

        return normalized

    def normalize_file(self, path: Path) -> str:
        """Normalize content of a file.
        
        Args:
            path: Path to file to normalize
            
        Returns:
            Normalized file content
            
        Raises:
            FileNotFoundError: If file does not exist
            UnicodeDecodeError: If file cannot be decoded as UTF-8
        """
        content = path.read_text(encoding="utf-8")
        return self.normalize(content)

    def _normalize_newlines(self, text: str) -> str:
        """Normalize line endings to configured style."""
        # First, normalize all line endings to \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Then apply configured style
        if self.config.newline_style == "crlf":
            text = text.replace("\n", "\r\n")
        elif self.config.newline_style == "native":
            import os
            if os.linesep != "\n":
                text = text.replace("\n", os.linesep)
        # "lf" style keeps \n

        return text

    def _redact_timestamps(self, text: str) -> str:
        """Redact timestamps for stable comparison."""
        for pattern in self._timestamp_patterns:
            text = pattern.sub(self.config.timestamp_replacement, text)
        return text

    def _normalize_paths(self, text: str) -> str:
        """Normalize path separators."""
        if self.config.path_separator == "/":
            # Normalize backslashes to forward slashes
            text = text.replace("\\", "/")
        elif self.config.path_separator == "\\":
            # Normalize forward slashes to backslashes
            text = text.replace("/", "\\")
        return text

    def _collapse_whitespace(self, text: str) -> str:
        """Collapse multiple whitespace characters."""
        # Replace multiple spaces/tabs with single space
        text = self._whitespace_pattern.sub(" ", text)
        # Collapse multiple blank lines to single blank line
        text = self._blank_line_pattern.sub("\n\n", text)
        return text

    def _trim_lines(self, text: str) -> str:
        """Trim whitespace from each line."""
        lines = text.split("\n")
        lines = [line.strip() for line in lines]
        return "\n".join(lines)


def normalize_text(text: str, **kwargs: Any) -> str:
    """Convenience function for one-off text normalization.
    
    Args:
        text: Text to normalize
        **kwargs: Configuration overrides (see TextNormalizationConfig)
        
    Returns:
        Normalized text
        
    Example:
        >>> normalize_text("  hello   world  ", trim_final=True)
        'hello world'
    """
    config = TextNormalizationConfig(**kwargs)
    normalizer = TextNormalizer(config)
    return normalizer.normalize(text)


def normalize_lines(lines: list[str], **kwargs: Any) -> list[str]:
    """Convenience function for one-off line normalization.
    
    Args:
        lines: Lines to normalize
        **kwargs: Configuration overrides (see TextNormalizationConfig)
        
    Returns:
        Normalized lines
    """
    config = TextNormalizationConfig(**kwargs)
    normalizer = TextNormalizer(config)
    return normalizer.normalize_lines(lines)


# Default normalizer instance for convenience
default_normalizer = TextNormalizer()


def canonical_text(text: str) -> str:
    """Quick canonical form for content hashing.
    
    Uses conservative defaults suitable for generating content hashes.
    
    Args:
        text: Text to canonicalize
        
    Returns:
        Canonical text form
        
    Example:
        >>> canonical_text("Hello\\n\\nWorld\\r\\n")
        'Hello\\nWorld'
    """
    return default_normalizer.normalize(text)
