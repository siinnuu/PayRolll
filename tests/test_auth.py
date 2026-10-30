"""
Automated tests for Authentication (Module 2).
Tests login page rendering, successful/failed login, CSRF validation, session invalidation,
and protected route redirection.
"""

from unittest.mock import patch, MagicMock
import werkzeug.security as ws
from flask import session


def test_login_page_renders(client):
    """Verify /login GET returns HTTP 200 and renders login form with CSRF token."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Finance Manager Login" in response.data
    assert b"csrf_token" in response.data
    assert b"Sign In to Dashboard" in response.data


def test_login_success_establishes_session(client):
    """Verify valid credentials establish an authenticated session and redirect to dashboard."""
    # First get the page to generate a session CSRF token
    get_res = client.get("/login")
    with client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token")

    mock_user = {
        "id": 42,
        "username": "michael.fin",
        "email": "michael.chang@example.com",
        "password_hash": ws.generate_password_hash("ValidPass@123"),
        "role": "ACCOUNTANT",
        "is_active": True,
    }

    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=mock_user):
        response = client.post(
            "/login",
            data={
                "username": "michael.fin",
                "password": "ValidPass@123",
                "csrf_token": csrf_token,
            },
            follow_redirects=False
        )

        assert response.status_code == 302
        assert "/dashboard" in response.location

        with client.session_transaction() as sess:
            assert sess.get("user_id") == 42
            assert sess.get("username") == "michael.fin"
            assert sess.get("role") == "ACCOUNTANT"


def test_login_failed_invalid_password(client):
    """Verify submitting incorrect password returns HTTP 401 and prevents session creation."""
    client.get("/login")
    with client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token")

    mock_user = {
        "id": 42,
        "username": "michael.fin",
        "email": "michael.chang@example.com",
        "password_hash": ws.generate_password_hash("CorrectPass@123"),
        "role": "ACCOUNTANT",
        "is_active": True,
    }

    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=mock_user):
        response = client.post(
            "/login",
            data={
                "username": "michael.fin",
                "password": "WrongPassword@999",
                "csrf_token": csrf_token,
            }
        )

        assert response.status_code == 401
        assert b"Invalid username or password" in response.data

        with client.session_transaction() as sess:
            assert sess.get("user_id") is None


def test_login_failed_non_existent_user(client):
    """Verify non-existent username returns HTTP 401."""
    client.get("/login")
    with client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token")

    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=None):
        response = client.post(
            "/login",
            data={
                "username": "non_existent_user",
                "password": "AnyPassword@123",
                "csrf_token": csrf_token,
            }
        )

        assert response.status_code == 401
        assert b"Invalid username or password" in response.data


def test_login_failed_inactive_user(client):
    """Verify inactive user cannot log in."""
    client.get("/login")
    with client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token")

    mock_inactive_user = {
        "id": 99,
        "username": "disabled_user",
        "email": "disabled@example.com",
        "password_hash": ws.generate_password_hash("ValidPass@123"),
        "role": "ACCOUNTANT",
        "is_active": False,
    }

    with patch("repositories.user_repository.UserRepository.get_by_username", return_value=mock_inactive_user):
        response = client.post(
            "/login",
            data={
                "username": "disabled_user",
                "password": "ValidPass@123",
                "csrf_token": csrf_token,
            }
        )

        assert response.status_code == 401
        assert b"deactivated" in response.data


def test_csrf_protection_blocks_post_without_token(client):
    """Verify state-modifying POST without CSRF token is rejected with HTTP 400."""
    response = client.post(
        "/login",
        data={
            "username": "michael.fin",
            "password": "AnyPassword@123",
            # No csrf_token provided
        }
    )
    assert response.status_code == 400


def test_logout_clears_session(client):
    """Verify logout invalidates session and redirects to login."""
    # Pre-populate session
    with client.session_transaction() as sess:
        sess["user_id"] = 42
        sess["username"] = "michael.fin"
        sess["role"] = "ACCOUNTANT"

    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location

    with client.session_transaction() as sess:
        assert sess.get("user_id") is None
        assert sess.get("username") is None


def test_protected_dashboard_redirects_unauthenticated(client):
    """Verify accessing /dashboard without a session redirects to /login."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location
    assert "next=/dashboard" in response.location or "next=%2Fdashboard" in response.location


def test_protected_unfinished_route_redirects_unauthenticated(client):
    """Verify accessing unfinished module /employees without a session redirects to /login."""
    response = client.get("/employees", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location
    assert "next=/employees" in response.location or "next=%2Femployees" in response.location
