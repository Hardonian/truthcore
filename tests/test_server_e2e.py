"""End-to-end tests for the Truth Core HTTP server."""

from __future__ import annotations

from fastapi.testclient import TestClient

from truthcore.server import create_app


def test_health_endpoint():
    """Health endpoint returns a healthy status."""
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "version" in payload


def test_status_requires_api_key(monkeypatch):
    """Status endpoint enforces API key when configured."""
    monkeypatch.setenv("TRUTHCORE_API_KEY", "test-key-123")
    client = TestClient(create_app())

    response = client.get("/api/v1/status")
    assert response.status_code == 401

    response = client.get("/api/v1/status", headers={"Authorization": "Bearer test-key-123"})
    assert response.status_code == 200
    assert response.json()["security"]["auth_enabled"] is True
