# Governance

## Overview

This document describes the governance model for Truth Core, an open-source
deterministic verification framework.

## Project Roles

### Maintainers

Current maintainers:

- **[@maintainer1]** - Project Lead, Core Architecture
- **[@maintainer2]** - CLI & Integrations
- **[@maintainer3]** - Dashboard & UI

Maintainers have commit access and are responsible for:
- Reviewing and merging PRs
- Managing releases
- Setting project direction
- Enforcing code of conduct

### Contributors

Anyone who contributes code, documentation, or other improvements.
Contributors are recognized in:
- Git commit history
- Release notes
- CONTRIBUTORS file (generated)

### Community Members

Users who participate in discussions, report issues, or help others.

## Decision Making

### Day-to-Day Decisions

Made by maintainers through:
- PR reviews
- Issue triage
- Direct commits for minor fixes

### Significant Changes

Require discussion and consensus:
- New major features
- Breaking changes
- Architectural changes
- Policy changes

Process:
1. Open a GitHub Discussion or RFC issue
2. Allow at least 1 week for community input
3. Maintainers make final decision
4. Document decision in ADR (Architecture Decision Record)

### Breaking Changes

Breaking changes require:
- Minor version bump minimum
- Migration guide in UPGRADE_NOTES.md
- Deprecation period where possible
- Approval from 2+ maintainers

## Versioning Policy

We follow [Semantic Versioning 2.0](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Schedule

- **Patch releases**: As needed for bugs/security
- **Minor releases**: Monthly (feature accumulation)
- **Major releases**: Annually or for breaking changes

### Deprecation Policy

Features are deprecated in release N and removed in release N+1:

1. Mark as deprecated with warning
2. Document in CHANGELOG.md
3. Provide migration path
4. Remove in next major version

## Commit Access

### Obtaining Commit Access

Contributors may be granted commit access after:
- Multiple quality PRs merged
- Understanding of project direction
- Agreement to follow guidelines

### Commit Guidelines

With great power comes great responsibility:
- Use PRs for significant changes
- Squash minor fixes
- Never force-push to main
- Maintain green CI

## Community Participation

### Communication Channels

- **GitHub Issues**: Bug reports, features
- **GitHub Discussions**: Questions, ideas
- **Pull Requests**: Code contributions

### Meeting Notes

Major decisions are documented in:
- ADRs in `docs/architecture/`
- Meeting notes in `docs/meetings/`
- RFCs in GitHub Discussions

## Conflict Resolution

If disagreements arise:

1. Discuss in PR/issue with respectful dialogue
2. Escalate to maintainers if needed
3. Maintainers make binding decision
4. Document rationale

## Licensing

All contributions are licensed under the MIT License.
See [LICENSE](LICENSE) for full text.

## Changes to Governance

Changes to this document require:
- PR with rationale
- 2-week review period
- Approval from 2/3 of maintainers

---

**Last updated**: 2026-01-31
