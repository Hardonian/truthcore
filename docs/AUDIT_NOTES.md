# Truth Core Repository Audit Notes

**Date**: 2026-02-03  
**Auditor**: Kimi (Principal Engineer + Security/QA Lead)  
**Scope**: Full repo hardening for ship-ready OSS

---

## Executive Summary

This is a **mixed Python + TypeScript monorepo** for the Truth Core deterministic verification framework. While the codebase shows good architectural decisions and has working CI, it requires significant hardening to meet OSS production standards.

**Current State**: Beta-quality with ≥1299 lint errors, test failures, missing TypeScript CI coverage, and repo hygiene issues.

**Target State**: Zero-warning, zero-error, fully-tested, security-hardened, merge-blocking CI.

---

## Phase 0 Findings

### 1. Repository Structure

```
truthcore/
├── src/truthcore/           # Python main package (70K+ lines CLI)
├── tests/                  # Python tests (pytest)
├── dashboard/             # Vite + TypeScript frontend
├── packages/
│   └── ts-contract-sdk/    # TypeScript SDK (Vitest, ESLint, tsup)
├── docs/                   # Documentation
├── examples/              # Example bundles
├── scripts/               # Build/utility scripts
├── pyproject.toml         # Python config (hatchling)
└── .github/workflows/     # CI configuration
```

**Package Manager Situation**: 
- Root: No package.json (Python-only at root)
- Dashboard: npm with package-lock.json
- TS SDK: npm with package-lock.json
- **Problem**: No unified package management, no pnpm workspace

### 2. Python Codebase Analysis

**Framework**: Python 3.11+ with FastAPI, Pydantic v2, Click, Rich, Structlog

**Key Modules**:
- `cli.py` (70KB): Main CLI interface - **high risk** (long lines, complexity)
- `server.py` (26KB): FastAPI server - **security critical**
- `verdict/`, `engines/`, `invariants/`: Core logic
- `replay/`, `spine/`: Replay/simulation system

**Linting (ruff)**: 
- **1299+ errors** (whitespace, line length, unused vars, missing docstrings)
- `cli.py` alone has 100+ line length violations
- `cache.py` has trailing whitespace throughout

**Type Checking (pyright)**:
- Many `Unknown` type errors in `anomaly_scoring.py`
- Missing type arguments for generic classes
- `reportUnknownParameterType` errors

**Tests**:
- Import failures in `test_replay.py` (cannot import `SeverityLevel`)
- Missing `fastapi` dependency causes `test_server.py` to fail
- 339 tests collected but 2 collection errors

### 3. TypeScript SDK Analysis

**Package**: `@truth-core/contract-sdk`

**Current State**:
- ✅ ESLint passes (0 errors)
- ✅ Typecheck passes
- ✅ Tests pass (39 tests, Vitest)
- ❌ No formatting tool (Prettier/Biome)
- ❌ No format script in package.json

**Tech Stack**:
- TypeScript 5.3, tsup (build), Vitest (test), ESLint (lint)
- Outputs: ESM + CJS with declarations
- Exports: `index`, `types`, `helpers`

### 4. Dashboard Analysis

**Package**: `truthcore-dashboard`

**Current State**:
- ❌ No linting (ESLint not configured)
- ❌ No testing (no test runner)
- ❌ No formatting (no Prettier/Biome)
- ❌ No typecheck script
- Only has: `dev`, `build`, `preview`

**Tech Stack**:
- Vite 5.0, TypeScript 5.3
- Vanilla TypeScript (no framework)
- Single-file architecture (`main.ts` is 20KB)

### 5. CI/CD Analysis

**File**: `.github/workflows/ci.yml`

**Strengths**:
- Matrix testing (Python 3.11, 3.12, 3.13)
- Multi-stage pipeline (test → replay → integration → build)
- Coverage reporting
- Determinism tests

**Weaknesses**:
- **No TypeScript CI coverage** (SDK and Dashboard not tested)
- `pyright` runs with `|| true` (ignores failures)
- No dependency auditing
- No security scanning
- No lint enforcement (ruff runs but may not block)
- Uses deprecated `codecov-action@v3`

### 6. Security & Risk Inventory

**High Priority**:
1. **No security scanning**: No CodeQL, no dependency audit in CI
2. **No secret scanning**: `.env` gitignored but no gitleaks/pre-commit
3. **FastAPI server**: No security headers middleware visible
4. **CLI arguments**: No validation/sanitization audit performed

**Medium Priority**:
1. **node_modules in git**: Present in dashboard/ and packages/ts-contract-sdk/
2. **No security.md**: Has placeholder but lacks threat model
3. **No input validation audit**: Zod/schemas used but coverage unknown

**Low Priority**:
1. **No health check endpoint**: For server deployments
2. **No error boundaries**: Dashboard lacks error handling

### 7. Configuration Issues

**pyproject.toml**:
- ruff config ignores D100, D104, D107 (module/package docstrings)
- pyright uses `typeCheckingMode: "basic"` (not strict)
- Missing: pytest timeout, coverage thresholds

**TypeScript configs**:
- SDK: Good strictness (`strict: true`)
- Dashboard: Good strictness but no `noImplicitReturns`
- Neither has `noUncheckedIndexedAccess`

**.gitignore**:
- Missing `node_modules/` (explains why node_modules are in git)
- Missing `dist/` for TypeScript builds

---

## Required Fixes by Phase

### Phase 1: Single Source of Truth Commands

**Missing**:
- Root `verify` script that runs all checks
- Dashboard: `lint`, `typecheck`, `test`, `format`
- TS SDK: `format` script
- No pnpm workspace configuration

**Action**: Create unified command structure with pnpm workspace or npm scripts at root.

### Phase 2: TypeScript Hardening

**Python**:
- Fix 1299+ ruff errors (line lengths, whitespace, unused vars)
- Fix pyright errors (Unknown types)
- Add stricter pyright config (`strict` mode for type checking)

**TypeScript**:
- SDK: Add `noUncheckedIndexedAccess` to tsconfig
- Dashboard: Add full ESLint + typecheck setup

### Phase 3: ESLint + Formatting

**Required**:
- Dashboard: ESLint + Prettier setup
- TS SDK: Add Prettier
- Python: ruff format (already configured but not enforced)

**Rules to Add**:
- `@typescript-eslint/no-floating-promises`
- `@typescript-eslint/consistent-type-imports`
- `unused-imports/no-unused-imports`

### Phase 4: Testing

**Python**:
- Fix import errors in test_replay.py
- Fix missing fastapi dependency
- Add test coverage thresholds

**Dashboard**:
- Add Vitest or Playwright
- Add smoke tests for critical paths

### Phase 5: Security Hardening

**Required**:
- Add CodeQL workflow
- Add dependency audit step to CI
- Add gitleaks or similar for secret scanning
- Audit FastAPI security headers
- Create SECURITY.md with threat model

### Phase 6: Runtime Resilience

**Required**:
- Add health check endpoint to server
- Add error boundaries to dashboard
- Standardize error responses

### Phase 7: CI/CD Hardening

**Required**:
- Add TypeScript CI jobs (SDK + Dashboard)
- Remove `|| true` from pyright
- Update codecov-action to v4
- Add merge-blocking gates
- Add caching for pip/npm

### Phase 8: Repo Polish

**Required**:
- Fix .gitignore (add node_modules/, dist/)
- Remove node_modules from git
- Add .editorconfig
- Add CONTRIBUTING.md updates
- Add pre-commit hooks (optional)

---

## Files to Modify (Full List)

### Critical Path
1. `.gitignore` - Add node_modules/, dist/
2. `pyproject.toml` - Stricter ruff/pyright, fix deps
3. `package.json` (root) - Create with verify script
4. `pnpm-workspace.yaml` - Create for monorepo
5. `.github/workflows/ci.yml` - Full overhaul
6. `.github/workflows/codeql.yml` - Create
7. `.github/dependabot.yml` - Create

### Python Fixes
8. `src/truthcore/cli.py` - Fix line lengths, whitespace
9. `src/truthcore/cache.py` - Fix whitespace, unused vars
10. `src/truthcore/anomaly_scoring.py` - Fix type errors
11. `tests/test_replay.py` - Fix imports
12. `src/truthcore/replay/simulator.py` - Fix imports
13. `src/truthcore/verdict/models.py` - Ensure exports

### TypeScript SDK
14. `packages/ts-contract-sdk/package.json` - Add format script
15. `packages/ts-contract-sdk/.prettierrc` - Create
16. `packages/ts-contract-sdk/tsconfig.json` - Add strictness

### Dashboard
17. `dashboard/package.json` - Add lint, test, format scripts
18. `dashboard/.eslintrc.cjs` - Create
19. `dashboard/.prettierrc` - Create
20. `dashboard/vitest.config.ts` - Create
21. `dashboard/tsconfig.json` - Add strictness

### Documentation
22. `docs/AUDIT_NOTES.md` - This file
23. `docs/SECURITY.md` - Create detailed version
24. `docs/TESTING.md` - Create
25. `CONTRIBUTING.md` - Update

---

## Success Criteria

When complete, the following must pass:

```bash
# Python
ruff check src/truthcore tests  # 0 errors
pyright src/truthcore           # 0 errors
pytest tests/                   # All pass

# TypeScript SDK
cd packages/ts-contract-sdk
npm run lint                    # 0 errors/warnings
npm run typecheck               # 0 errors
npm run test                    # All pass
npm run format:check            # 0 issues

# Dashboard
cd dashboard
npm run lint                    # 0 errors
npm run typecheck               # 0 errors
npm run test                    # All pass
npm run format:check            # 0 issues

# Root
pnpm verify                     # All gates pass
```

---

## Estimated Effort

- **Phase 0** (Audit): ✅ Complete
- **Phase 1** (Commands): 30 min
- **Phase 2** (TypeScript): 2 hours (mostly Python fixes)
- **Phase 3** (Lint/Format): 1 hour
- **Phase 4** (Testing): 30 min (mostly fixes)
- **Phase 5** (Security): 1 hour
- **Phase 6** (Resilience): 30 min
- **Phase 7** (CI/CD): 1 hour
- **Phase 8** (Polish): 30 min

**Total**: ~7 hours of focused work

---

## Risk Assessment

**Low Risk**: Formatting changes, config updates, CI additions  
**Medium Risk**: Fixing Python imports (may change API surface)  
**High Risk**: None - changes are additive or cosmetic

**Rollback Strategy**: All changes are in version control; can revert any commit.

---

## Next Steps

1. Start with `.gitignore` and node_modules cleanup
2. Fix Python import/test failures (blockers)
3. Add root package.json with verify script
4. Fix ruff errors systematically
5. Update CI with TypeScript coverage
6. Add security scanning
7. Final verification
