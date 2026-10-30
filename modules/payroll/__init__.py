"""
Payroll Module package initialization (Module 6).
Exposes payroll_bp Blueprint.
"""

from modules.payroll.routes import payroll_bp

__all__ = ["payroll_bp"]
