"""
Authentication routes for Employee Payroll Management System.
Handles login, session initiation, CSRF protection, and logout.
"""

from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from modules.auth.services import authenticate_user, login_user_session, logout_user_session

auth_bp = Blueprint("auth", __name__)


def is_safe_redirect_url(target: str) -> bool:
    """Ensure redirect URL is local to prevent open-redirect vulnerabilities."""
    if not target:
        return False
    # Only allow relative local paths starting with a single '/'
    return target.startswith("/") and not target.startswith("//")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    User login endpoint.
    GET: Render the Bootstrap 5 login page with CSRF token.
    POST: Authenticate credentials against `users` table and establish session.
    """
    # If user is already authenticated, redirect directly to dashboard
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user, error = authenticate_user(username, password)
        if error or not user:
            flash(error or "Authentication failed.", "danger")
            return render_template("auth/login.html", username=username, next=next_url), 401

        # Establish authenticated session
        login_user_session(user)
        flash(f"Welcome back, {user.get('username')} ({user.get('role')})!", "success")

        # Redirect to intended URL if safe, otherwise default to dashboard
        if is_safe_redirect_url(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", next=next_url)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Invalidates current session and redirects to login page.
    Supports both GET and POST requests.
    """
    logout_user_session()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))
