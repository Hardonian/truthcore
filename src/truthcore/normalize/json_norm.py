"""Normalization Toolkit - Canonical JSON Normalization.

Provides deterministic JSON normalization with stable key ordering,
numeric precision control, and safe parsing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class JSONNormalizationError(Exception):
    """Error during JSON normalization."""
    pass


@dataclass(frozen=True)
class JSONNormalizationConfig:
    """Configuration for JSON normalization.
    
    All settings default to safe, deterministic values.
    """

    # Key ordering
    sort_keys: bool = True

    # Numeric handling
    numeric_format: str = "string"  # "string", "float", "decimal"
    float_precision: int = 15

    # Size limits (for safety)
    max_depth: int = 100
    max_size_bytes: int = 50 * 1024 * 1024  # 50MB
    max_keys: int = 10000
    max_string_length: int = 100000

    # Output formatting
    indent: int | None = None  # None for compact, 2 for readable
    ensure_ascii: bool = True
    separators: tuple[str, str] = (",", ":")

    # Null handling
    preserve_null: bool = True

    # Array handling
    sort_arrays: bool = False  # Sort arrays of primitives for stability

    def __post_init__(self):
        """Validate configuration."""
        if self.numeric_format not in ("string", "float", "decimal"):
            raise ValueError(f"Invalid numeric_format: {self.numeric_format}")


class JSONNormalizer:
    """Deterministic JSON normalizer.
    
    Normalizes JSON to a canonical form suitable for content hashing
    and comparison. All operations are deterministic and stable.
    """

    def __init__(self, config: JSONNormalizationConfig | None = None):
        """Initialize with configuration.
        
        Args:
            config: Normalization configuration (uses defaults if None)
        """
        self.config = config or JSONNormalizationConfig()

    def normalize(self, data: Any) -> Any:
        """Normalize data structure to canonical form.
        
        Args:
            data: JSON-serializable data structure
            
        Returns:
            Normalized data structure
            
        Raises:
            JSONNormalizationError: If data exceeds limits or is invalid
            
        Example:
            >>> normalizer = JSONNormalizer()
            >>> normalizer.normalize({"b": 1, "a": 2})
            {'a': 2, 'b': 1}
        """
        return self._normalize_value(data, depth=0)

    def normalize_string(self, json_str: str) -> str:
        """Normalize a JSON string.
        
        Args:
            json_str: JSON string to normalize
            
        Returns:
            Normalized JSON string
            
        Raises:
            JSONNormalizationError: If JSON is invalid or exceeds limits
        """
        # Check size limit
        if len(json_str.encode("utf-8")) > self.config.max_size_bytes:
            raise JSONNormalizationError(
                f"JSON exceeds maximum size: {self.config.max_size_bytes} bytes"
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise JSONNormalizationError(f"Invalid JSON: {e}") from e

        normalized = self.normalize(data)
        return self.serialize(normalized)

    def serialize(self, data: Any) -> str:
        """Serialize data to canonical JSON string.
        
        Args:
            data: Data to serialize
            
        Returns:
            Canonical JSON string
        """
        kwargs: dict[str, Any] = {
            "sort_keys": self.config.sort_keys,
            "ensure_ascii": self.config.ensure_ascii,
            "separators": self.config.separators,
        }

        if self.config.indent is not None:
            kwargs["indent"] = self.config.indent

        return json.dumps(data, **kwargs)

    def parse_safe(self, json_str: str) -> Any:
        """Safely parse JSON with limits.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Parsed data structure
            
        Raises:
            JSONNormalizationError: If JSON is invalid or exceeds limits
        """
        # Check size limit
        size_bytes = len(json_str.encode("utf-8"))
        if size_bytes > self.config.max_size_bytes:
            raise JSONNormalizationError(
                f"JSON size ({size_bytes} bytes) exceeds maximum ({self.config.max_size_bytes} bytes)"
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise JSONNormalizationError(f"Invalid JSON: {e}") from e

        # Validate depth and structure
        self._validate_structure(data)

        return data

    def _normalize_value(self, value: Any, depth: int) -> Any:
        """Recursively normalize a value."""
        if depth > self.config.max_depth:
            raise JSONNormalizationError(
                f"JSON depth exceeds maximum: {self.config.max_depth}"
            )

        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return self._normalize_number(value)

        if isinstance(value, str):
            return self._normalize_string(value)

        if isinstance(value, list):
            return self._normalize_array(value, depth)

        if isinstance(value, dict):
            return self._normalize_object(value, depth)

        if isinstance(value, Decimal):
            return self._normalize_number(float(value))

        # Handle other types by converting to string
        return str(value)

    def _normalize_number(self, value: float | int) -> Any:
        """Normalize a numeric value."""
        if self.config.numeric_format == "string":
            # Use repr for maximum precision, then strip trailing zeros
            if isinstance(value, float):
                s = repr(value)
                # Handle scientific notation
                if "e" in s.lower():
                    return s
                # Strip trailing zeros after decimal
                if "." in s:
                    s = s.rstrip("0").rstrip(".")
                return s
            return str(value)

        elif self.config.numeric_format == "decimal":
            try:
                return str(Decimal(value))
            except InvalidOperation:
                return str(value)

        else:  # float
            if isinstance(value, float):
                # Round to configured precision to avoid float drift
                return round(value, self.config.float_precision)
            return value

    def _normalize_string(self, value: str) -> str:
        """Normalize a string value."""
        if len(value) > self.config.max_string_length:
            raise JSONNormalizationError(
                f"String length ({len(value)}) exceeds maximum ({self.config.max_string_length})"
            )
        return value

    def _normalize_array(self, value: list[Any], depth: int) -> list[Any]:
        """Normalize an array."""
        normalized = [self._normalize_value(item, depth + 1) for item in value]

        # Optionally sort arrays of primitives for stability
        if self.config.sort_arrays:
            try:
                # Only sort if all elements are comparable primitives
                if all(isinstance(x, (int, float, str, bool)) for x in normalized):
                    normalized = sorted(normalized, key=lambda x: (type(x).__name__, x))
            except TypeError:
                pass  # Mixed types, don't sort

        return normalized

    def _normalize_object(self, value: dict[str, Any], depth: int) -> dict[str, Any]:
        """Normalize an object."""
        if len(value) > self.config.max_keys:
            raise JSONNormalizationError(
                f"Object key count ({len(value)}) exceeds maximum ({self.config.max_keys})"
            )

        # Normalize all values
        normalized = {
            k: self._normalize_value(value[k], depth + 1)
            for k in value
        }

        return normalized

    def _validate_structure(self, data: Any, depth: int = 0) -> None:
        """Validate data structure against limits."""
        if depth > self.config.max_depth:
            raise JSONNormalizationError(
                f"JSON depth exceeds maximum: {self.config.max_depth}"
            )

        if isinstance(data, dict):
            if len(data) > self.config.max_keys:
                raise JSONNormalizationError(
                    f"Object key count ({len(data)}) exceeds maximum"
                )
            for key, value in data.items():
                if len(key) > self.config.max_string_length:
                    raise JSONNormalizationError(
                        f"Key length ({len(key)}) exceeds maximum"
                    )
                self._validate_structure(value, depth + 1)

        elif isinstance(data, list):
            for item in data:
                self._validate_structure(item, depth + 1)

        elif isinstance(data, str):
            if len(data) > self.config.max_string_length:
                raise JSONNormalizationError(
                    f"String length ({len(data)}) exceeds maximum"
                )


def canonical_json(data: Any, **kwargs: Any) -> str:
    """Quick canonical JSON for content hashing.
    
    Uses compact, sorted representation suitable for hashing.
    
    Args:
        data: Data to serialize
        **kwargs: Optional configuration overrides
        
    Returns:
        Canonical JSON string
        
    Example:
        >>> canonical_json({"b": 1, "a": 2})
        '{"a":1,"b":1}'
    """
    config = JSONNormalizationConfig(
        sort_keys=True,
        indent=None,
        separators=(",", ":"),
        ensure_ascii=True,
        **kwargs,
    )
    normalizer = JSONNormalizer(config)
    normalized = normalizer.normalize(data)
    return normalizer.serialize(normalized)


def normalize_json(data: Any, **kwargs: Any) -> Any:
    """Normalize JSON data structure.
    
    Args:
        data: JSON data to normalize
        **kwargs: Configuration overrides
        
    Returns:
        Normalized data structure
    """
    config = JSONNormalizationConfig(**kwargs)
    normalizer = JSONNormalizer(config)
    return normalizer.normalize(data)


def parse_json_safe(json_str: str, **kwargs: Any) -> Any:
    """Safely parse JSON with limits.
    
    Args:
        json_str: JSON string to parse
        **kwargs: Configuration overrides for limits
        
    Returns:
        Parsed data structure
        
    Raises:
        JSONNormalizationError: If JSON is invalid or exceeds limits
    """
    config = JSONNormalizationConfig(**kwargs)
    normalizer = JSONNormalizer(config)
    return normalizer.parse_safe(json_str)
