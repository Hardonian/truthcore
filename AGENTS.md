# AGENTS.md — Truth Core Operating Manual

> **Truth Core** — Deterministic, evidence-based verification framework for software systems.  
> **Repo:** Hybrid Python + TypeScript monorepo | **License:** MIT | **Version:** 0.2.0

---

## 1. Purpose

- **What:** Truth Core is a deterministic verification engine producing signed, content-addressed evidence artifacts (verdicts, readiness reports, traces) for CI/CD pipelines.
- **Who:** Software teams running automated verification, compliance checks, AI agent trace validation, and release readiness gates.
- **Done means:**
  1. All verification commands (`truthctl judge`, `truthctl replay`, `truthctl simulate`) produce deterministic outputs.
  2. CLI, HTTP server, and GitHub Actions produce identical verdicts given identical inputs.
  3. Dashboard renders results offline with no external CDN dependencies.
  4. All CI gates pass (lint, typecheck, test, build, determinism).
  5. No fake claims, no hard-coded thresholds without justification, no drift in schema versions.

---

## 2. Repo Map

| Path | Purpose | Source of Truth? |
|------|---------|------------------|
| `src/truthcore/` | Python verification engine (CLI, server, engines, invariants) | Yes — Core logic |
| `src/truthcore/cli.py` | Main CLI entry point (truthctl commands) | Yes — CLI surface |
| `src/truthcore/policy/` | Policy-as-code YAML packs (security, privacy, agent, logging) | Yes — Policy definitions |
| `src/truthcore/schemas/` | JSON schemas for verdict contracts (v1.0.0, v2.0.0) | Yes — Contract definitions |
| `src/truthcore/engines/` | Verification engines (readiness, agent trace, reconciliation, knowledge) | Yes — Engine logic |
| `src/truthcore/replay/` | Replay and simulation modules (bundle, replayer, simulator, diff) | Yes — Replay logic |
| `dashboard/` | Static HTML dashboard (Vite + vanilla TypeScript) | Yes — UI build output |
| `packages/ts-contract-sdk/` | TypeScript SDK for verdict contracts | Yes — SDK source |
| `tests/` | pytest-based test suite | Yes — Test definitions |
| `tests/fixtures/golden/` | Golden test fixtures (expected_verdict.json) | Yes — Regression baselines |
| `examples/` | Example bundles, replay configs, server API demos | Reference — Examples |
| `docs/` | Architecture diagrams, implementation trackers, reference docs | Reference — Documentation |
| `integrations/github-actions/` | GitHub Actions integration | Yes — CI/CD integration |
| `.github/workflows/` | CI workflows (ci.yml, release.yml) | Yes — CI definitions |
| `pyproject.toml` | Python package config, ruff, pytest, build | Yes — Py config |
| `package.json` (root) | Monorepo scripts, pnpm workspace config | Yes — TS config |

---

## 3. Golden Rules (Invariants)

### Security & Privacy
- **No secrets in code.** Use `.env.example` for templates; never commit credentials.
- **Path traversal protection.** All file paths validated before access (see `security.py`).
- **Resource limits.** Enforce limits on file size, JSON depth, upload size (configurable).
- **Evidence signing.** All artifacts signed with Ed25519; tampering detected via `provenance/verifier.py`.
- **Safe archive extraction.** Zip extraction with traversal checks enabled.

### Data Integrity
- **Determinism is sacred.** Same inputs must produce identical outputs:
  - Stable sorting of all collections
  - Normalized UTC timestamps
  - Canonical JSON serialization (sorted keys)
  - Content-addressed hashing (blake2b, sha256, sha3)
  - No random sampling or probabilistic methods
- **No fake data/claims.** All thresholds must be justified; no hard-coded customer metrics.
- **Schema versioning.** All contracts versioned (v1.0.0, v2.0.0); migrations supported via `migrations/`.

### Code Quality
- **Minimal diffs.** Refactor only when necessary; prefer targeted fixes.
- **CI must stay green.** Any red build is P0.
- **No dead imports.** Run `ruff check` to detect.
- **No unused files.** Remove artifacts not referenced in code or tests.
- **Type safety.** All Python functions must have type hints; TypeScript strict mode enabled.

---

## 4. Agent Workflow

### 4.1 Discover
- Read `README.md` for high-level context.
- Check `package.json` (root) for monorepo scripts.
- Review recent commits: `git log --oneline -15`.
- Identify entry points: `src/truthcore/cli.py`, `src/truthcore/server.py`.

### 4.2 Diagnose
- Gather evidence: logs, reproduction steps, file paths.
- Check existing tests in `tests/` or `packages/ts-contract-sdk/` for patterns.
- Run lint/typecheck to surface issues early.
- Search for similar implementations before adding new code.

### 4.3 Implement
- **Smallest safe patch.** One concern per PR.
- Follow existing patterns in adjacent modules.
- Add tests for new functionality (see CONTRIBUTING.md test guidelines).
- Update docs if user-facing behavior changes.

### 4.4 Verify
- Run full verification: `pnpm run verify` (runs Python + TypeScript checks).
- Run specific checks:
  - Python: `pnpm run python:lint`, `pnpm run python:typecheck`, `pnpm run python:test`
  - TypeScript: `pnpm run ts:lint`, `pnpm run ts:typecheck`, `pnpm run ts:test`, `pnpm run ts:build`
- Ensure dashboard builds: `cd dashboard && pnpm run build`
- Ensure SDK builds: `cd packages/ts-contract-sdk && pnpm run build`

### 4.5 Report
- PR description must include:
  - Root cause (if fixing a bug)
  - Files changed (concise list)
  - Verification steps (commands run, outputs)
  - Breaking changes (if any)

---

## 5. Command Cookbook

### Installation
```bash
# Full setup (Python + TypeScript)
pnpm run install:all

# Python only
pip install -e '.[dev,parquet]'

# TypeScript only
pnpm install
cd dashboard && pnpm install
cd packages/ts-contract-sdk && pnpm install
```

### Development
```bash
# Run CLI (after Python install)
truthctl --help

# Start dashboard dev server
pnpm run dev:dashboard
# Or: cd dashboard && pnpm run dev

# Start HTTP server
truthctl serve --port 8080 --reload
```

### Lint
```bash
# All (Python + TypeScript)
pnpm run lint

# Python only
pnpm run python:lint
pnpm run python:lint:fix    # Auto-fix

# TypeScript only
pnpm run ts:lint
pnpm run ts:lint:fix
```

### Typecheck
```bash
# All
pnpm run typecheck

# Python only (Pyright)
pnpm run python:typecheck

# TypeScript only
pnpm run ts:typecheck
```

### Test
```bash
# All (Python + TypeScript)
pnpm run test

# Python only (pytest)
pnpm run python:test
pnpm run python:test:cov    # With coverage (80% threshold)

# TypeScript only (vitest)
pnpm run ts:test
```

### Build
```bash
# TypeScript packages (SDK + dashboard)
pnpm run build

# Dashboard only
cd dashboard && pnpm run build

# SDK only
cd packages/ts-contract-sdk && pnpm run build
```

### Format
```bash
# All
pnpm run format

# Python only
pnpm run python:format

# TypeScript only
pnpm run ts:format
```

### Full Verification
```bash
# Run everything (CI equivalent)
pnpm run verify

# CI mode
pnpm run verify:ci
```

---

## 6. Change Safety Checklist

Before committing, verify:

- [ ] **Lint passes** — `pnpm run lint` exits 0
- [ ] **Typecheck passes** — `pnpm run typecheck` exits 0
- [ ] **Tests pass** — `pnpm run test` exits 0 (Python coverage ≥80%)
- [ ] **Build succeeds** — `pnpm run build` creates valid outputs
- [ ] **No dead imports** — `ruff check` clean
- [ ] **No unused files** — no orphaned test fixtures or temp files
- [ ] **Schema consistency** — if changing verdict models, update schema versions and migrations
- [ ] **Dashboard renders** — `cd dashboard && pnpm run build` succeeds
- [ ] **SDK builds** — `cd packages/ts-contract-sdk && pnpm run build` succeeds
- [ ] **Documentation updated** — README, CHANGELOG, or docs/ if user-facing
- [ ] **Conventional commits** — follow `type(scope): description` format

---

## 7. Code Standards

### Python
- **Ruff** for linting and formatting (configured in `pyproject.toml`)
- **Pyright** for type checking (strict)
- **Google-style** docstrings required for public APIs
- **Type hints** mandatory on all functions; use `|` for unions
- **Imports** sorted; no circular dependencies
- **Error handling** — use custom exceptions in `severity.py`; log via structured logging

### TypeScript
- **ESLint** with `@typescript-eslint`
- **Strict mode** enabled in all tsconfig.json
- **tsup** for SDK bundling (ESM + CJS + types)
- **Vite** for dashboard builds
- **No frameworks** in dashboard — vanilla TypeScript only
- **Accessibility** — keyboard nav, ARIA labels, responsive design

### Error Boundaries & Logging
- **Python:** Structured logging via `logging` module; all CLI errors propagate to `cli.py` error handlers
- **Server:** `server_security.py` handles rate limiting, request validation, auth
- **Refusal codes:** Standardized refusal reasons in `refusal_codes.py` for deterministic error handling
- **No stack traces in production** unless `--debug` flag set

### Environment Variables
- Store in `.env` (gitignored); use `.env.example` as template
- Validate at startup via `config/` module
- **Never log secrets** — use `***REDACTED***` pattern

---

## 8. PR / Commit Standards

### Branch Naming
```
feature/<short-description>     # New features
fix/<short-description>         # Bug fixes
docs/<short-description>        # Documentation only
refactor/<short-description>    # Code refactoring
test/<short-description>        # Test additions/changes
chore/<short-description>       # Tooling, deps, build
```

### Commit Message Style
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(verdict): add score normalization for edge cases
fix(cli): handle missing config file gracefully
docs(readme): update installation instructions
test(replay): add determinism regression tests
```

### PR Description Template
```markdown
## Summary
Brief description of changes.

## Root Cause (if bug fix)
What caused the issue.

## Files Changed
- `src/truthcore/...` — description
- `tests/...` — description

## Verification Steps
1. Ran `pnpm run verify` → all green
2. Specific test: `pytest tests/test_... -v`
3. Manual test: `truthctl judge --inputs ...`

## Breaking Changes
None / List any API or CLI changes.

## Related Issues
Fixes #XXX
```

---

## 9. Roadmap Hooks (Agent-Ready Backlog)

### 30 Days — Stabilization
1. **Import boundary audit** — Ensure no cross-package imports violating monorepo boundaries
2. **Golden fixture refresh** — Update all `tests/fixtures/golden/*/expected_verdict.json` to current schema
3. **Cache eviction policy** — Verify `cache.py` TTL and size limits work under load
4. **Server rate limiting** — Load test `rate_limit.py` with concurrent connections
5. **Documentation drift** — Audit README examples for accuracy

### 60 Days — Quality Gates
6. **CI parallelization** — Split CI jobs for faster feedback (current: ~15 min)
7. **Determinism regression suite** — Add nightly job replaying 100 historical bundles
8. **SDK publishing** — Automate npm publish for `@truth-core/contract-sdk` on release
9. **Policy pack coverage** — Expand `policy/packs/` with compliance frameworks (SOC2, ISO27001)
10. **Type coverage** — Enforce 100% type coverage in Python (currently inferred)

### 90 Days — Ecosystem
11. **Plugin architecture** — Design public API for custom engines/invariants
12. **Webhook integrations** — Add outgoing webhooks for verdict events
13. **Dashboard real-time** — WebSocket support for live verification updates
14. **Parquet history queries** — SQL interface for historical analysis in `parquet_store.py`
15. **Multi-language SDKs** — PoC for Go/Rust contract SDKs

---

## 10. Quick Reference

| Task | Command |
|------|---------|
| Full verify | `pnpm run verify` |
| Python only | `pnpm run verify:python` |
| TypeScript only | `pnpm run verify:ts` |
| Run CLI | `truthctl --help` |
| Run server | `truthctl serve --port 8080` |
| Build dashboard | `cd dashboard && pnpm run build` |
| Build SDK | `cd packages/ts-contract-sdk && pnpm run build` |
| Run tests | `pnpm run test` |
| Format code | `pnpm run format` |
| CI check | `pnpm run ci` |

---

**Last updated:** 2026-02-05  
**Maintained by:** AI agents + human reviewers  
**Questions?** See `CONTRIBUTING.md` or open an issue.
