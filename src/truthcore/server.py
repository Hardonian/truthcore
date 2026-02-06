"""Truth Core HTTP server with API endpoints."""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import os
import secrets
import tempfile
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi import status as http_status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from truthcore import __version__
from truthcore.anomaly_scoring import (
    AgentBehaviorScorer,
    KnowledgeHealthScorer,
    ReadinessAnomalyScorer,
    ReconciliationAnomalyScorer,
    ScorecardWriter,
)
from truthcore.cache import ContentAddressedCache, JsonTtlCache
from truthcore.impact import ChangeImpactEngine
from truthcore.invariant_dsl import InvariantDSL
from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.parquet_store import HistoryCompactor
from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
from truthcore.security import SecurityLimits, safe_extract_zip

# Import security utilities
from truthcore.server_security import (
    AuthenticationError,
    ErrorCategory,
    ErrorSeverity,
    RateLimitError,
    RequestIDMiddleware,
    RequestTimingMiddleware,
    SecurityMiddleware,
    ValidationError,
    create_error_response,
    generate_error_id,
    validate_api_key_format,
)
from truthcore.ui_geometry import UIGeometryParser, UIReachabilityChecker

# Configure logging
logger = logging.getLogger(__name__)

# Security configuration
SECURITY_BEARER = HTTPBearer(auto_error=False)
SECURITY_BEARER_DEPENDENCY = Depends(SECURITY_BEARER)
UPLOAD_FILE_FIELD = File(None)


class JudgeRequest(BaseModel):
    """Request model for judge endpoint."""

    profile: str = "base"
    strict: bool | None = None
    parallel: bool = True
    policy_pack: str | None = None
    sign: bool = False


class IntelRequest(BaseModel):
    """Request model for intel endpoint."""

    mode: str = "readiness"
    compact: bool = False
    retention_days: int = 90


class ExplainRuleset(BaseModel):
    """Ruleset container for explain requests."""

    rules: list[dict[str, Any]]


class ExplainRequest(BaseModel):
    """Request model for explain endpoint."""

    rule_id: str
    data: dict[str, Any]
    ruleset: ExplainRuleset


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: str


class JobStatus(BaseModel):
    """Job execution status."""

    job_id: str
    status: str  # pending, running, completed, failed
    command: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


# In-memory job storage (in production, use Redis or similar)
jobs: dict[str, JobStatus] = {}

# Rate limiting storage: {client_id: [(timestamp, count), ...]}
rate_limit_storage: dict[str, deque[float]] = {}
rate_limit_last_seen: dict[str, float] = {}


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = SECURITY_BEARER_DEPENDENCY,
    api_key: str | None = None,
) -> bool:
    """Verify API key authentication.

    Args:
        credentials: Bearer token from Authorization header
        api_key: Optional API key from query parameter

    Returns:
        True if authentication successful or disabled

    Raises:
        AuthenticationError: If authentication fails and is required
    """
    # Get expected API key from environment
    expected_key = os.environ.get("TRUTHCORE_API_KEY")

    # If no API key configured, authentication is disabled (with warning)
    if not expected_key:
        return True

    # Check for API key in header or query param
    provided_key = None
    if credentials and credentials.credentials:
        provided_key = credentials.credentials
    elif api_key:
        provided_key = api_key

    if not provided_key:
        raise AuthenticationError(
            "API key required. Provide via Authorization: Bearer <key> header or ?api_key= query parameter",
        )

    # Validate API key format
    if not validate_api_key_format(provided_key):
        raise AuthenticationError("Invalid API key format")

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_key, expected_key):
        raise AuthenticationError("Invalid API key")

    return True


def check_rate_limit(
    request: Request,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> bool:
    """Check rate limit for a client.

    Args:
        request: FastAPI request object
        max_requests: Maximum requests per window
        window_seconds: Time window in seconds

    Returns:
        True if within rate limit

    Raises:
        RateLimitError: If rate limit exceeded
    """
    # Get client identifier (IP + capped User-Agent)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")[:256]
    client_id = f"{client_ip}:{user_agent}"

    now = time.monotonic()
    window_start = now - window_seconds

    # Get or initialize client's request history
    client_history = rate_limit_storage.get(client_id)
    if client_history is None:
        client_history = deque()

    # Filter to only requests within the window
    while client_history and client_history[0] <= window_start:
        client_history.popleft()

    # Count total requests in window
    total_requests = len(client_history)

    if total_requests >= max_requests:
        raise RateLimitError(
            message=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds",
            retry_after=window_seconds,
        )

    # Record this request
    client_history.append(now)
    rate_limit_storage[client_id] = client_history
    rate_limit_last_seen[client_id] = now

    # Evict stale or excess clients to bound memory growth
    try:
        max_clients = int(os.environ.get("TRUTHCORE_RATE_LIMIT_MAX_CLIENTS", "5000"))
    except ValueError:
        max_clients = 5000
    if max_clients > 0:
        if len(rate_limit_storage) > max_clients:
            sorted_clients = sorted(rate_limit_last_seen.items(), key=lambda item: item[1])
            for client_key, _last_seen in sorted_clients[: max(0, len(rate_limit_storage) - max_clients)]:
                rate_limit_storage.pop(client_key, None)
                rate_limit_last_seen.pop(client_key, None)
    else:
        rate_limit_storage.clear()
        rate_limit_last_seen.clear()

    return True


def get_cors_origins() -> list[str]:
    """Get allowed CORS origins from environment or default.

    Returns:
        List of allowed origins. Empty list means no CORS (same-origin only).
    """
    origins_env = os.environ.get("TRUTHCORE_CORS_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    return []  # Default: no cross-origin allowed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Truth Core server starting up")

    # Check security configuration
    api_key = os.environ.get("TRUTHCORE_API_KEY")
    cors_origins = get_cors_origins()

    if not api_key:
        logger.warning(
            "TRUTHCORE_API_KEY not set - API authentication is DISABLED. This is INSECURE for production deployments."
        )
    else:
        logger.info("API authentication enabled")

    if not cors_origins:
        logger.warning(
            "TRUTHCORE_CORS_ORIGINS not set - CORS disabled (same-origin only). "
            "Frontend will need to be served from same origin."
        )
    else:
        logger.info(f"CORS enabled for origins: {cors_origins}")

    yield
    # Shutdown
    jobs.clear()
    rate_limit_storage.clear()
    logger.info("Truth Core server shutting down")


def create_app(
    cache_dir: Path | None = None,
    static_dir: Path | None = None,
    debug: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cache_dir: Optional cache directory path
        static_dir: Optional static files directory
        debug: Enable debug mode (shows stack traces in errors)

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Truth Core API",
        description="Deterministic evidence-based verification framework",
        version=__version__,
        lifespan=lifespan,
    )

    # Add CORS middleware (configured via environment)
    cors_origins = get_cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,  # Never allow credentials with CORS
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    # Add security middleware
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(RequestIDMiddleware)
    if os.environ.get("TRUTHCORE_TIMING_ENABLED", "").lower() in {"1", "true", "yes"}:
        app.add_middleware(RequestTimingMiddleware)

    # Initialize cache
    cache = ContentAddressedCache(cache_dir) if cache_dir else None
    impact_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    impact_shared_cache = JsonTtlCache(cache_dir, "impact") if cache_dir else None
    impact_locks: dict[str, asyncio.Lock] = {}

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions with standardized error envelopes."""
        error_id = generate_error_id()
        request_id = getattr(request.state, "request_id", "unknown")

        # Determine error category based on exception type
        if isinstance(exc, ValidationError):
            category = ErrorCategory.VALIDATION
            status_code = http_status.HTTP_422_UNPROCESSABLE_ENTITY
        elif isinstance(exc, AuthenticationError):
            category = ErrorCategory.AUTHENTICATION
            status_code = http_status.HTTP_401_UNAUTHORIZED
        elif isinstance(exc, RateLimitError):
            category = ErrorCategory.RATE_LIMIT
            status_code = http_status.HTTP_429_TOO_MANY_REQUESTS
        else:
            category = ErrorCategory.INTERNAL
            status_code = http_status.HTTP_500_INTERNAL_SERVER_ERROR

        # Log error
        logger.error(
            f"Error {error_id} (request: {request_id}): {exc}",
            exc_info=debug,
        )

        # Create standardized error response
        error_content = create_error_response(
            error_id=error_id,
            request_id=request_id,
            error=exc,
            category=category,
            severity=ErrorSeverity.ERROR if not isinstance(exc, ValidationError) else ErrorSeverity.WARNING,
            include_traceback=debug,
        )

        return JSONResponse(
            status_code=status_code,
            content=error_content,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Wrap HTTP exceptions in a standardized error envelope."""
        error_id = generate_error_id()
        request_id = getattr(request.state, "request_id", "unknown")
        error_content = create_error_response(
            error_id=error_id,
            request_id=request_id,
            error=exc,
            category=ErrorCategory.VALIDATION if exc.status_code < 500 else ErrorCategory.INTERNAL,
            severity=ErrorSeverity.WARNING if exc.status_code < 500 else ErrorSeverity.ERROR,
            include_traceback=debug,
        )
        return JSONResponse(status_code=exc.status_code, content=error_content)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
        """Wrap request validation errors in a standardized envelope."""
        error_id = generate_error_id()
        request_id = getattr(request.state, "request_id", "unknown")
        error_content = create_error_response(
            error_id=error_id,
            request_id=request_id,
            error=exc,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.WARNING,
            include_traceback=debug,
        )
        return JSONResponse(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_content)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the HTML GUI."""
        if static_dir and (static_dir / "index.html").exists():
            with open(static_dir / "index.html", encoding="utf-8") as f:
                return f.read()

        # Build auth status HTML
        if os.environ.get("TRUTHCORE_API_KEY"):
            auth_status = '<p style="color: #28a745;">✅ API authentication is enabled.</p>'
        else:
            auth_status = (
                '<p style="color: #dc3545;">⚠️ API authentication is DISABLED. Set TRUTHCORE_API_KEY for production.</p>'
            )

        # Build CORS status HTML
        cors_origins = get_cors_origins()
        if cors_origins:
            origins_str = ", ".join(cors_origins)
            cors_status = f"<p>CORS enabled for: {origins_str}</p>"
        else:
            cors_status = (
                "<p>CORS is disabled (same-origin only). "
                "Set TRUTHCORE_CORS_ORIGINS to enable cross-origin requests.</p>"
            )

        # Default response if no static files
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Truth Core Server</title>
            <style>
                body {{ font-family: system-ui, sans-serif;
                       max-width: 800px; margin: 50px auto; padding: 20px; }}
                h1 {{ color: #333; }}
                .version {{ color: #666; }}
                .endpoints {{ background: #f5f5f5; padding: 20px;
                              border-radius: 8px; }}
                code {{ background: #e0e0e0; padding: 2px 6px;
                        border-radius: 3px; }}
                .security {{ background: #fff3cd; padding: 15px;
                            border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Truth Core Server</h1>
            <p class="version">Version: {__version__}</p>

            <div class="security">
                <strong>Security Notice:</strong>
                {auth_status}
                {cors_status}
            </div>

            <div class="endpoints">
                <h2>API Endpoints</h2>
                <ul>
                    <li><code>GET /health</code> - Health check</li>
                    <li><code>POST /api/v1/judge</code> - Run readiness check</li>
                    <li><code>POST /api/v1/intel</code> - Run intelligence analysis</li>
                    <li><code>POST /api/v1/explain</code> - Explain invariant rules</li>
                    <li><code>GET /api/v1/cache/stats</code> - Cache statistics</li>
                </ul>
                <p>Full API docs: <a href="/docs">/docs</a></p>
            </div>
        </body>
        </html>
        """

    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=__version__,
            timestamp=normalize_timestamp(),
        )

    @app.get("/api/v1/status")
    async def status(
        request: Request,
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=60, window_seconds=60)),
    ):
        """Get server status and capabilities."""
        return {
            "version": __version__,
            "cache_enabled": cache is not None,
            "cache_dir": str(cache_dir) if cache_dir else None,
            "commands": [
                "judge",
                "intel",
                "explain",
                "cache-stats",
                "impact",
            ],
            "security": {
                "auth_enabled": bool(os.environ.get("TRUTHCORE_API_KEY")),
                "cors_origins": get_cors_origins(),
            },
        }

    @app.post("/api/v1/judge")
    async def judge(
        request: Request,
        profile: str = Form(default="base"),
        strict: bool | None = Form(default=None),
        parallel: bool = Form(default=True),
        policy_pack: str | None = Form(default=None),
        sign: bool = Form(default=False),
        inputs: UploadFile | None = UPLOAD_FILE_FIELD,
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=10, window_seconds=60)),
    ):
        """Run readiness check.

        Args:
            request: FastAPI request
            judge_request: Judge configuration
            inputs: Optional input file/directory as zip
            _auth: Authentication check (injected)
            _rate: Rate limiting check (injected)

        Returns:
            Judgment results
        """
        job_id = f"judge_{int(time.time() * 1000)}"
        start_time = time.time()
        judge_request = JudgeRequest(
            profile=profile,
            strict=strict,
            parallel=parallel,
            policy_pack=policy_pack,
            sign=sign,
        )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                out_path = tmp_path / "output"
                out_path.mkdir()

                # Handle uploaded inputs
                inputs_path = None
                if inputs:
                    inputs_zip = tmp_path / "inputs.zip"
                    max_size = 100 * 1024 * 1024
                    await _write_upload_to_path(inputs, inputs_zip, max_size)

                    inputs_path = tmp_path / "inputs"
                    inputs_path.mkdir()
                    safe_extract_zip(inputs_zip, inputs_path, SecurityLimits(max_file_size=max_size))

                # Create manifest
                manifest = RunManifest.create(
                    command="judge",
                    config={
                        "profile": judge_request.profile,
                        "strict": judge_request.strict,
                        "parallel": judge_request.parallel,
                    },
                    input_dir=inputs_path or Path("."),
                    profile=judge_request.profile,
                )

                # Check cache
                cache_key = manifest.compute_cache_key()
                if cache:
                    cached = cache.get(cache_key)
                    if cached:
                        return {
                            "job_id": job_id,
                            "status": "completed",
                            "cached": True,
                            "manifest": manifest.to_dict(),
                            "results_path": str(cached),
                        }

                # Run UI geometry checks if facts present
                if inputs_path:
                    ui_facts = inputs_path / "ui_facts.json"
                    if ui_facts.exists():
                        parser = UIGeometryParser(ui_facts)
                        checker = UIReachabilityChecker(parser)
                        ui_results = checker.run_all_checks()

                        with open(out_path / "ui_geometry.json", "w") as f:
                            json.dump(ui_results, f, indent=2)

                # Create readiness output
                readiness_data = {
                    "version": __version__,
                    "profile": judge_request.profile,
                    "timestamp": normalize_timestamp(),
                    "passed": True,
                    "findings": [],
                }

                with open(out_path / "readiness.json", "w") as f:
                    json.dump(readiness_data, f, indent=2, sort_keys=True)

                # Run policy pack if specified
                if judge_request.policy_pack:
                    pack = PolicyPackLoader.load_pack(judge_request.policy_pack)
                    engine = PolicyEngine(inputs_path or Path("."), out_path)
                    policy_result = engine.run_pack(pack)
                    engine.write_outputs(policy_result)
                    readiness_data["policy_findings"] = len(policy_result.findings)
                    readiness_data["policy_blocked"] = policy_result.has_blocking()

                # Generate evidence manifest
                from truthcore.provenance.manifest import EvidenceManifest

                evidence_manifest = EvidenceManifest.generate(
                    bundle_dir=out_path,
                    run_manifest_hash=cache_key,
                    config_hash=manifest.config_hash,
                    limits=SecurityLimits(),
                )
                evidence_manifest.write_json(out_path / "evidence.manifest.json")

                # Sign if requested
                if judge_request.sign:
                    from truthcore.provenance.signing import Signer

                    signer = Signer()
                    if signer.is_configured():
                        manifest_path = out_path / "evidence.manifest.json"
                        signer.sign_file(manifest_path, out_path / "evidence.sig")
                        readiness_data["signed"] = True

                # Update manifest
                manifest.duration_ms = int((time.time() - start_time) * 1000)
                manifest.write(out_path)

                # Cache results
                if cache:
                    cache.put(cache_key, out_path, manifest.to_dict())

                # Read results
                with open(out_path / "readiness.json", encoding="utf-8") as f:
                    results = json.load(f)

                return {
                    "job_id": job_id,
                    "status": "completed",
                    "cached": False,
                    "manifest": manifest.to_dict(),
                    "results": results,
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in judge endpoint: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error processing request",
            ) from e

    @app.post("/api/v1/intel")
    async def intel(
        request: Request,
        mode: str = Form(default="readiness"),
        compact: bool = Form(default=False),
        retention_days: int = Form(default=90),
        inputs: UploadFile | None = UPLOAD_FILE_FIELD,
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=10, window_seconds=60)),
    ):
        """Run intelligence analysis.

        Args:
            request: FastAPI request
            intel_request: Intel configuration
            inputs: Optional input file/directory as zip
            _auth: Authentication check (injected)
            _rate: Rate limiting check (injected)

        Returns:
            Analysis results
        """
        job_id = f"intel_{int(time.time() * 1000)}"
        intel_request = IntelRequest(
            mode=mode,
            compact=compact,
            retention_days=retention_days,
        )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)

                # Handle uploaded inputs
                inputs_path = None
                if inputs:
                    inputs_zip = tmp_path / "inputs.zip"
                    max_size = 100 * 1024 * 1024
                    await _write_upload_to_path(inputs, inputs_zip, max_size)

                    inputs_path = tmp_path / "inputs"
                    inputs_path.mkdir()
                    safe_extract_zip(inputs_zip, inputs_path, SecurityLimits(max_file_size=max_size))

                inputs_path = inputs_path or Path(".")

                # Create appropriate scorer
                if intel_request.mode == "readiness":
                    scorer = ReadinessAnomalyScorer(inputs_path)
                elif intel_request.mode == "recon":
                    scorer = ReconciliationAnomalyScorer(inputs_path)
                elif intel_request.mode == "agent":
                    scorer = AgentBehaviorScorer(inputs_path)
                elif intel_request.mode == "knowledge":
                    scorer = KnowledgeHealthScorer(inputs_path)
                else:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown mode: {intel_request.mode}",
                    )

                # Run analysis
                scores = scorer.score()

                # Write scorecard
                writer = ScorecardWriter(tmp_path)
                writer.write(scores, mode=intel_request.mode)

                # Compact if requested
                if intel_request.compact:
                    compactor = HistoryCompactor(
                        retention_days=intel_request.retention_days,
                    )
                    stats = compactor.compact(inputs_path)
                else:
                    stats = None

                return {
                    "job_id": job_id,
                    "status": "completed",
                    "mode": intel_request.mode,
                    "scores": scores,
                    "compact_stats": stats,
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in intel endpoint: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error processing request",
            ) from e

    @app.post("/api/v1/explain")
    async def explain(
        explain_request: ExplainRequest,
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=30, window_seconds=60)),
    ):
        """Explain invariant rule evaluation.

        Args:
            explain_request: Explain configuration with rule and data
            _auth: Authentication check (injected)
            _rate: Rate limiting check (injected)

        Returns:
            Explanation of rule evaluation
        """
        try:
            rule_data = next(
                (rule for rule in explain_request.ruleset.rules if rule.get("id") == explain_request.rule_id),
                None,
            )
            if rule_data is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Rule '{explain_request.rule_id}' not found in ruleset",
                )

            explainer = InvariantDSL(explain_request.data)
            explanation = explainer.explain(rule_data)

            return {
                "rule_id": explain_request.rule_id,
                "explanation": explanation,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in explain endpoint: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error processing request",
            ) from e

    @app.get("/api/v1/cache/stats")
    async def cache_stats(
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=60, window_seconds=60)),
    ):
        """Get cache statistics."""
        if not cache:
            raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cache not enabled")

        try:
            stats = cache.get_stats()
            return {
                "enabled": True,
                "cache_dir": str(cache_dir),
                "stats": stats,
            }
        except Exception as e:
            logger.exception(f"Error getting cache stats: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error retrieving cache statistics",
            ) from e

    @app.post("/api/v1/cache/clear")
    async def cache_clear(
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=5, window_seconds=60)),
    ):
        """Clear all cache entries."""
        if not cache:
            raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cache not enabled")

        try:
            cache.clear()
            logger.info("Cache cleared via API")
            return {"status": "cleared", "timestamp": normalize_timestamp()}
        except Exception as e:
            logger.exception(f"Error clearing cache: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error clearing cache",
            ) from e

    @app.post("/api/v1/impact")
    async def impact(
        request: Request,
        diff: str = Form(...),
        profile: str = Form(default="base"),
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=10, window_seconds=60)),
    ):
        """Run change impact analysis.

        Args:
            request: FastAPI request
            diff: Git diff text
            profile: Analysis profile
            _auth: Authentication check (injected)
            _rate: Rate limiting check (injected)

        Returns:
            Impact analysis results
        """
        try:
            try:
                cache_ttl = float(os.environ.get("TRUTHCORE_IMPACT_CACHE_TTL", "60"))
            except ValueError:
                cache_ttl = 60.0
            try:
                cache_max_entries = int(os.environ.get("TRUTHCORE_IMPACT_CACHE_MAX_ENTRIES", "128"))
            except ValueError:
                cache_max_entries = 128
            if cache_max_entries < 1:
                cache_ttl = 0

            # Validate diff size (1MB max to prevent DoS)
            max_diff_size = 1024 * 1024
            if len(diff) > max_diff_size:
                raise HTTPException(
                    status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Diff too large. Maximum size: {max_diff_size} bytes",
                )

            cache_key = None
            now = time.monotonic()
            if cache_ttl > 0:
                diff_hash = hashlib.blake2s(diff.encode("utf-8"), digest_size=16).hexdigest()
                cache_key = f"{profile}:{diff_hash}"
                cached = impact_cache.get(cache_key)
                if cached and cached[0] > now:
                    return {**cached[1], "cache": {"hit": True, "ttl_s": cache_ttl}}
                if impact_shared_cache:
                    shared_cached = impact_shared_cache.get(cache_key, now)
                    if shared_cached:
                        impact_cache[cache_key] = (now + cache_ttl, shared_cached)
                        return {**shared_cached, "cache": {"hit": True, "ttl_s": cache_ttl, "layer": "shared"}}

            if cache_key and cache_ttl > 0:
                lock = impact_locks.setdefault(cache_key, asyncio.Lock())
                async with lock:
                    now = time.monotonic()
                    cached = impact_cache.get(cache_key)
                    if cached and cached[0] > now:
                        return {**cached[1], "cache": {"hit": True, "ttl_s": cache_ttl}}
                    if impact_shared_cache:
                        shared_cached = impact_shared_cache.get(cache_key, now)
                        if shared_cached:
                            impact_cache[cache_key] = (now + cache_ttl, shared_cached)
                            return {
                                **shared_cached,
                                "cache": {"hit": True, "ttl_s": cache_ttl, "layer": "shared"},
                            }

                    engine = ChangeImpactEngine()
                    plan = engine.analyze(
                        diff_text=diff,
                        changed_files=None,
                        profile=profile,
                        source="api",
                    )

                    payload = {
                        "engines": [
                            {"id": e.engine_id, "include": e.include, "reason": e.reason} for e in plan.engines
                        ],
                        "invariants": [
                            {"id": i.rule_id, "include": i.include, "reason": i.reason} for i in plan.invariants
                        ],
                    }
                    impact_cache[cache_key] = (now + cache_ttl, payload)
                    if len(impact_cache) > cache_max_entries:
                        impact_cache.pop(next(iter(impact_cache)))
                    if impact_shared_cache:
                        impact_shared_cache.put(cache_key, payload, now + cache_ttl)
                    return {**payload, "cache": {"hit": False, "ttl_s": cache_ttl}}

            engine = ChangeImpactEngine()
            plan = engine.analyze(
                diff_text=diff,
                changed_files=None,
                profile=profile,
                source="api",
            )

            return {
                "engines": [{"id": e.engine_id, "include": e.include, "reason": e.reason} for e in plan.engines],
                "invariants": [{"id": i.rule_id, "include": i.include, "reason": i.reason} for i in plan.invariants],
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in impact endpoint: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error processing impact analysis",
            ) from e

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(
        job_id: str,
        _auth: bool = Depends(verify_api_key),
        _rate: bool = Depends(functools.partial(check_rate_limit, max_requests=60, window_seconds=60)),
    ):
        """Get job status by ID."""
        if job_id not in jobs:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Job not found")
        return jobs[job_id]

    # Serve static files if directory provided, or use default GUI
    if static_dir and static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    else:
        # Use built-in GUI as default
        from truthcore.gui import GUI_DIR

        if GUI_DIR.exists() and (GUI_DIR / "index.html").exists():
            app.mount("/static", StaticFiles(directory=GUI_DIR), name="static")

    return app


async def _write_upload_to_path(
    upload: UploadFile,
    destination: Path,
    max_size: int,
) -> int:
    """Stream an uploaded file to disk with size enforcement."""
    bytes_written = 0
    try:
        with open(destination, "wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_size:
                    f.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size: {max_size} bytes",
                    )
                f.write(chunk)
    finally:
        await upload.close()

    return bytes_written
