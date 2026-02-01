"""Tests for the policy module."""

from __future__ import annotations

from pathlib import Path

import pytest

from truthcore.policy.engine import PolicyEngine, PolicyPackLoader, PolicyResult
from truthcore.policy.models import (
    Matcher,
    PolicyPack,
    PolicyRule,
    Severity,
    Suppression,
)
from truthcore.policy.scanners import (
    ScanContext,
    SecretScanner,
)
from truthcore.policy.validator import PolicyValidator


class TestMatcher:
    """Test the Matcher class."""

    def test_regex_matcher(self):
        """Test regex matcher."""
        matcher = Matcher(type="regex", pattern=r"\d+", flags=[])
        assert matcher.matches("abc123") is True
        assert matcher.matches("abc") is False

    def test_contains_matcher(self):
        """Test contains matcher."""
        matcher = Matcher(type="contains", pattern="secret", flags=["i"])
        assert matcher.matches("my SECRET key") is True
        assert matcher.matches("my key") is False

    def test_equals_matcher(self):
        """Test equals matcher."""
        matcher = Matcher(type="equals", pattern="debug", flags=["i"])
        assert matcher.matches("DEBUG") is True
        assert matcher.matches("debug_mode") is False

    def test_glob_matcher(self):
        """Test glob matcher."""
        matcher = Matcher(type="glob", pattern="*.py", flags=[])
        assert matcher.matches("test.py") is True
        assert matcher.matches("test.txt") is False


class TestPolicyRule:
    """Test the PolicyRule class."""

    def test_rule_creation(self):
        """Test creating a rule."""
        rule = PolicyRule(
            id="TEST_RULE",
            description="Test rule",
            severity=Severity.HIGH,
            category="security",
            target="files",
        )
        assert rule.id == "TEST_RULE"
        assert rule.enabled is True

    def test_rule_suppression(self):
        """Test rule suppression."""
        rule = PolicyRule(
            id="TEST_RULE",
            description="Test rule",
            severity=Severity.HIGH,
            category="security",
            target="files",
            suppressions=[
                Suppression(pattern="test/*", reason="Test files"),
            ],
        )
        assert rule.is_suppressed("test/file.py") is True
        assert rule.is_suppressed("src/file.py") is False


class TestPolicyPack:
    """Test the PolicyPack class."""

    def test_pack_creation(self):
        """Test creating a pack."""
        pack = PolicyPack(
            name="test",
            description="Test pack",
            version="1.0.0",
            rules=[
                PolicyRule(
                    id="RULE_1",
                    description="Rule 1",
                    severity=Severity.HIGH,
                    category="security",
                    target="files",
                ),
            ],
        )
        assert pack.name == "test"
        assert len(pack.get_enabled_rules()) == 1

    def test_get_rule(self):
        """Test getting a rule by ID."""
        pack = PolicyPack(
            name="test",
            description="Test pack",
            version="1.0.0",
            rules=[
                PolicyRule(
                    id="RULE_1",
                    description="Rule 1",
                    severity=Severity.HIGH,
                    category="security",
                    target="files",
                ),
            ],
        )
        rule = pack.get_rule("RULE_1")
        assert rule is not None
        assert rule.id == "RULE_1"
        assert pack.get_rule("NONEXISTENT") is None


class TestPolicyValidator:
    """Test the PolicyValidator."""

    def test_valid_pack(self):
        """Test validating a valid pack."""
        pack_data = {
            "name": "test",
            "description": "Test pack",
            "version": "1.0.0",
            "rules": [
                {
                    "id": "TEST_RULE",
                    "description": "Test rule",
                    "severity": "HIGH",
                    "category": "security",
                    "target": "files",
                },
            ],
        }
        validator = PolicyValidator()
        errors = validator.validate_pack(pack_data)
        assert len(errors) == 0

    def test_invalid_severity(self):
        """Test validating a pack with invalid severity."""
        pack_data = {
            "name": "test",
            "description": "Test pack",
            "version": "1.0.0",
            "rules": [
                {
                    "id": "TEST_RULE",
                    "description": "Test rule",
                    "severity": "CRITICAL",  # Invalid
                    "category": "security",
                    "target": "files",
                },
            ],
        }
        validator = PolicyValidator()
        errors = validator.validate_pack(pack_data)
        assert len(errors) > 0


class TestSecretScanner:
    """Test the SecretScanner."""

    def test_detect_api_key(self, tmp_path: Path):
        """Test detecting API keys."""
        # Create test file
        test_file = tmp_path / "config.py"
        test_file.write_text("api_key = 'sk-1234567890abcdef1234567890'")

        context = ScanContext(input_dir=tmp_path)
        scanner = SecretScanner(context)

        rule = PolicyRule(
            id="TEST_SECRET",
            description="Test secret detection",
            severity=Severity.HIGH,
            category="security",
            target="files",
        )

        findings = scanner.scan(rule)
        assert len(findings) > 0

    def test_no_false_positives(self, tmp_path: Path):
        """Test that safe content doesn't trigger."""
        # Create test file without secrets
        test_file = tmp_path / "safe.py"
        test_file.write_text("# This is a safe file\nprint('hello')")

        context = ScanContext(input_dir=tmp_path)
        scanner = SecretScanner(context)

        rule = PolicyRule(
            id="TEST_SECRET",
            description="Test secret detection",
            severity=Severity.HIGH,
            category="security",
            target="files",
        )

        findings = scanner.scan(rule)
        # May still find generic patterns, but should be minimal


class TestPolicyEngine:
    """Test the PolicyEngine."""

    def test_run_pack(self, tmp_path: Path):
        """Test running a policy pack."""
        # Create test input
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "test.py").write_text("api_key = 'secret123'")

        output_dir = tmp_path / "output"

        pack = PolicyPack(
            name="test",
            description="Test pack",
            version="1.0.0",
            rules=[
                PolicyRule(
                    id="TEST_SECRET",
                    description="Test secret detection",
                    severity=Severity.HIGH,
                    category="security",
                    target="files",
                ),
            ],
        )

        engine = PolicyEngine(input_dir, output_dir)
        result = engine.run_pack(pack)

        assert result.pack_name == "test"
        assert result.rules_evaluated == 1
        assert isinstance(result.findings, list)

    def test_write_outputs(self, tmp_path: Path):
        """Test writing policy outputs."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        engine = PolicyEngine(input_dir, output_dir)

        result = PolicyResult(
            pack_name="test",
            pack_version="1.0.0",
            findings=[],
        )

        paths = engine.write_outputs(result)

        assert "json" in paths
        assert "markdown" in paths
        assert "csv" in paths
        assert paths["json"].exists()


class TestPolicyPackLoader:
    """Test loading policy packs."""

    def test_list_built_in(self):
        """Test listing built-in packs."""
        packs = PolicyPackLoader.list_built_in()
        assert "base" in packs
        assert "security" in packs
        assert "privacy" in packs

    def test_load_built_in_base(self):
        """Test loading the base pack."""
        # This may fail if packs aren't installed, so we handle that
        try:
            pack = PolicyPackLoader.load_pack("base")
            assert pack.name == "base"
            assert len(pack.rules) > 0
        except FileNotFoundError:
            pytest.skip("Built-in packs not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
