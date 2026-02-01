# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0-rc.1] - Launch Candidate - 2026-02-01

### Added
- **Static Dashboard** - Professional offline-capable HTML dashboard
  - Run browser with filtering and sorting
  - Finding tables with severity/category/engine filters
  - SVG charts generated locally (no external dependencies)
  - Dark/light theme support
  - Import/export for runs and snapshots
  - GitHub Pages ready
  - Accessibility features (keyboard nav, screen reader)
- Dashboard CLI commands:
  - `truthctl dashboard build` - Build static dashboard
  - `truthctl dashboard serve` - Serve locally
  - `truthctl dashboard snapshot` - Create portable snapshot
  - `truthctl dashboard demo` - Run demo with sample data
- **Governance & Community**:
  - CONTRIBUTING.md - Development guidelines
  - CODE_OF_CONDUCT.md - Community standards
  - SECURITY.md - Security policy and reporting
  - GOVERNANCE.md - Project governance model
  - Issue templates (bug, feature, security)
  - Pull request template
- **GitHub Actions** - Release automation workflow

### Changed
- README.md - Complete overhaul with dashboard section
- Project status changed from "Beta" to "Production Ready"
- Enhanced documentation with key concepts section

### Security
- Dashboard content sanitization (HTML escaping)
- Path traversal protection in file browser
- Markdown preview sanitization
- CSP-friendly implementation

### Performance
- Deterministic output ordering everywhere
- Streaming reads for large files
- SVG chart optimization

## [Unreleased]

### Added

- **HTTP Server Mode** - New `truthctl serve` command for running Truth Core as a service
  - FastAPI-based REST API with all core commands exposed
  - Interactive HTML GUI for web-based access
  - Automatic API documentation at `/docs` (Swagger UI)
  - Support for file uploads, caching, and multiple workers
  - CORS enabled for cross-origin requests
- Server endpoints:
  - `GET /health` - Health check
  - `GET /api/v1/status` - Server capabilities
  - `POST /api/v1/judge` - Run readiness checks
  - `POST /api/v1/intel` - Run intelligence analysis
  - `POST /api/v1/explain` - Explain invariant rules
  - `GET /api/v1/cache/stats` - Cache statistics
  - `POST /api/v1/cache/clear` - Clear cache
  - `POST /api/v1/impact` - Change impact analysis
- New dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`
- Comprehensive test suite for server endpoints (`tests/test_server.py`)
- Server documentation (`docs/server.md`)

## [0.2.0] - 2024-01-15

### Added
- Content-addressed caching with blake2b/sha256/sha3 hashing
- Parallel engine execution
- Security hardening (path traversal protection, resource limits)
- Run manifests with full provenance
- Evidence bundle signing (Ed25519)
- Bundle verification and replay
- Policy-as-code with built-in packs
- Contract versioning and validation
- Migration system for version upgrades
- Parquet history storage (optional)
- UI geometry reachability checks
- Truth graph construction and querying
- Change impact analysis
- Anomaly scoring (readiness, recon, agent, knowledge)
- TypeScript SDK for consuming artifacts

### Changed
- Improved CLI with subcommands and better help
- Enhanced output formats (JSON, Markdown, CSV)

### Fixed
- Various bug fixes and performance improvements

## [0.1.0] - 2023-12-01

### Added
- Initial release
- Basic readiness checking
- Simple CLI interface
- JSON output format
