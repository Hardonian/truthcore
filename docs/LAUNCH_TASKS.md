# Truth Core Launch Sprint - Task Checklist

**Sprint Goal:** Professional OSS launch with zero warnings, full dashboard, and polished documentation.

**Status:** IN PROGRESS  
**Started:** 2026-01-31  
**Target Completion:** 2026-02-01

---

## Phase 0 - Baseline & Planning ✅

- [x] Run current verification and capture baseline status
- [x] Create LAUNCH_TASKS.md (this file)
- [x] Create Risk List document
- [x] Establish task tracking

**Verification Baseline:**
- Python: 3.13.9
- Current version: 0.2.0
- Status: Clean working tree

---

## Phase 1 - Static Dashboard (Offline, Pages-Ready)

### Dashboard Core Structure
- [ ] Create `dashboard/` directory
- [ ] Set up build system (Vite + vanilla TS)
- [ ] Create dashboard README.md
- [ ] Configure TypeScript
- [ ] Set up build outputs to `dashboard/dist/`

### Dashboard Pages
- [ ] **Run Browser Page**
  - [ ] Load runs from directory structure
  - [ ] List runs with metadata (date, profile, verdict, score, failures)
  - [ ] Sortable/filterable run list
  - [ ] Run selection and navigation

- [ ] **Run Detail Page**
  - [ ] Overview tab (verdict summary + subscores)
  - [ ] Findings tab (filterable table: severity/category/engine/rule)
  - [ ] Invariants tab (pass/fail, explain links)
  - [ ] Policy tab (rules hit, redaction indicators)
  - [ ] Provenance tab (signed/verified status)
  - [ ] Evidence Browser (file list, safe text/markdown preview)

- [ ] **Dashboard Graphs (SVG/Canvas, No External Deps)**
  - [ ] Severity distribution bar chart (SVG)
  - [ ] Trend graph (if history exists)
  - [ ] Engine contributions breakdown (SVG)
  - [ ] Hotspot list (top files/routes with failures)

- [ ] **Import/Export Features**
  - [ ] Import: File picker for runs folder
  - [ ] Export: Create static snapshot (dashboard + embedded JSON)
  - [ ] Snapshot is fully self-contained for hosting

- [ ] **Accessibility & UX Polish**
  - [ ] Keyboard navigation
  - [ ] Local font (no CDN)
  - [ ] Dark/light theme toggle
  - [ ] No layout shifts
  - [ ] Fast load with many runs

---

## Phase 2 - CLI + Dashboard Integration

- [ ] Add `truthctl dashboard build` command
  - [ ] Accept `--runs <dir>` and `--out <dir>`
  - [ ] Build dashboard with embedded run data

- [ ] Add `truthctl dashboard serve` command
  - [ ] Accept `--runs <dir>` and `--port 8787`
  - [ ] Default localhost, warn on 0.0.0.0
  - [ ] Serve dashboard from built files

- [ ] Add `truthctl dashboard snapshot` command
  - [ ] Package runs + dashboard into single folder
  - [ ] No secrets included
  - [ ] Optional evidence manifest

- [ ] Add tests for dashboard commands
  - [ ] Build command smoke test
  - [ ] Serve command smoke test
  - [ ] Snapshot command smoke test

---

## Phase 3 - Codebase Refactor & Cleanup

### Refactor Targets
- [ ] Unify finding models across engines/invariants/policy
- [ ] Unify reporter generation into shared utilities
- [ ] Remove duplicated parsing logic
- [ ] Route all parsing through normalize module

### Architecture Cleanup
- [ ] Create `src/truthcore/arch/` with internal interfaces:
  - [ ] Engine protocol
  - [ ] Reporter protocol
  - [ ] Artifact protocol (read/write/validate/version)
- [ ] Each engine declares:
  - [ ] Artifact types it produces
  - [ ] Required inputs
  - [ ] Deterministic guarantees

### Performance Pass
- [ ] Profile hot paths (parsing/scanning)
- [ ] Streaming reads for large files
- [ ] Consistent limits enforcement

### Security Pass
- [ ] Dashboard HTML content escaping
- [ ] File browsing path traversal prevention
- [ ] Markdown preview sanitization

---

## Phase 4 - OSS Launch Quality

### README Overhaul (Root)
- [ ] Crisp product statement
- [ ] 60-second quickstart
- [ ] Dashboard screenshots (generated from demo)
- [ ] Key concepts: evidence, invariants, policy, provenance, verdict
- [ ] "Integrate in 3 minutes" CI snippet
- [ ] "Run locally" snippet
- [ ] Dashboard section with screenshot
- [ ] Contribution guidelines link

### Governance & Community
- [ ] CONTRIBUTING.md (development, testing, style)
- [ ] CODE_OF_CONDUCT.md
- [ ] SECURITY.md (vulnerability reporting, posture, signing)
- [ ] GOVERNANCE.md (maintainers, versioning policy)
- [ ] LICENSE (confirm MIT)
- [ ] Issue templates (bug report, feature request)
- [ ] PR template

### Documentation
- [ ] Update docs/assets/ with dashboard screenshots
- [ ] Verify all documentation is accurate and current
- [ ] Cross-reference docs with code

---

## Phase 5 - Demo & E2E Verification

- [ ] Add `truthctl demo` command
  - [ ] Run judge on examples
  - [ ] Produce verdict/policy/provenance artifacts
  - [ ] Create runs/<run_id>/ directory
  - [ ] Build dashboard and point to runs
  - [ ] Output: `demo_out/dashboard/index.html`

- [ ] Add tests:
  - [ ] Dashboard build smoke test
  - [ ] Snapshot packaging test
  - [ ] Demo command smoke test

- [ ] Update verify:full script to include:
  - [ ] Python lint/typecheck/test/build
  - [ ] CLI smoke tests
  - [ ] Demo smoke test
  - [ ] Dashboard build smoke

---

## Phase 6 - Final Clean Pass

### Zero Warnings Goal
- [ ] ruff clean (no errors/warnings)
- [ ] pyright clean (no type errors)
- [ ] pytest clean with warnings-as-errors
- [ ] python -m build clean
- [ ] No deprecated APIs (search and replace)
- [ ] Dependencies minimal and pinned

### Documentation Accuracy
- [ ] All docs accurate and current
- [ ] No stale references
- [ ] Examples work as documented

### CHANGELOG
- [ ] Update CHANGELOG.md with "Launch Candidate"
- [ ] Include highlights:
  - [ ] Dashboard
  - [ ] Governance
  - [ ] Security posture
  - [ ] Determinism
  - [ ] Contracts/migrations
  - [ ] Replay/simulation

---

## Verification Checklist (Final)

Before launch, confirm:

- [ ] All tests pass (`pytest -q`)
- [ ] No lint errors (`ruff check .`)
- [ ] No type errors (`pyright src/truthcore`)
- [ ] Build succeeds (`python -m build`)
- [ ] Demo runs successfully (`truthctl demo --out demo_out/`)
- [ ] Dashboard builds (`truthctl dashboard build --runs ...`)
- [ ] No secrets in repo
- [ ] No network calls in tests
- [ ] Deterministic outputs verified
- [ ] Documentation complete

---

## Risk List

See `docs/LAUNCH_RISKS.md` for detailed risk assessment.

High-level risks:
1. Dashboard complexity may exceed time budget
2. Cross-platform build issues (Windows vs Unix)
3. Large file handling in dashboard
4. Security review completeness
5. Documentation drift from code

---

## Progress Tracking

| Phase | Status | Progress |
|-------|--------|----------|
| 0 | ✅ Complete | 100% |
| 1 | 🔄 In Progress | 0% |
| 2 | ⏳ Pending | 0% |
| 3 | ⏳ Pending | 0% |
| 4 | ⏳ Pending | 0% |
| 5 | ⏳ Pending | 0% |
| 6 | ⏳ Pending | 0% |

---

**Last Updated:** 2026-01-31
