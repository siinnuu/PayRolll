"""
Tests for health check endpoints and connectivity reporting.
"""

import json


def test_health_html_endpoint(client):
    """Verify /health returns HTML diagnostics page."""
    response = client.get("/health")
    assert response.status_code in (200, 503)
    assert b"System Health" in response.data
    assert b"Flask Application Subsystem" in response.data
    assert b"MySQL Database Subsystem" in response.data


def test_health_json_format_param(client):
    """Verify /health?format=json returns structured JSON."""
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
    assert "message" in data["database"]
    assert "host" in data["database"]
    assert "timestamp" in data


def test_api_health_endpoint(client):
    """Verify /api/health returns JSON directly."""
    response = client.get("/api/health")
    assert response.status_code in (200, 503)
    assert response.content_type == "application/json"
    
    data = response.get_json()
    assert "flask" in data
    assert "database" in data
    assert isinstance(data["database"]["connected"], bool)


def test_health_accept_header(client):
    """Verify sending Accept: application/json triggers JSON response."""
    response = client.get("/health", headers={"Accept": "application/json"})
    assert response.content_type == "application/json"
    data = response.get_json()
    assert data["flask"]["status"] == "online"
