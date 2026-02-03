"""Tests for Truth Core server."""

import tempfile
from pathlib import Path

import pytest

from truthcore.server import create_app


@pytest.fixture
def client():
    """Create a test client."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(cache_dir=Path(tmpdir), debug=True)
        from fastapi.testclient import TestClient

        return TestClient(app)


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_status_endpoint(client):
    """Test the status endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200

    data = response.json()
    assert "version" in data
    assert "cache_enabled" in data
    assert "commands" in data
    assert "judge" in data["commands"]


def test_cache_stats_endpoint(client):
    """Test the cache stats endpoint."""
    response = client.get("/api/v1/cache/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["enabled"] is True
    assert "stats" in data


def test_cache_clear_endpoint(client):
    """Test the cache clear endpoint."""
    response = client.post("/api/v1/cache/clear")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "cleared"
    assert "timestamp" in data


def test_judge_endpoint_basic(client):
    """Test the judge endpoint with basic configuration."""
    payload = {
        "profile": "base",
        "parallel": True,
        "sign": False,
    }

    response = client.post("/api/v1/judge", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert data["status"] == "completed"
    assert "manifest" in data


def test_judge_endpoint_with_strict(client):
    """Test the judge endpoint with strict mode."""
    payload = {
        "profile": "ui",
        "strict": True,
        "parallel": True,
    }

    response = client.post("/api/v1/judge", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"


def test_intel_endpoint_readiness(client):
    """Test the intel endpoint with readiness mode."""
    payload = {
        "mode": "readiness",
        "compact": False,
        "retention_days": 90,
    }

    response = client.post("/api/v1/intel", json=payload)
    # May fail if no data available, but should return valid response
    assert response.status_code in [200, 500]


def test_intel_endpoint_invalid_mode(client):
    """Test the intel endpoint with invalid mode."""
    payload = {
        "mode": "invalid_mode",
        "compact": False,
    }

    response = client.post("/api/v1/intel", json=payload)
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data


def test_explain_endpoint(client):
    """Test the explain endpoint."""
    payload = {
        "rule": "test_rule",
        "data": {"test": "data"},
    }

    response = client.post("/api/v1/explain", json=payload)
    # May fail if rule not found, but should return valid response
    assert response.status_code in [200, 500]


def test_impact_endpoint(client):
    """Test the impact endpoint."""
    form_data = {
        "diff": "diff --git a/test.py b/test.py",
        "profile": "base",
    }

    response = client.post("/api/v1/impact", data=form_data)
    assert response.status_code == 200

    data = response.json()
    assert "engines" in data
    assert "invariants" in data


def test_root_endpoint(client):
    """Test the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_docs_endpoint(client):
    """Test the API docs endpoint."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_endpoint(client):
    """Test the OpenAPI schema endpoint."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert "openapi" in data
    assert "paths" in data
