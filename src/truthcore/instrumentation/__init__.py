"""
Silent Instrumentation Layer for Cognitive Substrate.

Zero-impact observability adapter that captures system behavior without
modifying logic, outcomes, or performance.

Core Guarantees:
- Observe-only: No enforcement, no branching
- Feature-flagged: Default disabled
- Zero hard failures: Never propagates exceptions
- Minimal overhead: <1μs disabled, <100μs enabled
- Fully removable: No side effects

Usage:
    from truthcore.instrumentation import get_core, get_adapter

    # Emit events
    core = get_core()
    core.emit({"signal_type": "assertion", "claim": "ready"})

    # Use boundary adapters
    adapter = get_adapter()
    adapter.on_engine_start("readiness", inputs)
"""

from truthcore.instrumentation.config import InstrumentationConfig
from truthcore.instrumentation.core import InstrumentationCore
from truthcore.instrumentation.health import InstrumentationHealth

# Global instances (lazy-initialized)
_core_instance: InstrumentationCore | None = None
_config_instance: InstrumentationConfig | None = None


def get_config() -> InstrumentationConfig:
    """Get global configuration instance (lazy-initialized)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = InstrumentationConfig.from_env()
    return _config_instance


def get_core() -> InstrumentationCore:
    """Get global instrumentation core instance (lazy-initialized)."""
    global _core_instance
    if _core_instance is None:
        config = get_config()
        _core_instance = InstrumentationCore(config)
    return _core_instance


def get_adapter():
    """Get boundary adapter for instrumentation hooks."""
    from truthcore.instrumentation.adapters import BoundaryAdapter
    return BoundaryAdapter(get_core())


def set_enabled(enabled: bool, **kwargs) -> None:
    """
    Enable or disable instrumentation at runtime.

    Args:
        enabled: Master on/off switch
        **kwargs: Optional config overrides (e.g., signals={}, sampling_rate=0.1)
    """
    global _core_instance, _config_instance

    # If enabling from disabled state, need to recreate core with enabled config
    if enabled and (_core_instance is None or not _core_instance.config.enabled):
        # Reset and create new core with enabled=True
        if _core_instance:
            _core_instance.shutdown()

        # Update or create config
        if _config_instance is None:
            _config_instance = InstrumentationConfig.from_env()

        _config_instance.enabled = True

        # Apply kwargs to config
        if kwargs:
            for key, value in kwargs.items():
                if hasattr(_config_instance, key):
                    setattr(_config_instance, key, value)

        # Create new core with enabled config
        _core_instance = InstrumentationCore(_config_instance)

    elif not enabled:
        # Disabling - just set flag
        core = get_core()
        core._enabled = False
    else:
        # Already enabled, just update settings
        core = get_core()
        if kwargs:
            config = get_config()
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)


def set_sampling_rate(rate: float) -> None:
    """Set sampling rate (0.0 to 1.0)."""
    config = get_config()
    config.sampling_rate = max(0.0, min(1.0, rate))


def reset() -> None:
    """Reset instrumentation (mainly for testing)."""
    global _core_instance, _config_instance
    if _core_instance:
        _core_instance.shutdown()
    _core_instance = None
    _config_instance = None


__all__ = [
    "InstrumentationConfig",
    "InstrumentationCore",
    "InstrumentationHealth",
    "get_config",
    "get_core",
    "get_adapter",
    "set_enabled",
    "set_sampling_rate",
    "reset",
]
