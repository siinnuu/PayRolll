"""
Pytest test fixtures and configuration.
"""

import pytest
from app import create_app
from config import TestingConfig


@pytest.fixture
def app():
    """Create and configure a testing Flask application instance."""
    app = create_app(TestingConfig)
    yield app


@pytest.fixture
def client(app):
    """Provide a test client for simulating HTTP requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Provide a test runner for Flask CLI commands."""
    return app.test_cli_runner()
