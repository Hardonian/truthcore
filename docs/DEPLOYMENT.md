# Deployment Guide

## Requirements
- Python **3.11+**
- Node.js **18+** (Node 20 recommended)
- `pnpm` **8+**

## Local Development
```bash
# Python deps
pip install -e '.[dev,parquet]'

# Node deps
pnpm install
cd dashboard && pnpm install
cd packages/ts-contract-sdk && pnpm install

# Run CLI
truthctl --help

# Run API server
truthctl serve --port 8080 --reload
```

## Production Deployment
```bash
# Install without dev dependencies
pip install truth-core

# Configure environment
cp .env.example .env
# Edit values to match your environment

# Run API server (example)
TRUTHCORE_API_KEY=... truthctl serve --port 8080
```

## Static Dashboard
```bash
# Build a portable dashboard bundle
truthctl dashboard build --runs ./results --out ./dashboard-dist

# Serve locally for quick inspection
truthctl dashboard serve --runs ./results --port 8787
```

## Environment Variables
See `.env.example` for the full list. The most important are:
- `TRUTHCORE_API_KEY` (enable API authentication)
- `TRUTHCORE_CACHE_DIR`, `TRUTHCORE_CACHE_ENABLED`
- `TRUTHCORE_CORS_ORIGINS`
- `TRUTHCORE_RATE_LIMIT_MAX`, `TRUTHCORE_RATE_LIMIT_WINDOW`
- `TRUTHCORE_SIGNING_PRIVATE_KEY` / `TRUTHCORE_SIGNING_PUBLIC_KEY`

## Health Check
```bash
curl -s http://localhost:8080/health | jq
```
