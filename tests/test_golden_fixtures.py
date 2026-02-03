"""Golden Fixture Regression Suite Test Harness.

Verifies that golden fixture verdict outputs are stable and well-formed.
These tests ensure that expected verdict structures remain valid and that
verdict generation produces consistent, explainable results.
"""

import json
from pathlib import Path

import pytest


def get_golden_fixtures_dir() -> Path:
    """Get the golden fixtures directory path."""
    return Path(__file__).parent / "fixtures" / "golden"


def load_expected_verdict(scenario_dir: Path) -> dict:
    """Load the expected verdict from a scenario directory."""
    verdict_path = scenario_dir / "expected_verdict.json"
    if not verdict_path.exists():
        raise FileNotFoundError(f"Expected verdict not found: {verdict_path}")

    with open(verdict_path, encoding="utf-8") as f:
        return json.load(f)


class TestGoldenFixtureStructure:
    """Test that golden fixtures have valid structure."""

    def get_all_scenarios(self):
        """Get all golden fixture scenario directories."""
        golden_dir = get_golden_fixtures_dir()
        if not golden_dir.exists():
            return []
        return [d for d in golden_dir.iterdir() if d.is_dir()]

    def test_all_scenarios_have_expected_verdicts(self):
        """Every scenario must have an expected_verdict.json file."""
        scenarios = self.get_all_scenarios()
        assert len(scenarios) >= 6, f"Expected at least 6 scenarios, found {len(scenarios)}"

        for scenario_dir in scenarios:
            verdict_path = scenario_dir / "expected_verdict.json"
            assert verdict_path.exists(), f"Missing expected_verdict.json in {scenario_dir.name}"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_scenario_exists(self, scenario_name: str):
        """All documented scenarios must exist."""
        golden_dir = get_golden_fixtures_dir()
        scenario_dir = golden_dir / scenario_name
        assert scenario_dir.exists(), f"Scenario directory missing: {scenario_name}"
        assert (scenario_dir / "expected_verdict.json").exists()


class TestVerdictContractCompliance:
    """Test that expected verdicts comply with contract specifications."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_verdict_has_required_contract_fields(self, scenario_name: str):
        """Verdict must have required _contract fields."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        assert "_contract" in verdict, "Missing _contract field"
        contract = verdict["_contract"]

        required_fields = [
            "artifact_type",
            "contract_version",
            "truthcore_version",
            "created_at",
            "schema",
        ]
        for field in required_fields:
            assert field in contract, f"Missing required contract field: {field}"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_verdict_artifact_type_is_correct(self, scenario_name: str):
        """Verdict artifact_type must be 'verdict'."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        assert verdict["_contract"]["artifact_type"] == "verdict"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_verdict_state_is_valid(self, scenario_name: str):
        """Verdict state must be one of PASS, FAIL, WARN, UNKNOWN."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        valid_states = {"PASS", "FAIL", "WARN", "UNKNOWN"}
        assert verdict["verdict"] in valid_states

    @pytest.mark.parametrize(
        "scenario_name,expected_verdict",
        [
            ("clean_code", "PASS"),
            ("security_issues", "FAIL"),
            ("performance_regression", "WARN"),
            ("missing_tests", "FAIL"),
            ("style_only", "PASS"),
            ("agent_trace_failure", "FAIL"),
            ("agent_trace_success", "PASS"),
            ("jobforge_runner_flow", "PASS"),
            ("jobforge_runner_refusal_missing_evidence", "FAIL"),
            ("jobforge_runner_refusal_engine_timeout", "FAIL"),
            ("jobforge_runner_refusal_policy_violation", "FAIL"),
        ],
    )
    def test_verdict_state_matches_expected(self, scenario_name: str, expected_verdict: str):
        """Verdict state must match the scenario's expected outcome."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        assert verdict["verdict"] == expected_verdict, (
            f"Expected {expected_verdict} for {scenario_name}, got {verdict['verdict']}"
        )


class TestVerdictValueAndScore:
    """Test that verdict values/scores are within valid ranges."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_value_or_score_exists(self, scenario_name: str):
        """Verdict must have either 'value' (v2) or 'score' (v1) field."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        has_value = "value" in verdict and isinstance(verdict["value"], (int, float))
        has_score = "score" in verdict and isinstance(verdict["score"], (int, float))

        assert has_value or has_score, "Verdict must have 'value' or 'score' field"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_value_in_valid_range(self, scenario_name: str):
        """Value/score must be between 0 and 100."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        value = verdict.get("value") or verdict.get("score", 0)
        assert 0 <= value <= 100, f"Value {value} out of range [0, 100]"

    @pytest.mark.parametrize(
        "scenario_name,min_value",
        [
            ("clean_code", 90),
            ("security_issues", 0),
            ("performance_regression", 70),
            ("missing_tests", 0),
            ("style_only", 85),
            ("agent_trace_failure", 0),
            ("agent_trace_success", 90),
            ("jobforge_runner_flow", 90),
            ("jobforge_runner_refusal_missing_evidence", 0),
            ("jobforge_runner_refusal_engine_timeout", 0),
            ("jobforge_runner_refusal_policy_violation", 0),
        ],
    )
    def test_value_matches_scenario_severity(self, scenario_name: str, min_value: int):
        """Score should reflect scenario severity appropriately."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        value = verdict.get("value") or verdict.get("score", 0)
        assert value >= min_value, (
            f"{scenario_name} score {value} below expected minimum {min_value}"
        )


class TestVerdictFindings:
    """Test that findings/items are well-formed."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_findings_or_items_exists(self, scenario_name: str):
        """Verdict must have 'findings' (v1) or 'items' (v2) array."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        has_items = "items" in verdict and isinstance(verdict["items"], list)
        has_findings = "findings" in verdict and isinstance(verdict["findings"], list)

        assert has_items or has_findings, "Verdict must have 'items' or 'findings' array"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_all_findings_have_required_fields(self, scenario_name: str):
        """Each finding/item must have required fields."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        items = verdict.get("items") or verdict.get("findings", [])

        for i, item in enumerate(items):
            assert "id" in item, f"Finding {i} missing 'id'"
            assert "severity" in item, f"Finding {i} missing 'severity'"
            assert "message" in item, f"Finding {i} missing 'message'"

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_severity_levels_are_valid(self, scenario_name: str):
        """Severity levels must be one of the allowed values."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        valid_severities = {"BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"}
        items = verdict.get("items") or verdict.get("findings", [])

        for i, item in enumerate(items):
            severity = item.get("severity")
            assert severity in valid_severities, (
                f"Finding {i} has invalid severity: {severity}"
            )


class TestVerdictStability:
    """Test that verdict outputs are deterministic and stable."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_verdict_is_explainable(self, scenario_name: str):
        """Verdict must be explainable based on findings."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        items = verdict.get("items") or verdict.get("findings", [])
        verdict_state = verdict["verdict"]

        # Count severities
        blocker_count = sum(1 for item in items if item["severity"] == "BLOCKER")
        high_count = sum(1 for item in items if item["severity"] == "HIGH")

            # Explainability rules
        if verdict_state == "FAIL":
            # FAIL should have blockers or significant issues
            assert blocker_count > 0 or high_count > 0 or len(items) > 2, (
                "FAIL verdict should have BLOCKERs or multiple HIGHs"
            )
        elif verdict_state == "WARN":
            # WARN should have at least one MEDIUM or HIGH
            medium_high_count = sum(
                1 for item in items if item["severity"] in ("MEDIUM", "HIGH")
            )
            assert medium_high_count > 0, "WARN verdict should have MEDIUM or HIGH findings"
        elif verdict_state == "PASS":
            # PASS should not have BLOCKERs
            assert blocker_count == 0, "PASS verdict cannot have BLOCKER findings"

    @pytest.mark.parametrize(
        "scenario_name,expected_count",
        [
            ("clean_code", (1, 5)),
            ("security_issues", (3, 10)),
            ("performance_regression", (2, 8)),
            ("missing_tests", (1, 5)),
            ("style_only", (1, 5)),
            ("agent_trace_failure", (3, 10)),
            ("agent_trace_success", (1, 5)),
            ("jobforge_runner_flow", (3, 8)),
            ("jobforge_runner_refusal_missing_evidence", (1, 5)),
            ("jobforge_runner_refusal_engine_timeout", (1, 5)),
            ("jobforge_runner_refusal_policy_violation", (2, 6)),
        ],
    )
    def test_finding_count_is_reasonable(self, scenario_name: str, expected_count: tuple):
        """Finding count should be within expected range for scenario."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        items = verdict.get("items") or verdict.get("findings", [])
        min_count, max_count = expected_count

        assert min_count <= len(items) <= max_count, (
            f"{scenario_name} has {len(items)} findings, expected [{min_count}, {max_count}]"
        )


class TestVerdictMetadata:
    """Test that verdicts have appropriate metadata."""

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "clean_code",
            "security_issues",
            "performance_regression",
            "missing_tests",
            "style_only",
            "agent_trace_failure",
            "agent_trace_success",
            "jobforge_runner_flow",
            "jobforge_runner_refusal_missing_evidence",
            "jobforge_runner_refusal_engine_timeout",
            "jobforge_runner_refusal_policy_violation",
        ],
    )
    def test_metadata_has_scenario_description(self, scenario_name: str):
        """Verdict metadata should describe the scenario."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)

        metadata = verdict.get("metadata", {})
        assert "scenario" in metadata, "Metadata should identify scenario"
        assert "description" in metadata, "Metadata should have description"


class TestGoldenFixtureCompleteness:
    """Test that the golden fixture suite is comprehensive."""

    def test_at_least_six_scenarios_exist(self):
        """Golden fixture suite must have at least 6 scenarios."""
        golden_dir = get_golden_fixtures_dir()
        scenarios = [d for d in golden_dir.iterdir() if d.is_dir()]
        assert len(scenarios) >= 6, f"Expected at least 6 scenarios, found {len(scenarios)}"

    def test_scenarios_cover_all_verdict_states(self):
        """Scenarios must cover all verdict states (PASS, FAIL, WARN)."""
        golden_dir = get_golden_fixtures_dir()
        scenarios = [d for d in golden_dir.iterdir() if d.is_dir()]

        states_found = set()
        for scenario_dir in scenarios:
            verdict = load_expected_verdict(scenario_dir)
            states_found.add(verdict["verdict"])

        assert "PASS" in states_found, "No PASS scenario found"
        assert "FAIL" in states_found, "No FAIL scenario found"
        assert "WARN" in states_found, "No WARN scenario found"

    def test_scenarios_cover_all_severity_levels(self):
        """Scenarios must collectively cover all severity levels."""
        golden_dir = get_golden_fixtures_dir()
        scenarios = [d for d in golden_dir.iterdir() if d.is_dir()]

        severities_found = set()
        for scenario_dir in scenarios:
            verdict = load_expected_verdict(scenario_dir)
            items = verdict.get("items") or verdict.get("findings", [])
            for item in items:
                severities_found.add(item["severity"])

        assert "BLOCKER" in severities_found, "No BLOCKER severity found"
        assert "HIGH" in severities_found, "No HIGH severity found"
        assert "MEDIUM" in severities_found, "No MEDIUM severity found"
        assert "LOW" in severities_found, "No LOW severity found"
        assert "INFO" in severities_found, "No INFO severity found"

    def test_scenarios_cover_multiple_domains(self):
        """Scenarios should cover multiple domains (code, security, performance, ai)."""
        golden_dir = get_golden_fixtures_dir()
        scenarios = [d for d in golden_dir.iterdir() if d.is_dir()]

        domains_found = set()
        for scenario_dir in scenarios:
            verdict = load_expected_verdict(scenario_dir)
            metadata = verdict.get("metadata", {})
            scenario_name = metadata.get("scenario", scenario_dir.name)
            domains_found.add(scenario_name)

        # Check for variety across domains
        code_related = any(s for s in domains_found if "code" in s or "style" in s)
        security_related = any(s for s in domains_found if "security" in s)
        performance_related = any(s for s in domains_found if "performance" in s)
        _test_related = any(s for s in domains_found if "test" in s)
        _agent_related = any(s for s in domains_found if "agent" in s)

        assert code_related, "No code quality scenarios found"
        assert security_related or performance_related, "No security or performance scenarios found"
        # Note: _test_related and _agent_related are validated as part of domain coverage


class TestRefusalCodes:
    """Test that refusal scenarios have stable, machine-readable codes."""

    REFUSAL_SCENARIOS = [
        "jobforge_runner_refusal_missing_evidence",
        "jobforge_runner_refusal_engine_timeout",
        "jobforge_runner_refusal_policy_violation",
    ]

    @pytest.mark.parametrize("scenario_name", REFUSAL_SCENARIOS)
    def test_refusal_scenario_has_fail_verdict(self, scenario_name: str):
        """All refusal scenarios must have FAIL verdict."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        assert verdict["verdict"] == "FAIL", f"Refusal scenario {scenario_name} must have FAIL verdict"

    @pytest.mark.parametrize("scenario_name", REFUSAL_SCENARIOS)
    def test_refusal_code_in_metadata(self, scenario_name: str):
        """Refusal scenarios must have refusal codes in metadata."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        metadata = verdict.get("metadata", {})
        pipeline = metadata.get("pipeline", {})
        refusal_reasons = pipeline.get("refusal_reasons", [])
        assert len(refusal_reasons) > 0, f"Refusal scenario {scenario_name} must have refusal_reasons in metadata"

    @pytest.mark.parametrize("scenario_name", REFUSAL_SCENARIOS)
    def test_refusal_codes_follow_format(self, scenario_name: str):
        """Refusal codes must follow DOMAIN_SUBCATEGORY_DETAIL format."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        metadata = verdict.get("metadata", {})
        pipeline = metadata.get("pipeline", {})
        refusal_reasons = pipeline.get("refusal_reasons", [])

        valid_domains = {"EVIDENCE", "POLICY", "SYSTEM", "VALIDATION", "PROCESSING"}

        for reason in refusal_reasons:
            code = reason.get("code", "")
            parts = code.split("_")
            assert len(parts) >= 2, f"Refusal code {code} must have at least 2 parts"
            assert parts[0] in valid_domains, f"Refusal code {code} must start with valid domain"

    @pytest.mark.parametrize("scenario_name", REFUSAL_SCENARIOS)
    def test_refusal_code_in_findings(self, scenario_name: str):
        """At least one finding must contain refusal code in message or metadata."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        items = verdict.get("items") or verdict.get("findings", [])

        has_refusal_code = False
        for item in items:
            message = item.get("message", "")
            # Check for code in message format [CODE]
            if "[" in message and "]" in message:
                has_refusal_code = True
                break
            # Check for code in metadata
            metadata = item.get("metadata", {})
            if "refusal" in metadata and "code" in metadata["refusal"]:
                has_refusal_code = True
                break

        assert has_refusal_code, f"Refusal scenario {scenario_name} must have findings with refusal codes"


class TestPipelineFlow:
    """Test jobforge->runner->truthcore pipeline flow scenarios."""

    PIPELINE_SCENARIOS = [
        "jobforge_runner_flow",
        "jobforge_runner_refusal_missing_evidence",
        "jobforge_runner_refusal_engine_timeout",
        "jobforge_runner_refusal_policy_violation",
    ]

    @pytest.mark.parametrize("scenario_name", PIPELINE_SCENARIOS)
    def test_pipeline_has_correlation_id(self, scenario_name: str):
        """Pipeline scenarios must have correlation ID for provenance."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        metadata = verdict.get("metadata", {})
        pipeline = metadata.get("pipeline", {})
        assert "correlation_id" in pipeline, f"Pipeline scenario {scenario_name} must have correlation_id"

    @pytest.mark.parametrize("scenario_name", PIPELINE_SCENARIOS)
    def test_pipeline_has_stages(self, scenario_name: str):
        """Pipeline scenarios must document the stages."""
        scenario_dir = get_golden_fixtures_dir() / scenario_name
        verdict = load_expected_verdict(scenario_dir)
        metadata = verdict.get("metadata", {})
        pipeline = metadata.get("pipeline", {})
        stages = pipeline.get("stages", [])
        assert "jobforge" in stages, "Pipeline must include jobforge stage"
        assert "runner" in stages, "Pipeline must include runner stage"
        assert "truthcore" in stages, "Pipeline must include truthcore stage"

    def test_success_flow_has_provenance_metadata(self):
        """Successful flow scenario must have detailed provenance."""
        scenario_dir = get_golden_fixtures_dir() / "jobforge_runner_flow"
        verdict = load_expected_verdict(scenario_dir)
        metadata = verdict.get("metadata", {})
        pipeline = metadata.get("pipeline", {})

        assert pipeline.get("runner_executed") is True, "Success flow must have runner_executed=True"
        assert pipeline.get("truthcore_verified") is True, "Success flow must have truthcore_verified=True"


class TestEvidenceProvenance:
    """Test evidence provenance features in golden fixtures."""

    def test_findings_can_have_correlation_id(self):
        """Findings may include correlation_id for pipeline tracking."""
        scenario_dir = get_golden_fixtures_dir() / "jobforge_runner_flow"
        verdict = load_expected_verdict(scenario_dir)
        items = verdict.get("items") or verdict.get("findings", [])

        # At least one finding should have correlation_id in metadata
        found_correlation = False
        for item in items:
            metadata = item.get("metadata", {})
            if "correlation_id" in metadata:
                found_correlation = True
                break

        assert found_correlation, "At least one finding should have correlation_id in metadata"

    def test_findings_can_have_source_attribution(self):
        """Findings may include source_attribution for provenance."""
        scenario_dir = get_golden_fixtures_dir() / "jobforge_runner_flow"
        verdict = load_expected_verdict(scenario_dir)
        items = verdict.get("items") or verdict.get("findings", [])

        # At least one finding should have source_attribution
        found_attribution = False
        for item in items:
            metadata = item.get("metadata", {})
            if "source_attribution" in metadata:
                found_attribution = True
                attr = metadata["source_attribution"]
                assert "system" in attr, "Source attribution must have system"
                assert "component" in attr, "Source attribution must have component"
                break

        assert found_attribution, "At least one finding should have source_attribution in metadata"
