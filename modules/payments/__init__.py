"""
Payments Module package initialization (Module 7).
Exposes payments_bp Blueprint.
"""

from modules.payments.routes import payments_bp

__all__ = ["payments_bp"]
