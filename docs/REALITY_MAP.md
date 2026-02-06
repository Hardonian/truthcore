# Reality Map

## Stack & Entry Points
- **Python 3.11+** core engine and CLI (`truthctl`) with FastAPI server for HTTP access.【F:src/truthcore/cli.py†L1-L200】【F:src/truthcore/server.py†L1-L940】
- **Dashboard**: Vite + vanilla TypeScript static UI in `dashboard/`.【F:dashboard/package.json†L1-L80】
- **TypeScript SDK**: `packages/ts-contract-sdk` for contract parsing and helpers.【F:packages/ts-contract-sdk/package.json†L1-L80】

## Primary User Flows
1. **CLI verification** (`truthctl judge`, `truthctl replay`, `truthctl simulate`)
   - Produces content-addressed outputs, run manifests, and signed evidence if keys are configured.【F:src/truthcore/cli.py†L1-L200】
2. **HTTP API**
   - `GET /health` for liveness.
   - `GET /api/v1/status` for capability/feature status.
   - `POST /api/v1/judge` for readiness verification.
   - `POST /api/v1/intel` for anomaly scoring.
   - `POST /api/v1/explain` for rule explanations.
   - Cache and impact endpoints for operational use.【F:src/truthcore/server.py†L372-L940】
3. **Dashboard**
   - `truthctl dashboard build/serve/snapshot/demo` generates static dashboards for offline viewing.【F:src/truthcore/cli.py†L1-L200】

## Critical APIs & Security Boundaries
- **API Key Authentication** (optional): enabled when `TRUTHCORE_API_KEY` is set; enforced via bearer token or query param.【F:src/truthcore/server.py†L70-L140】
- **Rate limiting**: in-memory limiter applied to most API routes; configurable via environment and code defaults.【F:src/truthcore/server.py†L90-L210】
- **Input validation and sanitization** for file handling, JSON, and zip extraction using security limits.【F:src/truthcore/security.py†L1-L240】
- **Signed evidence** via Ed25519 when cryptography is available and keys are configured.【F:src/truthcore/provenance/signing.py†L1-L300】

## Data & Storage
- **Cache**: content-addressed cache under `.truthcache` or configured directory.【F:src/truthcore/cache.py†L1-L220】
- **Optional Parquet history**: stored under `.truthparquet` when enabled.【F:src/truthcore/parquet_store.py†L1-L170】
- **Artifacts**: run manifests, verdicts, markdown reports, and evidence bundles written to output directories.【F:src/truthcore/manifest.py†L1-L200】

## Observability
- **Request ID middleware** and structured error envelopes for consistent error responses.【F:src/truthcore/server_security.py†L1-L210】
- **Optional timing middleware** via `TRUTHCORE_TIMING_ENABLED`/`TRUTHCORE_TIMING_LOG_MS`.【F:src/truthcore/server_security.py†L72-L140】

## CI + Verification Gates
- GitHub Actions CI runs lint, typecheck, tests, builds, contract checks, and security scans across Python and TypeScript packages.【F:.github/workflows/ci.yml†L1-L260】
