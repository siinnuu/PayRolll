"""
Employee Management routes for Employee Payroll Management System (Module 3).
Implements paginated listing, add, view details, search, edit, deactivation,
reactivation, and historical audit preservation.
"""

import math
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from modules.auth.services import login_required, role_required
from repositories.employee_repository import EmployeeRepository
from modules.employees.services import validate_employee_data

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")
employee_repo = EmployeeRepository()


@employees_bp.route("")
@employees_bp.route("/")
@login_required
def index():
    """
    Paginated employee directory with search and status filters.
    """
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "ALL").strip().upper()
    department_filter = request.args.get("department", "ALL").strip()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    per_page = 10
    employees, total_count = employee_repo.get_paginated_employees(
        search=search_query or None,
        status_filter=status_filter if status_filter != "ALL" else None,
        department_filter=department_filter if department_filter != "ALL" else None,
        page=page,
        per_page=per_page
    )

    total_pages = max(1, math.ceil(total_count / per_page))
    departments = employee_repo.get_all_departments()

    return render_template(
        "employees/index.html",
        employees=employees,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        search_query=search_query,
        status_filter=status_filter,
        department_filter=department_filter,
        departments=departments,
    )


@employees_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """
    Add a new employee and initialize their salary settings atomically in a transaction.
    """
    departments = employee_repo.get_all_departments()

    if request.method == "POST":
        form_data = request.form.to_dict()
        cleaned_data, errors = validate_employee_data(form_data)

        if errors:
            flash("Please correct the errors in the form before submitting.", "danger")
            return render_template(
                "employees/add.html",
                form_data=form_data,
                errors=errors,
                departments=departments,
            ), 422

        try:
            base_salary = cleaned_data.pop("base_salary")
            new_id = employee_repo.create_employee(cleaned_data, base_salary)
            flash(
                f"Employee {cleaned_data['first_name']} {cleaned_data['last_name']} ({cleaned_data['employee_code']}) added successfully.",
                "success"
            )
            return redirect(url_for("employees.view", employee_id=new_id))
        except Exception as e:
            flash(f"Failed to create employee due to database error: {str(e)}", "danger")
            return render_template(
                "employees/add.html",
                form_data=form_data,
                errors={},
                departments=departments,
            ), 500

    # Auto-generate next employee code for placeholder
    suggested_code = employee_repo.generate_next_employee_code()
    initial_data = {
        "employee_code": suggested_code,
        "status": "ACTIVE",
        "department": departments[0] if departments else "Engineering",
    }
    return render_template(
        "employees/add.html",
        form_data=initial_data,
        errors={},
        departments=departments,
    )


@employees_bp.route("/<int:employee_id>")
@login_required
def view(employee_id: int):
    """
    View complete profile details for an individual employee.
    """
    employee = employee_repo.get_by_id(employee_id)
    if not employee:
        flash(f"Employee with ID #{employee_id} was not found.", "warning")
        return redirect(url_for("employees.index"))

    history = employee_repo.has_historical_records(employee_id)
    return render_template(
        "employees/view.html",
        employee=employee,
        history=history,
    )


@employees_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
def edit(employee_id: int):
    """
    Edit existing employee details and salary settings.
    """
    employee = employee_repo.get_by_id(employee_id)
    if not employee:
        flash(f"Employee with ID #{employee_id} was not found.", "warning")
        return redirect(url_for("employees.index"))

    departments = employee_repo.get_all_departments()

    if request.method == "POST":
        form_data = request.form.to_dict()
        # Preserve original employee_code so it cannot be arbitrarily mutated if disabled
        form_data["employee_code"] = employee["employee_code"]
        cleaned_data, errors = validate_employee_data(form_data, employee_id=employee_id)

        if errors:
            flash("Please correct the errors in the form.", "danger")
            return render_template(
                "employees/edit.html",
                employee=employee,
                form_data=form_data,
                errors=errors,
                departments=departments,
            ), 422

        try:
            base_salary = cleaned_data.pop("base_salary", None)
            employee_repo.update_employee(employee_id, cleaned_data, base_salary=base_salary)
            flash("Employee profile updated successfully.", "success")
            return redirect(url_for("employees.view", employee_id=employee_id))
        except Exception as e:
            flash(f"Failed to update employee: {str(e)}", "danger")
            return render_template(
                "employees/edit.html",
                employee=employee,
                form_data=form_data,
                errors={},
                departments=departments,
            ), 500

    return render_template(
        "employees/edit.html",
        employee=employee,
        form_data=employee,
        errors={},
        departments=departments,
    )


@employees_bp.route("/<int:employee_id>/deactivate", methods=["POST"])
@login_required
def deactivate(employee_id: int):
    """
    Deactivate an employee (sets status = 'INACTIVE').
    Preserves all historical payroll, attendance, and disbursement records.
    """
    employee = employee_repo.get_by_id(employee_id)
    if not employee:
        flash(f"Employee with ID #{employee_id} not found.", "warning")
        return redirect(url_for("employees.index"))

    success = employee_repo.set_employee_status(employee_id, "INACTIVE")
    if success:
        flash(
            f"Employee {employee['first_name']} {employee['last_name']} ({employee['employee_code']}) has been deactivated. Historical payroll records remain preserved.",
            "warning"
        )
    else:
        flash("Failed to deactivate employee.", "danger")

    return redirect(request.referrer or url_for("employees.view", employee_id=employee_id))


@employees_bp.route("/<int:employee_id>/reactivate", methods=["POST"])
@login_required
def reactivate(employee_id: int):
    """
    Reactivate an inactive employee (sets status = 'ACTIVE').
    """
    employee = employee_repo.get_by_id(employee_id)
    if not employee:
        flash(f"Employee with ID #{employee_id} not found.", "warning")
        return redirect(url_for("employees.index"))

    success = employee_repo.set_employee_status(employee_id, "ACTIVE")
    if success:
        flash(
            f"Employee {employee['first_name']} {employee['last_name']} ({employee['employee_code']}) is now active.",
            "success"
        )
    else:
        flash("Failed to reactivate employee.", "danger")

    return redirect(request.referrer or url_for("employees.view", employee_id=employee_id))


@employees_bp.route("/<int:employee_id>/delete", methods=["POST"])
@login_required
def delete(employee_id: int):
    """
    Attempt to permanently delete an employee.
    Strictly blocked if historical attendance or payroll records exist.
    """
    success, message = employee_repo.delete_employee(employee_id)
    if success:
        flash(message, "success")
        return redirect(url_for("employees.index"))
    else:
        flash(message, "danger")
        return redirect(url_for("employees.view", employee_id=employee_id))
