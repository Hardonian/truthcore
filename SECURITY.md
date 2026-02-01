# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability,
please report it responsibly:

**Please do NOT:**
- Open public issues for security bugs
- Discuss vulnerabilities in public forums

**Please DO:**
- Email security reports to: [security@truthcore.example.com]
- Include detailed reproduction steps
- Allow time for response before public disclosure

## Response Process

1. **Acknowledgment**: Within 48 hours
2. **Assessment**: Within 1 week
3. **Fix Development**: Timeline based on severity
4. **Release**: Coordinated disclosure with reporter
5. **Recognition**: Public acknowledgment (with permission)

## Security Features

Truth Core implements defense in depth:

### Evidence Integrity
- Content-addressed storage (BLAKE2b, SHA256, SHA3)
- Ed25519 signatures for evidence bundles
- Tamper-evident manifests

### Input Validation
- Path traversal protection
- JSON depth limits
- File size limits
- Safe archive extraction

### Output Sanitization
- Markdown sanitization
- HTML escaping in reports
- Safe file preview

### Determinism
- No random or time-based behavior
- Stable sorting and ordering
- Reproducible outputs

## Best Practices for Users

1. **Signing Keys**: Keep private keys secure
2. **Verification**: Always verify signatures on published evidence
3. **Dependencies**: Pin dependencies in production
4. **Updates**: Keep up with security updates

## Security Checklist for Deployments

- [ ] Signing keys generated securely
- [ ] Private keys stored in environment/secrets manager
- [ ] Verification enabled for evidence bundles
- [ ] Resource limits configured appropriately
- [ ] Audit logging enabled
- [ ] Dependencies scanned for vulnerabilities

## Audit Logging

Enable comprehensive logging:

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
```

## Compliance

Truth Core helps with:
- **SOC 2**: Evidence integrity and audit trails
- **ISO 27001**: Security policy enforcement
- **GDPR**: Data processing verification

## Vulnerability History

| CVE / Issue | Version | Description | Fixed |
|-------------|---------|-------------|-------|
| None yet    | -       | -           | -     |

---

**Last updated**: 2026-01-31
