"""
Authentication services, session handlers, and route security decorators.
Uses Werkzeug password hashing and secure session management.
"""

from functools import wraps
from typing import Any, Dict, List, Optional, Tuple
import werkzeug.security as ws
from flask import session, redirect, url_for, flash, request, g
from repositories.user_repository import UserRepository

user_repo = UserRepository()


def authenticate_user(username: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Authenticate credentials against the `users` table.
    
    Returns:
        (user_dict, None) on success, or (None, error_message) on failure.
    """
    if not username or not password:
        return None, "Please provide both username and password."

    user = user_repo.get_by_username(username.strip())
    if not user:
        return None, "Invalid username or password."

    # Check active status
    if not user.get("is_active", False):
        return None, "Your account has been deactivated. Please contact an administrator."

    # Verify password hash using Werkzeug
    password_hash = user.get("password_hash")
    if not password_hash or not ws.check_password_hash(password_hash, password):
        return None, "Invalid username or password."

    return user, None


def login_user_session(user: Dict[str, Any]) -> None:
    """
    Populate Flask session with authenticated user identity.
    Regenerates session token to protect against session fixation.
    """
    # Keep CSRF token intact if present, regenerate session contents
    csrf_token = session.get("_csrf_token")
    session.clear()
    if csrf_token:
        session["_csrf_token"] = csrf_token

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]
    session["role"] = user["role"]
    session.permanent = True  # Respect PERMANENT_SESSION_LIFETIME


def logout_user_session() -> None:
    """Safely clear all authentication session data."""
    session.clear()


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Retrieve current authenticated user data from session or database.
    Caches the user in Flask's application context `g.current_user`.
    """
    if hasattr(g, "current_user") and g.current_user is not None:
        return g.current_user

    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None

    try:
        user = user_repo.get_by_id(user_id)
        if user and user.get("is_active"):
            g.current_user = user
        else:
            # Fallback to cached session identity if user lookup returned None
            g.current_user = {
                "id": user_id,
                "username": session.get("username", "User"),
                "email": session.get("email", ""),
                "role": session.get("role", "ACCOUNTANT"),
            }
    except Exception:
        # Gracefully preserve session if database is momentarily unreachable
        g.current_user = {
            "id": user_id,
            "username": session.get("username", "User"),
            "email": session.get("email", ""),
            "role": session.get("role", "ACCOUNTANT"),
        }

    return g.current_user


def login_required(view_func):
    """
    Decorator protecting routes from unauthenticated access.
    Redirects unauthenticated requests to the login view, retaining the next URL.
    """
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return decorated_view


def role_required(*allowed_roles: str):
    """
    Decorator enforcing role-based authorization (e.g. 'ADMIN', 'ACCOUNTANT').
    Requires user to be logged in and possess at least one of the allowed roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def decorated_view(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.path))

            user_role = session.get("role", "")
            if user_role not in allowed_roles:
                flash("You do not have permission to access this resource.", "danger")
                return redirect(url_for("dashboard.index"))

            return view_func(*args, **kwargs)

        return decorated_view

    return decorator
