"""Tests for boundary adapters."""

import time
import pytest

from truthcore.instrumentation.config import InstrumentationConfig
from truthcore.instrumentation.core import InstrumentationCore
from truthcore.instrumentation.adapters import BoundaryAdapter


class MockFinding:
    """Mock Finding object for testing."""

    def __init__(self, rule_id: str, severity: str, message: str):
        self.rule_id = rule_id
        self.severity = MockSeverity(severity)
        self.message = message
        self.file_path = "test.py"
        self.line_number = 42


class MockSeverity:
    """Mock Severity enum."""

    def __init__(self, value: str):
        self.value = value


class MockVerdict:
    """Mock VerdictResult object for testing."""

    def __init__(self, verdict: str, value: int, summary: str):
        self.verdict = MockSeverity(verdict)
        self.value = value
        self.summary = summary


@pytest.fixture
def adapter():
    """Create adapter with enabled instrumentation."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)
    adapter = BoundaryAdapter(core)
    yield adapter
    core.shutdown()


def test_adapter_engine_lifecycle(adapter):
    """Test engine start/finish instrumentation."""
    inputs = {"param1": "value1", "param2": 42}
    outputs = {"result": "success"}

    # Start
    adapter.on_engine_start("test_engine", inputs)
    time.sleep(0.01)

    # Finish
    adapter.on_engine_finish("test_engine", outputs, duration_ms=123.45, success=True)
    time.sleep(0.01)

    # Check events were queued
    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 2


def test_adapter_finding_created(adapter):
    """Test finding creation instrumentation."""
    finding = MockFinding(
        rule_id="test.rule",
        severity="BLOCKER",
        message="Test finding"
    )

    adapter.on_finding_created(finding)
    time.sleep(0.01)

    # Should have queued assertion signal
    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_verdict_decided(adapter):
    """Test verdict decision instrumentation."""
    verdict = MockVerdict(
        verdict="FAIL",
        value=72,
        summary="Test verdict summary"
    )

    adapter.on_verdict_decided(verdict)
    time.sleep(0.01)

    # Should have queued decision signal
    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_policy_evaluated(adapter):
    """Test policy evaluation instrumentation."""
    adapter.on_policy_evaluated(
        policy_id="test.policy",
        result=False,
        enforcement_mode="warn"
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_human_override(adapter):
    """Test human override instrumentation."""
    adapter.on_human_override(
        original_decision="FAIL",
        override_decision="PASS",
        actor="user@example.com",
        rationale="urgent hotfix",
        scope="deployment_xyz",
        authority="team_lead"
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_cache_decision(adapter):
    """Test cache decision instrumentation."""
    adapter.on_cache_decision(key="test_key", hit=True, reused=True)
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_evidence_input(adapter):
    """Test evidence input instrumentation."""
    adapter.on_evidence_input(
        evidence_type="file_read",
        source="policy_engine",
        content_hash_value="sha256:abc123",
        metadata={"size": 1024}
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_belief_change(adapter):
    """Test belief change instrumentation."""
    adapter.on_belief_change(
        subject="deployment_ready",
        old_value={"verdict": "PASS", "score": 95},
        new_value={"verdict": "FAIL", "score": 72},
        trigger="new_blocker"
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_economic_signal(adapter):
    """Test economic signal instrumentation."""
    adapter.on_economic_signal(
        metric="token_usage",
        amount=1500.0,
        unit="tokens",
        applies_to="run_abc123",
        cost_estimate=0.015
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_semantic_usage(adapter):
    """Test semantic usage instrumentation."""
    adapter.on_semantic_usage(
        term="deployment_ready",
        definition_source="settler.config",
        actual_usage="score >= 90",
        context="verdict_aggregation"
    )
    time.sleep(0.01)

    stats = adapter.core.health.get_stats()
    assert stats["events_queued"] >= 1


def test_adapter_with_disabled_instrumentation():
    """Test adapter with disabled instrumentation."""
    config = InstrumentationConfig(enabled=False)
    core = InstrumentationCore(config)
    adapter = BoundaryAdapter(core)

    try:
        # All calls should be no-ops
        adapter.on_engine_start("test", {})
        adapter.on_finding_created(MockFinding("test", "INFO", "test"))
        adapter.on_verdict_decided(MockVerdict("PASS", 100, "test"))

        # No events should be queued
        stats = adapter.core.health.get_stats()
        assert stats["events_queued"] == 0

    finally:
        core.shutdown()


def test_adapter_exception_safety():
    """Test adapter never raises exceptions."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)
    adapter = BoundaryAdapter(core)

    try:
        # These should not raise even with invalid inputs
        adapter.on_engine_start("test", None)  # type: ignore
        adapter.on_finding_created(None)  # type: ignore
        adapter.on_verdict_decided(object())  # type: ignore

        # Adapter should still work
        adapter.on_engine_finish("test", {}, 0.0, True)

    finally:
        core.shutdown()
