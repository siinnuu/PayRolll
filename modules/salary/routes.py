"""
Salary Configuration and Salary Calculation routes (Module 5).
Manages employee salary structures, allowances, overtime rates, deductions,
and the interactive Salary Preview calculation engine.
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
from modules.salary.services import SalaryService
from modules.attendance.validators import MONTH_NAMES

salary_bp = Blueprint("salary", __name__, url_prefix="/salary")
service = SalaryService()


@salary_bp.route("")
@salary_bp.route("/")
@login_required
def index():
    """
    Paginated directory of employee salary configurations, compensation metrics,
    and links to salary preview.
    """
    search_query = request.args.get("search", "").strip()
    department_filter = request.args.get("department", "ALL").strip()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    structures, total_count = service.get_paginated_salary_structures(
        search=search_query or None,
        department=department_filter if department_filter != "ALL" else None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, math.ceil(total_count / per_page))
    summary = service.get_summary_metrics()

    # Get distinct departments for filter dropdown
    departments = service.employee_repo.get_all_departments()

    return render_template(
        "salary/index.html",
        structures=structures,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        search_query=search_query,
        department_filter=department_filter,
        departments=departments,
        summary=summary,
    )


@salary_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit(employee_id: int):
    """
    Configure or update salary structure (base salary, allowances, overtime rate,
    other deductions, and effective date) for an employee.
    """
    salary_cfg = service.get_salary_configuration(employee_id)
    if not salary_cfg:
        # Check if employee exists
        employee = service.employee_repo.get_by_id(employee_id)
        if not employee:
            flash(f"Employee #{employee_id} not found.", "warning")
            return redirect(url_for("salary.index"))
        salary_cfg = {
            "employee_id": employee_id,
            "employee_code": employee["employee_code"],
            "first_name": employee["first_name"],
            "last_name": employee["last_name"],
            "department": employee["department"],
            "designation": employee["designation"],
            "base_salary": "0.00",
            "hourly_rate": "0.00",
            "hra": "0.00",
            "transport_allowance": "0.00",
            "medical_allowance": "0.00",
            "other_allowances": "0.00",
            "other_deductions": "0.00",
            "effective_from": date.today().isoformat(),
        }

    if request.method == "POST":
        form_data = request.form.to_dict()
        success, errors = service.update_salary_configuration(employee_id, form_data)
        if errors:
            flash("Please correct the validation errors in the form.", "danger")
            return render_template(
                "salary/edit.html",
                salary_cfg=salary_cfg,
                form_data=form_data,
                errors=errors,
            ), 422

        emp_name = f"{salary_cfg.get('first_name', '')} {salary_cfg.get('last_name', '')}".strip() or f"Employee #{employee_id}"
        code_str = f" ({salary_cfg['employee_code']})" if salary_cfg.get('employee_code') else ""
        flash(
            f"Salary structure for {emp_name}{code_str} updated successfully.",
            "success"
        )
        return redirect(url_for("salary.index"))

    # GET Request: prefill form with existing settings
    form_data = {
        "base_salary": str(salary_cfg["base_salary"]),
        "hourly_rate": str(salary_cfg["hourly_rate"]),
        "hra": str(salary_cfg["hra"]),
        "transport_allowance": str(salary_cfg["transport_allowance"]),
        "medical_allowance": str(salary_cfg["medical_allowance"]),
        "other_allowances": str(salary_cfg["other_allowances"]),
        "other_deductions": str(salary_cfg["other_deductions"]),
        "effective_from": str(salary_cfg["effective_from"]),
    }

    return render_template(
        "salary/edit.html",
        salary_cfg=salary_cfg,
        form_data=form_data,
        errors={},
    )


@salary_bp.route("/preview", methods=["GET"])
@login_required
def preview():
    """
    Interactive Salary Preview page for the Finance Manager.
    Pulls actual employee and attendance records from MySQL and calculates:
    Basic salary, Allowances, Daily salary, Unpaid leave days, Leave deduction,
    Overtime hours & payment, Other deductions, Gross salary, Total deductions, Net salary.
    """
    today = date.today()
    active_employees = service.get_active_employees()
    available_years = service.attendance_repo.get_available_years()

    raw_emp_id = request.args.get("employee_id")
    raw_year = request.args.get("year")
    raw_month = request.args.get("month")
    raw_allow_negative = request.args.get("allow_negative_net")

    allow_negative_net = (raw_allow_negative == "1" or raw_allow_negative == "true")

    selected_emp_id = None
    if raw_emp_id and raw_emp_id.isdigit():
        selected_emp_id = int(raw_emp_id)
    elif active_employees:
        # Default to first active employee
        selected_emp_id = active_employees[0]["id"]

    try:
        selected_year = int(raw_year) if raw_year and raw_year.isdigit() else today.year
    except (ValueError, TypeError):
        selected_year = today.year

    try:
        selected_month = int(raw_month) if raw_month and raw_month.isdigit() else today.month
        if not (1 <= selected_month <= 12):
            selected_month = today.month
    except (ValueError, TypeError):
        selected_month = today.month

    preview_data = None
    if selected_emp_id:
        preview_data = service.preview_salary_calculation(
            employee_id=selected_emp_id,
            year=selected_year,
            month=selected_month,
            allow_negative_net=allow_negative_net,
        )

    return render_template(
        "salary/preview.html",
        active_employees=active_employees,
        available_years=available_years,
        month_names=MONTH_NAMES,
        selected_employee_id=selected_emp_id,
        selected_year=selected_year,
        selected_month=selected_month,
        allow_negative_net=allow_negative_net,
        preview_data=preview_data,
    )


@salary_bp.route("/api/preview", methods=["GET"])
@login_required
def api_preview():
    """
    JSON API endpoint returning live salary calculation results
    for AJAX/dynamic client-side previews.
    """
    today = date.today()
    emp_id = request.args.get("employee_id", type=int)
    year = request.args.get("year", type=int, default=today.year)
    month = request.args.get("month", type=int, default=today.month)
    allow_negative = request.args.get("allow_negative_net", default="0") in ("1", "true")

    if not emp_id:
        return jsonify({"status": "error", "message": "Employee ID is required."}), 400

    result = service.preview_salary_calculation(
        employee_id=emp_id,
        year=year,
        month=month,
        allow_negative_net=allow_negative,
    )

    if result["status"] == "success":
        calc = result["calculation"]
        return jsonify({
            "status": "success",
            "employee_id": emp_id,
            "employee_name": f"{result['employee']['first_name']} {result['employee']['last_name']}",
            "year": year,
            "month": month,
            "basic_salary": str(calc.basic_salary),
            "total_working_days": calc.total_working_days,
            "daily_salary": str(calc.daily_salary),
            "paid_leave_days": str(calc.paid_leave_days),
            "unpaid_leave_days": str(calc.unpaid_leave_days),
            "leave_deduction": str(calc.leave_deduction),
            "allowances": str(calc.allowances),
            "overtime_hours": str(calc.overtime_hours),
            "overtime_rate": str(calc.overtime_rate),
            "overtime_payment": str(calc.overtime_payment),
            "other_deductions": str(calc.other_deductions),
            "gross_salary": str(calc.gross_salary),
            "total_deductions": str(calc.total_deductions),
            "net_salary": str(calc.net_salary),
            "formula_explanations": calc.formula_explanations,
        })
    else:
        return jsonify({
            "status": result["status"],
            "error_message": result["error_message"],
            "employee_id": emp_id,
            "year": year,
            "month": month,
        }), 422
