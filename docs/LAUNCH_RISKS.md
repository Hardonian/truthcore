# Launch Risk Assessment

**Document Purpose:** Identify and mitigate risks that could impact the Truth Core OSS launch timeline or quality.

**Created:** 2026-01-31  
**Review Cycle:** Daily during launch sprint

---

## Risk Register

### R1: Dashboard Scope Creep
**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Timeline slip, incomplete features

**Description:** The static dashboard has many requirements (charts, tables, import/export, accessibility). Risk of not completing all features in time.

**Mitigation:**
- Prioritize core features (run browser, findings table, basic SVG charts)
- Defer advanced features (complex animations, real-time updates)
- Use simple, proven tech (vanilla TS + Vite)
- Implement MVP first, polish second

**Owner:** Principal Engineer  
**Status:** MONITORING

---

### R2: Cross-Platform Build Issues
**Severity:** MEDIUM  
**Probability:** MEDIUM  
**Impact:** CI failures, contributor friction

**Description:** Windows path handling, line endings, and file permissions differ from Unix. Dashboard build may behave differently.

**Mitigation:**
- Use pathlib consistently in Python
- Configure .gitattributes for line endings
- Test dashboard build on both Windows and Unix
- Use forward slashes in URLs/paths internally

**Owner:** DevOps Lead  
**Status:** MONITORING

---

### R3: File Size/Performance Issues
**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** Dashboard unusable with many runs

**Description:** Loading thousands of runs with large JSON files could slow dashboard or cause memory issues.

**Mitigation:**
- Implement pagination in run browser
- Lazy load run details
- Streaming reads for large files
- Set reasonable limits (max 1000 runs displayed)
- Virtual scrolling for long tables

**Owner:** Performance Lead  
**Status:** MONITORING

---

### R4: Security Vulnerabilities
**Severity:** HIGH  
**Probability:** LOW  
**Impact:** Reputational damage, security issues

**Description:** Dashboard may introduce XSS, path traversal, or other security issues if not properly sanitized.

**Mitigation:**
- HTML escape all dynamic content
- Path traversal validation for file browser
- CSP headers for dashboard
- Markdown sanitization
- Security review checklist
- Third-party audit if time permits

**Owner:** Security Lead  
**Status:** MONITORING

---

### R5: Documentation Drift
**Severity:** MEDIUM  
**Probability:** HIGH  
**Impact:** Confused users, support burden

**Description:** As code changes rapidly during sprint, documentation may become stale or inaccurate.

**Mitigation:**
- Update docs immediately when code changes
- Use doc-driven development for public APIs
- Include documentation in PR review checklist
- Verify all examples work before launch
- Add documentation smoke tests

**Owner:** Tech Writer  
**Status:** MONITORING

---

### R6: Dependency Vulnerabilities
**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** Security alerts post-launch

**Description:** Dependencies may have known vulnerabilities that could block launch or require urgent patches.

**Mitigation:**
- Run `pip-audit` or similar before launch
- Pin all dependencies
- Use only well-maintained packages
- Have upgrade path documented
- Monitor CVE databases

**Owner:** Security Lead  
**Status:** MONITORING

---

### R7: Determinism Regression
**Severity:** HIGH  
**Probability:** LOW  
**Impact:** Core value proposition compromised

**Description:** Changes during refactoring could accidentally introduce non-deterministic behavior (timestamps, ordering, randomness).

**Mitigation:**
- Run determinism tests before each commit
- Verify stable JSON ordering
- Check no uuid4 or random calls
- Validate timestamp normalization
- Add regression tests

**Owner:** Principal Engineer  
**Status:** MONITORING

---

### R8: Test Flakiness
**Severity:** MEDIUM  
**Probability:** MEDIUM  
**Impact:** CI failures, false positives

**Description:** New dashboard tests or refactored tests may be flaky due to timing, file system, or ordering issues.

**Mitigation:**
- Mock file system where possible
- Use temporary directories with cleanup
- Avoid time-based assertions
- Run tests multiple times to verify stability
- Separate unit and integration tests

**Owner:** QA Lead  
**Status:** MONITORING

---

### R9: License Compliance
**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** Legal issues, license violation

**Description:** Dashboard dependencies or fonts may have incompatible licenses.

**Mitigation:**
- Use only MIT/Apache/BSD licensed deps
- No GPL dependencies in distributed code
- Include license headers where required
- Generate license attribution file
- Review font licenses

**Owner:** Legal/OSS Lead  
**Status:** MONITORING

---

### R10: GitHub Pages Compatibility
**Severity:** LOW  
**Probability:** MEDIUM  
**Impact:** Dashboard won't deploy to Pages

**Description:** GitHub Pages has limitations (no server-side, Jekyll processing, base URL issues).

**Mitigation:**
- Use relative paths in dashboard
- No underscore-prefixed dirs (Jekyll)
- Test with `gh-pages` branch locally
- Verify base URL handling
- SPA routing with hash-based URLs

**Owner:** DevOps Lead  
**Status:** MONITORING

---

## Risk Matrix

| Risk | Severity | Probability | Score | Priority |
|------|----------|-------------|-------|----------|
| R1 Dashboard Scope | HIGH | MEDIUM | 6 | P1 |
| R4 Security | HIGH | LOW | 4 | P2 |
| R7 Determinism | HIGH | LOW | 4 | P2 |
| R5 Documentation | MEDIUM | HIGH | 6 | P1 |
| R2 Cross-Platform | MEDIUM | MEDIUM | 4 | P2 |
| R3 Performance | MEDIUM | LOW | 2 | P3 |
| R6 Dependencies | MEDIUM | LOW | 2 | P3 |
| R8 Test Flakiness | MEDIUM | MEDIUM | 4 | P2 |
| R9 License | MEDIUM | LOW | 2 | P3 |
| R10 Pages | LOW | MEDIUM | 2 | P3 |

*Score = Severity × Probability (High=3, Medium=2, Low=1)*

---

## Daily Risk Review Questions

1. Have any new risks emerged today?
2. Are mitigation strategies working?
3. Have any risks been resolved?
4. Do we need to escalate any risks?
5. Is the dashboard scope still manageable?

---

**Next Review:** Daily at standup
