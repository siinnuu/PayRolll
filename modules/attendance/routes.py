"""
Attendance and Leave Management routes for Employee Payroll Management System (Module 4).
Implements monthly attendance listing, search & filters, summary dashboard,
add/edit forms with calendar working days calculation, and employee history ledger.
"""

from datetime import date
import math
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    abort,
)
from modules.auth.services import login_required
from modules.attendance.services import AttendanceService
from modules.attendance.validators import MONTH_NAMES

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")
service = AttendanceService()


@attendance_bp.route("")
@attendance_bp.route("/")
@login_required
def index():
    """
    Paginated monthly attendance directory with search, employee filter,
    month/year period selectors, and summary analytics.
    """
    search_query = request.args.get("search", "").strip()

    # Period filters
    raw_year = request.args.get("year", "").strip()
    raw_month = request.args.get("month", "").strip()
    raw_emp_id = request.args.get("employee_id", "").strip()

    selected_year = int(raw_year) if raw_year and raw_year.isdigit() else None
    selected_month = int(raw_month) if raw_month and raw_month.isdigit() else None
    selected_emp_id = int(raw_emp_id) if raw_emp_id and raw_emp_id.isdigit() else None

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    records, total_count = service.get_paginated_attendance_records(
        employee_id=selected_emp_id,
        year=selected_year,
        month=selected_month,
        search=search_query or None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, math.ceil(total_count / per_page))

    # Summary metrics for the filtered period
    summary = service.get_attendance_summary(year=selected_year, month=selected_month)

    # Active employees and filter options
    active_employees = service.get_active_employees()
    available_years = service.get_available_years()

    return render_template(
        "attendance/attendance_list.html",
        records=records,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        search_query=search_query,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_employee_id=selected_emp_id,
        summary=summary,
        active_employees=active_employees,
        available_years=available_years,
        month_names=MONTH_NAMES,
    )


@attendance_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """
    Record monthly attendance for an active employee.
    Calculates default working days and validates leaves and overtime.
    """
    active_employees = service.get_active_employees()
    today = date.today()

    if request.method == "POST":
        form_data = request.form.to_dict()
        new_id, errors = service.create_attendance_record(form_data)

        if errors:
            flash("Please correct the validation errors below before submitting.", "danger")
            # Calculate calendar info for display
            try:
                y = int(form_data.get("year", today.year))
                m = int(form_data.get("month", today.month))
            except (ValueError, TypeError):
                y, m = today.year, today.month
            calendar_info = service.get_month_calendar_details(y, m)

            return render_template(
                "attendance/attendance_form.html",
                is_edit=False,
                form_data=form_data,
                errors=errors,
                active_employees=active_employees,
                calendar_info=calendar_info,
                month_names=MONTH_NAMES,
            ), 422

        flash("Monthly attendance record created successfully.", "success")
        return redirect(url_for("attendance.index"))

    # GET Request: Prepare initial defaults
    prefill_emp_id = request.args.get("employee_id", type=int)
    prefill_year = request.args.get("year", type=int, default=today.year)
    prefill_month = request.args.get("month", type=int, default=today.month)

    # Calculate default working days (weekdays)
    calendar_info = service.get_month_calendar_details(prefill_year, prefill_month)
    default_working_days = calendar_info["default_working_days"]

    # If employee preselected, get their overtime rate
    prefill_ot_rate = "0.00"
    if prefill_emp_id:
        emp = service.get_employee_by_id(prefill_emp_id)
        if emp and emp.get("hourly_rate"):
            prefill_ot_rate = str(emp["hourly_rate"])

    form_data = {
        "employee_id": prefill_emp_id or "",
        "year": prefill_year,
        "month": prefill_month,
        "total_working_days": default_working_days,
        "present_days": default_working_days,  # Default to full attendance
        "paid_leaves": 0,
        "unpaid_leaves": 0,
        "overtime_hours": 0.0,
        "overtime_rate": prefill_ot_rate,
        "notes": "",
    }

    return render_template(
        "attendance/attendance_form.html",
        is_edit=False,
        form_data=form_data,
        errors={},
        active_employees=active_employees,
        calendar_info=calendar_info,
        month_names=MONTH_NAMES,
    )


@attendance_bp.route("/<int:attendance_id>/edit", methods=["GET", "POST"])
@login_required
def edit(attendance_id: int):
    """
    Edit an existing monthly attendance record.
    """
    record = service.get_attendance_by_id(attendance_id)
    if not record:
        flash(f"Attendance record #{attendance_id} was not found.", "warning")
        return redirect(url_for("attendance.index"))

    active_employees = service.get_active_employees()

    if request.method == "POST":
        form_data = request.form.to_dict()
        # Ensure employee_id, year, month are preserved from the original record if disabled in form
        form_data["employee_id"] = record["employee_id"]
        form_data["year"] = record["year"]
        form_data["month"] = record["month"]

        success, errors = service.update_attendance_record(attendance_id, form_data)
        if errors:
            flash("Please correct the validation errors below before submitting.", "danger")
            calendar_info = service.get_month_calendar_details(record["year"], record["month"])
            return render_template(
                "attendance/attendance_form.html",
                is_edit=True,
                attendance_id=attendance_id,
                record=record,
                form_data=form_data,
                errors=errors,
                active_employees=active_employees,
                calendar_info=calendar_info,
                month_names=MONTH_NAMES,
            ), 422

        flash(
            f"Attendance record for {record['first_name']} {record['last_name']} "
            f"({MONTH_NAMES[record['month']]} {record['year']}) updated successfully.",
            "success"
        )
        return redirect(url_for("attendance.index"))

    # GET Request: prefill from existing record
    calendar_info = service.get_month_calendar_details(record["year"], record["month"])
    form_data = {
        "employee_id": record["employee_id"],
        "year": record["year"],
        "month": record["month"],
        "total_working_days": record["total_working_days"],
        "present_days": record["present_days"],
        "paid_leaves": record["paid_leaves"],
        "unpaid_leaves": record["unpaid_leaves"],
        "overtime_hours": record["overtime_hours"],
        "overtime_rate": record["overtime_rate"],
        "notes": record["notes"] or "",
    }

    return render_template(
        "attendance/attendance_form.html",
        is_edit=True,
        attendance_id=attendance_id,
        record=record,
        form_data=form_data,
        errors={},
        active_employees=active_employees,
        calendar_info=calendar_info,
        month_names=MONTH_NAMES,
    )


@attendance_bp.route("/employee/<int:employee_id>")
@login_required
def employee_history(employee_id: int):
    """
    Display complete historical monthly attendance ledger for a specific employee.
    Includes career attendance totals, leave tallies, and overtime summary.
    """
    employee, history, stats = service.get_employee_attendance_history(employee_id)
    if not employee:
        flash(f"Employee #{employee_id} not found.", "warning")
        return redirect(url_for("attendance.index"))

    return render_template(
        "attendance/employee_history.html",
        employee=employee,
        history=history,
        stats=stats,
        month_names=MONTH_NAMES,
    )


@attendance_bp.route("/api/working-days")
@login_required
def api_working_days():
    """
    Helper API returning calendar working days and weekend counts for a selected month/year.
    Enables instant dynamic client-side recalculation in attendance forms.
    """
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not (1 <= month <= 12):
            month = today.month
    except (ValueError, TypeError):
        year, month = today.year, today.month

    calendar_info = service.get_month_calendar_details(year, month)
    return jsonify(calendar_info)
