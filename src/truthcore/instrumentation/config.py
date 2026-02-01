"""
Configuration system for Silent Instrumentation Layer.

Supports:
- Environment variable configuration
- YAML file configuration
- Runtime overrides
- Feature flags per signal type
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputMode(Enum):
    """Output destination for instrumentation events."""
    LOG = "log"           # Structured logging
    FILE = "file"         # JSONL file
    SUBSTRATE = "substrate"  # Direct to Cognitive Substrate
    NULL = "null"         # Discard (for testing)


@dataclass
class SignalFlags:
    """Feature flags for individual signal types."""
    assertions: bool = True
    evidence: bool = True
    beliefs: bool = True
    decisions: bool = True
    overrides: bool = True
    economics: bool = True
    policies: bool = True
    semantics: bool = True

    def is_enabled(self, signal_type: str) -> bool:
        """Check if a specific signal type is enabled."""
        # Handle non-string types (invalid signals)
        if not isinstance(signal_type, str):
            return True  # Default to True for invalid types

        # Map signal types to flag names
        signal_to_flag = {
            "assertion": "assertions",
            "decision": "decisions",
            "override": "overrides",
            "evidence": "evidence",
            "belief_change": "beliefs",
            "economic": "economics",
            "policy_reference": "policies",
            "semantic_usage": "semantics",
            "engine_lifecycle": "assertions",  # Engine lifecycle treated as assertions
        }

        flag_name = signal_to_flag.get(signal_type, signal_type)

        # Default to True if unknown signal type
        return getattr(self, flag_name, True)

    @classmethod
    def from_dict(cls, data: dict[str, bool]) -> "SignalFlags":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class SafetyLimits:
    """Safety limits for instrumentation."""
    queue_size: int = 10000
    auto_disable_threshold: int = 10
    max_event_size_bytes: int = 1_000_000  # 1MB per event


@dataclass
class InstrumentationConfig:
    """
    Configuration for Silent Instrumentation Layer.

    All flags default to safe values:
    - enabled: False (master switch off)
    - sampling_rate: 1.0 (100% when enabled)
    - output_mode: LOG (structured logging)
    """

    # Master switch
    enabled: bool = False

    # Signal type flags
    signals: SignalFlags = field(default_factory=SignalFlags)

    # Sampling
    sampling_rate: float = 1.0  # 0.0 to 1.0

    # Output configuration
    output_mode: OutputMode = OutputMode.LOG
    output_path: str | None = None
    fallback_mode: OutputMode = OutputMode.LOG

    # Safety limits
    safety: SafetyLimits = field(default_factory=SafetyLimits)

    # Telemetry
    telemetry_enabled: bool = True  # Internal health telemetry

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not 0.0 <= self.sampling_rate <= 1.0:
            raise ValueError(f"sampling_rate must be 0.0-1.0, got {self.sampling_rate}")

        if self.safety.queue_size < 1:
            raise ValueError(f"queue_size must be >= 1, got {self.safety.queue_size}")

        if self.safety.auto_disable_threshold < 1:
            raise ValueError(f"auto_disable_threshold must be >= 1, got {self.safety.auto_disable_threshold}")

    @classmethod
    def from_env(cls) -> "InstrumentationConfig":
        """
        Create configuration from environment variables.

        Environment variables:
            COGNITIVE_OBSERVE: Master enable flag (true/false)
            COGNITIVE_OBSERVE_SAMPLING: Sampling rate (0.0-1.0)
            COGNITIVE_OBSERVE_OUTPUT: Output mode (log/file/substrate/null)
            COGNITIVE_OBSERVE_PATH: Output file path
            COGNITIVE_OBSERVE_QUEUE_SIZE: Max queue size
        """
        enabled = os.getenv("COGNITIVE_OBSERVE", "false").lower() == "true"
        sampling = float(os.getenv("COGNITIVE_OBSERVE_SAMPLING", "1.0"))
        output_str = os.getenv("COGNITIVE_OBSERVE_OUTPUT", "log").lower()
        output_path = os.getenv("COGNITIVE_OBSERVE_PATH")
        queue_size = int(os.getenv("COGNITIVE_OBSERVE_QUEUE_SIZE", "10000"))

        # Parse output mode
        try:
            output_mode = OutputMode[output_str.upper()]
        except KeyError:
            output_mode = OutputMode.LOG

        return cls(
            enabled=enabled,
            sampling_rate=sampling,
            output_mode=output_mode,
            output_path=output_path,
            safety=SafetyLimits(queue_size=queue_size),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstrumentationConfig":
        """Create configuration from dictionary (e.g., YAML)."""
        enabled = data.get("enabled", False)
        sampling_rate = data.get("sampling_rate", 1.0)

        # Parse output mode
        output_str = data.get("output_mode", "log")
        try:
            output_mode = OutputMode[output_str.upper()]
        except KeyError:
            output_mode = OutputMode.LOG

        fallback_str = data.get("fallback_mode", "log")
        try:
            fallback_mode = OutputMode[fallback_str.upper()]
        except KeyError:
            fallback_mode = OutputMode.LOG

        # Parse signals
        signals_data = data.get("signals", {})
        signals = SignalFlags.from_dict(signals_data) if signals_data else SignalFlags()

        # Parse safety limits
        safety_data = data.get("safety", {})
        safety = SafetyLimits(**safety_data) if safety_data else SafetyLimits()

        return cls(
            enabled=enabled,
            signals=signals,
            sampling_rate=sampling_rate,
            output_mode=output_mode,
            output_path=data.get("output_path"),
            fallback_mode=fallback_mode,
            safety=safety,
            telemetry_enabled=data.get("telemetry_enabled", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "signals": {
                "assertions": self.signals.assertions,
                "evidence": self.signals.evidence,
                "beliefs": self.signals.beliefs,
                "decisions": self.signals.decisions,
                "overrides": self.signals.overrides,
                "economics": self.signals.economics,
                "policies": self.signals.policies,
                "semantics": self.signals.semantics,
            },
            "sampling_rate": self.sampling_rate,
            "output_mode": self.output_mode.value,
            "output_path": self.output_path,
            "fallback_mode": self.fallback_mode.value,
            "safety": {
                "queue_size": self.safety.queue_size,
                "auto_disable_threshold": self.safety.auto_disable_threshold,
                "max_event_size_bytes": self.safety.max_event_size_bytes,
            },
            "telemetry_enabled": self.telemetry_enabled,
        }


# Default configurations for common scenarios

DISABLED_CONFIG = InstrumentationConfig(enabled=False)

OBSERVE_ONLY_CONFIG = InstrumentationConfig(
    enabled=True,
    signals=SignalFlags(
        assertions=True,
        decisions=True,
        overrides=True,
        evidence=False,  # Skip high-volume
        economics=False,
    ),
    sampling_rate=0.1,  # 10% sampling
    output_mode=OutputMode.LOG,
)

FULL_OBSERVABILITY_CONFIG = InstrumentationConfig(
    enabled=True,
    signals=SignalFlags(),  # All enabled
    sampling_rate=1.0,
    output_mode=OutputMode.SUBSTRATE,
    fallback_mode=OutputMode.FILE,
)
