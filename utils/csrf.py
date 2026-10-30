"""
CSRF Protection Utility for Employee Payroll Management System.
Implements cryptographically secure, session-bound CSRF token generation and validation.
"""

import hmac
import secrets
from functools import wraps
from flask import session, request, abort, current_app


def generate_csrf_token() -> str:
    """Generate or retrieve a cryptographically secure CSRF token stored in the session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf_token(token: str) -> bool:
    """Validate a given token against the current session token."""
    session_token = session.get("_csrf_token")
    if not session_token or not token:
        return False
    return hmac.compare_digest(str(session_token), str(token))


def csrf_protect_request():
    """
    Hook to validate CSRF tokens on state-modifying requests (POST, PUT, PATCH, DELETE).
    Can be registered with app.before_request.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Allow disabling CSRF in testing environment when explicitly configured
        if current_app.config.get("TESTING") and current_app.config.get("WTF_CSRF_ENABLED") is False:
            return

        # Check if view is marked as exempt
        endpoint = request.endpoint
        if endpoint:
            view_func = current_app.view_functions.get(endpoint)
            if getattr(view_func, "_csrf_exempt", False):
                return

        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not token or not validate_csrf_token(token):
            abort(400, description="Invalid or missing CSRF token. Please refresh the page and try again.")


def csrf_exempt(view_func):
    """Decorator to mark a route as exempt from CSRF validation."""
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        return view_func(*args, **kwargs)

    decorated_view._csrf_exempt = True
    return decorated_view
