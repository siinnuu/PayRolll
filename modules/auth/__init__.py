"""
Authentication module for the Employee Payroll Management System.
"""

from modules.auth.routes import auth_bp
from modules.auth.services import login_required, role_required, get_current_user

__all__ = ["auth_bp", "login_required", "role_required", "get_current_user"]
