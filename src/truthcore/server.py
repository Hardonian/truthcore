"""Truth Core HTTP server with API endpoints."""

from __future__ import annotations

import json
import tempfile
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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
from truthcore.cache import ContentAddressedCache
from truthcore.impact import ChangeImpactEngine
from truthcore.invariant_dsl import InvariantExplainer
from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.parquet_store import HistoryCompactor, ParquetStore
from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
from truthcore.replay import (
    BundleExporter,
    ReplayBundle,
    ReplayEngine,
    SimulationChanges,
    SimulationEngine,
)
from truthcore.security import SecurityLimits
from truthcore.truth_graph import TruthGraph, TruthGraphBuilder
from truthcore.ui_geometry import UIGeometryParser, UIReachabilityChecker


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


class ExplainRequest(BaseModel):
    """Request model for explain endpoint."""

    rule: str
    data: dict[str, Any]
    rules: dict[str, Any] | None = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    yield
    # Shutdown
    jobs.clear()


def create_app(
    cache_dir: Path | None = None,
    static_dir: Path | None = None,
    debug: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cache_dir: Optional cache directory path
        static_dir: Optional static files directory
        debug: Enable debug mode

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Truth Core API",
        description="Deterministic evidence-based verification framework",
        version=__version__,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize cache
    cache = ContentAddressedCache(cache_dir) if cache_dir else None

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the HTML GUI."""
        if static_dir and (static_dir / "index.html").exists():
            with open(static_dir / "index.html", encoding="utf-8") as f:
                return f.read()

        # Default response if no static files
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Truth Core Server</title>
            <style>
                body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                h1 {{ color: #333; }}
                .version {{ color: #666; }}
                .endpoints {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
                code {{ background: #e0e0e0; padding: 2px 6px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Truth Core Server</h1>
            <p class="version">Version: {__version__}</p>
            <div class="endpoints">
                <h2>API Endpoints</h2>
                <ul>
                    <li><code>GET /health</code> - Health check</li>
                    <li><code>POST /judge</code> - Run readiness check</li>
                    <li><code>POST /intel</code> - Run intelligence analysis</li>
                    <li><code>POST /explain</code> - Explain invariant rules</li>
                    <li><code>GET /cache/stats</code> - Cache statistics</li>
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
    async def status():
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
        }

    @app.post("/api/v1/judge")
    async def judge(
        request: JudgeRequest,
        inputs: UploadFile | None = File(None),
    ):
        """Run readiness check.

        Args:
            request: Judge configuration
            inputs: Optional input file/directory as zip

        Returns:
            Judgment results
        """
        job_id = f"judge_{int(time.time() * 1000)}"
        start_time = time.time()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                out_path = tmp_path / "output"
                out_path.mkdir()

                # Handle uploaded inputs
                inputs_path = None
                if inputs:
                    import shutil
                    import zipfile

                    inputs_zip = tmp_path / "inputs.zip"
                    with open(inputs_zip, "wb") as f:
                        content = await inputs.read()
                        f.write(content)

                    inputs_path = tmp_path / "inputs"
                    inputs_path.mkdir()

                    with zipfile.ZipFile(inputs_zip, "r") as zf:
                        zf.extractall(inputs_path)

                # Create manifest
                manifest = RunManifest.create(
                    command="judge",
                    config={
                        "profile": request.profile,
                        "strict": request.strict,
                        "parallel": request.parallel,
                    },
                    input_dir=inputs_path or Path("."),
                    profile=request.profile,
                )

                # Check cache
                if cache:
                    cache_key = manifest.compute_cache_key()
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
                    "profile": request.profile,
                    "timestamp": normalize_timestamp(),
                    "passed": True,
                    "findings": [],
                }

                with open(out_path / "readiness.json", "w") as f:
                    json.dump(readiness_data, f, indent=2, sort_keys=True)

                # Run policy pack if specified
                if request.policy_pack:
                    pack = PolicyPackLoader.load_pack(request.policy_pack)
                    engine = PolicyEngine(inputs_path or Path("."), out_path)
                    policy_result = engine.run_pack(pack)
                    engine.write_outputs(policy_result)
                    readiness_data["policy_findings"] = len(policy_result.findings)
                    readiness_data["policy_blocked"] = policy_result.has_blocking()

                # Generate evidence manifest
                from truthcore.provenance.manifest import EvidenceManifest

                evidence_manifest = EvidenceManifest.generate(
                    bundle_dir=out_path,
                    run_manifest_hash=manifest.compute_cache_key(),
                    config_hash=manifest.config_hash,
                    limits=SecurityLimits(),
                )
                evidence_manifest.write_json(out_path / "evidence.manifest.json")

                # Sign if requested
                if request.sign:
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
                    cache_key = manifest.compute_cache_key()
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

        except Exception as e:
            if debug:
                traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/v1/intel")
    async def intel(
        request: IntelRequest,
        inputs: UploadFile | None = File(None),
    ):
        """Run intelligence analysis.

        Args:
            request: Intel configuration
            inputs: Optional input file/directory as zip

        Returns:
            Analysis results
        """
        job_id = f"intel_{int(time.time() * 1000)}"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)

                # Handle uploaded inputs
                inputs_path = None
                if inputs:
                    import zipfile

                    inputs_zip = tmp_path / "inputs.zip"
                    with open(inputs_zip, "wb") as f:
                        content = await inputs.read()
                        f.write(content)

                    inputs_path = tmp_path / "inputs"
                    inputs_path.mkdir()

                    with zipfile.ZipFile(inputs_zip, "r") as zf:
                        zf.extractall(inputs_path)

                inputs_path = inputs_path or Path(".")

                # Create appropriate scorer
                if request.mode == "readiness":
                    scorer = ReadinessAnomalyScorer(inputs_path)
                elif request.mode == "recon":
                    scorer = ReconciliationAnomalyScorer(inputs_path)
                elif request.mode == "agent":
                    scorer = AgentBehaviorScorer(inputs_path)
                elif request.mode == "knowledge":
                    scorer = KnowledgeHealthScorer(inputs_path)
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown mode: {request.mode}",
                    )

                # Run analysis
                scores = scorer.score()

                # Write scorecard
                writer = ScorecardWriter(tmp_path)
                writer.write(scores, mode=request.mode)

                # Compact if requested
                if request.compact:
                    compactor = HistoryCompactor(
                        retention_days=request.retention_days,
                    )
                    stats = compactor.compact(inputs_path)
                else:
                    stats = None

                return {
                    "job_id": job_id,
                    "status": "completed",
                    "mode": request.mode,
                    "scores": scores,
                    "compact_stats": stats,
                }

        except Exception as e:
            if debug:
                traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/v1/explain")
    async def explain(request: ExplainRequest):
        """Explain invariant rule evaluation.

        Args:
            request: Explain configuration with rule and data

        Returns:
            Explanation of rule evaluation
        """
        try:
            explainer = InvariantExplainer()

            # Load rules if provided
            if request.rules:
                explainer.load_rules_from_dict(request.rules)

            explanation = explainer.explain(request.rule, request.data)

            return {
                "rule": request.rule,
                "explanation": explanation,
            }

        except Exception as e:
            if debug:
                traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/v1/cache/stats")
    async def cache_stats():
        """Get cache statistics."""
        if not cache:
            raise HTTPException(status_code=503, detail="Cache not enabled")

        try:
            stats = cache.get_stats()
            return {
                "enabled": True,
                "cache_dir": str(cache_dir),
                "stats": stats,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/v1/cache/clear")
    async def cache_clear():
        """Clear all cache entries."""
        if not cache:
            raise HTTPException(status_code=503, detail="Cache not enabled")

        try:
            cache.clear()
            return {"status": "cleared", "timestamp": normalize_timestamp()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/v1/impact")
    async def impact(
        diff: str = Form(...),
        profile: str = Form(default="base"),
    ):
        """Run change impact analysis.

        Args:
            diff: Git diff text
            profile: Analysis profile

        Returns:
            Impact analysis results
        """
        try:
            engine = ChangeImpactEngine()
            plan = engine.analyze(
                diff_text=diff,
                changed_files=None,
                profile=profile,
                source="api",
            )

            return {
                "engines": [
                    {"id": e.engine_id, "include": e.include, "reason": e.reason}
                    for e in plan.engines
                ],
                "invariants": [
                    {"id": i.rule_id, "include": i.include, "reason": i.reason}
                    for i in plan.invariants
                ],
            }

        except Exception as e:
            if debug:
                traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(job_id: str):
        """Get job status by ID."""
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return jobs[job_id]

    # Serve static files if directory provided
    if static_dir and static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app
