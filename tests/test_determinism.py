"""Determinism test suite for TruthCore.

Verifies that:
1. Same input -> same output byte-for-byte (10x stability check)
2. Canonical JSON produces identical output across runs
3. Evidence hashes are stable
4. Rule evaluation order is deterministic
5. Verdict aggregation produces identical results
6. Explainability envelopes have stable content hashes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from truthcore.canonical import canonical_hash, canonical_json, evidence_hash
from truthcore.determinism import (
    FIXED_GIT_SHA,
    FIXED_RUN_ID,
    FIXED_TIMESTAMP,
    determinism_mode,
    is_deterministic,
    stable_git_sha,
    stable_isoformat,
    stable_now,
    stable_random_hex,
    stable_run_id,
    stable_timestamp,
    stable_uuid_hex,
)
from truthcore.envelope import ExplainabilityEnvelope, ReasonEntry, UncertaintyNote
from truthcore.invariant_dsl import InvariantDSL
from truthcore.manifest import RunManifest, hash_dict, normalize_timestamp
from truthcore.severity import Category, EngineHealth, Severity
from truthcore.verdict.aggregator import VerdictAggregator
from truthcore.verdict.models import Mode, VerdictThresholds


class TestDeterminismMode:
    """Test the determinism mode flag and fixed values."""

    def test_determinism_mode_context_manager(self):
        """Determinism mode should be active within context."""
        assert not is_deterministic()
        with determinism_mode():
            assert is_deterministic()
        assert not is_deterministic()

    def test_fixed_timestamp(self):
        """Timestamps should be fixed in determinism mode."""
        with determinism_mode():
            t1 = stable_timestamp()
            t2 = stable_timestamp()
            assert t1 == t2 == FIXED_TIMESTAMP

    def test_fixed_run_id(self):
        """Run IDs should be fixed in determinism mode."""
        with determinism_mode():
            r1 = stable_run_id()
            r2 = stable_run_id()
            assert r1 == r2 == FIXED_RUN_ID

    def test_fixed_uuid(self):
        """UUIDs should be fixed in determinism mode."""
        with determinism_mode():
            u1 = stable_uuid_hex()
            u2 = stable_uuid_hex()
            assert u1 == u2

    def test_fixed_git_sha(self):
        """Git SHA should be fixed in determinism mode."""
        with determinism_mode():
            s1 = stable_git_sha()
            s2 = stable_git_sha()
            assert s1 == s2 == FIXED_GIT_SHA

    def test_fixed_random_hex(self):
        """Random hex should be fixed in determinism mode."""
        with determinism_mode():
            r1 = stable_random_hex(8)
            r2 = stable_random_hex(8)
            assert r1 == r2 == "0" * 16

    def test_normalize_timestamp_deterministic(self):
        """normalize_timestamp() should return fixed value in determinism mode."""
        with determinism_mode():
            ts1 = normalize_timestamp()
            ts2 = normalize_timestamp()
            assert ts1 == ts2 == FIXED_TIMESTAMP


class TestCanonicalJSON:
    """Test canonical JSON serialization stability."""

    def test_sorted_keys(self):
        """Keys should be sorted at all levels."""
        data = {"z": 1, "a": 2, "m": {"z": 3, "a": 4}}
        result = canonical_json(data)
        assert result == '{"a":2,"m":{"a":4,"z":3},"z":1}'

    def test_no_whitespace(self):
        """No whitespace in output."""
        data = {"key": "value", "nested": {"a": 1}}
        result = canonical_json(data)
        assert " " not in result
        assert "\n" not in result

    def test_null_handling(self):
        """None should serialize as null."""
        assert canonical_json({"x": None}) == '{"x":null}'

    def test_bool_handling(self):
        """Booleans should serialize as true/false."""
        assert canonical_json({"a": True, "b": False}) == '{"a":true,"b":false}'

    def test_negative_zero(self):
        """Negative zero should normalize to positive zero."""
        result = canonical_json({"x": -0.0})
        assert result == '{"x":0.0}'

    def test_nan_raises(self):
        """NaN values should raise an error."""
        with pytest.raises(ValueError, match="NaN"):
            canonical_json({"x": float("nan")})

    def test_inf_stable_string(self):
        """Infinity should be represented as a stable string."""
        result = canonical_json({"x": float("inf")})
        assert result == '{"x":"Infinity"}'
        result_neg = canonical_json({"x": float("-inf")})
        assert result_neg == '{"x":"-Infinity"}'

    def test_arrays_preserve_order(self):
        """Arrays should maintain their order."""
        data = {"items": [3, 1, 2]}
        result = canonical_json(data)
        assert result == '{"items":[3,1,2]}'

    def test_ascii_only(self):
        """Output should be ASCII-only."""
        data = {"name": "test"}
        result = canonical_json(data)
        assert all(ord(c) < 128 for c in result)

    def test_identical_across_calls(self):
        """Same input should produce identical output every time."""
        data = {"complex": {"nested": [1, 2, {"a": "b"}], "flag": True}}
        results = [canonical_json(data) for _ in range(100)]
        assert len(set(results)) == 1


class TestCanonicalHashing:
    """Test that hashing is stable and cross-platform consistent."""

    def test_hash_stability(self):
        """Same data should produce identical hash across calls."""
        data = {"finding": "xss", "severity": "HIGH", "count": 5}
        hashes = [canonical_hash(data) for _ in range(100)]
        assert len(set(hashes)) == 1

    def test_hash_dict_uses_canonical(self):
        """hash_dict should use canonical JSON internally."""
        data = {"z": 1, "a": 2}
        h1 = hash_dict(data)
        h2 = hash_dict(data)
        assert h1 == h2

    def test_key_order_independence(self):
        """Hash should be identical regardless of key insertion order."""
        d1 = {"a": 1, "b": 2, "c": 3}
        d2 = {"c": 3, "a": 1, "b": 2}
        assert canonical_hash(d1) == canonical_hash(d2)

    def test_evidence_hash_stable(self):
        """Evidence packet hashes must be stable."""
        packet = {
            "packet_id": "test-001",
            "artifacts": [{"type": "verdict", "path": "/out/verdict.json"}],
            "source": {"repository": "test-repo", "commit_sha": "abc123"},
        }
        h1 = evidence_hash(packet)
        h2 = evidence_hash(packet)
        assert h1 == h2

    def test_different_data_different_hash(self):
        """Different data should produce different hashes."""
        d1 = {"value": 1}
        d2 = {"value": 2}
        assert canonical_hash(d1) != canonical_hash(d2)


class TestRuleEngineDeterminism:
    """Test that rule evaluation is deterministic."""

    def _make_dsl(self) -> InvariantDSL:
        """Create a DSL with test data."""
        data = {
            "coverage": 85,
            "findings": [
                {"severity": "HIGH", "rule": "xss"},
                {"severity": "LOW", "rule": "style"},
                {"severity": "HIGH", "rule": "sqli"},
            ],
            "blocker_count": 0,
            "threshold": 80,
        }
        dsl = InvariantDSL(data)
        dsl.set_explain_mode(True)
        return dsl

    def test_single_rule_deterministic(self):
        """Single rule evaluation should be deterministic."""
        rule = {"id": "coverage_check", "operator": ">=", "left": "coverage", "right": "threshold"}

        results = []
        for _ in range(10):
            dsl = self._make_dsl()
            passed, evaluation = dsl.evaluate_rule(rule)
            results.append((passed, evaluation.to_dict() if evaluation else None))

        # All 10 runs should be identical
        first = json.dumps(results[0], sort_keys=True)
        for r in results[1:]:
            assert json.dumps(r, sort_keys=True) == first

    def test_composite_rule_deterministic(self):
        """Composite (all/any) rules should be deterministic."""
        rule = {
            "id": "composite_check",
            "all": [
                {"id": "cov", "operator": ">=", "left": "coverage", "right": 80},
                {"id": "no_blockers", "operator": "==", "left": "blocker_count", "right": 0},
            ],
        }

        results = []
        for _ in range(10):
            dsl = self._make_dsl()
            passed, evaluation = dsl.evaluate_rule(rule)
            results.append((passed, evaluation.to_dict() if evaluation else None))

        first = json.dumps(results[0], sort_keys=True)
        for r in results[1:]:
            assert json.dumps(r, sort_keys=True) == first

    def test_aggregation_deterministic(self):
        """Aggregation rules should be deterministic."""
        rule = {
            "id": "high_count",
            "aggregation": "count",
            "path": "findings",
            "filter": {"severity": "HIGH"},
            "operator": "==",
            "right": 2,
        }

        results = []
        for _ in range(10):
            dsl = self._make_dsl()
            passed, evaluation = dsl.evaluate_rule(rule)
            results.append((passed, evaluation.to_dict() if evaluation else None))

        first = json.dumps(results[0], sort_keys=True)
        for r in results[1:]:
            assert json.dumps(r, sort_keys=True) == first

    def test_batch_evaluate_sorted_by_id(self):
        """evaluate_rules should sort by rule ID."""
        dsl = self._make_dsl()
        rules = [
            {"id": "z_rule", "operator": ">=", "left": "coverage", "right": 80},
            {"id": "a_rule", "operator": "==", "left": "blocker_count", "right": 0},
            {"id": "m_rule", "operator": ">", "left": "coverage", "right": 0},
        ]
        results = dsl.evaluate_rules(rules)
        assert len(results) == 3
        # Results should be in alphabetical order by rule ID
        evals = [r[1] for r in results if r[1]]
        assert [e.rule_id for e in evals] == ["a_rule", "m_rule", "z_rule"]

    def test_evaluation_sequence_is_monotonic(self):
        """Evaluation sequence numbers should be monotonically increasing."""
        dsl = self._make_dsl()
        rules = [
            {"id": "r1", "operator": ">=", "left": "coverage", "right": 80},
            {"id": "r2", "operator": "==", "left": "blocker_count", "right": 0},
        ]
        for rule in rules:
            dsl.evaluate_rule(rule)

        sequences = [e.sequence for e in dsl.evaluations]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)  # All unique


class TestVerdictDeterminism:
    """Test that verdict aggregation is deterministic end-to-end."""

    def _make_aggregator(self) -> VerdictAggregator:
        """Create an aggregator with test findings."""
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        aggregator = VerdictAggregator(
            thresholds=thresholds,
            expected_engines=["lint", "test"],
        )

        # Register engine health
        aggregator.register_engine_health(EngineHealth(
            engine_id="lint", expected=True, ran=True, succeeded=True,
            timestamp="2025-01-01T00:00:00Z", findings_reported=2,
        ))
        aggregator.register_engine_health(EngineHealth(
            engine_id="test", expected=True, ran=True, succeeded=True,
            timestamp="2025-01-01T00:00:00Z", findings_reported=1,
        ))

        # Add findings
        aggregator.add_finding(
            finding_id="f1", tool="lint", severity="HIGH",
            category="security", message="XSS vulnerability found",
            location="src/app.py:42", rule_id="SEC001",
            source_engine="lint", run_id="test-run",
        )
        aggregator.add_finding(
            finding_id="f2", tool="lint", severity="MEDIUM",
            category="types", message="Missing type annotation",
            location="src/app.py:100", rule_id="TYP001",
            source_engine="lint", run_id="test-run",
        )
        aggregator.add_finding(
            finding_id="f3", tool="test", severity="LOW",
            category="general", message="Test coverage below 90%",
            location="tests/", rule_id="COV001",
            source_engine="test", run_id="test-run",
        )

        return aggregator

    def test_verdict_10x_identical(self):
        """Same inputs must produce byte-identical JSON output 10 times."""
        with determinism_mode():
            outputs = []
            for _ in range(10):
                agg = self._make_aggregator()
                result = agg.aggregate(mode=Mode.PR, run_id="test-run")
                output_json = json.dumps(result.to_dict(), sort_keys=True)
                outputs.append(output_json)

            # All 10 must be identical
            assert len(set(outputs)) == 1, "Verdict output is not deterministic across 10 runs"

    def test_envelope_10x_identical(self):
        """Explainability envelope must be identical across 10 runs."""
        with determinism_mode():
            envelopes = []
            for _ in range(10):
                agg = self._make_aggregator()
                result = agg.aggregate(mode=Mode.PR, run_id="test-run")
                envelope = result.to_envelope()
                envelopes.append(json.dumps(envelope, sort_keys=True))

            assert len(set(envelopes)) == 1, "Envelope is not deterministic across 10 runs"

    def test_findings_sorted_deterministically(self):
        """Top findings should be in stable order."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")

            ids = [f.finding_id for f in result.top_findings]
            # HIGH severity first, then MEDIUM, then LOW
            assert ids == ["f1", "f2", "f3"]

    def test_engines_sorted_by_id(self):
        """Engine contributions should be sorted by engine_id."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")

            engine_ids = [e.engine_id for e in result.engines]
            assert engine_ids == sorted(engine_ids)

    def test_categories_sorted_by_value(self):
        """Category breakdowns should be sorted by category value."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")

            cat_values = [c.category.value for c in result.categories]
            assert cat_values == sorted(cat_values)

    def test_verdict_has_reasons_mapped_to_rules(self):
        """Verdict output should include reasons mapped to rule IDs."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")
            envelope = result.to_envelope()

            # Must have reasons
            assert len(envelope["reasons"]) > 0, "Envelope must have reasons"

            # Each reason must have rule_id
            for reason in envelope["reasons"]:
                assert "rule_id" in reason, "Each reason must have a rule_id"
                assert reason["rule_id"], "rule_id must not be empty"

    def test_verdict_has_evidence_refs(self):
        """Verdict output should include evidence references."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")
            envelope = result.to_envelope()

            assert len(envelope["evidence_refs"]) > 0, "Must have evidence refs"

    def test_verdict_has_content_hash(self):
        """Envelope must include stable content hash."""
        with determinism_mode():
            agg = self._make_aggregator()
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")
            envelope = result.to_envelope()

            assert "content_hash" in envelope
            assert len(envelope["content_hash"]) == 32  # blake2b 16-byte digest


class TestExplainabilityEnvelope:
    """Test the explainability envelope structure and stability."""

    def test_envelope_has_all_required_fields(self):
        """Envelope must have decision, reasons, evidence_refs, uncertainty."""
        env = ExplainabilityEnvelope(
            decision="SHIP",
            reasons=[ReasonEntry("rule_1", "All checks passed", "ship")],
            evidence_refs=["ev_001"],
            uncertainty=[UncertaintyNote("engine", "1 engine degraded", "informational")],
            payload={"verdict": "SHIP"},
        )
        d = env.to_dict()
        assert "decision" in d
        assert "reasons" in d
        assert "evidence_refs" in d
        assert "uncertainty" in d
        assert "content_hash" in d
        assert "timestamp" in d
        assert "envelope_version" in d

    def test_envelope_hash_is_deterministic(self):
        """Content hash should be identical for identical inputs."""
        with determinism_mode():
            envs = []
            for _ in range(10):
                env = ExplainabilityEnvelope(
                    decision="NO_SHIP",
                    reasons=[ReasonEntry("sec_001", "XSS found", "no_ship", "HIGH")],
                    evidence_refs=["ev_002"],
                    payload={"verdict": "NO_SHIP", "total_points": 50},
                )
                envs.append(env.content_hash)

            assert len(set(envs)) == 1

    def test_uncertainty_notes_explicit(self):
        """Uncertainty notes should prevent fake precision."""
        env = ExplainabilityEnvelope(
            decision="DEGRADED",
            uncertainty=[
                UncertaintyNote(
                    source="engine_health",
                    description="2 engines failed",
                    impact="may_change_verdict",
                    confidence_range=(0.3, 0.7),
                ),
            ],
        )
        d = env.to_dict()
        assert len(d["uncertainty"]) == 1
        assert d["uncertainty"][0]["impact"] == "may_change_verdict"
        assert d["uncertainty"][0]["confidence_range"] == [0.3, 0.7]


class TestGoldenVerdictReproduction:
    """Test that verdicts can be reproduced from fixture inputs."""

    HAPPY_PATH_FINDINGS = {
        "findings": [
            {"id": "f1", "severity": "INFO", "category": "general",
             "message": "All checks passed", "tool": "lint"},
        ],
    }

    MISSING_EVIDENCE_FINDINGS = {
        "findings": [
            {"id": "f1", "severity": "BLOCKER", "category": "security",
             "message": "[EVIDENCE_MISSING] Required security scan not provided",
             "tool": "policy", "rule_id": "EVIDENCE_REQUIRED_001"},
        ],
    }

    CONFLICTING_EVIDENCE_FINDINGS = {
        "findings": [
            {"id": "f1", "severity": "HIGH", "category": "security",
             "message": "SQL injection detected", "tool": "sast", "rule_id": "SEC_SQLI_001"},
            {"id": "f2", "severity": "INFO", "category": "security",
             "message": "SQL injection check passed", "tool": "dast", "rule_id": "SEC_SQLI_002"},
        ],
    }

    AMBIGUOUS_CLASSIFICATION_FINDINGS = {
        "findings": [
            {"id": "f1", "severity": "MEDIUM", "category": "general",
             "message": "Hardcoded credential-like string found",
             "tool": "lint", "rule_id": "AMB_CRED_001"},
            {"id": "f2", "severity": "MEDIUM", "category": "general",
             "message": "Potential PII exposure in log statement",
             "tool": "lint", "rule_id": "AMB_PII_001"},
        ],
    }

    PARTIAL_COMPLIANCE_FINDINGS = {
        "findings": [
            {"id": "f1", "severity": "HIGH", "category": "types",
             "message": "Missing type annotations in public API",
             "tool": "typecheck", "rule_id": "TYP_PUB_001"},
            {"id": "f2", "severity": "LOW", "category": "build",
             "message": "Deprecated dependency version",
             "tool": "deps", "rule_id": "DEP_OLD_001"},
            {"id": "f3", "severity": "INFO", "category": "general",
             "message": "Test coverage at 82% (threshold: 80%)",
             "tool": "coverage", "rule_id": "COV_PCT_001"},
        ],
    }

    @pytest.mark.parametrize("scenario,findings_data,expected_has_blockers", [
        ("happy_path", HAPPY_PATH_FINDINGS, False),
        ("missing_evidence", MISSING_EVIDENCE_FINDINGS, True),
        ("conflicting_evidence", CONFLICTING_EVIDENCE_FINDINGS, False),
        ("ambiguous_classification", AMBIGUOUS_CLASSIFICATION_FINDINGS, False),
        ("partial_compliance", PARTIAL_COMPLIANCE_FINDINGS, False),
    ])
    def test_scenario_10x_stable(self, scenario, findings_data, expected_has_blockers):
        """Each scenario must produce identical output 10 times."""
        with determinism_mode():
            outputs = []
            for _ in range(10):
                agg = VerdictAggregator(
                    thresholds=VerdictThresholds.for_mode(Mode.PR),
                    expected_engines=["lint"],
                )
                agg.register_engine_health(EngineHealth(
                    engine_id="lint", expected=True, ran=True, succeeded=True,
                    timestamp="2025-01-01T00:00:00Z",
                ))
                agg.add_findings_from_json(findings_data, run_id="test-run")
                result = agg.aggregate(mode=Mode.PR, run_id="test-run")

                assert (result.blockers > 0) == expected_has_blockers
                outputs.append(json.dumps(result.to_dict(), sort_keys=True))

            assert len(set(outputs)) == 1, f"{scenario}: not deterministic across 10 runs"

    @pytest.mark.parametrize("scenario,findings_data", [
        ("happy_path", HAPPY_PATH_FINDINGS),
        ("missing_evidence", MISSING_EVIDENCE_FINDINGS),
        ("conflicting_evidence", CONFLICTING_EVIDENCE_FINDINGS),
        ("ambiguous_classification", AMBIGUOUS_CLASSIFICATION_FINDINGS),
        ("partial_compliance", PARTIAL_COMPLIANCE_FINDINGS),
    ])
    def test_scenario_envelope_has_reasons(self, scenario, findings_data):
        """Each scenario envelope must have reasons mapped to rule IDs."""
        with determinism_mode():
            agg = VerdictAggregator(
                thresholds=VerdictThresholds.for_mode(Mode.PR),
                expected_engines=["lint"],
            )
            agg.register_engine_health(EngineHealth(
                engine_id="lint", expected=True, ran=True, succeeded=True,
                timestamp="2025-01-01T00:00:00Z",
            ))
            agg.add_findings_from_json(findings_data, run_id="test-run")
            result = agg.aggregate(mode=Mode.PR, run_id="test-run")
            envelope = result.to_envelope()

            assert envelope["decision"] in ("SHIP", "NO_SHIP", "CONDITIONAL", "DEGRADED")
            assert len(envelope["reasons"]) > 0
            for reason in envelope["reasons"]:
                assert reason["rule_id"]
                assert reason["description"]
                assert reason["effect"] in ("ship", "no_ship", "degrade", "info")


class TestEnvelopeSchemaValidation:
    """Test that envelopes conform to the JSON schema."""

    @pytest.fixture
    def envelope_schema(self):
        """Load the envelope schema."""
        import jsonschema
        schema_path = Path(__file__).parent.parent / "contracts" / "explainability_envelope.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)

    def test_basic_envelope_validates(self, envelope_schema):
        """A basic envelope should validate against the schema."""
        import jsonschema
        with determinism_mode():
            env = ExplainabilityEnvelope(
                decision="SHIP",
                reasons=[ReasonEntry("rule_1", "All checks passed", "ship")],
                evidence_refs=["ev_001"],
                payload={"verdict": "SHIP"},
            )
            jsonschema.validate(env.to_dict(), envelope_schema)

    def test_verdict_envelope_validates(self, envelope_schema):
        """Verdict-derived envelope should validate against the schema."""
        import jsonschema
        with determinism_mode():
            agg = VerdictAggregator(
                thresholds=VerdictThresholds.for_mode(Mode.PR),
                expected_engines=["lint"],
            )
            agg.register_engine_health(EngineHealth(
                engine_id="lint", expected=True, ran=True, succeeded=True,
                timestamp="2025-01-01T00:00:00Z",
            ))
            agg.add_finding(
                finding_id="f1", tool="lint", severity="HIGH",
                category="security", message="XSS found",
                rule_id="SEC001", source_engine="lint", run_id="test",
            )
            result = agg.aggregate(mode=Mode.PR, run_id="test")
            envelope = result.to_envelope()
            jsonschema.validate(envelope, envelope_schema)

    def test_envelope_with_uncertainty_validates(self, envelope_schema):
        """Envelope with uncertainty notes should validate."""
        import jsonschema
        with determinism_mode():
            env = ExplainabilityEnvelope(
                decision="DEGRADED",
                reasons=[ReasonEntry("engine_fail", "2 engines failed", "degrade")],
                uncertainty=[UncertaintyNote(
                    "engine_health", "Results may be incomplete",
                    "may_change_verdict", (0.3, 0.7),
                )],
                payload={"verdict": "DEGRADED"},
            )
            jsonschema.validate(env.to_dict(), envelope_schema)


class TestManifestDeterminism:
    """Test that RunManifest is deterministic in determinism mode."""

    def test_manifest_create_deterministic(self):
        """RunManifest.create should produce identical manifests in determinism mode."""
        with determinism_mode():
            manifests = []
            for _ in range(10):
                m = RunManifest.create(
                    command="judge",
                    config={"profile": "ui", "mode": "pr"},
                )
                manifests.append(json.dumps(m.to_dict(), sort_keys=True))

            assert len(set(manifests)) == 1

    def test_manifest_has_stable_run_id(self):
        """Run ID should be fixed in determinism mode."""
        with determinism_mode():
            m = RunManifest.create(command="judge", config={})
            assert m.run_id == FIXED_RUN_ID

    def test_manifest_has_stable_timestamp(self):
        """Timestamp should be fixed in determinism mode."""
        with determinism_mode():
            m = RunManifest.create(command="judge", config={})
            assert m.timestamp == FIXED_TIMESTAMP
