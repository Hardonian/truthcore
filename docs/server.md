# Truth Core Server

The Truth Core server provides a REST API and web interface for running verification commands remotely.

## Quick Start

```bash
# Start the server
truthctl serve

# Start on custom port
truthctl serve --port 8080

# Start with cache enabled
truthctl serve --cache-dir ./cache

# Development mode with auto-reload
truthctl serve --reload
```

## API Endpoints

### Health & Status

- `GET /health` - Health check
- `GET /api/v1/status` - Server capabilities and configuration

### Core Commands

- `POST /api/v1/judge` - Run readiness check
- `POST /api/v1/intel` - Run intelligence analysis
- `POST /api/v1/explain` - Explain invariant rules

### Cache Management

- `GET /api/v1/cache/stats` - Get cache statistics
- `POST /api/v1/cache/clear` - Clear all cache entries

### Change Analysis

- `POST /api/v1/impact` - Run change impact analysis

## Web Interface

The server provides an HTML GUI at the root path (`/`). Features include:

- **Dashboard** - View server status and quick actions
- **Judge** - Run readiness checks with file uploads
- **Intel** - Run intelligence analysis on historical data
- **API** - Browse available endpoints

## Configuration

### Command Line Options

```
--host, -h        Host to bind to (default: 127.0.0.1)
--port, -p        Port to listen on (default: 8000)
--cache-dir       Enable caching with specified directory
--static-dir      Serve custom static files
--reload          Enable auto-reload for development
--workers, -w     Number of worker processes
--debug           Enable debug mode
```

### Environment Variables

- `TRUTHCORE_CACHE_DIR` - Default cache directory
- `TRUTHCORE_DEBUG` - Enable debug mode
- `TRUTHCORE_RATE_LIMIT_MAX_CLIENTS` - Max tracked clients in rate limit storage (default: 5000)

## Usage Examples

### Running Readiness Check via API

```bash
# Using curl
curl -X POST http://localhost:8000/api/v1/judge \
  -H "Content-Type: application/json" \
  -d '{"profile": "ui", "parallel": true}'
```

```python
# Using Python requests
import requests

response = requests.post(
    "http://localhost:8000/api/v1/judge",
    json={"profile": "ui", "parallel": True}
)
results = response.json()
```

### Running with File Upload

```bash
# Create a ZIP with inputs
zip -r inputs.zip ./test-outputs/

# Upload and run
curl -X POST http://localhost:8000/api/v1/judge \
  -F "profile=ui" \
  -F "inputs=@inputs.zip"
```

### Running Intelligence Analysis

```bash
curl -X POST http://localhost:8000/api/v1/intel \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "readiness",
    "compact": false,
    "retention_days": 90
  }'
```

### Explaining Invariant Rules

The explain endpoint requires a structured payload with a ruleset and rule ID.

```bash
curl -X POST http://localhost:8000/api/v1/explain \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "UI_BUTTON_VISIBLE",
    "data": {"button_text": "Save"},
    "ruleset": {
      "rules": [
        {"id": "UI_BUTTON_VISIBLE", "when": "button_text == \"Save\""}
      ]
    }
  }'
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e ".[dev,parquet]"

EXPOSE 8000

CMD ["truthctl", "serve", "--host", "0.0.0.0"]
```

### Production Settings

```bash
# Run with multiple workers
truthctl serve --host 0.0.0.0 --workers 4

# With cache and static files
truthctl serve \
  --cache-dir /var/cache/truthcore \
  --static-dir /var/www/truthcore \
  --workers 4
```

## Authentication (Future)

The current server does not implement authentication. For production use:

1. Use a reverse proxy (nginx, traefik) with authentication
2. Deploy behind a VPN or private network
3. Use API keys (planned for future release)

## API Documentation

Interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI Schema: `http://localhost:8000/openapi.json`

## Troubleshooting

### Port Already in Use

```bash
# Use a different port
truthctl serve --port 8080
```

### Cache Not Working

Ensure the cache directory exists and is writable:

```bash
mkdir -p ./cache
truthctl serve --cache-dir ./cache
```

### Import Errors

If you see import errors for server dependencies:

```bash
pip install "truth-core[server]"
```

## Security Considerations

- The server runs with the same permissions as the user who started it
- File uploads are extracted to temporary directories
- CORS is enabled for all origins by default (configure in production)
- No authentication is implemented (use reverse proxy)

## Performance

- Requests are processed synchronously
- Cache hits avoid recomputation
- File uploads are processed in memory then extracted
- Use `--workers` for concurrent request handling
