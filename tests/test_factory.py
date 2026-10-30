"""
Tests for Flask application factory pattern (create_app).
"""

from flask import Flask
from app import create_app
from config import TestingConfig


def test_create_app_factory():
    """Verify create_app returns a configured Flask instance."""
    app = create_app(TestingConfig)
    assert isinstance(app, Flask)
    assert app.testing is True
    assert "db" in app.extensions


def test_blueprints_registered(app):
    """Verify required blueprints (core, health) are properly registered."""
    blueprint_names = list(app.blueprints.keys())
    assert "core" in blueprint_names
    assert "health" in blueprint_names


def test_index_route(client):
    """Verify landing page renders successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"PayMaster Pro" in response.data
    assert b"Employee Payroll Management System" in response.data
    assert b"Module 1" in response.data


def test_404_error_handler(client):
    """Verify custom 404 handler renders the 404 template."""
    response = client.get("/non-existent-route-404")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data
