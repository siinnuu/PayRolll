"""
Monthly Payroll Processing routes (Module 6).
Handles monthly payroll directory, search & period filters, controlled batch runs,
individual generation, detailed payslip statement views, and status transitions.
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
from modules.payroll.services import (
    PayrollService,
    DuplicatePayrollError,
    MissingPayrollInputsError,
    InvalidStatusTransitionError,
    PayrollProcessingError,
)
from modules.attendance.validators import MONTH_NAMES

MONTH_DICT = {i: MONTH_NAMES[i] for i in range(1, 13)}

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")
service = PayrollService()


@payroll_bp.route("")
@payroll_bp.route("/")
@login_required
def index():
    """
    Paginated payroll records directory with month/year/employee/status filters,
    search toolbar, and summary financial metrics.
    """
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "ALL").strip().upper()

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
    records, total_count = service.payroll_repo.get_paginated_payroll(
        year=selected_year,
        month=selected_month,
        employee_id=selected_emp_id,
        status=status_filter if status_filter != "ALL" else None,
        search=search_query or None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, math.ceil(total_count / per_page))

    # Aggregated summary metrics for filtered period
    summary = service.payroll_repo.get_monthly_summary(year=selected_year, month=selected_month)

    active_employees = service.employee_repo.get_active_employees()
    available_years = service.payroll_repo.get_available_years()

    return render_template(
        "payroll/index.html",
        records=records,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        search_query=search_query,
        status_filter=status_filter,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_employee_id=selected_emp_id,
        summary=summary,
        active_employees=active_employees,
        available_years=available_years,
        month_names=MONTH_DICT,
    )


@payroll_bp.route("/run", methods=["GET", "POST"])
@login_required
def batch_run():
    """
    Controlled monthly payroll run for eligible active employees.
    Verifies attendance and salary structures before batch execution.
    """
    today = date.today()
    raw_year = request.args.get("year") or request.form.get("year")
    raw_month = request.args.get("month") or request.form.get("month")

    try:
        year = int(raw_year) if raw_year and str(raw_year).isdigit() else today.year
    except (ValueError, TypeError):
        year = today.year

    try:
        month = int(raw_month) if raw_month and str(raw_month).isdigit() else today.month
        if not (1 <= month <= 12):
            month = today.month
    except (ValueError, TypeError):
        month = today.month

    if request.method == "POST":
        # Check if specific employee IDs were selected
        selected_ids = request.form.getlist("selected_employee_ids")
        emp_ids = [int(i) for i in selected_ids if i.isdigit()] if selected_ids else None

        result = service.generate_batch_payroll_run(year=year, month=month, employee_ids=emp_ids)
        succ = result["successful_count"]
        skip = result["skipped_count"]

        if succ > 0:
            flash(
                f"Batch payroll run complete for {MONTH_NAMES[month]} {year}: "
                f"{succ} record(s) generated successfully ({skip} skipped/ineligible).",
                "success"
            )
        else:
            flash(
                f"Batch run complete: 0 records generated ({skip} skipped/ineligible). "
                "Ensure active employees have recorded attendance and salary structures.",
                "warning"
            )
        return redirect(url_for("payroll.index", year=year, month=month))

    # GET Request: Audit eligibility for selected month
    audited = service.get_eligible_employees_for_period(year=year, month=month)
    available_years = service.payroll_repo.get_available_years()

    eligible_count = sum(1 for a in audited if a["is_eligible"])

    return render_template(
        "payroll/batch_run.html",
        audited_employees=audited,
        year=year,
        month=month,
        eligible_count=eligible_count,
        total_count=len(audited),
        available_years=available_years,
        month_names=MONTH_DICT,
    )


@payroll_bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate_individual():
    """
    Generate an individual employee payroll record with preview verification.
    """
    today = date.today()
    active_employees = service.employee_repo.get_active_employees()
    available_years = service.payroll_repo.get_available_years()

    if request.method == "POST":
        raw_emp_id = request.form.get("employee_id")
        raw_year = request.form.get("year")
        raw_month = request.form.get("month")
        remarks = request.form.get("remarks")

        if not raw_emp_id or not raw_year or not raw_month:
            flash("Please select employee, year, and month to generate payroll.", "danger")
            return redirect(url_for("payroll.generate_individual"))

        try:
            emp_id = int(raw_emp_id)
            year = int(raw_year)
            month = int(raw_month)
        except (ValueError, TypeError):
            flash("Invalid input values provided.", "danger")
            return redirect(url_for("payroll.generate_individual"))

        try:
            payroll_id = service.generate_single_payroll(
                employee_id=emp_id, year=year, month=month, remarks=remarks
            )
            flash("Payroll record generated successfully in DRAFT status.", "success")
            return redirect(url_for("payroll.view", payroll_id=payroll_id))
        except DuplicatePayrollError as err:
            flash(str(err), "warning")
            return redirect(url_for("payroll.index", year=year, month=month))
        except (MissingPayrollInputsError, PayrollProcessingError) as err:
            flash(f"Failed to generate payroll: {str(err)}", "danger")
            return redirect(url_for("payroll.generate_individual", employee_id=emp_id, year=year, month=month))

    # GET Request: prefill preview if query params supplied
    selected_emp_id = request.args.get("employee_id", type=int)
    selected_year = request.args.get("year", type=int, default=today.year)
    selected_month = request.args.get("month", type=int, default=today.month)

    preview_data = None
    if selected_emp_id:
        preview_data = service.preview_employee_payroll(
            employee_id=selected_emp_id, year=selected_year, month=selected_month
        )

    return render_template(
        "payroll/generate.html",
        active_employees=active_employees,
        available_years=available_years,
        month_names=MONTH_DICT,
        selected_employee_id=selected_emp_id,
        selected_year=selected_year,
        selected_month=selected_month,
        preview_data=preview_data,
    )


@payroll_bp.route("/<int:payroll_id>")
@login_required
def view(payroll_id: int):
    """
    Detailed monthly payroll statement and payslip view with salary snapshot,
    attendance breakdown, and approval status actions.
    """
    details = service.get_payroll_details(payroll_id)
    if not details or not details.get("payroll"):
        flash(f"Payroll record #{payroll_id} was not found.", "warning")
        return redirect(url_for("payroll.index"))

    payroll = details["payroll"]
    attendance = details["attendance"]
    salary_cfg = details["salary_settings"]

    return render_template(
        "payroll/view.html",
        payroll=payroll,
        attendance=attendance,
        salary_cfg=salary_cfg,
        month_names=MONTH_DICT,
    )


@payroll_bp.route("/<int:payroll_id>/status", methods=["POST"])
@login_required
def update_status(payroll_id: int):
    """
    Transition payroll status:
    - approve: DRAFT -> APPROVED
    - cancel: DRAFT -> CANCELLED
    - reopen: APPROVED -> DRAFT (requires reason)
    """
    action = request.form.get("action", "").lower().strip()
    reason = request.form.get("reason", "").strip() or None

    target_status_map = {
        "approve": "APPROVED",
        "cancel": "CANCELLED",
        "reopen": "DRAFT",
    }

    if action not in target_status_map:
        flash("Invalid action requested.", "danger")
        return redirect(url_for("payroll.view", payroll_id=payroll_id))

    target_status = target_status_map[action]

    try:
        success, message = service.transition_payroll_status(
            payroll_id=payroll_id,
            target_status=target_status,
            reason=reason,
        )
        if success:
            flash(message, "success")
        else:
            flash(message, "danger")
    except InvalidStatusTransitionError as err:
        flash(str(err), "danger")
    except Exception as err:
        flash(f"Unexpected error updating payroll status: {str(err)}", "danger")

    return redirect(url_for("payroll.view", payroll_id=payroll_id))
