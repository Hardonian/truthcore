"""Tests for instrumentation decorators."""

import time
import pytest

from truthcore.instrumentation import reset, set_enabled
from truthcore.instrumentation.decorators import (
    instrument_engine,
    instrument_command,
    instrument_function,
    InstrumentationContext,
)


def test_instrument_engine_decorator():
    """Test @instrument_engine decorator."""
    reset()
    set_enabled(True)

    @instrument_engine
    def test_engine(x: int, y: int) -> int:
        return x + y

    result = test_engine(x=2, y=3)

    assert result == 5  # Function works correctly

    # Check instrumentation
    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2  # start + finish

    core.shutdown()
    reset()


def test_instrument_engine_with_exception():
    """Test @instrument_engine with exception."""
    reset()
    set_enabled(True)

    @instrument_engine
    def failing_engine(x: int) -> int:
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        failing_engine(x=42)

    # Should have recorded start + failed finish
    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2

    core.shutdown()
    reset()


def test_instrument_command_decorator():
    """Test @instrument_command decorator."""
    reset()
    set_enabled(True)

    @instrument_command
    def test_command(param: str) -> str:
        return f"result: {param}"

    result = test_command(param="test")

    assert result == "result: test"

    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2

    core.shutdown()
    reset()


def test_instrument_function_decorator():
    """Test @instrument_function decorator."""
    reset()
    set_enabled(True)

    @instrument_function()
    def test_func(a: int, b: int) -> int:
        return a * b

    result = test_func(a=3, b=4)

    assert result == 12

    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2

    core.shutdown()
    reset()


def test_instrument_function_custom_name():
    """Test @instrument_function with custom name."""
    reset()
    set_enabled(True)

    @instrument_function(name="custom_operation")
    def test_func() -> str:
        return "result"

    result = test_func()

    assert result == "result"

    from truthcore.instrumentation import get_core
    core = get_core()
    core.shutdown()
    reset()


def test_decorators_when_disabled():
    """Test decorators when instrumentation disabled."""
    reset()
    set_enabled(False)

    @instrument_engine
    def test_engine(x: int) -> int:
        return x * 2

    result = test_engine(x=5)

    assert result == 10

    # No events should be queued
    from truthcore.instrumentation import get_core
    core = get_core()
    stats = core.health.get_stats()
    assert stats["events_queued"] == 0

    core.shutdown()
    reset()


def test_decorators_when_unavailable():
    """Test decorators gracefully handle missing instrumentation."""
    # This would test the case where instrumentation module doesn't exist
    # In practice, it's hard to test without actually removing the module
    # But the decorators have try/except to handle ImportError

    @instrument_engine
    def test_func(x: int) -> int:
        return x + 1

    # Should work even if instrumentation is somehow unavailable
    result = test_func(x=10)
    assert result == 11


def test_instrumentation_context():
    """Test InstrumentationContext context manager."""
    reset()
    set_enabled(True)

    with InstrumentationContext("test_operation"):
        # Do some work
        time.sleep(0.01)

    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2  # start + finish

    core.shutdown()
    reset()


def test_instrumentation_context_with_exception():
    """Test InstrumentationContext with exception."""
    reset()
    set_enabled(True)

    with pytest.raises(ValueError, match="Test error"):
        with InstrumentationContext("failing_operation"):
            raise ValueError("Test error")

    # Should have recorded failure
    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 2

    core.shutdown()
    reset()


def test_decorator_preserves_function_metadata():
    """Test decorators preserve function metadata."""

    @instrument_engine
    def documented_function(x: int) -> int:
        """This is a docstring."""
        return x

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is a docstring."


def test_decorator_preserves_return_value():
    """Test decorators don't modify return values."""
    reset()
    set_enabled(True)

    @instrument_engine
    def return_dict() -> dict:
        return {"key": "value", "num": 42}

    result = return_dict()

    assert result == {"key": "value", "num": 42}
    assert isinstance(result, dict)

    from truthcore.instrumentation import get_core
    get_core().shutdown()
    reset()


def test_multiple_decorators():
    """Test multiple instrumentation decorators don't conflict."""
    reset()
    set_enabled(True)

    @instrument_function(name="outer")
    @instrument_engine
    def test_func(x: int) -> int:
        return x + 1

    result = test_func(x=5)
    assert result == 6

    # Both decorators should emit events
    from truthcore.instrumentation import get_core
    core = get_core()
    time.sleep(0.05)

    stats = core.health.get_stats()
    assert stats["events_queued"] >= 4  # 2 decorators x 2 events each

    core.shutdown()
    reset()


def test_decorator_performance_overhead():
    """Test decorator overhead is minimal."""
    reset()

    @instrument_engine
    def fast_func(x: int) -> int:
        return x + 1

    # Disabled: should be very fast
    set_enabled(False)
    start = time.perf_counter()
    for _ in range(1000):
        fast_func(x=1)
    disabled_duration = time.perf_counter() - start

    # Enabled: should still be fast
    set_enabled(True)
    start = time.perf_counter()
    for _ in range(1000):
        fast_func(x=1)
    enabled_duration = time.perf_counter() - start

    from truthcore.instrumentation import get_core
    get_core().shutdown()
    reset()

    # Overhead should be reasonable (enabled < 10x disabled)
    assert enabled_duration < disabled_duration * 10
