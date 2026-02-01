# Server API Example

This example demonstrates how to use the Truth Core HTTP server programmatically via its REST API.

## Prerequisites

```bash
pip install requests
```

## Starting the Server

First, start the Truth Core server:

```bash
# Basic startup
truthctl serve

# With caching enabled
truthctl serve --cache-dir .truthcache

# On a specific port
truthctl serve --port 8080

# Development mode with auto-reload
truthctl serve --reload
```

## Running the Example

Once the server is running on port 8000:

```bash
python server_api_example.py
```

## What It Demonstrates

1. **Health Check** - Verify server is running
2. **Status Check** - Get server capabilities
3. **Run Judge** - Execute readiness check via API
4. **Impact Analysis** - Run change impact analysis
5. **Cache Stats** - Retrieve cache statistics

## API Endpoints Used

- `GET /health` - Health check
- `GET /api/v1/status` - Server status
- `POST /api/v1/judge` - Run readiness check
- `POST /api/v1/impact` - Run impact analysis
- `GET /api/v1/cache/stats` - Get cache statistics

## Web Interface

Visit `http://localhost:8000/` in your browser to use the interactive web GUI.

## API Documentation

Interactive documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
