"""Security middleware and error handling for Truth Core server.

Provides:
- Request ID tracing
- Security headers
- Error taxonomy with consistent envelopes
- Input validation and sanitization
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Error categories for classification."""

    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    INTERNAL = "internal"
    EXTERNAL = "external"
    CONFIGURATION = "configuration"


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ErrorDetail:
    """Structured error detail."""

    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    code: str
    field: str | None = None
    suggestion: str | None = None


@dataclass
class ErrorEnvelope:
    """Standard error response envelope."""

    success: bool = False
    error_id: str = ""
    request_id: str = ""
    timestamp: str = ""
    category: ErrorCategory = ErrorCategory.INTERNAL
    severity: ErrorSeverity = ErrorSeverity.ERROR
    message: str = ""
    code: str = ""
    details: list[dict[str, Any]] | None = None
    traceback: str | None = None
    documentation_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "error_id": self.error_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "error": {
                "category": self.category.value,
                "severity": self.severity.value,
                "message": self.message,
                "code": self.code,
                "details": self.details or [],
            },
            "meta": {
                "documentation_url": self.documentation_url,
                "traceback": self.traceback if self.traceback else None,
            },
        }


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security headers and request handling middleware."""

    def __init__(
        self,
        app,
        csp_policy: str | None = None,
        allow_iframe: bool = False,
        strict_transport: bool = True,
    ):
        super().__init__(app)
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self';"
        )
        self.allow_iframe = allow_iframe
        self.strict_transport = strict_transport

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and add security headers."""
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN" if self.allow_iframe else "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # Strict Transport Security (HTTPS only)
        if self.strict_transport:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID middleware for tracing."""

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add request ID to response."""
        # Get or generate request ID
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[self.header_name] = request_id

        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Request timing middleware for lightweight telemetry."""

    def __init__(
        self,
        app,
        header_name: str = "X-Request-Duration-ms",
        log_threshold_ms: float | None = None,
    ) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.log_threshold_ms = log_threshold_ms

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Measure request duration and optionally log slow requests."""
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers[self.header_name] = f"{duration_ms:.2f}"

        if self.log_threshold_ms is None:
            env_threshold = os.environ.get("TRUTHCORE_TIMING_LOG_MS")
            if env_threshold:
                try:
                    self.log_threshold_ms = float(env_threshold)
                except ValueError:
                    self.log_threshold_ms = None

        if self.log_threshold_ms is not None and duration_ms >= self.log_threshold_ms:
            logger.info(
                "Slow request %s %s took %.2fms",
                request.method,
                request.url.path,
                duration_ms,
            )

        return response


def create_error_response(
    error_id: str,
    request_id: str,
    error: Exception,
    category: ErrorCategory = ErrorCategory.INTERNAL,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_id: Unique error identifier
        request_id: Request trace ID
        error: The exception that occurred
        category: Error category
        severity: Error severity
        include_traceback: Whether to include traceback

    Returns:
        Error envelope as dictionary
    """
    from datetime import UTC, datetime

    envelope = ErrorEnvelope(
        error_id=error_id,
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
        category=category,
        severity=severity,
        message=str(error),
        code=f"TRUTHCORE_{category.upper()}_{severity.upper()}",
        documentation_url=f"https://docs.truthcore.io/errors/{category.value}",
    )

    if include_traceback:
        import traceback

        envelope.traceback = traceback.format_exc()

    return envelope.to_dict()


def sanitize_cache_key(key: str) -> str:
    """Sanitize cache key to prevent path traversal.

    Args:
        key: Raw cache key

    Returns:
        Sanitized key safe for filesystem use

    Raises:
        ValueError: If key contains invalid characters
    """
    # Only allow alphanumeric, dash, underscore, and dot
    if not re.match(r"^[a-zA-Z0-9_.\-]+$", key):
        raise ValueError(f"Invalid cache key: {key}. Only alphanumeric, dash, underscore, and dot allowed.")

    # Prevent path traversal attempts
    if ".." in key or key.startswith("/") or key.startswith("\\"):
        raise ValueError(f"Invalid cache key: {key}. Path traversal detected.")

    return key


def sanitize_path(path: str, base_dir: str | None = None) -> str:
    """Sanitize file path to prevent traversal.

    Args:
        path: Raw path
        base_dir: Optional base directory to restrict to

    Returns:
        Sanitized path

    Raises:
        ValueError: If path attempts traversal outside base_dir
    """
    from pathlib import Path

    # Normalize path
    clean_path = Path(path).resolve()

    # Check for traversal if base_dir provided
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            clean_path.relative_to(base)
        except ValueError as err:
            raise ValueError(f"Path {path} attempts directory traversal outside {base_dir}") from err

    return str(clean_path)


class ValidationError(Exception):
    """Validation error with structured details."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.code = code
        self.details = details or {}


class AuthenticationError(Exception):
    """Authentication failure."""

    def __init__(self, message: str = "Authentication failed", code: str = "AUTH_FAILED"):
        super().__init__(message)
        self.code = code


class AuthorizationError(Exception):
    """Authorization failure."""

    def __init__(self, message: str = "Access denied", code: str = "ACCESS_DENIED"):
        super().__init__(message)
        self.code = code


class RateLimitError(Exception):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        code: str = "RATE_LIMIT_EXCEEDED",
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.code = code


def validate_api_key_format(api_key: str) -> bool:
    """Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if valid format, False otherwise
    """
    # Must be at least 32 chars, alphanumeric with some symbols
    if len(api_key) < 32:
        return False

    # Check for reasonable entropy (not just repeating chars)
    unique_chars = len(set(api_key))
    if unique_chars < 8:
        return False

    return True


def generate_error_id() -> str:
    """Generate unique error ID."""
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_hex(8)
    return f"err_{timestamp}_{random_part}"

