"""
EKOS API Integration Tests
Tests authentication routes, healthcheck, and document upload schemas.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns app metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "EKOS" in data["name"]
    assert data["status"] == "running"


def test_healthcheck_endpoint():
    """Test health check returns system state."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
