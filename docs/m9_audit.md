# M9 Baseline Audit Report

**Date:** 2026-02-01  
**Version:** 0.2.0  
**Status:** In Progress

## Summary

This document records the baseline state of the truth-core repository at the start of M9 (End-to-End Resilience + Hardening + Zero-Warnings + Repo Polish).

---

## Baseline Test Results

### Pytest Results
- **Passed:** 120 tests
- **Failed:** 7 tests
- **Status:** FAILING

### Failed Tests

1. **test_policy.py::TestPolicyPackLoader::test_load_built_in_base**
   - Issue: `SecurityError: Text content too long: src\truthcore\policy\packs\base.yaml (2022 chars)`
   - Location: `src/truthcore/security.py:125`
   - **Root Cause:** DEFAULT_MAX_STRING_LENGTH (10MB) not being applied correctly in conditional

2. **test_provenance.py::TestEvidenceManifest::test_security_limits**
   - Issue: Expected SecurityError for 200MB file, but no error raised
   - **Root Cause:** File reading not using security limits in EvidenceManifest

3. **test_provenance.py::TestBundleVerifier::test_verify_with_signature**
   - Issue: `assert None is True` for `result.signature_valid`
   - **Root Cause:** Signature verification returning None instead of boolean

4. **test_provenance.py::TestBundleVerifier::test_signature_tampering**
   - Issue: `assert None is False` for `result.signature_valid`
   - **Root Cause:** Signature verification returning None instead of boolean

5. **test_provenance.py::TestVerificationResult::test_markdown_output**
   - Issue: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d`
   - **Root Cause:** Markdown file not using UTF-8 encoding for emoji characters

6. **test_upgrades.py::TestInvariantDSL::test_simple_rule_evaluation**
   - Issue: `assert False is True`
   - **Root Cause:** Rule evaluation logic not working correctly

7. **test_upgrades.py::TestInvariantDSL::test_all_composition**
   - Issue: `assert False is True`
   - **Root Cause:** All composition logic not working correctly

### Lint Results (ruff check .)

**Status:** VIOLATIONS FOUND in scripts/

1. **W291** Trailing whitespace (scripts/check_contract_versions.py:6)
2. **F401** Unused import `json` (scripts/check_contract_versions.py:19)
3. **W293** Blank line contains whitespace (multiple occurrences)

**src/truthcore/** status: Clean (no violations)

### Type Check Results

**Status:** pyright not installed - unable to verify
- Missing type checking tool
- pyproject.toml configured for pyright but not in PATH

### Build Results

**Status:** FAIL
- `python -m build` failed: No module named 'build'
- Build tool not installed

### CLI Commands Tested

**truthctl --help**: PASS  
Available commands:
- bundle, cache-clear, cache-compact, cache-stats, explain
- generate-keys, graph, graph-query, index, intel, judge
- plan, policy-explain, policy-list, policy-run, recon
- replay, simulate, trace, verdict, verify-bundle

**Missing commands:**
- `doctor` - Not implemented (needs to be added in M9)

---

## Code Quality Issues

### Version Inconsistency
- `src/truthcore/__init__.py`: 0.1.0
- `pyproject.toml`: 0.2.0
- **Action:** Align versions to 0.2.0

### Security Issues

1. **Conditional Logic Bug in safe_read_text()**
   ```python
   if len(text) > limits.max_string_length if limits else DEFAULT_MAX_STRING_LENGTH:
   ```
   This logic is incorrect - it evaluates `limits.max_string_length if limits` as the condition.

2. **Missing Input Validation**
   - File size limits not enforced consistently
   - Path traversal checks present but not comprehensive

3. **Error Handling**
   - Some errors show raw tracebacks instead of structured output
   - JSON output mode needs better error structure

### Test Coverage Gaps

- Security limit enforcement not fully tested
- Signature verification tests failing
- Encoding issues on Windows

---

## Required M9 Fixes

### Phase 1: Zero-Warnings
1. Fix all ruff violations in scripts/
2. Install and run pyright type checking
3. Install build tool and verify package builds
4. Fix version inconsistency

### Phase 2: E2E Resilience
1. Fix security.py conditional logic bug
2. Fix signature verification to return booleans
3. Fix markdown encoding to use UTF-8
4. Add doctor command
5. Add safe mode flag
6. Improve error handling with structured output

### Phase 3: Security Hardening
1. Add SBOM generation
2. Add bandit/ruff security rules
3. Verify bundle signing and verification
4. Add path traversal defense tests

### Phase 4: Performance
1. Add timing/profiling hooks
2. Optimize caching
3. Verify determinism

### Phase 5: Professionalization
1. Rewrite README
2. Clean up docs
3. Add demo command
4. Add examples polish

### Phase 6: Final Verification
1. Create verify:full script
2. Update CI to zero-warnings
3. Update CHANGELOG

---

## M9 Success Criteria

- [ ] Zero ruff violations (src/ and scripts/)
- [ ] Zero type check errors
- [ ] All tests passing (0 failures)
- [ ] Package builds successfully
- [ ] CLI doctor command works
- [ ] verify:full script runs clean
- [ ] No deprecated dependencies
- [ ] No TODOs in code
- [ ] Professional README
- [ ] Clean docs index

---

## Progress Tracking

| Phase | Status | Completion |
|-------|--------|------------|
| 0 - Baseline | COMPLETE | 100% |
| 1 - Zero-Warnings | IN PROGRESS | 0% |
| 2 - Resilience | PENDING | 0% |
| 3 - Security | PENDING | 0% |
| 4 - Performance | PENDING | 0% |
| 5 - Professionalization | PENDING | 0% |
| 6 - Final Verification | PENDING | 0% |

---

*Last updated: 2026-02-01*
