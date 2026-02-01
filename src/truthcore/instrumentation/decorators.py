"""
Decorators for instrumenting functions and commands.

Provides easy integration with minimal code changes:
- @instrument_engine: For engine functions
- @instrument_command: For CLI commands
- @instrument_function: Generic function instrumentation

All decorators are safe no-ops if instrumentation is unavailable.
"""

import functools
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def instrument_engine(func: F) -> F:
    """
    Decorator that instruments an engine function.

    Records engine start/finish with duration.
    Safe no-op if instrumentation is disabled or unavailable.

    Usage:
        @instrument_engine
        def run_readiness_engine(inputs, profile):
            # ... engine logic ...
            return results
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Try to get adapter (optional import)
        try:
            from truthcore.instrumentation import get_adapter
            adapter = get_adapter()
        except (ImportError, AttributeError, Exception):
            # Instrumentation not available, run normally
            return func(*args, **kwargs)

        engine_name = func.__name__
        start_time = time.perf_counter()

        # Record start (never blocks, never throws)
        try:
            adapter.on_engine_start(engine_name, kwargs)
        except Exception:
            pass  # Silently ignore instrumentation failures

        try:
            # Execute original function
            result = func(*args, **kwargs)

            # Record successful finish
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                adapter.on_engine_finish(engine_name, result, duration_ms, success=True)
            except Exception:
                pass

            return result

        except Exception as e:
            # Application exception, not instrumentation
            # Record failure signal, then re-raise unchanged
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                adapter.on_engine_finish(
                    engine_name,
                    {"error": str(e)},
                    duration_ms,
                    success=False
                )
            except Exception:
                pass

            raise  # Re-raise original exception unchanged

    return wrapper  # type: ignore


def instrument_command(func: F) -> F:
    """
    Decorator that instruments a CLI command.

    Records command start/finish with duration.
    Safe no-op if instrumentation is disabled or unavailable.

    Usage:
        @click.command()
        @instrument_command
        def judge(inputs, profile, out):
            # ... CLI logic ...
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Try to get adapter (optional import)
        try:
            from truthcore.instrumentation import get_adapter
            adapter = get_adapter()
        except (ImportError, AttributeError, Exception):
            # Instrumentation not available, run normally
            return func(*args, **kwargs)

        command_name = func.__name__
        start_time = time.perf_counter()

        # Record start
        try:
            adapter.on_engine_start(f"cli.{command_name}", kwargs)
        except Exception:
            pass

        try:
            # Execute original function
            result = func(*args, **kwargs)

            # Record finish
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                adapter.on_engine_finish(
                    f"cli.{command_name}",
                    {},
                    duration_ms,
                    success=True
                )
            except Exception:
                pass

            return result

        except Exception as e:
            # Record failure, then re-raise
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                adapter.on_engine_finish(
                    f"cli.{command_name}",
                    {"error": str(e)},
                    duration_ms,
                    success=False
                )
            except Exception:
                pass

            raise

    return wrapper  # type: ignore


def instrument_function(name: str | None = None) -> Callable[[F], F]:
    """
    Generic decorator for instrumenting any function.

    Args:
        name: Optional custom name (defaults to function name)

    Usage:
        @instrument_function()
        def my_function(x, y):
            return x + y

        @instrument_function(name="custom_name")
        def another_function():
            pass
    """
    def decorator(func: F) -> F:
        function_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from truthcore.instrumentation import get_adapter
                adapter = get_adapter()
            except (ImportError, AttributeError, Exception):
                return func(*args, **kwargs)

            start_time = time.perf_counter()

            try:
                adapter.on_engine_start(function_name, kwargs)
            except Exception:
                pass

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                try:
                    adapter.on_engine_finish(function_name, {}, duration_ms, success=True)
                except Exception:
                    pass

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000

                try:
                    adapter.on_engine_finish(
                        function_name,
                        {"error": str(e)},
                        duration_ms,
                        success=False
                    )
                except Exception:
                    pass

                raise

        return wrapper  # type: ignore

    return decorator


# Context manager for manual instrumentation
class InstrumentationContext:
    """
    Context manager for manual instrumentation.

    Usage:
        with InstrumentationContext("my_operation"):
            # ... do work ...
            pass
    """

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.adapter = None

    def __enter__(self):
        try:
            from truthcore.instrumentation import get_adapter
            self.adapter = get_adapter()
            self.start_time = time.perf_counter()
            self.adapter.on_engine_start(self.name, {})
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.adapter and self.start_time:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            try:
                self.adapter.on_engine_finish(
                    self.name,
                    {"error": str(exc_val)} if exc_val else {},
                    duration_ms,
                    success=(exc_val is None)
                )
            except Exception:
                pass
        return False  # Don't suppress exceptions
