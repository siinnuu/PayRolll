"""
Reports Analytics Service Layer.
Coordinates report data aggregation, CSV serialization, and statistical summaries.
"""

import csv
from decimal import Decimal
import io
import logging
from typing import Any, Dict, List, Optional, Tuple

from repositories.reports_repository import ReportsRepository
from repositories.employee_repository import EmployeeRepository
from repositories.payroll_repository import PayrollRepository
from modules.attendance.validators import MONTH_NAMES

logger = logging.getLogger(__name__)


class ReportsService:
    """Service handling analytical reporting aggregations, CSV generation, and summary data."""

    def __init__(
        self,
        reports_repo: Optional[ReportsRepository] = None,
        employee_repo: Optional[EmployeeRepository] = None,
        payroll_repo: Optional[PayrollRepository] = None,
    ):
        self.reports_repo = reports_repo or ReportsRepository()
        self.employee_repo = employee_repo or EmployeeRepository()
        self.payroll_repo = payroll_repo or PayrollRepository()

    def get_monthly_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch monthly financial aggregates and status counts."""
        return self.reports_repo.get_monthly_payroll_summary(year=year, month=month)

    def get_employee_salary_history(
        self,
        employee_id: Optional[int] = None,
        department: Optional[str] = None,
        year: Optional[int] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch paginated historical salary vouchers for employees."""
        return self.reports_repo.get_employee_salary_history(
            employee_id=employee_id,
            department=department,
            year=year,
            page=page,
            per_page=per_page,
        )

    def get_attendance_summary(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
        employee_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """Fetch monthly attendance logs and aggregates."""
        return self.reports_repo.get_attendance_and_leave_summary(
            year=year,
            month=month,
            department=department,
            employee_id=employee_id,
            page=page,
            per_page=per_page,
        )

    def get_department_summary(self) -> List[Dict[str, Any]]:
        """Fetch department workforce distribution and salary commitment."""
        return self.reports_repo.get_department_summary()

    def get_status_and_method_distributions(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch payroll status and payment method breakdowns."""
        status_dist = self.reports_repo.get_payroll_status_distribution(year=year, month=month)
        method_dist = self.reports_repo.get_payment_method_distribution(year=year, month=month)
        return {
            "status_distribution": status_dist,
            "method_distribution": method_dist,
        }

    def generate_payroll_csv(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
    ) -> str:
        """Serialize Monthly Payroll Register into RFC-4180 compliant CSV."""
        rows = self.reports_repo.get_payroll_export_data(year=year, month=month, department=department)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header row
        writer.writerow([
            "Payroll Code",
            "Employee Code",
            "Employee Name",
            "Department",
            "Designation",
            "Year",
            "Month",
            "Basic Salary (INR)",
            "Allowances (INR)",
            "Overtime Pay (INR)",
            "Gross Salary (INR)",
            "Leave Deduction (INR)",
            "Other Deductions (INR)",
            "Total Deductions (INR)",
            "Net Salary (INR)",
            "Payroll Status",
            "Generated Date",
            "Payment Reference",
            "Payment Method",
            "Payment Date",
            "Payment Status",
        ])

        for r in rows:
            writer.writerow([
                r.get("payroll_code", ""),
                r.get("employee_code", ""),
                r.get("employee_name", ""),
                r.get("department", ""),
                r.get("designation", ""),
                r.get("year", ""),
                MONTH_NAMES[r["month"]] if 1 <= r.get("month", 0) <= 12 else r.get("month", ""),
                f"{float(r.get('basic_pay', 0)):.2f}",
                f"{float(r.get('allowances_total', 0)):.2f}",
                f"{float(r.get('overtime_pay', 0)):.2f}",
                f"{float(r.get('gross_pay', 0)):.2f}",
                f"{float(r.get('leave_deduction', 0)):.2f}",
                f"{float(r.get('other_deductions', 0)):.2f}",
                f"{float(r.get('total_deductions', 0)):.2f}",
                f"{float(r.get('net_pay', 0)):.2f}",
                r.get("payroll_status", ""),
                str(r.get("generated_date", "")),
                r.get("payment_reference", "") or "",
                r.get("payment_method", "") or "",
                str(r.get("payment_date", "") or ""),
                r.get("payment_status", "") or "",
            ])

        return output.getvalue()

    def generate_attendance_csv(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
    ) -> str:
        """Serialize Monthly Attendance Summary into RFC-4180 compliant CSV."""
        rows = self.reports_repo.get_attendance_export_data(year=year, month=month, department=department)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Employee Code",
            "Employee Name",
            "Department",
            "Designation",
            "Year",
            "Month",
            "Total Working Days",
            "Days Worked",
            "Paid Leaves",
            "Unpaid Leaves (LWP)",
            "Overtime Hours",
            "Overtime Rate (INR/hr)",
            "Notes",
        ])

        for r in rows:
            writer.writerow([
                r.get("employee_code", ""),
                r.get("employee_name", ""),
                r.get("department", ""),
                r.get("designation", ""),
                r.get("year", ""),
                MONTH_NAMES[r["month"]] if 1 <= r.get("month", 0) <= 12 else r.get("month", ""),
                r.get("total_working_days", ""),
                f"{float(r.get('days_worked', 0)):.1f}",
                f"{float(r.get('paid_leaves', 0)):.1f}",
                f"{float(r.get('unpaid_leaves', 0)):.1f}",
                f"{float(r.get('overtime_hours', 0)):.2f}",
                f"{float(r.get('overtime_rate', 0)):.2f}",
                r.get("notes", "") or "",
            ])

        return output.getvalue()

    def generate_payments_csv(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> str:
        """Serialize Payment History into RFC-4180 compliant CSV."""
        rows = self.reports_repo.get_payment_export_data(year=year, month=month)
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Payment Reference",
            "Payroll Code",
            "Employee Code",
            "Employee Name",
            "Department",
            "Year",
            "Month",
            "Payment Method",
            "Amount Paid (INR)",
            "Payment Date",
            "Status",
            "Transaction Notes",
        ])

        for r in rows:
            writer.writerow([
                r.get("payment_reference", ""),
                r.get("payroll_code", ""),
                r.get("employee_code", ""),
                r.get("employee_name", ""),
                r.get("department", ""),
                r.get("year", ""),
                MONTH_NAMES[r["month"]] if 1 <= r.get("month", 0) <= 12 else r.get("month", ""),
                r.get("payment_method", ""),
                f"{float(r.get('amount_paid', 0)):.2f}",
                str(r.get("payment_date", "")),
                r.get("payment_status", ""),
                r.get("transaction_notes", "") or "",
            ])

        return output.getvalue()

    def generate_departments_csv(self) -> str:
        """Serialize Department Summary into RFC-4180 compliant CSV."""
        rows = self.reports_repo.get_department_summary()
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "Department",
            "Total Employees",
            "Active Employees",
            "Inactive Employees",
            "Total Base Payroll (INR)",
            "Avg Base Salary (INR)",
            "Allowances Pool (INR)",
            "Min Salary (INR)",
            "Max Salary (INR)",
        ])

        for r in rows:
            writer.writerow([
                r.get("department", ""),
                r.get("total_employees", 0),
                r.get("active_count", 0),
                r.get("inactive_count", 0),
                f"{float(r.get('total_base_payroll', 0)):.2f}",
                f"{float(r.get('avg_base_salary', 0)):.2f}",
                f"{float(r.get('total_allowances_pool', 0)):.2f}",
                f"{float(r.get('min_salary', 0)):.2f}",
                f"{float(r.get('max_salary', 0)):.2f}",
            ])

        return output.getvalue()
