# Security Notes

## Threat Model (Summary)
Truth Core processes untrusted inputs (codebases, bundles, replay artifacts). Primary risks:
- Path traversal and unsafe archive extraction
- Resource exhaustion (large uploads, deep JSON)
- Unauthorized access to API endpoints
- Tampering with evidence artifacts

## Controls Implemented
- **Path traversal protection** for all file access and archive extraction.
- **Resource limits** on file sizes, JSON depth, and JSON size.
- **API key authentication** when `TRUTHCORE_API_KEY` is configured.
- **Rate limiting** per client to prevent abuse.
- **Signed evidence** with Ed25519 when keys are configured.
- **Standardized error envelopes** to avoid stack trace leaks in production.

## Operational Guidance
- Always set `TRUTHCORE_API_KEY` in production environments.
- Limit CORS to trusted origins (`TRUTHCORE_CORS_ORIGINS`).
- Use a reverse proxy (nginx/Traefik) with TLS termination for public deployments.
- Store signing keys in a secret manager, not on disk.

## Webhooks
No webhook endpoints are exposed by default. If webhooks are added, they must:
- Verify signatures against a known secret.
- Use raw body verification and reject replayed event IDs.
- Enforce strict JSON schema validation.

## Reporting Vulnerabilities
Please see `SECURITY.md` in the repository root for the official reporting process.
