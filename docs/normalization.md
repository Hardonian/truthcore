# Normalization Toolkit (M5)

Deterministic normalization for making inputs boring and consistent. All operations are stable, platform-agnostic, and suitable for content hashing.

## Overview

The normalization toolkit provides three main capabilities:

1. **Canonical Text Normalization** - Normalize text for comparison/hashing
2. **Canonical JSON Normalization** - Normalize JSON structures for comparison/hashing  
3. **Log Parser Helpers** - Parse common tool outputs into structured findings

## Quick Start

```python
from truthcore.normalize import canonical_text, canonical_json

# Normalize text
clean = canonical_text("  hello   world  \n")  # 'hello world'

# Normalize JSON
json_str = canonical_json({"b": 1, "a": 2})  # '{"a":1,"b":1}'
```

## Canonical Text Normalization

### Basic Usage

```python
from truthcore.normalize import TextNormalizer, TextNormalizationConfig

# Use defaults
normalizer = TextNormalizer()
result = normalizer.normalize("  messy   text  \r\n")

# Configure behavior
config = TextNormalizationConfig(
    collapse_whitespace=True,
    redact_timestamps=True,
    normalize_paths=True,
)
normalizer = TextNormalizer(config)
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `collapse_whitespace` | True | Collapse multiple spaces/tabs |
| `trim_lines` | True | Trim each line |
| `trim_final` | True | Trim final result |
| `newline_style` | "lf" | "lf", "crlf", or "native" |
| `redact_timestamps` | False | Replace timestamps with placeholder |
| `normalize_paths` | True | Convert paths to forward slashes |

### Timestamp Redaction

For stable content hashing, redact timestamps:

```python
from truthcore.normalize import normalize_text

# Redact timestamps
result = normalize_text(
    "Error at 2024-01-15T10:30:00Z",
    redact_timestamps=True
)
# Result: "Error at [TIMESTAMP]"
```

## Canonical JSON Normalization

### Basic Usage

```python
from truthcore.normalize import JSONNormalizer, canonical_json

# Quick canonical form
json_str = canonical_json({"z": 1, "a": 2})  # Sorted keys, compact

# Full control
normalizer = JSONNormalizer()
normalized = normalizer.normalize({"z": 1, "a": 2})
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `sort_keys` | True | Sort object keys |
| `numeric_format` | "string" | "string", "float", or "decimal" |
| `max_depth` | 100 | Maximum nesting depth |
| `max_size_bytes` | 50MB | Maximum JSON size |
| `indent` | None | Indentation (None=compact) |

### Safe Parsing

```python
from truthcore.normalize import parse_json_safe, JSONNormalizationError

try:
    data = parse_json_safe(large_json_string, max_depth=50)
except JSONNormalizationError as e:
    print(f"JSON error: {e}")
```

## Log Parser Helpers

### Supported Parsers

- `eslint-json` - ESLint JSON output
- `eslint-text` - ESLint text output  
- `tsc` - TypeScript compiler output
- `playwright-json` - Playwright JSON report
- `build` - Generic build logs

### Usage

```python
from truthcore.normalize import get_parser, parse_with
from pathlib import Path

# Parse from file
parser = get_parser("eslint-json")
findings = parser.parse_file(Path("eslint-output.json"))

# Or parse content directly
content = Path("build.log").read_text()
findings = parse_with("build", content)
```

### Finding Structure

Each parsed finding has:

```python
{
    "tool": "eslint",
    "severity": "HIGH",  # BLOCKER, HIGH, MEDIUM, LOW, INFO
    "message": "Missing semicolon",
    "location": "src/app.js:10:5",
    "rule_id": "semi",
    "category": "style",
    "metadata": {...}
}
```

### Custom Parsers

```python
from truthcore.normalize import RegexLogParser, register_parser

# Create parser
parser = RegexLogParser(
    tool_name="mytool",
    pattern=r"(?P<severity>ERROR|WARN): (?P<message>.+)",
    severity_map={"ERROR": SeverityLevel.HIGH}
)

# Register for reuse
register_parser("mytool", lambda: parser)

# Use it
findings = parse_with("mytool", log_content)
```

## Integration with Engines

Use normalization in your engines:

```python
from truthcore.normalize import canonical_text, canonical_json

# Normalize for content hashing
def compute_fingerprint(text: str) -> str:
    return hashlib.sha256(
        canonical_text(text).encode()
    ).hexdigest()[:16]

# Normalize JSON outputs
def normalize_output(data: dict) -> str:
    return canonical_json(data)
```

## Determinism Guarantees

- **Same input → Same output** (deterministic)
- **No random sampling** (stable sorting)
- **No network calls** (local only)
- **UTC timestamps only** (timezone-independent)
- **Consistent path separators** (forward slash)

## Performance

- Pre-compiled regex patterns
- Streaming file reading
- Configurable size limits
- Memory-efficient for large files

## API Reference

### Text Functions

- `canonical_text(text)` - Quick canonical form
- `normalize_text(text, **kwargs)` - Configurable normalization
- `normalize_lines(lines, **kwargs)` - Normalize line list

### JSON Functions

- `canonical_json(data)` - Quick canonical JSON
- `normalize_json(data, **kwargs)` - Configurable normalization
- `parse_json_safe(json_str, **kwargs)` - Safe parsing with limits

### Parser Functions

- `get_parser(tool_name)` - Get registered parser
- `register_parser(name, factory)` - Register custom parser
- `parse_with(tool_name, content)` - Parse with registered parser
- `infer_severity(text)` - Infer severity from text
