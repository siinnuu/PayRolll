"""
Core routes for the Employee Payroll Management System.
Redirects the home route to authenticated dashboard or login.
"""

from flask import Blueprint, redirect, url_for, session

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    """
    Main landing route.
    Redirects authenticated users directly to the Finance Manager dashboard,
    and unauthenticated visitors to the login view.
    """
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))
