"""
Attendance and Leave Management service layer (Module 4).
Orchestrates business operations, employee lookups, working day computations,
summary statistics, and validation between routes and repositories.
"""

from datetime import date
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple

from repositories.attendance_repository import AttendanceRepository
from repositories.employee_repository import EmployeeRepository
from modules.attendance.validators import (
    calculate_default_working_days,
    get_month_calendar_info,
    validate_attendance_data,
    MONTH_NAMES,
)

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service orchestrating monthly attendance, leaves, overtime, and employee ledger operations."""

    def __init__(
        self,
        attendance_repo: Optional[AttendanceRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
    ):
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.employee_repo = employee_repo or EmployeeRepository()

    def get_active_employees(self) -> List[Dict[str, Any]]:
        """Retrieve all active employees for selection in attendance recording."""
        return self.employee_repo.get_active_employees()

    def get_employee_by_id(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """Fetch employee details by ID."""
        return self.employee_repo.get_by_id(employee_id)

    def get_working_days_for_period(self, year: int, month: int) -> int:
        """Calculate the standard working days in a month (excluding weekends)."""
        return calculate_default_working_days(year, month, exclude_weekends=True)

    def get_month_calendar_details(self, year: int, month: int) -> Dict[str, Any]:
        """Get calendar metadata and weekend breakdown for a period."""
        return get_month_calendar_info(year, month)

    def get_available_years(self) -> List[int]:
        """List of years with recorded attendance or current year."""
        return self.attendance_repo.get_available_years()

    def get_paginated_attendance_records(
        self,
        employee_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve filtered and paginated monthly attendance summaries."""
        return self.attendance_repo.get_paginated_attendance(
            employee_id=employee_id,
            year=year,
            month=month,
            search=search,
            page=page,
            per_page=per_page,
        )

    def get_attendance_by_id(self, attendance_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific monthly attendance record with joined employee info."""
        return self.attendance_repo.get_by_id(attendance_id)

    def get_attendance_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compute aggregated metrics for the selected period with robust default fallbacks."""
        summary = dict(self.attendance_repo.get_monthly_summary(year=year, month=month) or {})
        defaults = {
            "total_records": 0,
            "total_working_days": 0,
            "total_present_days": Decimal("0.0"),
            "total_paid_leaves": Decimal("0.0"),
            "total_unpaid_leaves": Decimal("0.0"),
            "total_leaves": Decimal("0.0"),
            "total_absent_days": Decimal("0.0"),
            "total_overtime_hours": Decimal("0.00"),
            "total_overtime_cost": Decimal("0.00"),
            "attendance_rate": 0.0,
        }
        for k, v in defaults.items():
            if k not in summary or summary[k] is None:
                summary[k] = v
        return summary

    def get_employee_attendance_history(
        self, employee_id: int, limit: int = 36
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieve employee profile along with their full monthly attendance ledger and lifetime stats.
        
        Returns:
            (employee_profile, history_records, summary_stats)
        """
        employee = self.employee_repo.get_by_id(employee_id)
        if not employee:
            return None, [], {}

        history = self.attendance_repo.get_attendance_history_for_employee(employee_id, limit=limit)

        # Aggregate employee-specific lifetime statistics
        total_months = len(history)
        total_present = sum(Decimal(str(r.get("present_days", 0))) for r in history)
        total_paid_leaves = sum(Decimal(str(r.get("paid_leaves", 0))) for r in history)
        total_unpaid_leaves = sum(Decimal(str(r.get("unpaid_leaves", 0))) for r in history)
        total_leaves = total_paid_leaves + total_unpaid_leaves
        total_ot_hours = sum(Decimal(str(r.get("overtime_hours", 0))) for r in history)
        total_working_days = sum(int(r.get("total_working_days", 0)) for r in history)

        avg_attendance_rate = 0.0
        if total_working_days > 0:
            avg_attendance_rate = round(float(total_present / total_working_days) * 100, 1)

        stats = {
            "total_months": total_months,
            "total_present_days": total_present,
            "total_paid_leaves": total_paid_leaves,
            "total_unpaid_leaves": total_unpaid_leaves,
            "total_leaves": total_leaves,
            "total_overtime_hours": total_ot_hours,
            "avg_attendance_rate": avg_attendance_rate,
        }

        return employee, history, stats

    def create_attendance_record(
        self, form_data: Dict[str, Any]
    ) -> Tuple[Optional[int], Dict[str, str]]:
        """
        Validate and insert a new monthly attendance record.
        
        Returns:
            (new_attendance_id, errors_dict)
        """
        cleaned_data, errors = validate_attendance_data(form_data, attendance_id=None)
        if errors:
            return None, errors

        try:
            new_id = self.attendance_repo.create_attendance(cleaned_data)
            return new_id, {}
        except Exception as e:
            logger.error("Failed to create attendance record in database: %s", e)
            return None, {"database": f"Database error creating attendance: {str(e)}"}

    def update_attendance_record(
        self, attendance_id: int, form_data: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Validate and update an existing monthly attendance record.
        
        Returns:
            (success: bool, errors_dict)
        """
        # First ensure the record exists
        existing = self.attendance_repo.get_by_id(attendance_id)
        if not existing:
            return False, {"not_found": "Attendance record not found."}

        cleaned_data, errors = validate_attendance_data(form_data, attendance_id=attendance_id)
        if errors:
            return False, errors

        try:
            self.attendance_repo.update_attendance(attendance_id, cleaned_data)
            return True, {}
        except Exception as e:
            logger.error("Failed to update attendance record #%s: %s", attendance_id, e)
            return False, {"database": f"Database error updating attendance: {str(e)}"}
