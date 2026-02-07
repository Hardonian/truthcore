"""Golden tests for evidence packets and deterministic evaluation."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from truthcore.evidence import EvidencePacket, RuleEvaluation
from truthcore.policy.models import PolicyPack, PolicyRule, Severity
from truthcore.rules_engine import RulesEngine
from truthcore.rules_engine import RulesEngine


class TestEvidencePacketDeterminism:
    """Test that evidence packets are generated deterministically."""

    def test_evidence_packet_serialization_deterministic(self):
        """Evidence packet serialization should be deterministic."""

        pack = PolicyPack(
            name="test-pack",
            description="Test pack",
            version="1.0.0",
            rules=[PolicyRule(
                id="test-rule",
                description="Test rule",
                severity=Severity.HIGH,
                category="test",
                target="files",
            )],
        )

        rule_eval = RuleEvaluation(
            rule_id="test-rule",
            rule_description="Test rule",
            triggered=True,
            matches_found=1,
            threshold_met=True,
            suppressed=False,
            findings=[],
            alternatives_not_triggered=["No matches found for any rule patterns"],
        )

        # Compute policy pack hash
        pack_content = str(sorted(pack.to_dict().items()))
        policy_pack_hash = hashlib.sha256(pack_content.encode("utf-8")).hexdigest()[:16]

        # Create packet twice
        packet1 = EvidencePacket(
            evaluation_id="test-id-1",
            timestamp="2024-01-01T00:00:00",
            version="1.0.0",
            policy_pack_name=pack.name,
            policy_pack_version=pack.version,
            policy_pack_hash=policy_pack_hash,
            input_hash="test-hash-123",
            input_summary={"test": "data"},
            rules_evaluated=1,
            rules_triggered=1,
            rule_evaluations=[rule_eval],
            decision="allow",
            decision_reason="Test decision",
            blocking_findings=0,
        )

        packet2 = EvidencePacket(
            evaluation_id="test-id-2",
            timestamp="2024-01-01T00:00:00",
            version="1.0.0",
            policy_pack_name=pack.name,
            policy_pack_version=pack.version,
            policy_pack_hash=policy_pack_hash,
            input_hash="test-hash-123",
            input_summary={"test": "data"},
            rules_evaluated=1,
            rules_triggered=1,
            rule_evaluations=[rule_eval],
            decision="allow",
            decision_reason="Test decision",
            blocking_findings=0,
        )

        # Serialize both
        dict1 = packet1.to_dict()
        dict2 = packet2.to_dict()

        # Remove non-deterministic fields for comparison
        for d in [dict1, dict2]:
            d.pop("evaluation_id", None)
            d.pop("timestamp", None)

        assert dict1 == dict2, "Evidence packet serialization is not deterministic"

    def test_content_hash_deterministic(self):
        """Content hash should be deterministic."""
        pack = PolicyPack(
            name="test-pack",
            description="Test pack",
            version="1.0.0",
            rules=[PolicyRule(
                id="test-rule",
                description="Test rule",
                severity=Severity.HIGH,
                category="test",
                target="files",
            )],
        )

        rule_eval = RuleEvaluation(
            rule_id="test-rule",
            rule_description="Test rule",
            triggered=True,
            matches_found=1,
            threshold_met=True,
            suppressed=False,
            findings=[],
            alternatives_not_triggered=[],
        )

        # Compute policy pack hash
        pack_content = str(sorted(pack.to_dict().items()))
        policy_pack_hash = hashlib.sha256(pack_content.encode("utf-8")).hexdigest()[:16]

        packet1 = EvidencePacket(
            evaluation_id="test-id-1",
            timestamp="2024-01-01T00:00:00",
            version="1.0.0",
            policy_pack_name=pack.name,
            policy_pack_version=pack.version,
            policy_pack_hash=policy_pack_hash,
            input_hash="test-hash-123",
            input_summary={"test": "data"},
            rules_evaluated=1,
            rules_triggered=1,
            rule_evaluations=[rule_eval],
            decision="allow",
            decision_reason="Test decision",
            blocking_findings=0,
        )

        packet2 = EvidencePacket(
            evaluation_id="test-id-1",  # Same ID for content hash test
            timestamp="2024-01-01T00:00:00",
            version="1.0.0",
            policy_pack_name=pack.name,
            policy_pack_version=pack.version,
            policy_pack_hash=policy_pack_hash,
            input_hash="test-hash-123",
            input_summary={"test": "data"},
            rules_evaluated=1,
            rules_triggered=1,
            rule_evaluations=[rule_eval],
            decision="allow",
            decision_reason="Test decision",
            blocking_findings=0,
        )

        assert packet1.compute_content_hash() == packet2.compute_content_hash()


class TestRulesEngineIntegration:
    """Integration tests for the rules engine with evidence packets."""

    def test_evaluate_with_base_pack(self):
        """Test evaluation with base policy pack."""
        # Create temporary input directory with test file
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()

            # Create a test file that should trigger a rule
            test_file = input_dir / "test.py"
            test_file.write_text('API_KEY = "sk-1234567890abcdef"')

            # Evaluate
            engine = RulesEngine("base")
            result = engine.evaluate(input_dir)

            assert "decision" in result
            assert "evidence" in result
            assert isinstance(result["evidence"], EvidencePacket)
            assert "summary" in result

            # Should detect the API key
            assert result["decision"] in ["deny", "conditional"]
            assert result["findings_count"] > 0

    def test_evaluate_clean_input(self):
        """Test evaluation with clean input."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()

            # Create a clean test file
            test_file = input_dir / "test.py"
            test_file.write_text('print("Hello, World!")')

            engine = RulesEngine("base")
            result = engine.evaluate(input_dir)

            assert result["decision"] == "allow"
            assert result["findings_count"] == 0

    def test_evidence_packet_structure(self):
        """Test that evidence packet has all required fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()

            test_file = input_dir / "test.py"
            test_file.write_text('print("test")')

            engine = RulesEngine("base")
            result = engine.evaluate(input_dir)

            evidence = result["evidence"]
            packet_dict = evidence.to_dict()

            # Check required fields
            assert "evaluation_id" in packet_dict
            assert "timestamp" in packet_dict
            assert "version" in packet_dict
            assert "policy_pack" in packet_dict
            assert "input" in packet_dict
            assert "evaluation" in packet_dict
            assert "decision" in packet_dict
            assert "execution_metadata" in packet_dict
            assert "content_hash" in packet_dict

            # Check evaluation details
            evaluation = packet_dict["evaluation"]
            assert "rules_evaluated" in evaluation
            assert "rules_triggered" in evaluation
            assert "rule_evaluations" in evaluation

            # Check rule evaluations have explain why not
            for rule_eval in evaluation["rule_evaluations"]:
                assert "alternatives_not_triggered" in rule_eval

    def test_markdown_summary_generation(self):
        """Test that markdown summary is generated correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            input_dir.mkdir()

            test_file = input_dir / "test.py"
            test_file.write_text('print("test")')

            engine = RulesEngine("base")
            result = engine.evaluate(input_dir)

            summary = result["summary"]
            assert isinstance(summary, str)
            assert "# Evidence Packet Summary" in summary
            assert "Decision:" in summary
