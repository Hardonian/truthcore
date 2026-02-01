"""Normalization Toolkit (M5).

Deterministic normalization for making inputs boring and consistent.
All operations are stable, platform-agnostic, and suitable for content hashing.

Example:
    >>> from truthcore.normalize import canonical_text, canonical_json
    >>> canonical_text("  hello   world  \\n")
    'hello world'
    >>> canonical_json({"b": 1, "a": 2})
    '{"a":1,"b":1}'
"""

from truthcore.normalize.json_norm import (
    JSONNormalizationConfig,
    JSONNormalizationError,
    JSONNormalizer,
    canonical_json,
    normalize_json,
    parse_json_safe,
)
from truthcore.normalize.parsers import (
    BaseLogParser,
    BlockParser,
    BuildLogParser,
    ESLintJSONParser,
    ESLintTextParser,
    ParsedFinding,
    ParserError,
    PlaywrightJSONParser,
    RegexLogParser,
    SeverityLevel,
    TypeScriptCompilerParser,
    get_parser,
    infer_severity,
    parse_with,
    register_parser,
)
from truthcore.normalize.text import (
    TextNormalizationConfig,
    TextNormalizer,
    canonical_text,
    default_normalizer,
    normalize_lines,
    normalize_text,
)

__all__ = [
    # Text normalization
    "TextNormalizer",
    "TextNormalizationConfig",
    "canonical_text",
    "normalize_text",
    "normalize_lines",
    "default_normalizer",
    # JSON normalization
    "JSONNormalizer",
    "JSONNormalizationConfig",
    "JSONNormalizationError",
    "canonical_json",
    "normalize_json",
    "parse_json_safe",
    # Log parsers
    "BaseLogParser",
    "RegexLogParser",
    "BlockParser",
    "ParsedFinding",
    "SeverityLevel",
    "ParserError",
    "get_parser",
    "register_parser",
    "parse_with",
    "infer_severity",
    # Specific parsers
    "ESLintJSONParser",
    "ESLintTextParser",
    "TypeScriptCompilerParser",
    "PlaywrightJSONParser",
    "BuildLogParser",
]
