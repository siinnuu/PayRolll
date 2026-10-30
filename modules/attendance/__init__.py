"""
Attendance and Leave Management module initialization (Module 4).
Exposes the attendance Blueprint.
"""

from modules.attendance.routes import attendance_bp

__all__ = ["attendance_bp"]
