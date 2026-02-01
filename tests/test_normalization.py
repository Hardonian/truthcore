"""Tests for Normalization Toolkit (M5)."""

from __future__ import annotations

import pytest

from truthcore.normalize import (
    TextNormalizationConfig,
    TextNormalizer,
    canonical_text,
    normalize_text,
)
from truthcore.normalize.json_norm import (
    JSONNormalizationConfig,
    JSONNormalizationError,
    JSONNormalizer,
    canonical_json,
    parse_json_safe,
)
from truthcore.normalize.parsers import (
    BuildLogParser,
    ESLintJSONParser,
    ESLintTextParser,
    SeverityLevel,
    TypeScriptCompilerParser,
    get_parser,
    infer_severity,
    parse_with,
)


class TestTextNormalization:
    """Tests for text normalization."""

    def test_canonical_text_basic(self):
        """Test basic text normalization."""
        result = canonical_text("  hello   world  \n")
        assert result == "hello world"

    def test_canonical_text_newlines(self):
        """Test newline normalization."""
        # Various newline styles should normalize to same output
        result_crlf = canonical_text("hello\r\nworld")
        result_cr = canonical_text("hello\rworld")
        result_lf = canonical_text("hello\nworld")

        assert result_crlf == result_cr == result_lf
        assert "\r" not in result_crlf

    def test_determinism_same_input(self):
        """Test that same input produces identical output."""
        input_text = "  messy   text  \r\nwith  spaces\n"

        result1 = canonical_text(input_text)
        result2 = canonical_text(input_text)
        result3 = canonical_text(input_text)

        assert result1 == result2 == result3

    def test_whitespace_collapsing(self):
        """Test whitespace collapsing."""
        result = canonical_text("hello    world    test")
        assert result == "hello world test"

    def test_trim_lines(self):
        """Test line trimming."""
        result = canonical_text("  line1  \n  line2  ")
        assert "  line1  " not in result
        assert "  line2  " not in result

    def test_path_normalization(self):
        """Test path separator normalization."""
        config = TextNormalizationConfig(normalize_paths=True)
        normalizer = TextNormalizer(config)

        result = normalizer.normalize("path\\to\\file.txt")
        assert result == "path/to/file.txt"

    def test_timestamp_redaction(self):
        """Test timestamp redaction."""
        config = TextNormalizationConfig(redact_timestamps=True)
        normalizer = TextNormalizer(config)

        result = normalizer.normalize("Error at 2024-01-15T10:30:00Z")
        assert "[TIMESTAMP]" in result
        assert "2024-01-15" not in result

    def test_configurable_whitespace(self):
        """Test configurable whitespace handling."""
        config = TextNormalizationConfig(collapse_whitespace=False)
        normalizer = TextNormalizer(config)

        result = normalizer.normalize("hello   world")
        assert result == "hello   world"  # Not collapsed

    def test_empty_input(self):
        """Test empty input handling."""
        result = canonical_text("")
        assert result == ""

    def test_normalize_lines(self):
        """Test line list normalization."""
        lines = ["  line1  ", "  line2  ", ""]
        result = normalize_text("\n".join(lines))
        assert "line1" in result
        assert "line2" in result


class TestJSONNormalization:
    """Tests for JSON normalization."""

    def test_canonical_json_sorts_keys(self):
        """Test that canonical JSON sorts keys."""
        data = {"z": 1, "a": 2, "m": 3}
        result = canonical_json(data)

        # Keys should be in alphabetical order
        assert result.index('"a"') < result.index('"m"')
        assert result.index('"m"') < result.index('"z"')

    def test_determinism_same_input(self):
        """Test that same JSON produces identical output."""
        data = {"b": {"y": 1, "x": 2}, "a": [3, 1, 2]}

        result1 = canonical_json(data)
        result2 = canonical_json(data)
        result3 = canonical_json(data)

        assert result1 == result2 == result3

    def test_nested_sorting(self):
        """Test that nested objects are also sorted."""
        data = {"outer": {"z": 1, "a": 2}}
        result = canonical_json(data)

        assert '"a"' in result
        assert '"z"' in result

    def test_numeric_string_format(self):
        """Test numeric formatting as strings."""
        config = JSONNormalizationConfig(numeric_format="string")
        normalizer = JSONNormalizer(config)

        result = normalizer.normalize({"value": 3.14159})
        serialized = normalizer.serialize(result)

        assert "3.14159" in serialized

    def test_max_depth_enforcement(self):
        """Test max depth enforcement."""
        # Create deeply nested structure
        data = {}
        current = data
        for i in range(150):
            current["nested"] = {}
            current = current["nested"]

        normalizer = JSONNormalizer()

        with pytest.raises(JSONNormalizationError):
            normalizer.normalize(data)

    def test_safe_parsing_valid(self):
        """Test safe parsing of valid JSON."""
        json_str = '{"key": "value", "number": 42}'
        result = parse_json_safe(json_str)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_safe_parsing_invalid(self):
        """Test safe parsing of invalid JSON."""
        json_str = '{"key": invalid}'

        with pytest.raises(JSONNormalizationError):
            parse_json_safe(json_str)

    def test_empty_json(self):
        """Test empty JSON handling."""
        result = canonical_json({})
        assert result == "{}"

    def test_array_normalization(self):
        """Test array normalization."""
        data = {"items": [3, 1, 2]}
        result = canonical_json(data)

        # Arrays should preserve order by default
        assert "[3,1,2]" in result or "[3, 1, 2]" in result

    def test_unicode_handling(self):
        """Test Unicode handling."""
        data = {"message": "Hello 世界"}
        result = canonical_json(data)

        assert "Hello" in result


class TestLogParsers:
    """Tests for log parsers."""

    def test_eslint_text_parser(self):
        """Test ESLint text parser."""
        log = """src/app.js:10:5: error Missing semicolon [semi]
src/app.js:20:3: warning Unused variable [no-unused-vars]"""

        parser = ESLintTextParser()
        findings = parser.parse(log)

        assert len(findings) == 2
        assert findings[0].severity == SeverityLevel.HIGH
        assert findings[1].severity == SeverityLevel.LOW
        assert findings[0].rule_id == "semi"

    def test_eslint_json_parser(self):
        """Test ESLint JSON parser."""
        json_log = """[{
            "filePath": "src/app.js",
            "messages": [
                {"line": 10, "column": 5, "severity": 2, "message": "Missing semicolon", "ruleId": "semi"},
                {"line": 20, "column": 3, "severity": 1, "message": "Unused var", "ruleId": "no-unused-vars"}
            ]
        }]"""

        parser = ESLintJSONParser()
        findings = parser.parse(json_log)

        assert len(findings) == 2
        assert findings[0].severity == SeverityLevel.HIGH
        assert findings[0].location == "src/app.js:10:5"

    def test_tsc_parser(self):
        """Test TypeScript compiler parser."""
        log = "src/app.ts(10,5): error TS2345: Argument of type 'string' is not assignable to parameter of type 'number'."

        parser = TypeScriptCompilerParser()
        findings = parser.parse(log)

        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.HIGH
        assert findings[0].rule_id == "TS2345"
        assert "src/app.ts:10:5" in findings[0].location

    def test_build_log_parser(self):
        """Test build log parser."""
        log = """INFO: Build started
ERROR: Compilation failed
WARNING: Deprecated API usage"""

        parser = BuildLogParser()
        findings = parser.parse(log)

        assert len(findings) >= 2
        severities = [f.severity for f in findings]
        assert SeverityLevel.HIGH in severities
        assert SeverityLevel.MEDIUM in severities

    def test_severity_inference_blocker(self):
        """Test severity inference for blockers."""
        text = "CRITICAL ERROR: System failure"
        severity = infer_severity(text)
        assert severity == SeverityLevel.BLOCKER

    def test_severity_inference_high(self):
        """Test severity inference for high."""
        text = "ERROR: Something failed"
        severity = infer_severity(text)
        assert severity == SeverityLevel.HIGH

    def test_severity_inference_medium(self):
        """Test severity inference for medium."""
        text = "WARNING: Be careful"
        severity = infer_severity(text)
        assert severity == SeverityLevel.MEDIUM

    def test_severity_inference_low(self):
        """Test severity inference for low."""
        text = "NOTICE: Minor issue"
        severity = infer_severity(text)
        assert severity == SeverityLevel.LOW

    def test_get_parser_valid(self):
        """Test getting a valid parser."""
        parser = get_parser("eslint-json")
        assert parser is not None
        assert isinstance(parser, ESLintJSONParser)

    def test_get_parser_invalid(self):
        """Test getting an invalid parser."""
        parser = get_parser("nonexistent")
        assert parser is None

    def test_parse_with_valid(self):
        """Test parse_with with valid parser."""
        log = "src/app.js:10:5: error Missing semicolon [semi]"
        findings = parse_with("eslint-text", log)

        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.HIGH

    def test_parse_with_invalid(self):
        """Test parse_with with invalid parser."""
        with pytest.raises(ValueError):
            parse_with("nonexistent", "some log")

    def test_finding_to_dict(self):
        """Test finding conversion to dict."""
        from truthcore.normalize.parsers import ParsedFinding

        finding = ParsedFinding(
            tool="test",
            severity=SeverityLevel.HIGH,
            message="Test message",
            location="file:10:5",
            rule_id="test-rule",
        )

        data = finding.to_dict()
        assert data["tool"] == "test"
        assert data["severity"] == "HIGH"
        assert data["message"] == "Test message"


class TestDeterminism:
    """Tests for determinism guarantees."""

    def test_text_normalization_determinism(self):
        """Text normalization must be deterministic."""
        inputs = [
            "Hello World",
            "  padded  ",
            "multi\nline\n\ntext",
            "path\\to\\file",
            "2024-01-15T10:30:00Z timestamp",
        ]

        for input_text in inputs:
            results = [canonical_text(input_text) for _ in range(10)]
            assert all(r == results[0] for r in results), f"Non-deterministic for: {input_text}"

    def test_json_normalization_determinism(self):
        """JSON normalization must be deterministic."""
        inputs = [
            {"z": 1, "a": 2},
            {"nested": {"c": 1, "a": 2, "b": 3}},
            [3, 1, 2],
            {"items": [{"id": 2}, {"id": 1}]},
        ]

        for input_data in inputs:
            results = [canonical_json(input_data) for _ in range(10)]
            assert all(r == results[0] for r in results), f"Non-deterministic for: {input_data}"

    def test_parser_determinism(self):
        """Parsers must produce deterministic output."""
        log = """src/app.js:10:5: error Error 1 [rule1]
src/app.js:20:3: error Error 2 [rule2]
src/app.js:5:1: warning Warning 1 [rule3]"""

        parser = ESLintTextParser()

        results = [parser.parse(log) for _ in range(10)]

        # Check same number of findings each time
        assert all(len(r) == len(results[0]) for r in results)

        # Check findings are in same order
        for i in range(len(results[0])):
            messages = [r[i].message for r in results]
            assert all(m == messages[0] for m in messages)
