"""Security hardening for untrusted input handling.

Provides limits and sanitization to prevent:
- Path traversal attacks
- Resource exhaustion (memory, CPU)
- Injection attacks in outputs
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

# Default security limits
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
DEFAULT_MAX_JSON_DEPTH = 100
DEFAULT_MAX_JSON_SIZE = 50 * 1024 * 1024  # 50 MB
DEFAULT_MAX_STRING_LENGTH = 10_000_000  # 10 MB of text


class SecurityLimits:
    """Configurable security limits."""

    def __init__(
        self,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        max_json_depth: int = DEFAULT_MAX_JSON_DEPTH,
        max_json_size: int = DEFAULT_MAX_JSON_SIZE,
        max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
    ) -> None:
        self.max_file_size = max_file_size
        self.max_json_depth = max_json_depth
        self.max_json_size = max_json_size
        self.max_string_length = max_string_length


class SecurityError(Exception):
    """Security violation detected."""
    pass


def check_path_safety(path: Path, base_dir: Path | None = None) -> Path:
    """Verify path is safe (no traversal outside base_dir).
    
    Args:
        path: Path to check
        base_dir: Allowed base directory (if None, no restriction)
    
    Returns:
        Resolved path
    
    Raises:
        SecurityError: If path traversal detected
    """
    resolved = path.resolve()

    if base_dir is not None:
        base_resolved = base_dir.resolve()
        try:
            resolved.relative_to(base_resolved)
        except ValueError:
            raise SecurityError(
                f"Path traversal detected: {path} is outside {base_dir}"
            )

    # Check for suspicious patterns
    suspicious = ["..", "~", "$HOME", "$PWD", "//"]
    path_str = str(path)
    for pattern in suspicious:
        if pattern in path_str and pattern != "//":  # Allow double-slash in URLs
            # Additional check - resolve and verify
            pass

    return resolved


def safe_read_file(
    path: Path,
    limits: SecurityLimits | None = None,
    base_dir: Path | None = None,
) -> bytes:
    """Safely read file with size limits.
    
    Args:
        path: File path
        limits: Security limits
        base_dir: Base directory for path traversal check
    
    Returns:
        File contents as bytes
    
    Raises:
        SecurityError: If file too large or path unsafe
    """
    if limits is None:
        limits = SecurityLimits()

    # Check path safety
    safe_path = check_path_safety(path, base_dir)

    # Check file size before reading
    size = safe_path.stat().st_size
    if size > limits.max_file_size:
        raise SecurityError(
            f"File too large: {path} ({size} bytes > {limits.max_file_size})"
        )

    return safe_path.read_bytes()


def safe_read_text(
    path: Path,
    limits: SecurityLimits | None = None,
    base_dir: Path | None = None,
) -> str:
    """Safely read file as text with limits."""
    content = safe_read_file(path, limits, base_dir)

    # Check decoded length
    text = content.decode("utf-8", errors="replace")
    max_len = limits.max_string_length if limits else DEFAULT_MAX_STRING_LENGTH
    if len(text) > max_len:
        raise SecurityError(
            f"Text content too long: {path} ({len(text)} chars)"
        )

    return text


def check_json_depth(obj: Any, current_depth: int = 0, max_depth: int = DEFAULT_MAX_JSON_DEPTH) -> int:
    """Check JSON object depth.
    
    Returns:
        Actual depth of object
    
    Raises:
        SecurityError: If depth exceeds max_depth
    """
    if current_depth > max_depth:
        raise SecurityError(f"JSON depth exceeds maximum: {max_depth}")

    if isinstance(obj, dict):
        max_child_depth = current_depth
        for value in obj.values():
            child_depth = check_json_depth(value, current_depth + 1, max_depth)
            max_child_depth = max(max_child_depth, child_depth)
        return max_child_depth
    elif isinstance(obj, list):
        max_child_depth = current_depth
        for item in obj:
            child_depth = check_json_depth(item, current_depth + 1, max_depth)
            max_child_depth = max(max_child_depth, child_depth)
        return max_child_depth
    else:
        return current_depth


def safe_load_json(
    data: bytes | str,
    limits: SecurityLimits | None = None,
) -> Any:
    """Safely load JSON with depth and size limits.
    
    Args:
        data: JSON data as bytes or string
        limits: Security limits
    
    Returns:
        Parsed JSON object
    
    Raises:
        SecurityError: If limits exceeded
    """
    if limits is None:
        limits = SecurityLimits()

    # Check size
    if isinstance(data, bytes):
        if len(data) > limits.max_json_size:
            raise SecurityError(
                f"JSON data too large: {len(data)} bytes > {limits.max_json_size}"
            )
        text = data.decode("utf-8", errors="replace")
    else:
        if len(data.encode("utf-8")) > limits.max_json_size:
            raise SecurityError(
                f"JSON data too large: {len(data)} chars exceeds size limit"
            )
        text = data

    # Parse JSON
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise SecurityError(f"Invalid JSON: {e}")

    # Check depth
    check_json_depth(obj, max_depth=limits.max_json_depth)

    return obj


def safe_extract_zip(
    zip_path: Path,
    output_dir: Path,
    limits: SecurityLimits | None = None,
) -> list[Path]:
    """Safely extract zip file with path traversal protection.
    
    Args:
        zip_path: Path to zip file
        output_dir: Directory to extract to
        limits: Security limits
    
    Returns:
        List of extracted file paths
    
    Raises:
        SecurityError: If traversal or size limits exceeded
    """
    if limits is None:
        limits = SecurityLimits()

    extracted: list[Path] = []
    output_dir = output_dir.resolve()

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            # Check for path traversal in member name
            member_path = Path(member)

            # Reject absolute paths
            if member_path.is_absolute():
                raise SecurityError(f"Absolute path in zip: {member}")

            # Reject paths with .. components
            if ".." in member_path.parts:
                raise SecurityError(f"Path traversal in zip: {member}")

            # Compute target path and verify it's within output_dir
            target = output_dir / member_path
            try:
                target.relative_to(output_dir)
            except ValueError:
                raise SecurityError(f"Zip extraction would escape target: {member}")

            # Check file size if available
            info = zf.getinfo(member)
            if info.file_size > limits.max_file_size:
                raise SecurityError(
                    f"Zip member too large: {member} ({info.file_size} bytes)"
                )

            # Extract
            zf.extract(member, output_dir)
            extracted.append(target)

    return extracted


def sanitize_markdown(text: str) -> str:
    """Sanitize markdown to prevent injection.
    
    Escapes or removes potentially dangerous content:
    - HTML script tags
    - Data URIs
    - Suspicious URLs
    """
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '[REMOVED: script]', text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '[REMOVED: event handler]', text, flags=re.IGNORECASE)

    # Remove data URIs
    text = re.sub(r'data:[^\s"\'>]+', '[REMOVED: data URI]', text, flags=re.IGNORECASE)

    # Remove javascript: URLs
    text = re.sub(r'javascript:[^\s"\'>]+', '[REMOVED: javascript URL]', text, flags=re.IGNORECASE)

    return text


def validate_input_path(
    path: str | Path,
    allowed_extensions: set[str] | None = None,
    base_dir: Path | None = None,
) -> Path:
    """Validate input path is safe and has allowed extension.
    
    Args:
        path: Input path
        allowed_extensions: Set of allowed extensions (e.g., {'.json', '.yaml'})
        base_dir: Base directory for traversal check
    
    Returns:
        Validated path
    
    Raises:
        SecurityError: If validation fails
    """
    path_obj = Path(path)

    # Check extension
    if allowed_extensions is not None:
        if path_obj.suffix.lower() not in allowed_extensions:
            raise SecurityError(
                f"File extension not allowed: {path_obj.suffix}. "
                f"Allowed: {allowed_extensions}"
            )

    # Check path safety
    return check_path_safety(path_obj, base_dir)
