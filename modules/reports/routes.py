"""
Reports routes (Module 8).
Handles:
- Main analytical reporting portal with multi-tab filters (Payroll, Attendance, Salary History, Distributions, Departments).
- CSV exports for Payroll Register, Attendance Summary, Payment History, and Department Summary.
"""

from datetime import date
import math
from flask import (
    Blueprint,
    render_template,
    request,
    Response,
    url_for,
    flash,
)
from modules.auth.services import login_required
from modules.reports.services import ReportsService
from modules.attendance.validators import MONTH_NAMES

MONTH_DICT = {i: MONTH_NAMES[i] for i in range(1, 13)}

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")
service = ReportsService()


@reports_bp.route("")
@reports_bp.route("/")
@login_required
def index():
    """
    Main reporting dashboard with tabbed views for:
    - payroll: Monthly payroll summary and financial totals
    - attendance: Attendance reconciliation and leave breakdown
    - salary_history: Chronological employee salary history
    - status: Payroll status and payment method distribution
    - departments: Workforce count and salary commitment by department
    """
    tab = request.args.get("tab", "payroll").lower().strip()
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()
    department = request.args.get("department", "ALL").strip()
    raw_emp_id = request.args.get("employee_id", "").strip()

    selected_year = int(raw_year) if raw_year and raw_year.isdigit() else None
    selected_month = int(raw_month) if raw_month and raw_month.isdigit() else None
    selected_emp_id = int(raw_emp_id) if raw_emp_id and raw_emp_id.isdigit() else None

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10

    # Common dropdown choices
    departments = service.employee_repo.get_all_departments()
    active_employees = service.employee_repo.get_active_employees()
    available_years = service.payroll_repo.get_available_years()

    # 1. Monthly Payroll Summary
    payroll_summary = service.get_monthly_summary(year=selected_year, month=selected_month)

    # 2. Employee Salary History
    salary_history, hist_count = service.get_employee_salary_history(
        employee_id=selected_emp_id,
        department=department if department != "ALL" else None,
        year=selected_year,
        page=page,
        per_page=per_page,
    )
    hist_pages = max(1, math.ceil(hist_count / per_page))

    # 3. Attendance Summary
    att_rows, att_count, att_totals = service.get_attendance_summary(
        year=selected_year,
        month=selected_month,
        department=department if department != "ALL" else None,
        employee_id=selected_emp_id,
        page=page,
        per_page=per_page,
    )
    att_pages = max(1, math.ceil(att_count / per_page))

    # 4. Department Workforce Summary
    dept_summary = service.get_department_summary()

    # 5. Status & Method Distributions
    dist = service.get_status_and_method_distributions(year=selected_year, month=selected_month)

    return render_template(
        "reports/index.html",
        active_tab=tab,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_department=department,
        selected_employee_id=selected_emp_id,
        page=page,
        departments=departments,
        active_employees=active_employees,
        available_years=available_years,
        month_names=MONTH_DICT,
        payroll_summary=payroll_summary,
        salary_history=salary_history,
        hist_count=hist_count,
        hist_pages=hist_pages,
        att_rows=att_rows,
        att_count=att_count,
        att_totals=att_totals,
        att_pages=att_pages,
        dept_summary=dept_summary,
        status_distribution=dist["status_distribution"],
        method_distribution=dist["method_distribution"],
    )


@reports_bp.route("/export/payroll.csv")
@login_required
def export_payroll_csv():
    """Download Monthly Payroll Register as CSV."""
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()
    dept = request.args.get("department", "").strip()

    year = int(raw_year) if raw_year and raw_year.isdigit() else None
    month = int(raw_month) if raw_month and raw_month.isdigit() else None

    csv_data = service.generate_payroll_csv(year=year, month=month, department=dept or None)
    filename = f"Payroll_Register_{year or 'All'}_{month or 'All'}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/export/attendance.csv")
@login_required
def export_attendance_csv():
    """Download Attendance & Leave Summary as CSV."""
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()
    dept = request.args.get("department", "").strip()

    year = int(raw_year) if raw_year and raw_year.isdigit() else None
    month = int(raw_month) if raw_month and raw_month.isdigit() else None

    csv_data = service.generate_attendance_csv(year=year, month=month, department=dept or None)
    filename = f"Attendance_Summary_{year or 'All'}_{month or 'All'}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/export/payments.csv")
@login_required
def export_payments_csv():
    """Download Payment History as CSV."""
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()

    year = int(raw_year) if raw_year and raw_year.isdigit() else None
    month = int(raw_month) if raw_month and raw_month.isdigit() else None

    csv_data = service.generate_payments_csv(year=year, month=month)
    filename = f"Payment_History_{year or 'All'}_{month or 'All'}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@reports_bp.route("/export/departments.csv")
@login_required
def export_departments_csv():
    """Download Department Workforce Summary as CSV."""
    csv_data = service.generate_departments_csv()
    filename = "Department_Workforce_Summary.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
