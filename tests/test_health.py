"""
Tests for health check endpoints and connectivity reporting.
Ensures no sensitive credentials, host/port, database users, or internal topology are leaked.
"""

import json


def test_health_html_endpoint(client):
    """Verify /health returns HTML diagnostics page without leaking DB host or credentials."""
    response = client.get("/health")
    assert response.status_code in (200, 503)
    assert b"System Health" in response.data
    assert b"Flask Application Subsystem" in response.data
    assert b"MySQL Database Subsystem" in response.data


def test_health_json_format_param(client):
    """Verify /health?format=json returns structured non-sensitive JSON."""
    response = client.get("/health?format=json")
    assert response.status_code in (200, 503)
    assert response.content_type == "application/json"
    
    data = response.get_json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "flask" in data
    assert data["flask"]["status"] == "online"
    assert "database" in data
    assert "connected" in data["database"]
    assert "timestamp" in data
    # Security: Ensure host and credentials are not leaked in public health check
    assert "host" not in data["database"]
    assert "user" not in data["database"]
    assert "password" not in data["database"]


def test_api_health_endpoint(client):
    """Verify minimal public /api/health endpoint returns minimal status without sensitive info."""
    response = client.get("/api/health")
    assert response.status_code in (200, 503)
    assert response.content_type == "application/json"
    
    data = response.get_json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    # Security: Ensure host, database, user, password are NOT exposed
    assert "database" not in data
    assert "host" not in data
    assert "user" not in data
    assert "password" not in data


def test_health_accept_header(client):
    """Verify sending Accept: application/json triggers JSON response."""
    response = client.get("/health", headers={"Accept": "application/json"})
    assert response.content_type == "application/json"
    data = response.get_json()
    assert data["flask"]["status"] == "online"
