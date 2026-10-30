"""
Validation and service layer for Employee Management (Module 3).
Handles server-side data validation, format verification, and duplicate checks.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Tuple
from repositories.employee_repository import EmployeeRepository

employee_repo = EmployeeRepository()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_employee_data(
    form_data: Dict[str, Any],
    employee_id: Optional[int] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """
    Validate incoming employee form data on the server.
    
    Returns:
        (cleaned_data, errors_dict)
    """
    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    # 1. Employee Code
    emp_code = (form_data.get("employee_code") or "").strip().upper()
    if not emp_code:
        # Auto-generate if omitted
        emp_code = employee_repo.generate_next_employee_code()
    elif len(emp_code) > 20:
        errors["employee_code"] = "Employee code cannot exceed 20 characters."

    # Check code uniqueness
    existing_code = employee_repo.get_by_code(emp_code)
    if existing_code and (employee_id is None or existing_code.get("id") != employee_id):
        errors["employee_code"] = f"Employee code '{emp_code}' is already assigned to another employee."
    cleaned["employee_code"] = emp_code

    # 2. First Name
    first_name = (form_data.get("first_name") or "").strip()
    if not first_name:
        errors["first_name"] = "First name is required."
    elif len(first_name) > 50:
        errors["first_name"] = "First name cannot exceed 50 characters."
    cleaned["first_name"] = first_name

    # 3. Last Name
    last_name = (form_data.get("last_name") or "").strip()
    if not last_name:
        errors["last_name"] = "Last name is required."
    elif len(last_name) > 50:
        errors["last_name"] = "Last name cannot exceed 50 characters."
    cleaned["last_name"] = last_name

    # 4. Email
    email = (form_data.get("email") or "").strip().lower()
    if not email:
        errors["email"] = "Email address is required."
    elif not EMAIL_REGEX.match(email) or len(email) > 100:
        errors["email"] = "Please enter a valid email address (e.g., user@example.com)."
    else:
        existing_email = employee_repo.get_by_email(email)
        if existing_email and (employee_id is None or existing_email.get("id") != employee_id):
            errors["email"] = f"Email address '{email}' is already registered."
    cleaned["email"] = email

    # 5. Phone
    phone = (form_data.get("phone") or "").strip()
    if phone and len(phone) > 20:
        errors["phone"] = "Phone number cannot exceed 20 characters."
    cleaned["phone"] = phone or None

    # 6. Department
    department = (form_data.get("department") or "").strip()
    if not department:
        errors["department"] = "Department is required."
    elif len(department) > 50:
        errors["department"] = "Department cannot exceed 50 characters."
    cleaned["department"] = department

    # 7. Job Title / Designation
    designation = (form_data.get("designation") or "").strip()
    if not designation:
        errors["designation"] = "Job title is required."
    elif len(designation) > 50:
        errors["designation"] = "Job title cannot exceed 50 characters."
    cleaned["designation"] = designation

    # 8. Joining Date
    joining_date_str = (form_data.get("joining_date") or "").strip()
    if not joining_date_str:
        errors["joining_date"] = "Joining date is required."
    else:
        try:
            parsed_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            cleaned["joining_date"] = parsed_date.isoformat()
        except ValueError:
            errors["joining_date"] = "Joining date must be in YYYY-MM-DD format."

    # 9. Status
    status = (form_data.get("status") or "ACTIVE").strip().upper()
    if status not in ("ACTIVE", "INACTIVE", "TERMINATED", "ON_LEAVE"):
        errors["status"] = "Invalid employment status selected."
    cleaned["status"] = status

    # 10. Basic Monthly Salary
    salary_str = (form_data.get("base_salary") or "").strip()
    if not salary_str:
        errors["base_salary"] = "Basic monthly salary is required."
    else:
        try:
            # Strip commas or currency symbols if entered
            cleaned_salary = salary_str.replace("$", "").replace(",", "")
            salary_val = Decimal(cleaned_salary)
            if salary_val < Decimal("0.00"):
                errors["base_salary"] = "Basic salary cannot be negative."
            elif salary_val > Decimal("9999999999.99"):
                errors["base_salary"] = "Salary amount exceeds permissible limits."
            cleaned["base_salary"] = salary_val
        except (InvalidOperation, ValueError):
            errors["base_salary"] = "Please enter a valid numeric salary amount."

    if errors:
        return None, errors

    return cleaned, {}
