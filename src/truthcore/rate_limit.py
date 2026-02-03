"""Rate limiting backends for Truth Core server.

Supports both in-memory and Redis-based rate limiting.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_time: float
    retry_after: int | None = None


class RateLimitBackend(ABC):
    """Abstract base class for rate limit backends."""

    @abstractmethod
    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., IP address or API key)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            RateLimitResult with allowed status and remaining count
        """
        pass

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        pass


class MemoryRateLimitBackend(RateLimitBackend):
    """In-memory rate limit backend."""

    def __init__(self) -> None:
        self._storage: dict[str, list[tuple[float, int]]] = {}

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit in memory."""
        now = time.time()
        cutoff = now - window_seconds

        # Get or create entry
        if key not in self._storage:
            self._storage[key] = []

        # Remove old entries
        entries = self._storage[key]
        entries[:] = [(ts, count) for ts, count in entries if ts > cutoff]

        # Count current requests
        total_count = sum(count for _, count in entries)

        if total_count >= max_requests:
            # Rate limit exceeded
            oldest_entry = entries[0] if entries else (now, 0)
            reset_time = oldest_entry[0] + window_seconds
            retry_after = int(reset_time - now)

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=max(1, retry_after),
            )

        # Allow request
        entries.append((now, 1))

        return RateLimitResult(
            allowed=True,
            remaining=max(0, max_requests - total_count - 1),
            reset_time=now + window_seconds,
        )

    def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        if key in self._storage:
            del self._storage[key]


class RedisRateLimitBackend(RateLimitBackend):
    """Redis-based rate limit backend for distributed deployments."""

    def __init__(self, redis_url: str, timeout: int = 5) -> None:
        """Initialize Redis backend.

        Args:
            redis_url: Redis connection URL
            timeout: Connection timeout in seconds
        """
        self.redis_url = redis_url
        self.timeout = timeout
        self._redis: Any = None
        self._connect()

    def _connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis as redis_lib

            self._redis = redis_lib.from_url(
                self.redis_url,
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout,
            )
            # Test connection
            self._redis.ping()
        except ImportError:
            raise ImportError(
                "Redis backend requires 'redis' package. "
                "Install with: pip install redis"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit using Redis."""
        if not self._redis:
            raise ConnectionError("Redis connection not available")

        now = time.time()
        window_start = now - window_seconds

        pipeline = self._redis.pipeline()

        # Remove old entries
        pipeline.zremrangebyscore(key, 0, window_start)

        # Count current entries
        pipeline.zcard(key)

        # Add current request
        pipeline.zadd(key, {str(now): now})

        # Set expiry on key
        pipeline.expire(key, window_seconds)

        results = pipeline.execute()
        current_count = results[1]  # zcard result

        if current_count > max_requests:
            # Rate limit exceeded, remove our just-added entry
            self._redis.zrem(key, str(now))

            # Get oldest entry for retry_after calculation
            oldest = self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                reset_time = oldest_timestamp + window_seconds
                retry_after = int(reset_time - now)
            else:
                reset_time = now + window_seconds
                retry_after = window_seconds

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=max(1, retry_after),
            )

        return RateLimitResult(
            allowed=True,
            remaining=max(0, max_requests - current_count),
            reset_time=now + window_seconds,
        )

    def reset(self, key: str) -> None:
        """Reset rate limit for key."""
        if self._redis:
            self._redis.delete(key)


def create_rate_limit_backend(
    redis_url: str | None = None,
    timeout: int = 5,
) -> RateLimitBackend:
    """Create appropriate rate limit backend.

    Args:
        redis_url: Optional Redis URL for distributed rate limiting
        timeout: Connection timeout for Redis

    Returns:
        RateLimitBackend instance
    """
    if redis_url:
        return RedisRateLimitBackend(redis_url, timeout)
    return MemoryRateLimitBackend()
