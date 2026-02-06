"""Golden tests for policy ruleset evidence packets.

Loads golden test packets from /evidence-packets/*.json, validates them
against the schema, runs the policy evaluator, and asserts outputs match
expected results. Prevents ruleset regressions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
from truthcore.policy.models import PolicyPack, PolicyRule, Severity

# Paths
EVIDENCE_DIR = Path(__file__).parent.parent / "evidence-packets"
SCHEMA_PATH = EVIDENCE_DIR / "golden_test_packet.schema.json"


def _load_schema() -> dict[str, Any]:
    """Load the golden test packet JSON schema."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_packets() -> list[tuple[str, dict[str, Any]]]:
    """Load all golden test packets from evidence-packets directory."""
    packets = []
    for path in sorted(EVIDENCE_DIR.glob("GP-*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        packets.append((path.name, data))
    return packets


GOLDEN_SCHEMA = _load_schema()
GOLDEN_PACKETS = _load_packets()


def _packet_ids() -> list[str]:
    """Generate test IDs from packet filenames."""
    return [name for name, _ in GOLDEN_PACKETS]


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestGoldenPacketSchema:
    """Validate that all golden packets conform to the schema."""

    def test_schema_itself_is_valid(self):
        """The golden test schema must be a valid JSON Schema draft-07."""
        jsonschema.Draft7Validator.check_schema(GOLDEN_SCHEMA)

    @pytest.mark.parametrize(
        "name,packet", GOLDEN_PACKETS, ids=_packet_ids()
    )
    def test_packet_validates_against_schema(
        self, name: str, packet: dict[str, Any]
    ):
        """Each packet must pass JSON Schema validation."""
        jsonschema.validate(instance=packet, schema=GOLDEN_SCHEMA)

    def test_minimum_packet_count(self):
        """Corpus must contain at least 15 packets."""
        assert len(GOLDEN_PACKETS) >= 15, (
            f"Golden corpus has only {len(GOLDEN_PACKETS)} packets; need >= 15"
        )

    def test_packet_ids_are_unique(self):
        """All packet_id values must be unique."""
        ids = [p["packet_id"] for _, p in GOLDEN_PACKETS]
        assert len(ids) == len(set(ids)), "Duplicate packet_id detected"

    def test_all_packs_represented(self):
        """At least one packet per policy pack."""
        packs_in_corpus = {p["pack_name"] for _, p in GOLDEN_PACKETS}
        expected = {"base", "security", "privacy", "agent"}
        missing = expected - packs_in_corpus
        assert not missing, f"Missing packs in golden corpus: {missing}"


# ---------------------------------------------------------------------------
# Evaluator tests
# ---------------------------------------------------------------------------


class TestGoldenPacketEvaluator:
    """Run the policy evaluator against each golden packet and assert outcomes."""

    @pytest.mark.parametrize(
        "name,packet", GOLDEN_PACKETS, ids=_packet_ids()
    )
    def test_evaluator_output_matches_expected(
        self, name: str, packet: dict[str, Any], tmp_path: Path
    ):
        """Run the evaluator and check that the result matches expected."""
        # 1. Materialise input facts on disk
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        for file_spec in packet["input_facts"]["files"]:
            fpath = input_dir / file_spec["path"]
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(file_spec["content"], encoding="utf-8")

        output_dir = tmp_path / "output"

        # 2. Load the target policy pack
        pack_name = packet["pack_name"]
        try:
            pack = PolicyPackLoader.load_pack(pack_name)
        except FileNotFoundError:
            pytest.skip(f"Built-in pack '{pack_name}' not installed")

        # 3. Narrow to the single rule under test
        target_rule_id = packet["rule_id"]
        rule = pack.get_rule(target_rule_id)
        if rule is None:
            pytest.fail(
                f"Rule {target_rule_id} not found in pack {pack_name}"
            )

        single_rule_pack = PolicyPack(
            name=pack.name,
            description=pack.description,
            version=pack.version,
            rules=[rule],
            metadata=pack.metadata,
        )

        # 4. Run the engine
        engine = PolicyEngine(input_dir, output_dir)
        result = engine.run_pack(single_rule_pack)

        # 5. Assert expectations
        expected = packet["expected"]

        if expected["triggered"]:
            assert len(result.findings) >= expected["finding_count_min"], (
                f"[{packet['packet_id']}] Expected >= {expected['finding_count_min']} "
                f"findings, got {len(result.findings)}"
            )
        else:
            max_count = expected.get("finding_count_max", 0)
            assert len(result.findings) <= max_count, (
                f"[{packet['packet_id']}] Expected <= {max_count} findings "
                f"(triggered=false), got {len(result.findings)}"
            )

        if "finding_count_max" in expected and expected["triggered"]:
            assert len(result.findings) <= expected["finding_count_max"], (
                f"[{packet['packet_id']}] Expected <= {expected['finding_count_max']} "
                f"findings, got {len(result.findings)}"
            )

        if expected.get("has_blocking") is True:
            assert result.has_blocking(), (
                f"[{packet['packet_id']}] Expected blocking finding but none found"
            )
        elif expected.get("has_blocking") is False and expected["triggered"]:
            assert not result.has_blocking(), (
                f"[{packet['packet_id']}] Expected no blocking findings but found some"
            )

        if expected.get("severity") and result.findings:
            expected_sev = Severity(expected["severity"])
            actual_severities = {f.severity for f in result.findings}
            assert expected_sev in actual_severities, (
                f"[{packet['packet_id']}] Expected severity {expected_sev.value} "
                f"in findings, got {[s.value for s in actual_severities]}"
            )


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestGoldenPacketDeterminism:
    """Ensure golden test evaluations are deterministic (same input → same output)."""

    DETERMINISM_RUNS = 3

    @pytest.mark.parametrize(
        "name,packet",
        [(n, p) for n, p in GOLDEN_PACKETS if p["expected"]["triggered"]],
        ids=[n for n, p in GOLDEN_PACKETS if p["expected"]["triggered"]],
    )
    def test_deterministic_finding_count(
        self, name: str, packet: dict[str, Any], tmp_path: Path
    ):
        """Running the same packet N times must produce the same finding count."""
        counts = []
        for i in range(self.DETERMINISM_RUNS):
            run_dir = tmp_path / f"run-{i}"
            input_dir = run_dir / "input"
            input_dir.mkdir(parents=True)
            for file_spec in packet["input_facts"]["files"]:
                fpath = input_dir / file_spec["path"]
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(file_spec["content"], encoding="utf-8")

            output_dir = run_dir / "output"
            try:
                pack = PolicyPackLoader.load_pack(packet["pack_name"])
            except FileNotFoundError:
                pytest.skip(f"Built-in pack not installed")

            rule = pack.get_rule(packet["rule_id"])
            if rule is None:
                pytest.fail(f"Rule {packet['rule_id']} not found")

            single = PolicyPack(
                name=pack.name,
                description=pack.description,
                version=pack.version,
                rules=[rule],
                metadata=pack.metadata,
            )
            engine = PolicyEngine(input_dir, output_dir)
            result = engine.run_pack(single)
            counts.append(len(result.findings))

        assert len(set(counts)) == 1, (
            f"[{packet['packet_id']}] Non-deterministic: finding counts varied across "
            f"{self.DETERMINISM_RUNS} runs: {counts}"
        )
