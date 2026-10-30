"""
Automated unit and integration tests for Attendance and Leave Management (Module 4).
Tests:
- Valid attendance creation and storage
- Invalid months, years, or formats
- Negative day counts or overtime rejection
- Excess leave rejection (days worked + leaves > configured working days)
- Duplicate monthly attendance summary per employee enforcement
- Employee lookup & nonexistent employee rejection
- Inactive employee rejection
- Attendance history ledger for individual employee
- Editing existing attendance records
- Weekend/holiday working days calculation logic
- Working days API helper endpoint
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest

from modules.attendance.validators import (
    calculate_default_working_days,
    get_month_calendar_info,
    validate_attendance_data,
)


def authenticate_session(client, user_id=1, username="admin", role="ADMIN", token="valid_test_csrf_token_999"):
    """Helper to inject an authenticated session with a valid CSRF token."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["email"] = f"{username}@payroll.local"
        sess["role"] = role
        sess["_csrf_token"] = token
    return token


# Mock Employee Fixtures
MOCK_EMPLOYEE_ACTIVE = {
    "id": 1,
    "employee_code": "EMP001",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "department": "Engineering",
    "designation": "Lead Software Engineer",
    "status": "ACTIVE",
    "hourly_rate": Decimal("48.85"),
    "base_salary": Decimal("85000.00"),
}

MOCK_EMPLOYEE_INACTIVE = {
    "id": 2,
    "employee_code": "EMP002",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane.smith@example.com",
    "department": "Finance",
    "designation": "Financial Analyst",
    "status": "INACTIVE",
    "hourly_rate": Decimal("35.00"),
    "base_salary": Decimal("60000.00"),
}

MOCK_ATTENDANCE_RECORD = {
    "id": 101,
    "attendance_id": 101,
    "employee_id": 1,
    "employee_code": "EMP001",
    "first_name": "John",
    "last_name": "Doe",
    "department": "Engineering",
    "designation": "Lead Software Engineer",
    "employee_status": "ACTIVE",
    "year": 2026,
    "month": 10,
    "total_working_days": 22,
    "present_days": Decimal("20.0"),
    "absent_days": Decimal("0.0"),
    "paid_leaves": Decimal("1.0"),
    "unpaid_leaves": Decimal("1.0"),
    "total_leaves": Decimal("2.0"),
    "overtime_hours": Decimal("5.50"),
    "overtime_rate": Decimal("48.85"),
    "notes": "Regular October attendance",
    "created_at": "2026-10-31 17:00:00",
    "updated_at": "2026-10-31 17:00:00",
}


# =============================================================================
# 1. Access Control Tests
# =============================================================================

def test_attendance_index_unauthenticated_redirect(client):
    """Verify anonymous requests redirect to login."""
    response = client.get("/attendance", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_attendance_add_unauthenticated_redirect(client):
    """Verify anonymous access to attendance form redirects to login."""
    response = client.get("/attendance/add", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


# =============================================================================
# 2. Listing & Directory Tests
# =============================================================================

def test_attendance_index_renders_with_records_and_summary(client):
    """Verify attendance directory renders records, summary metrics, and filters."""
    authenticate_session(client)

    mock_summary = {
        "total_records": 1,
        "total_working_days": 22,
        "total_present_days": Decimal("20.0"),
        "total_paid_leaves": Decimal("1.0"),
        "total_unpaid_leaves": Decimal("1.0"),
        "total_leaves": Decimal("2.0"),
        "total_absent_days": Decimal("0.0"),
        "total_overtime_hours": Decimal("5.50"),
        "total_overtime_cost": Decimal("268.68"),
        "attendance_rate": 90.9,
    }

    with patch("repositories.attendance_repository.AttendanceRepository.get_paginated_attendance", return_value=([MOCK_ATTENDANCE_RECORD], 1)), \
         patch("repositories.attendance_repository.AttendanceRepository.get_monthly_summary", return_value=mock_summary), \
         patch("repositories.employee_repository.EmployeeRepository.get_active_employees", return_value=[MOCK_EMPLOYEE_ACTIVE]), \
         patch("repositories.attendance_repository.AttendanceRepository.get_available_years", return_value=[2026]):

        response = client.get("/attendance")
        assert response.status_code == 200
        assert b"Attendance &amp; Leave Management" in response.data or b"Attendance & Leave Management" in response.data
        assert b"EMP001" in response.data
        assert b"John Doe" in response.data
        assert b"October 2026" in response.data
        assert b"20.0" in response.data
        assert b"5.50 hrs" in response.data or b"5.5" in response.data


def test_attendance_filter_by_month_and_year(client):
    """Verify search and period filters pass query arguments to repository."""
    authenticate_session(client)

    with patch("repositories.attendance_repository.AttendanceRepository.get_paginated_attendance", return_value=([], 0)) as mock_query, \
         patch("repositories.attendance_repository.AttendanceRepository.get_monthly_summary", return_value={}), \
         patch("repositories.employee_repository.EmployeeRepository.get_active_employees", return_value=[MOCK_EMPLOYEE_ACTIVE]), \
         patch("repositories.attendance_repository.AttendanceRepository.get_available_years", return_value=[2026]):

        response = client.get("/attendance?year=2026&month=10&search=Engineering&employee_id=1")
        assert response.status_code == 200
        mock_query.assert_called_once_with(
            employee_id=1,
            year=2026,
            month=10,
            search="Engineering",
            page=1,
            per_page=10
        )


# =============================================================================
# 3. Add Attendance Tests (Valid & Validation Rules)
# =============================================================================

def test_attendance_add_page_renders_with_active_employees(client):
    """Verify GET /attendance/add renders form populated with active employees."""
    authenticate_session(client)

    with patch("repositories.employee_repository.EmployeeRepository.get_active_employees", return_value=[MOCK_EMPLOYEE_ACTIVE]):
        response = client.get("/attendance/add")
        assert response.status_code == 200
        assert b"Record Monthly Attendance" in response.data
        assert b"John Doe (EMP001)" in response.data
        assert b"Weekend &amp; Holiday Working Day Rule" in response.data or b"Weekend & Holiday" in response.data


def test_attendance_add_valid_record_success(client):
    """Verify successfully adding a monthly attendance record with proper parameters."""
    token = authenticate_session(client)

    payload = {
        "csrf_token": token,
        "employee_id": "1",
        "year": "2026",
        "month": "10",
        "total_working_days": "22",
        "present_days": "20.0",
        "paid_leaves": "1.0",
        "unpaid_leaves": "1.0",
        "overtime_hours": "5.50",
        "overtime_rate": "48.85",
        "notes": "Full month with 1 paid and 1 unpaid leave",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
         patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=None), \
         patch("repositories.attendance_repository.AttendanceRepository.create_attendance", return_value=101) as mock_create:

        response = client.post("/attendance/add", data=payload, follow_redirects=True)
        assert response.status_code == 200
        assert b"Monthly attendance record created successfully." in response.data
        assert mock_create.called
        created_data = mock_create.call_args[0][0]
        assert created_data["employee_id"] == 1
        assert created_data["year"] == 2026
        assert created_data["month"] == 10
        assert created_data["total_working_days"] == 22
        assert created_data["present_days"] == Decimal("20.0")
        assert created_data["paid_leaves"] == Decimal("1.0")
        assert created_data["unpaid_leaves"] == Decimal("1.0")
        assert created_data["total_leaves"] == Decimal("2.0")
        assert created_data["overtime_hours"] == Decimal("5.50")
        assert created_data["overtime_rate"] == Decimal("48.85")


def test_attendance_add_excess_leave_rejected(client):
    """
    Verify rejection when sum of days worked + paid leaves + unpaid leaves
    exceeds total configured working days.
    """
    token = authenticate_session(client)

    # 20 days worked + 2 paid + 2 unpaid = 24 days > 22 working days
    payload = {
        "csrf_token": token,
        "employee_id": "1",
        "year": "2026",
        "month": "10",
        "total_working_days": "22",
        "present_days": "20.0",
        "paid_leaves": "2.0",
        "unpaid_leaves": "2.0",
        "overtime_hours": "0",
        "overtime_rate": "48.85",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
         patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=None):

        response = client.post("/attendance/add", data=payload)
        assert response.status_code == 422
        assert b"exceeds the configured working days" in response.data or b"cannot exceed total working days" in response.data


def test_attendance_add_duplicate_monthly_summary_rejected(client):
    """
    Verify enforcement of one monthly attendance summary per employee.
    Duplicate (employee_id, year, month) must be rejected.
    """
    token = authenticate_session(client)

    payload = {
        "csrf_token": token,
        "employee_id": "1",
        "year": "2026",
        "month": "10",
        "total_working_days": "22",
        "present_days": "22.0",
        "paid_leaves": "0",
        "unpaid_leaves": "0",
        "overtime_hours": "0",
    }

    existing_record = {"id": 99, "employee_id": 1, "year": 2026, "month": 10}

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
         patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=existing_record):

        response = client.post("/attendance/add", data=payload)
        assert response.status_code == 422
        assert b"already exists" in response.data
        assert b"Only one attendance record per employee per month is allowed" in response.data


def test_attendance_add_negative_values_rejected(client):
    """Verify rejection of negative day counts or negative overtime."""
    token = authenticate_session(client)

    test_cases = [
        {"present_days": "-5.0"},
        {"paid_leaves": "-1.0"},
        {"unpaid_leaves": "-2.0"},
        {"overtime_hours": "-3.5"},
        {"overtime_rate": "-10.00"},
        {"total_working_days": "-20"},
    ]

    for bad_field in test_cases:
        payload = {
            "csrf_token": token,
            "employee_id": "1",
            "year": "2026",
            "month": "10",
            "total_working_days": "22",
            "present_days": "20.0",
            "paid_leaves": "0",
            "unpaid_leaves": "0",
            "overtime_hours": "0",
            "overtime_rate": "48.85",
        }
        payload.update(bad_field)

        with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
             patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=None):

            response = client.post("/attendance/add", data=payload)
            assert response.status_code == 422
            assert b"cannot be negative" in response.data or b"greater than zero" in response.data


def test_attendance_add_invalid_month_rejected(client):
    """Verify month must be strictly between 1 and 12."""
    token = authenticate_session(client)

    for invalid_month in ["0", "13", "99", "-1"]:
        payload = {
            "csrf_token": token,
            "employee_id": "1",
            "year": "2026",
            "month": invalid_month,
            "total_working_days": "22",
            "present_days": "20.0",
            "paid_leaves": "0",
            "unpaid_leaves": "0",
        }

        with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
             patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=None):

            response = client.post("/attendance/add", data=payload)
            assert response.status_code == 422
            assert b"Month must be between 1" in response.data or b"Invalid month" in response.data


def test_attendance_add_nonexistent_employee_rejected(client):
    """Verify rejection when employee does not exist in the database."""
    token = authenticate_session(client)

    payload = {
        "csrf_token": token,
        "employee_id": "99999",
        "year": "2026",
        "month": "10",
        "total_working_days": "22",
        "present_days": "20.0",
        "paid_leaves": "0",
        "unpaid_leaves": "0",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=None):
        response = client.post("/attendance/add", data=payload)
        assert response.status_code == 422
        assert b"does not exist in the database" in response.data


def test_attendance_add_inactive_employee_rejected(client):
    """Verify rejection when trying to create attendance for an inactive employee."""
    token = authenticate_session(client)

    payload = {
        "csrf_token": token,
        "employee_id": "2",
        "year": "2026",
        "month": "10",
        "total_working_days": "22",
        "present_days": "20.0",
        "paid_leaves": "0",
        "unpaid_leaves": "0",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_INACTIVE):
        response = client.post("/attendance/add", data=payload)
        assert response.status_code == 422
        assert b"Cannot create attendance for inactive employee" in response.data


# =============================================================================
# 4. Edit Attendance Tests
# =============================================================================

def test_attendance_edit_page_renders_with_record(client):
    """Verify GET /attendance/<id>/edit renders form populated with existing record."""
    authenticate_session(client)

    with patch("repositories.attendance_repository.AttendanceRepository.get_by_id", return_value=MOCK_ATTENDANCE_RECORD), \
         patch("repositories.employee_repository.EmployeeRepository.get_active_employees", return_value=[MOCK_EMPLOYEE_ACTIVE]):

        response = client.get("/attendance/101/edit")
        assert response.status_code == 200
        assert b"Edit Attendance Record" in response.data
        assert b"John Doe" in response.data
        assert b"EMP001" in response.data
        assert b"20.0" in response.data


def test_attendance_edit_success_updates_record(client):
    """Verify updating existing attendance record updates correctly."""
    token = authenticate_session(client)

    update_payload = {
        "csrf_token": token,
        "total_working_days": "22",
        "present_days": "21.0",
        "paid_leaves": "1.0",
        "unpaid_leaves": "0.0",
        "overtime_hours": "8.00",
        "overtime_rate": "48.85",
        "notes": "Updated: converted unpaid leave to approved present day",
    }

    with patch("repositories.attendance_repository.AttendanceRepository.get_by_id", return_value=MOCK_ATTENDANCE_RECORD), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
         patch("repositories.attendance_repository.AttendanceRepository.get_by_employee_and_period", return_value=MOCK_ATTENDANCE_RECORD), \
         patch("repositories.attendance_repository.AttendanceRepository.update_attendance", return_value=True) as mock_update:

        response = client.post("/attendance/101/edit", data=update_payload, follow_redirects=True)
        assert response.status_code == 200
        assert b"updated successfully" in response.data
        assert mock_update.called
        updated_data = mock_update.call_args[0][1]
        assert updated_data["present_days"] == Decimal("21.0")
        assert updated_data["unpaid_leaves"] == Decimal("0.0")
        assert updated_data["overtime_hours"] == Decimal("8.00")


# =============================================================================
# 5. Employee History & API Tests
# =============================================================================

def test_attendance_employee_history_view(client):
    """Verify employee history ledger displays past attendance records and career statistics."""
    authenticate_session(client)

    mock_history = [
        MOCK_ATTENDANCE_RECORD,
        {
            **MOCK_ATTENDANCE_RECORD,
            "id": 100,
            "month": 9,
            "present_days": Decimal("21.0"),
            "paid_leaves": Decimal("1.0"),
            "unpaid_leaves": Decimal("0.0"),
            "total_leaves": Decimal("1.0"),
            "overtime_hours": Decimal("6.50"),
        }
    ]

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=MOCK_EMPLOYEE_ACTIVE), \
         patch("repositories.attendance_repository.AttendanceRepository.get_attendance_history_for_employee", return_value=mock_history):

        response = client.get("/attendance/employee/1")
        assert response.status_code == 200
        assert b"Attendance History &amp; Leave Ledger" in response.data or b"Attendance History" in response.data
        assert b"John Doe" in response.data
        assert b"Engineering" in response.data
        assert b"October 2026" in response.data
        assert b"September 2026" in response.data


def test_attendance_api_working_days_endpoint(client):
    """Verify the /attendance/api/working-days JSON endpoint returns correct calendar calculations."""
    authenticate_session(client)

    response = client.get("/attendance/api/working-days?year=2026&month=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["year"] == 2026
    assert data["month"] == 10
    assert data["total_calendar_days"] == 31
    assert data["default_working_days"] == 22
    assert data["weekend_days"] == 9
    assert "weekend days" in data["explanation"].lower()


# =============================================================================
# 6. Working Days & Leave Domain Logic Tests
# =============================================================================

def test_calculate_default_working_days_weekend_exclusion():
    """Verify working day calculation correctly excludes Saturdays and Sundays."""
    # October 2026 has 31 days.
    # Oct 1 is Thursday, Oct 31 is Saturday.
    # Weekends in Oct 2026: Oct 3,4, 10,11, 17,18, 24,25, 31 (9 weekend days).
    # 31 - 9 = 22 weekdays.
    working_days = calculate_default_working_days(2026, 10, exclude_weekends=True)
    assert working_days == 22

    # September 2026 has 30 days.
    # Sep 1 is Tuesday, Sep 30 is Wednesday.
    # Weekends in Sep 2026: Sep 5,6, 12,13, 19,20, 26,27 (8 weekend days).
    # 30 - 8 = 22 weekdays.
    working_days_sep = calculate_default_working_days(2026, 9, exclude_weekends=True)
    assert working_days_sep == 22

    # February 2024 (leap year, 29 days)
    # Feb 1 is Thursday. 21 weekdays, 8 weekend days.
    working_days_feb = calculate_default_working_days(2024, 2, exclude_weekends=True)
    assert working_days_feb == 21


def test_month_calendar_info_metadata():
    """Verify calendar info returns proper explanation and breakdown."""
    info = get_month_calendar_info(2026, 10)
    assert info["year"] == 2026
    assert info["month"] == 10
    assert info["month_name"] == "October"
    assert info["total_calendar_days"] == 31
    assert info["default_working_days"] == 22
    assert info["weekend_days"] == 9
    assert "consisting of 22 standard working days" in info["explanation"]
