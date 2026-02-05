# SKILLS.md — Capability Map & Future Work Guide

> **Purpose:** Use this file to route tasks to the right agent/model/tooling based on current repository capabilities and known constraints.

---

## 1. How to Use This File

This document maps Truth Core's current capabilities, skill lanes, and known risks. Use it to:
- **Route tasks** — Match work types to appropriate skill lanes
- **Assess feasibility** — Check "Current Capability Inventory" before committing to features
- **Identify gaps** — Roadmap section highlights missing capabilities to address
- **Avoid pitfalls** — Known risks section documents real issues found in codebase

**Workflow:** Before starting work → Check relevant capability → Review associated risks → Proceed or escalate.

---

## 2. Current Capability Inventory

### Core Verification Engine
| Component | Status | Notes |
|-----------|--------|-------|
| CLI (truthctl) | ✅ Complete | Entry via `src/truthcore/cli.py`; 70K+ lines |
| HTTP Server | ✅ Complete | REST API + web GUI; `server.py` |
| Policy Engine | ✅ Complete | YAML-based policy packs in `policy/packs/` |
| Replay/Simulation | ✅ Complete | Bundle export, replay, simulation with diff |
| Determinism Enforcement | ✅ Complete | All outputs content-addressed |
| Cache System | ✅ Complete | Content-addressed cache with TTL in `cache.py` |
| Rate Limiting | ✅ Complete | `rate_limit.py` for server protection |

### Verification Engines
| Engine | Status | Notes |
|--------|--------|-------|
| Readiness Engine | ✅ Complete | `engines/readiness/` |
| Agent Trace Engine | ✅ Complete | `engines/agent_trace/` |
| Reconciliation Engine | ✅ Complete | `engines/reconciliation/` |
| Knowledge Engine | ✅ Complete | `engines/knowledge/` |

### Content & Contracts
| Component | Status | Notes |
|-----------|--------|-------|
| Verdict Contracts | ✅ Complete | JSON schemas v1.0.0 + v2.0.0 |
| Schema Migrations | ✅ Complete | `migrations/` supports v1→v2 |
| Policy Packs | ✅ Complete | security, privacy, agent, logging, base |
| Golden Fixtures | ✅ Complete | Regression tests in `tests/fixtures/golden/` |

### Frontend / Dashboard
| Component | Status | Notes |
|-----------|--------|-------|
| Static Dashboard | ✅ Complete | Vite + vanilla TypeScript; offline-capable |
| Chart Rendering | ✅ Complete | SVG-based charts, no external CDN |
| Theme Support | ✅ Complete | Dark/light mode with CSS variables |
| Accessibility | ✅ Partial | Keyboard nav present; ARIA labels need audit |

### SDKs & Integration
| Component | Status | Notes |
|-----------|--------|-------|
| TypeScript SDK | ✅ Complete | `@truth-core/contract-sdk` package |
| GitHub Actions | ✅ Complete | `integrations/github-actions/` |
| Python Package | ✅ Complete | pip installable with extras `[dev,parquet]` |

### DevOps & CI/CD
| Component | Status | Notes |
|-----------|--------|-------|
| GitHub Actions CI | ✅ Complete | `ci.yml` — lint, test, typecheck, security |
| Security Scanning | ✅ Complete | CodeQL, pip-audit, gitleaks |
| Coverage Reporting | ✅ Complete | codecov integration (80% threshold) |
| Determinism Tests | ✅ Complete | CI validates identical outputs across runs |

### Data Storage
| Component | Status | Notes |
|-----------|--------|-------|
| Local Filesystem | ✅ Complete | Default connector |
| S3 Connector | ✅ Complete | `connectors/s3.py` |
| Parquet History | ✅ Complete | Optional high-performance storage |
| Content-Addressed Cache | ✅ Complete | `.truthcache/` directory |

---

## 3. Skill Lanes

### 3.1 Policy-as-Code Engineering
**What:** Define and maintain YAML-based policy rules for security, privacy, and compliance.

**Key Locations:**
- `src/truthcore/policy/packs/` — Policy pack definitions
- `src/truthcore/policy/engine.py` — Policy execution logic
- `src/truthcore/invariant_dsl.py` — Invariant rule DSL

**Work Examples:**
- Add new security rule (e.g., detect hardcoded secrets)
- Create compliance pack for SOC2
- Extend invariant DSL with new operators

**Validation:**
- Policy files validate against schema
- Run `truthctl policy run --pack <name>` to test
- Check `tests/test_policy_*.py` for patterns

---

### 3.2 CLI & Server Engineering
**What:** Extend truthctl commands, HTTP API endpoints, or server functionality.

**Key Locations:**
- `src/truthcore/cli.py` — Main CLI (72K lines)
- `src/truthcore/server.py` — HTTP server
- `src/truthcore/server_security.py` — Security middleware
- `src/truthcore/rate_limit.py` — Rate limiting

**Work Examples:**
- Add new subcommand to truthctl
- Extend REST API with new endpoint
- Add server middleware (auth, logging)

**Validation:**
- CLI commands testable via `truthctl <cmd> --help`
- Server test via `truthctl serve` + curl/HTTP client
- Check `tests/test_cli.py`, `tests/test_server.py`

---

### 3.3 Verification Engine Development
**What:** Build new engines or extend existing ones for specialized verification.

**Key Locations:**
- `src/truthcore/engines/` — Engine implementations
- `src/truthcore/verdict/` — Verdict models and aggregation
- `src/truthcore/findings.py` — Finding generation

**Work Examples:**
- Add new engine (e.g., performance benchmarking)
- Extend readiness engine with new checks
- Implement custom verdict aggregation logic

**Validation:**
- Engines produce deterministic outputs
- Add tests in `tests/test_engines_*.py`
- Verify with golden fixtures

---

### 3.4 Dashboard & Frontend
**What:** Build UI components, themes, or visualization for the static dashboard.

**Key Locations:**
- `dashboard/src/` — TypeScript source
- `dashboard/src/main.ts` — Entry point
- `dashboard/src/styles.css` — CSS variables and themes

**Constraints:**
- **No frameworks** — vanilla TypeScript only
- **No external chart libs** — SVG charts only
- **Offline-first** — no CDN dependencies
- **Accessible** — keyboard nav, ARIA labels

**Work Examples:**
- Add new chart type
- Implement theme switching
- Build data table component

**Validation:**
- `cd dashboard && pnpm run build` must succeed
- Verify in browser with `pnpm run dev`
- Check accessibility with keyboard navigation

---

### 3.5 TypeScript SDK Development
**What:** Maintain and extend the `@truth-core/contract-sdk` package.

**Key Locations:**
- `packages/ts-contract-sdk/src/` — SDK source
- `packages/ts-contract-sdk/src/index.ts` — Main exports
- `packages/ts-contract-sdk/src/types.ts` — Type definitions

**Constraints:**
- Must support ESM + CJS + TypeScript
- Zero runtime dependencies
- Strict TypeScript mode

**Work Examples:**
- Add new verdict helpers
- Extend type definitions for v2 contracts
- Add validation utilities

**Validation:**
- `cd packages/ts-contract-sdk && pnpm run build` must succeed
- `pnpm run test` for vitest tests
- Verify both ESM and CJS outputs work

---

### 3.6 CI/CD & DevOps
**What:** Maintain GitHub Actions, build pipelines, and release automation.

**Key Locations:**
- `.github/workflows/ci.yml` — Main CI pipeline
- `.github/workflows/release.yml` — Release automation
- `integrations/github-actions/` — Reusable action

**Work Examples:**
- Optimize CI job parallelization
- Add new security scanning
- Automate SDK publishing on release

**Validation:**
- Test workflow with `act` or on PR branch
- Verify all jobs pass before merge

---

### 3.7 Replay & Simulation
**What:** Work with verification bundles, replay historical runs, simulate changes.

**Key Locations:**
- `src/truthcore/replay/bundle.py` — Bundle export/import
- `src/truthcore/replay/replayer.py` — Replay logic
- `src/truthcore/replay/simulator.py` — Simulation logic
- `src/truthcore/replay/diff.py` — Diff comparison

**Work Examples:**
- Extend bundle format with new metadata
- Add simulation scenario types
- Implement replay regression detection

**Validation:**
- Use example bundle: `examples/replay_bundle/`
- Test commands: `truthctl replay`, `truthctl simulate`
- Determinism test: same bundle → same verdict

---

## 4. "Which Agent for Which Task" Matrix

| Task Type | Recommended Approach | Validation |
|-----------|---------------------|------------|
| **Policy rule addition** | Engineer agent + policy SME | Run `truthctl policy run` with test inputs |
| **CLI bug fix** | Engineer agent | Unit test + integration test + golden fixture |
| **New verification engine** | Engineer agent + architect review | Engine tests + golden fixtures + determinism check |
| **Dashboard UI feature** | Frontend agent | Build passes + manual browser test |
| **SDK type fix** | Engineer agent | Build passes + typecheck + test |
| **CI optimization** | DevOps agent | Workflow dry-run + timing comparison |
| **Documentation update** | Writer agent | Review for accuracy + link check |
| **Security hardening** | Security engineer | Security audit + penetration test |
| **Replay bundle issue** | Engineer agent | Replay determinism test + diff analysis |
| **Performance optimization** | Engineer agent | Benchmark before/after + profile |

---

## 5. Known Risks & Pitfalls

### Risk 1: Schema Version Drift
**Symptom:** Tests pass but golden fixtures use old schema version.

**Likely Cause:**
- Changes to verdict models not reflected in schema files
- Migrations not updated for new fields

**Diagnosis:**
```bash
# Check schema versions
ls src/truthcore/schemas/verdict/

# Validate fixture against schema
python -c "import json; from truthcore.contracts.validate import validate; validate(json.load(open('tests/fixtures/golden/*/expected_verdict.json')))"
```

**Mitigation:**
- Always update schema when changing models
- Run `test_golden_fixtures.py` to validate

---

### Risk 2: Non-Deterministic Output
**Symptom:** Same inputs produce different verdicts across runs.

**Likely Cause:**
- Unsorted dictionary iteration
- Random sampling used
- Non-canonical JSON serialization

**Diagnosis:**
```bash
# Run determinism test
truthctl replay --bundle examples/replay_bundle/bundle --out /tmp/run1
truthctl replay --bundle examples/replay_bundle/bundle --out /tmp/run2
diff /tmp/run1/verdict.json /tmp/run2/verdict.json
```

**Mitigation:**
- Use `json.dumps(..., sort_keys=True)`
- Sort all collections before output
- Never use `random` without fixed seed

---

### Risk 3: Import Boundary Violations
**Symptom:** Cross-package imports causing circular dependencies.

**Likely Cause:**
- Importing from wrong package in monorepo
- Missing `__init__.py` exports

**Diagnosis:**
```bash
# Check imports
ruff check --select I,E,W src/truthcore

# Visualize import graph
pydeps src/truthcore --noshow
```

**Mitigation:**
- Follow monorepo boundaries (src/truthcore, dashboard, packages/)
- Use explicit exports in `__init__.py`

---

### Risk 4: Cache Inconsistency
**Symptom:** Stale cache entries causing wrong results.

**Likely Cause:**
- TTL not configured properly
- Cache key collision
- Manual cache manipulation

**Diagnosis:**
```bash
# Clear cache
truthctl cache-clear

# Check cache stats
truthctl cache-stats
```

**Mitigation:**
- Use content-addressed keys (hashes)
- Configure TTL based on use case
- Never manually edit `.truthcache/`

---

### Risk 5: Server Rate Limit Bypass
**Symptom:** Server overwhelmed by requests; rate limits not enforced.

**Likely Cause:**
- Rate limiter not applied to endpoint
- Configuration mismatch

**Diagnosis:**
```bash
# Check rate limit config
cat src/truthcore/config/defaults/*.py

# Load test
ab -n 1000 -c 10 http://localhost:8080/health
```

**Mitigation:**
- All public endpoints must use `@rate_limit` decorator
- Review `rate_limit.py` for bypass vectors

---

### Risk 6: TypeScript SDK Breaking Changes
**Symptom:** Consumers report type errors after SDK update.

**Likely Cause:**
- Exported type changed without migration path
- Missing backward compatibility layer

**Diagnosis:**
```bash
# Build SDK and check types
cd packages/ts-contract-sdk && pnpm run build && pnpm run typecheck
```

**Mitigation:**
- Follow semantic versioning strictly
- Export compatibility shims for deprecated types
- Test against example consumers

---

## 6. Roadmap

### Next 30 Days — Stabilization
1. ✅ **Import boundary audit** — Ensure clean monorepo boundaries
2. ⏳ **Golden fixture refresh** — Update all fixtures to current schema v2.0.0
3. ⏳ **Cache eviction policy validation** — Load test TTL and size limits
4. ⏳ **Server rate limiting hardening** — Penetration test rate limit bypasses
5. ⏳ **Documentation accuracy audit** — Verify all README examples work

### Next 60 Days — Quality Gates
6. ⏳ **CI parallelization** — Split test jobs for <10 min feedback
7. ⏳ **Determinism regression suite** — Nightly replay of 100 historical bundles
8. ⏳ **SDK auto-publish** — npm publish on GitHub release
9. ⏳ **Policy pack expansion** — SOC2, ISO27001 compliance packs
10. ⏳ **Python type coverage** — Enforce 100% strict coverage

### Next 90 Days — Ecosystem
11. ⏳ **Plugin architecture** — Public API for custom engines
12. ⏳ **Webhook system** — Outgoing webhooks for verdict events
13. ⏳ **Dashboard WebSocket** — Real-time verification updates
14. ⏳ **Parquet SQL interface** — Query historical data with SQL
15. ⏳ **Go/Rust SDK PoC** — Contract SDKs in additional languages

---

## 7. Definition of Done (DoD)

For any work to be considered **ship-ready** in Truth Core:

### Code Quality
- [ ] **Lint passes** — `pnpm run lint` exits 0
- [ ] **Typecheck passes** — `pnpm run typecheck` exits 0
- [ ] **Tests pass** — `pnpm run test` exits 0 (Python ≥80% coverage)
- [ ] **Build succeeds** — `pnpm run build` creates valid outputs
- [ ] **No dead code** — `ruff check` clean for Python, `eslint` clean for TS

### Functional Validation
- [ ] **Determinism verified** — Same inputs produce identical outputs
- [ ] **Golden fixtures updated** — If changing output format
- [ ] **Schema consistency** — Models match schema version
- [ ] **Documentation updated** — README, docs/, CHANGELOG if user-facing

### Integration
- [ ] **Dashboard builds** — `cd dashboard && pnpm run build` succeeds
- [ ] **SDK builds** — `cd packages/ts-contract-sdk && pnpm run build` succeeds
- [ ] **CLI works** — `truthctl --help` and affected commands tested
- [ ] **Server starts** — `truthctl serve` boots without errors

### Security & Safety
- [ ] **No secrets committed** — Checked with gitleaks
- [ ] **No path traversal** — File access uses validated paths
- [ ] **Rate limits applied** — If adding server endpoints
- [ ] **Resource limits** — File size, JSON depth limits configured

### Review
- [ ] **Conventional commits** — Follow `type(scope): description` format
- [ ] **PR description complete** — Root cause, files changed, verification steps
- [ ] **Review approved** — At least one reviewer sign-off

---

**Last updated:** 2026-02-05  
**Maintained by:** AI agents + human reviewers  
**Updates:** Submit PR following conventions in AGENTS.md
