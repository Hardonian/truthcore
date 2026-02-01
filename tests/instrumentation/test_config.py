"""Tests for instrumentation configuration."""

import os
import pytest

from truthcore.instrumentation.config import (
    InstrumentationConfig,
    OutputMode,
    SignalFlags,
    SafetyLimits,
    DISABLED_CONFIG,
    OBSERVE_ONLY_CONFIG,
    FULL_OBSERVABILITY_CONFIG,
)


def test_default_config():
    """Test default configuration is disabled."""
    config = InstrumentationConfig()
    assert config.enabled is False
    assert config.sampling_rate == 1.0
    assert config.output_mode == OutputMode.LOG


def test_signal_flags_defaults():
    """Test signal flags default to enabled."""
    flags = SignalFlags()
    assert flags.assertions is True
    assert flags.decisions is True
    assert flags.overrides is True
    assert flags.is_enabled("assertions") is True
    assert flags.is_enabled("unknown_type") is True  # Unknown types default to True


def test_signal_flags_selective():
    """Test selective signal flag configuration."""
    flags = SignalFlags(assertions=True, decisions=False, evidence=False)
    assert flags.is_enabled("assertions") is True
    assert flags.is_enabled("decisions") is False
    assert flags.is_enabled("evidence") is False


def test_config_validation():
    """Test configuration validation."""
    # Valid config
    config = InstrumentationConfig(sampling_rate=0.5)
    assert config.sampling_rate == 0.5

    # Invalid sampling rate
    with pytest.raises(ValueError, match="sampling_rate"):
        InstrumentationConfig(sampling_rate=1.5)

    with pytest.raises(ValueError, match="sampling_rate"):
        InstrumentationConfig(sampling_rate=-0.1)

    # Invalid queue size
    with pytest.raises(ValueError, match="queue_size"):
        InstrumentationConfig(safety=SafetyLimits(queue_size=0))

    # Invalid auto-disable threshold
    with pytest.raises(ValueError, match="auto_disable_threshold"):
        InstrumentationConfig(safety=SafetyLimits(auto_disable_threshold=0))


def test_config_from_env(monkeypatch):
    """Test configuration from environment variables."""
    monkeypatch.setenv("COGNITIVE_OBSERVE", "true")
    monkeypatch.setenv("COGNITIVE_OBSERVE_SAMPLING", "0.1")
    monkeypatch.setenv("COGNITIVE_OBSERVE_OUTPUT", "file")
    monkeypatch.setenv("COGNITIVE_OBSERVE_PATH", "/tmp/test.jsonl")
    monkeypatch.setenv("COGNITIVE_OBSERVE_QUEUE_SIZE", "5000")

    config = InstrumentationConfig.from_env()

    assert config.enabled is True
    assert config.sampling_rate == 0.1
    assert config.output_mode == OutputMode.FILE
    assert config.output_path == "/tmp/test.jsonl"
    assert config.safety.queue_size == 5000


def test_config_from_env_defaults(monkeypatch):
    """Test configuration from environment with defaults."""
    # Clear all relevant env vars
    for key in [
        "COGNITIVE_OBSERVE",
        "COGNITIVE_OBSERVE_SAMPLING",
        "COGNITIVE_OBSERVE_OUTPUT",
        "COGNITIVE_OBSERVE_PATH",
        "COGNITIVE_OBSERVE_QUEUE_SIZE",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = InstrumentationConfig.from_env()

    assert config.enabled is False
    assert config.sampling_rate == 1.0
    assert config.output_mode == OutputMode.LOG
    assert config.output_path is None
    assert config.safety.queue_size == 10000


def test_config_from_dict():
    """Test configuration from dictionary."""
    data = {
        "enabled": True,
        "sampling_rate": 0.5,
        "output_mode": "file",
        "output_path": "/var/log/test.jsonl",
        "fallback_mode": "log",
        "signals": {
            "assertions": True,
            "decisions": True,
            "evidence": False,
        },
        "safety": {
            "queue_size": 5000,
            "auto_disable_threshold": 5,
        },
        "telemetry_enabled": False,
    }

    config = InstrumentationConfig.from_dict(data)

    assert config.enabled is True
    assert config.sampling_rate == 0.5
    assert config.output_mode == OutputMode.FILE
    assert config.output_path == "/var/log/test.jsonl"
    assert config.fallback_mode == OutputMode.LOG
    assert config.signals.assertions is True
    assert config.signals.decisions is True
    assert config.signals.evidence is False
    assert config.safety.queue_size == 5000
    assert config.safety.auto_disable_threshold == 5
    assert config.telemetry_enabled is False


def test_config_to_dict():
    """Test configuration serialization to dictionary."""
    config = InstrumentationConfig(
        enabled=True,
        sampling_rate=0.75,
        output_mode=OutputMode.FILE,
        output_path="/test.jsonl",
    )

    data = config.to_dict()

    assert data["enabled"] is True
    assert data["sampling_rate"] == 0.75
    assert data["output_mode"] == "file"
    assert data["output_path"] == "/test.jsonl"
    assert "signals" in data
    assert "safety" in data


def test_preset_configs():
    """Test preset configurations."""
    # Disabled config
    assert DISABLED_CONFIG.enabled is False

    # Observe-only config
    assert OBSERVE_ONLY_CONFIG.enabled is True
    assert OBSERVE_ONLY_CONFIG.sampling_rate == 0.1
    assert OBSERVE_ONLY_CONFIG.signals.assertions is True
    assert OBSERVE_ONLY_CONFIG.signals.evidence is False

    # Full observability config
    assert FULL_OBSERVABILITY_CONFIG.enabled is True
    assert FULL_OBSERVABILITY_CONFIG.sampling_rate == 1.0
    assert FULL_OBSERVABILITY_CONFIG.output_mode == OutputMode.SUBSTRATE
    assert FULL_OBSERVABILITY_CONFIG.fallback_mode == OutputMode.FILE


def test_signal_flags_from_dict():
    """Test SignalFlags creation from dict."""
    data = {
        "assertions": True,
        "decisions": False,
        "overrides": True,
        "unknown_field": True,  # Should be ignored
    }

    flags = SignalFlags.from_dict(data)
    assert flags.assertions is True
    assert flags.decisions is False
    assert flags.overrides is True
