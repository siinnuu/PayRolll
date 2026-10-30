"""
Validation and business rule enforcement for Attendance & Leave Management (Module 4).
Enforces:
1. Strict non-negative numeric inputs for days worked, leaves, and overtime.
2. Total days worked + paid leaves + unpaid leaves <= total working days.
3. One monthly attendance summary per employee per month.
4. Active employee verification.
5. Standard working days calculation accounting for weekends (Saturdays & Sundays).
"""

import calendar
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from repositories.employee_repository import EmployeeRepository
from repositories.attendance_repository import AttendanceRepository

employee_repo = EmployeeRepository()
attendance_repo = AttendanceRepository()

MONTH_NAMES = [
    "",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def calculate_default_working_days(year: int, month: int, exclude_weekends: bool = True) -> int:
    """
    Calculate the standard working days in a given year and month.
    Excludes Saturdays and Sundays (standard 5-day working week).
    
    Args:
        year: Full year (e.g., 2026)
        month: Month number (1-12)
        exclude_weekends: If True, Saturdays and Sundays are excluded.
        
    Returns:
        Integer count of standard working days.
    """
    try:
        _, num_days = calendar.monthrange(year, month)
    except (ValueError, calendar.IllegalMonthError):
        return 30

    if not exclude_weekends:
        return num_days

    working_days = 0
    for day in range(1, num_days + 1):
        # weekday(): Monday is 0, Sunday is 6
        if date(year, month, day).weekday() < 5:  # Monday through Friday
            working_days += 1
    return working_days


def get_month_calendar_info(year: int, month: int) -> Dict[str, Any]:
    """
    Get detailed breakdown of calendar days, weekend days, and working days for a month.
    Used for transparent UI feedback and working days configuration.
    """
    try:
        _, total_days = calendar.monthrange(year, month)
        working_days = calculate_default_working_days(year, month, exclude_weekends=True)
        weekend_days = total_days - working_days
        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else f"Month {month}"
    except Exception:
        total_days = 30
        working_days = 22
        weekend_days = 8
        month_name = f"Month {month}"

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "total_calendar_days": total_days,
        "weekend_days": weekend_days,
        "default_working_days": working_days,
        "explanation": (
            f"{month_name} {year} has {total_days} calendar days, consisting of "
            f"{working_days} standard working days (Monday-Friday) and {weekend_days} weekend days. "
            "Finance managers may adjust working days if gazetted public holidays or "
            "alternate shifts apply."
        ),
    }


def parse_decimal_field(
    value: Any,
    field_name: str,
    errors: Dict[str, str],
    allow_zero: bool = True,
    min_val: Decimal = Decimal("0.0"),
    max_val: Optional[Decimal] = None,
    default: Decimal = Decimal("0.0"),
) -> Decimal:
    """Helper to cleanly parse and validate a Decimal input."""
    if value is None or str(value).strip() == "":
        return default

    str_val = str(value).strip()
    try:
        dec = Decimal(str_val)
    except (InvalidOperation, ValueError, TypeError):
        errors[field_name] = f"{field_name.replace('_', ' ').title()} must be a valid number."
        return default

    if dec < min_val:
        errors[field_name] = f"{field_name.replace('_', ' ').title()} cannot be negative."
        return dec

    if not allow_zero and dec == Decimal("0"):
        errors[field_name] = f"{field_name.replace('_', ' ').title()} must be greater than zero."
        return dec

    if max_val is not None and dec > max_val:
        errors[field_name] = f"{field_name.replace('_', ' ').title()} cannot exceed {max_val}."
        return dec

    return dec


def validate_attendance_data(
    form_data: Dict[str, Any],
    attendance_id: Optional[int] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
    """
    Server-side validation for monthly attendance records.
    
    Rules enforced:
    1. Employee must exist and be ACTIVE for new attendance entries.
    2. Year must be between 2000 and 2100.
    3. Month must be between 1 and 12.
    4. Enforce one monthly summary per employee per month (no duplicates).
    5. Total working days must be positive integer (> 0).
    6. Days worked (present_days), paid leaves, unpaid leaves, and overtime >= 0.
    7. Consistent leave calculation: total_leaves = paid_leaves + unpaid_leaves.
    8. Rule: (days_worked + paid_leaves + unpaid_leaves) <= total_working_days.
    9. Overtime hours and hourly rate must be non-negative.
    
    Returns:
        (cleaned_data, errors_dict)
    """
    errors: Dict[str, str] = {}
    cleaned: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 1. Employee Validation
    # -------------------------------------------------------------------------
    raw_emp_id = form_data.get("employee_id")
    if not raw_emp_id:
        errors["employee_id"] = "Please select an employee."
        employee = None
    else:
        try:
            emp_id = int(raw_emp_id)
            employee = employee_repo.get_by_id(emp_id)
            if not employee:
                errors["employee_id"] = f"Employee with ID #{emp_id} does not exist in the database."
            elif attendance_id is None and employee.get("status") != "ACTIVE":
                errors["employee_id"] = (
                    f"Cannot create attendance for inactive employee {employee['first_name']} {employee['last_name']} "
                    f"({employee['employee_code']}). Only active employees can receive new attendance records."
                )
            cleaned["employee_id"] = emp_id
        except (ValueError, TypeError):
            errors["employee_id"] = "Invalid employee identifier."
            employee = None

    # -------------------------------------------------------------------------
    # 2. Payroll Month and Year Validation
    # -------------------------------------------------------------------------
    raw_year = form_data.get("year")
    try:
        year = int(raw_year) if raw_year else date.today().year
        if not (2000 <= year <= 2100):
            errors["year"] = "Year must be between 2000 and 2100."
        cleaned["year"] = year
    except (ValueError, TypeError):
        errors["year"] = "Invalid year format."
        year = date.today().year
        cleaned["year"] = year

    raw_month = form_data.get("month")
    try:
        month = int(raw_month) if raw_month else date.today().month
        if not (1 <= month <= 12):
            errors["month"] = "Month must be between 1 (January) and 12 (December)."
        cleaned["month"] = month
    except (ValueError, TypeError):
        errors["month"] = "Invalid month selection."
        month = date.today().month
        cleaned["month"] = month

    # -------------------------------------------------------------------------
    # 3. Duplicate Attendance Check (One monthly summary per employee)
    # -------------------------------------------------------------------------
    if "employee_id" in cleaned and "year" in cleaned and "month" in cleaned and not errors:
        existing = attendance_repo.get_by_employee_and_period(
            cleaned["employee_id"], cleaned["year"], cleaned["month"]
        )
        if existing and (attendance_id is None or existing["id"] != attendance_id):
            m_name = MONTH_NAMES[cleaned["month"]]
            emp_name = f"{employee['first_name']} {employee['last_name']}" if employee else "this employee"
            errors["employee_id"] = (
                f"An attendance summary for {emp_name} for {m_name} {cleaned['year']} already exists. "
                f"Only one attendance record per employee per month is allowed. Please edit the existing record."
            )

    # -------------------------------------------------------------------------
    # 4. Total Working Days Validation
    # -------------------------------------------------------------------------
    raw_twd = form_data.get("total_working_days")
    try:
        twd = int(raw_twd) if raw_twd is not None and str(raw_twd).strip() != "" else calculate_default_working_days(year, month)
        if twd <= 0:
            errors["total_working_days"] = "Total working days must be greater than zero."
        elif twd > 31:
            errors["total_working_days"] = "Total working days cannot exceed 31 days in a month."
        cleaned["total_working_days"] = twd
    except (ValueError, TypeError):
        errors["total_working_days"] = "Total working days must be a valid positive integer."
        cleaned["total_working_days"] = 30

    # -------------------------------------------------------------------------
    # 5. Days Worked (Present Days) Validation
    # -------------------------------------------------------------------------
    present_days = parse_decimal_field(
        form_data.get("present_days"),
        "present_days",
        errors,
        allow_zero=True,
        min_val=Decimal("0.0"),
        default=Decimal("0.0"),
    )
    cleaned["present_days"] = present_days

    # -------------------------------------------------------------------------
    # 6. Leave Categories: Paid Leaves & Unpaid Leaves
    # -------------------------------------------------------------------------
    paid_leaves = parse_decimal_field(
        form_data.get("paid_leaves"),
        "paid_leaves",
        errors,
        allow_zero=True,
        min_val=Decimal("0.0"),
        default=Decimal("0.0"),
    )
    cleaned["paid_leaves"] = paid_leaves

    unpaid_leaves = parse_decimal_field(
        form_data.get("unpaid_leaves"),
        "unpaid_leaves",
        errors,
        allow_zero=True,
        min_val=Decimal("0.0"),
        default=Decimal("0.0"),
    )
    cleaned["unpaid_leaves"] = unpaid_leaves

    # Consistent Total Leave calculation:
    total_leaves = paid_leaves + unpaid_leaves
    cleaned["total_leaves"] = total_leaves

    # -------------------------------------------------------------------------
    # 7. Total Accounted Days vs Total Working Days Consistency Check
    # -------------------------------------------------------------------------
    working_days_dec = Decimal(str(cleaned.get("total_working_days", 30)))
    accounted_days = present_days + total_leaves

    if accounted_days > working_days_dec:
        excess_msg = (
            f"The total of days worked ({present_days}) and leave days ({total_leaves}) "
            f"equals {accounted_days} days, which exceeds the configured working days ({working_days_dec})."
        )
        errors["present_days"] = excess_msg
        errors["paid_leaves"] = "Days worked plus all leaves cannot exceed total working days."

    # Calculate unaccounted absent days (e.g., unauthorized absent days without leave)
    absent_days = max(Decimal("0.0"), working_days_dec - accounted_days)
    cleaned["absent_days"] = absent_days

    # -------------------------------------------------------------------------
    # 8. Overtime Hours and Hourly Overtime Rate
    # -------------------------------------------------------------------------
    overtime_hours = parse_decimal_field(
        form_data.get("overtime_hours"),
        "overtime_hours",
        errors,
        allow_zero=True,
        min_val=Decimal("0.0"),
        max_val=Decimal("300.00"),
        default=Decimal("0.00"),
    )
    cleaned["overtime_hours"] = overtime_hours

    # Overtime rate per hour
    # If not provided, fallback to employee's hourly rate from salary_settings if available
    default_ot_rate = Decimal("0.00")
    if employee and employee.get("hourly_rate"):
        try:
            default_ot_rate = Decimal(str(employee["hourly_rate"]))
        except Exception:
            default_ot_rate = Decimal("0.00")

    raw_ot_rate = form_data.get("overtime_rate")
    if raw_ot_rate is not None and str(raw_ot_rate).strip() != "":
        overtime_rate = parse_decimal_field(
            raw_ot_rate,
            "overtime_rate",
            errors,
            allow_zero=True,
            min_val=Decimal("0.0"),
            default=default_ot_rate,
        )
    else:
        overtime_rate = default_ot_rate
    cleaned["overtime_rate"] = overtime_rate

    # -------------------------------------------------------------------------
    # 9. Notes / Justification
    # -------------------------------------------------------------------------
    notes = (form_data.get("notes") or "").strip()
    if len(notes) > 255:
        errors["notes"] = "Notes cannot exceed 255 characters."
    cleaned["notes"] = notes or None

    if errors:
        return None, errors
    return cleaned, {}
