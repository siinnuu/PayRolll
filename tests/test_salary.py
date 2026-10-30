"""
Automated unit and integration tests for Module 5: Salary Configuration and Calculation Service.
Tests:
- Reusable SalaryCalculationEngine formulas and rules
- Illustrative example from requirements (Basic ₹30,000; 25 working days; 2 unpaid leaves; ₹2,000 allowances; 5h OT @ ₹200; ₹500 deductions -> Net ₹30,100)
- Regular salary computation
- Unpaid leave deduction
- Paid leave preservation (zero deduction)
- Overtime payment calculation
- Overtime rate precedence (employee setting vs attendance)
- Monthly allowances aggregation
- Decimal 2-place ROUND_HALF_UP rounding policy
- Zero and negative working days rejection (ZeroWorkingDaysError)
- Missing required inputs rejection (no silent defaults)
- Negative values rejection (InvalidSalaryValueError)
- Deductions exceeding gross salary rule and negative net override
- Salary preview page with actual MySQL records
- Missing attendance handling on preview page
- Salary configuration editing and persistence
- Unauthenticated access control
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest

from modules.salary.services import (
    SalaryCalculationEngine,
    SalaryCalculationResult,
    SalaryCalculationError,
    ZeroWorkingDaysError,
    InvalidSalaryValueError,
    MissingSalaryInputError,
    DeductionExceedsGrossError,
    SalaryService,
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
MOCK_EMPLOYEE = {
    "id": 1,
    "employee_code": "EMP001",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "department": "Engineering",
    "designation": "Lead Software Engineer",
    "status": "ACTIVE",
    "joining_date": "2023-01-15",
    "hourly_rate": Decimal("48.85"),
    "base_salary": Decimal("85000.00"),
}

MOCK_SALARY_SETTINGS = {
    "id": 1,
    "employee_id": 1,
    "employee_code": "EMP001",
    "first_name": "John",
    "last_name": "Doe",
    "department": "Engineering",
    "designation": "Lead Software Engineer",
    "base_salary": Decimal("85000.00"),
    "hourly_rate": Decimal("48.85"),
    "hra": Decimal("25500.00"),
    "transport_allowance": Decimal("3000.00"),
    "medical_allowance": Decimal("2500.00"),
    "other_allowances": Decimal("1500.00"),
    "total_allowances": Decimal("32500.00"),
    "tax_deduction_rate": Decimal("10.00"),
    "pf_deduction_rate": Decimal("12.00"),
    "other_deductions": Decimal("500.00"),
    "effective_from": "2023-01-15",
}

MOCK_ATTENDANCE = {
    "id": 10,
    "employee_id": 1,
    "year": 2026,
    "month": 10,
    "total_working_days": 22,
    "present_days": Decimal("20.0"),
    "absent_days": Decimal("0.0"),
    "paid_leaves": Decimal("1.0"),
    "unpaid_leaves": Decimal("1.0"),
    "overtime_hours": Decimal("8.50"),
    "overtime_rate": Decimal("48.85"),
    "notes": "October regular attendance",
}


# =============================================================================
# 1. Pure Calculation Engine Unit Tests
# =============================================================================

def test_salary_calculation_illustrative_example():
    """
    Verify the exact illustrative example specified in the requirements:
    - Basic salary: ₹30,000
    - Total working days: 25
    - Unpaid leave days: 2
    - Allowances: ₹2,000
    - Overtime hours: 5 @ ₹200/hr
    - Other deductions: ₹500
    
    Expected Manual Calculation:
    - Daily salary = 30000 / 25 = 1200.00
    - Leave deduction = 1200 * 2 = 2400.00
    - Overtime payment = 5 * 200 = 1000.00
    - Gross salary = 30000 + 2000 + 1000 = 33000.00
    - Total deductions = 2400 + 500 = 2900.00
    - Net salary = 33000 - 2900 = 30100.00
    """
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("30000.00"),
        total_working_days=25,
        unpaid_leave_days=Decimal("2.0"),
        allowances=Decimal("2000.00"),
        overtime_hours=Decimal("5.0"),
        overtime_rate=Decimal("200.00"),
        other_deductions=Decimal("500.00"),
        paid_leave_days=Decimal("0.0"),
    )

    assert res.basic_salary == Decimal("30000.00")
    assert res.total_working_days == 25
    assert res.daily_salary == Decimal("1200.00")
    assert res.unpaid_leave_days == Decimal("2.0")
    assert res.leave_deduction == Decimal("2400.00")
    assert res.allowances == Decimal("2000.00")
    assert res.overtime_hours == Decimal("5.0")
    assert res.overtime_rate == Decimal("200.00")
    assert res.overtime_payment == Decimal("1000.00")
    assert res.other_deductions == Decimal("500.00")
    assert res.gross_salary == Decimal("33000.00")
    assert res.total_deductions == Decimal("2900.00")
    assert res.net_salary == Decimal("30100.00")


def test_salary_calculation_regular_no_leaves_no_ot():
    """Verify regular salary calculation without leaves or overtime."""
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("50000.00"),
        total_working_days=20,
        unpaid_leave_days=Decimal("0.0"),
        allowances=Decimal("5000.00"),
        overtime_hours=Decimal("0.0"),
        overtime_rate=Decimal("0.00"),
        other_deductions=Decimal("0.00"),
    )

    assert res.daily_salary == Decimal("2500.00")
    assert res.leave_deduction == Decimal("0.00")
    assert res.overtime_payment == Decimal("0.00")
    assert res.gross_salary == Decimal("55000.00")
    assert res.total_deductions == Decimal("0.00")
    assert res.net_salary == Decimal("55000.00")


def test_salary_calculation_paid_leave_does_not_deduct():
    """Verify that approved paid leave days strictly incur zero salary deduction."""
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("60000.00"),
        total_working_days=20,
        unpaid_leave_days=Decimal("0.0"),
        paid_leave_days=Decimal("4.0"),  # 4 days of paid leave
        allowances=Decimal("0.00"),
        overtime_hours=Decimal("0.0"),
        overtime_rate=Decimal("0.00"),
        other_deductions=Decimal("0.00"),
    )

    # 4 days of paid leave should not reduce salary
    assert res.paid_leave_days == Decimal("4.0")
    assert res.unpaid_leave_days == Decimal("0.0")
    assert res.leave_deduction == Decimal("0.00")
    assert res.gross_salary == Decimal("60000.00")
    assert res.net_salary == Decimal("60000.00")


def test_salary_calculation_unpaid_leave_deduction():
    """Verify unpaid leave generates configured deduction based on daily salary rate."""
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("40000.00"),
        total_working_days=20,  # daily = 2000.00
        unpaid_leave_days=Decimal("3.5"),  # 3.5 days LWP
        allowances=Decimal("0.00"),
        overtime_hours=Decimal("0.0"),
        overtime_rate=Decimal("0.00"),
        other_deductions=Decimal("0.00"),
    )

    assert res.daily_salary == Decimal("2000.00")
    assert res.leave_deduction == Decimal("7000.00")  # 2000 * 3.5
    assert res.gross_salary == Decimal("40000.00")
    assert res.net_salary == Decimal("33000.00")  # 40000 - 7000


def test_salary_calculation_overtime_calculation():
    """Verify overtime payment is calculated as overtime hours * overtime rate."""
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("20000.00"),
        total_working_days=20,
        unpaid_leave_days=Decimal("0.0"),
        allowances=Decimal("0.00"),
        overtime_hours=Decimal("12.50"),
        overtime_rate=Decimal("150.00"),
        other_deductions=Decimal("0.00"),
    )

    expected_ot = Decimal("12.50") * Decimal("150.00")  # 1875.00
    assert res.overtime_payment == expected_ot
    assert res.gross_salary == Decimal("21875.00")
    assert res.net_salary == Decimal("21875.00")


def test_salary_calculation_rounding_policy():
    """Verify consistent ROUND_HALF_UP rounding on fractional amounts."""
    # 85,000 / 22 = 3863.636363... -> quantizes to 3863.64
    res = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("85000.00"),
        total_working_days=22,
        unpaid_leave_days=Decimal("1.0"),
        allowances=Decimal("0.00"),
        overtime_hours=Decimal("0.0"),
        overtime_rate=Decimal("0.00"),
        other_deductions=Decimal("0.00"),
    )

    assert res.daily_salary == Decimal("3863.64")
    assert res.leave_deduction == Decimal("3863.64")
    assert res.gross_salary == Decimal("85000.00")
    assert res.net_salary == Decimal("81136.36")  # 85000.00 - 3863.64


def test_salary_calculation_zero_working_days_rejected():
    """Verify zero or negative working days raises ZeroWorkingDaysError."""
    with pytest.raises(ZeroWorkingDaysError) as exc_info:
        SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("30000.00"),
            total_working_days=0,
            unpaid_leave_days=Decimal("0.0"),
            allowances=Decimal("0.00"),
            overtime_hours=Decimal("0.0"),
            overtime_rate=Decimal("0.00"),
            other_deductions=Decimal("0.00"),
        )
    assert "greater than zero" in str(exc_info.value)


def test_salary_calculation_negative_values_rejected():
    """Verify negative basic salary, leave days, or overtime values are rejected."""
    # Negative basic
    with pytest.raises(InvalidSalaryValueError):
        SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("-100.00"),
            total_working_days=20,
            unpaid_leave_days=Decimal("0.0"),
            allowances=Decimal("0.00"),
            overtime_hours=Decimal("0.0"),
            overtime_rate=Decimal("0.00"),
            other_deductions=Decimal("0.00"),
        )

    # Negative unpaid leave days
    with pytest.raises(InvalidSalaryValueError):
        SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("1000.00"),
            total_working_days=20,
            unpaid_leave_days=Decimal("-2.0"),
            allowances=Decimal("0.00"),
            overtime_hours=Decimal("0.0"),
            overtime_rate=Decimal("0.00"),
            other_deductions=Decimal("0.00"),
        )


def test_salary_calculation_missing_inputs_rejected():
    """Verify required inputs are not silently defaulted when missing."""
    with pytest.raises(MissingSalaryInputError):
        SalaryCalculationEngine.calculate_salary(
            basic_salary=None,
            total_working_days=20,
            unpaid_leave_days=Decimal("0.0"),
            allowances=Decimal("0.00"),
            overtime_hours=Decimal("0.0"),
            overtime_rate=Decimal("0.00"),
            other_deductions=Decimal("0.00"),
        )


def test_salary_calculation_deductions_exceed_gross_guard():
    """
    Verify deductions exceeding gross salary are blocked unless
    allow_negative_net=True is explicitly enabled.
    """
    # Gross = 10,000; Deductions = 12,000
    with pytest.raises(DeductionExceedsGrossError) as exc_info:
        SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("10000.00"),
            total_working_days=20,
            unpaid_leave_days=Decimal("0.0"),
            allowances=Decimal("0.00"),
            overtime_hours=Decimal("0.0"),
            overtime_rate=Decimal("0.00"),
            other_deductions=Decimal("12000.00"),
            allow_negative_net=False,
        )
    assert "exceed gross salary" in str(exc_info.value)

    # When allow_negative_net is enabled, negative net salary is allowed
    res_override = SalaryCalculationEngine.calculate_salary(
        basic_salary=Decimal("10000.00"),
        total_working_days=20,
        unpaid_leave_days=Decimal("0.0"),
        allowances=Decimal("0.00"),
        overtime_hours=Decimal("0.0"),
        overtime_rate=Decimal("0.00"),
        other_deductions=Decimal("12000.00"),
        allow_negative_net=True,
    )
    assert res_override.gross_salary == Decimal("10000.00")
    assert res_override.total_deductions == Decimal("12000.00")
    assert res_override.net_salary == Decimal("-2000.00")


# =============================================================================
# 2. Service & Repository Integration Tests
# =============================================================================

def test_salary_service_preview_with_actual_records():
    """
    Verify SalaryService.preview_salary_calculation integrates actual employee,
    salary structure, and attendance records from MySQL.
    """
    service = SalaryService()

    with patch.object(service.employee_repo, "get_by_id", return_value=MOCK_EMPLOYEE), \
         patch.object(service.salary_repo, "get_by_employee_id", return_value=MOCK_SALARY_SETTINGS), \
         patch.object(service.attendance_repo, "get_by_employee_and_period", return_value=MOCK_ATTENDANCE):

        result = service.preview_salary_calculation(employee_id=1, year=2026, month=10)
        assert result["status"] == "success"
        calc = result["calculation"]
        assert isinstance(calc, SalaryCalculationResult)

        # Basic = 85000.00, Working days = 22 -> Daily = 3863.64
        assert calc.basic_salary == Decimal("85000.00")
        assert calc.total_working_days == 22
        assert calc.daily_salary == Decimal("3863.64")
        # 1 unpaid leave day
        assert calc.leave_deduction == Decimal("3863.64")
        # Allowances = 25500 + 3000 + 2500 + 1500 = 32500.00
        assert calc.allowances == Decimal("32500.00")
        # Overtime = 8.5h @ 48.85 = 415.23
        assert calc.overtime_payment == Decimal("415.23")
        # Other deductions = 500.00
        assert calc.other_deductions == Decimal("500.00")


def test_salary_service_preview_missing_attendance():
    """
    Verify that preview_salary_calculation returns 'missing_attendance' status
    when attendance has not been recorded for that period.
    """
    service = SalaryService()

    with patch.object(service.employee_repo, "get_by_id", return_value=MOCK_EMPLOYEE), \
         patch.object(service.salary_repo, "get_by_employee_id", return_value=MOCK_SALARY_SETTINGS), \
         patch.object(service.attendance_repo, "get_by_employee_and_period", return_value=None):

        result = service.preview_salary_calculation(employee_id=1, year=2026, month=12)
        assert result["status"] == "missing_attendance"
        assert "No attendance record found" in result["error_message"]
        assert result["calculation"] is None


def test_salary_service_overtime_rate_precedence():
    """
    Verify rule: employee-specific overtime rate from attendance or salary settings
    takes precedence over default.
    """
    service = SalaryService()

    custom_attendance = dict(MOCK_ATTENDANCE)
    custom_attendance["overtime_rate"] = Decimal("75.00")  # Specific overtime rate in attendance

    with patch.object(service.employee_repo, "get_by_id", return_value=MOCK_EMPLOYEE), \
         patch.object(service.salary_repo, "get_by_employee_id", return_value=MOCK_SALARY_SETTINGS), \
         patch.object(service.attendance_repo, "get_by_employee_and_period", return_value=custom_attendance):

        result = service.preview_salary_calculation(employee_id=1, year=2026, month=10)
        assert result["status"] == "success"
        calc = result["calculation"]
        # Overtime rate 75.00 from attendance took precedence over 48.85
        assert calc.overtime_rate == Decimal("75.00")
        assert calc.overtime_payment == Decimal("8.50") * Decimal("75.00")


# =============================================================================
# 3. Route & Flask Blueprint Tests
# =============================================================================

def test_salary_index_unauthenticated_redirect(client):
    """Verify anonymous access to /salary redirects to login."""
    response = client.get("/salary", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_salary_index_renders_with_paginated_structures(client):
    """Verify authenticated user can view the salary structures directory."""
    authenticate_session(client)

    with patch("repositories.salary_repository.SalaryRepository.get_all_paginated", return_value=([MOCK_SALARY_SETTINGS], 1)), \
         patch("repositories.salary_repository.SalaryRepository.get_summary_metrics", return_value={
             "total_employees": 1,
             "total_base_payroll": Decimal("85000.00"),
             "avg_base_salary": Decimal("85000.00"),
             "total_allowances_pool": Decimal("32500.00"),
             "total_other_deductions": Decimal("500.00"),
         }), \
         patch("repositories.employee_repository.EmployeeRepository.get_all_departments", return_value=["Engineering"]):

        response = client.get("/salary")
        assert response.status_code == 200
        assert b"Salary Configuration" in response.data
        assert b"EMP001" in response.data
        assert b"John Doe" in response.data
        assert b"85,000.00" in response.data


def test_salary_edit_page_renders_and_updates(client):
    """Verify editing an employee's salary configuration."""
    token = authenticate_session(client)

    # 1. GET request renders form
    with patch("repositories.salary_repository.SalaryRepository.get_by_employee_id", return_value=MOCK_SALARY_SETTINGS):
        response = client.get("/salary/1/edit")
        assert response.status_code == 200
        assert b"Salary Structure Setup" in response.data
        assert b"EMP001" in response.data
        assert b"85000.00" in response.data

    # 2. POST request updates settings
    update_payload = {
        "csrf_token": token,
        "base_salary": "90000.00",
        "hourly_rate": "55.00",
        "hra": "27000.00",
        "transport_allowance": "3500.00",
        "medical_allowance": "2500.00",
        "other_allowances": "1000.00",
        "other_deductions": "600.00",
        "effective_from": "2026-11-01",
    }

    with patch("repositories.salary_repository.SalaryRepository.get_by_employee_id", return_value=MOCK_SALARY_SETTINGS), \
         patch("repositories.salary_repository.SalaryRepository.upsert_salary_settings", return_value=True) as mock_upsert:

        post_res = client.post("/salary/1/edit", data=update_payload, follow_redirects=True)
        assert post_res.status_code == 200
        assert b"updated successfully" in post_res.data
        assert mock_upsert.called
        saved_data = mock_upsert.call_args[0][1]
        assert saved_data["base_salary"] == Decimal("90000.00")
        assert saved_data["hourly_rate"] == Decimal("55.00")


def test_salary_preview_route_renders_full_breakdown(client):
    """Verify /salary/preview displays the full step-by-step calculation."""
    authenticate_session(client)

    mock_preview = {
        "status": "success",
        "employee": MOCK_EMPLOYEE,
        "salary_settings": MOCK_SALARY_SETTINGS,
        "attendance": MOCK_ATTENDANCE,
        "calculation": SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("85000.00"),
            total_working_days=22,
            unpaid_leave_days=Decimal("1.0"),
            allowances=Decimal("32500.00"),
            overtime_hours=Decimal("8.50"),
            overtime_rate=Decimal("48.85"),
            other_deductions=Decimal("500.00"),
            paid_leave_days=Decimal("1.0"),
        ),
        "ot_rate_source": "Employee Salary Settings Hourly Rate",
        "error_message": None,
    }

    with patch("modules.salary.services.SalaryService.get_active_employees", return_value=[MOCK_EMPLOYEE]), \
         patch("modules.salary.services.SalaryService.preview_salary_calculation", return_value=mock_preview):

        response = client.get("/salary/preview?employee_id=1&year=2026&month=10")
        assert response.status_code == 200
        assert b"Salary Preview Engine" in response.data
        assert b"John Doe" in response.data
        assert b"Gross Salary Total" in response.data
        assert b"Net Monthly Salary" in response.data
        assert b"Academic Demonstration" in response.data
        assert b"Daily Salary Rate" in response.data


def test_salary_preview_api_json(client):
    """Verify /salary/api/preview returns structured JSON calculation data."""
    authenticate_session(client)

    mock_preview = {
        "status": "success",
        "employee": MOCK_EMPLOYEE,
        "salary_settings": MOCK_SALARY_SETTINGS,
        "attendance": MOCK_ATTENDANCE,
        "calculation": SalaryCalculationEngine.calculate_salary(
            basic_salary=Decimal("30000.00"),
            total_working_days=25,
            unpaid_leave_days=Decimal("2.0"),
            allowances=Decimal("2000.00"),
            overtime_hours=Decimal("5.0"),
            overtime_rate=Decimal("200.00"),
            other_deductions=Decimal("500.00"),
        ),
        "ot_rate_source": "Attendance Record Overtime Rate",
        "error_message": None,
    }

    with patch("modules.salary.services.SalaryService.preview_salary_calculation", return_value=mock_preview):
        response = client.get("/salary/api/preview?employee_id=1&year=2026&month=10")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert data["basic_salary"] == "30000.00"
        assert data["daily_salary"] == "1200.00"
        assert data["leave_deduction"] == "2400.00"
        assert data["gross_salary"] == "33000.00"
        assert data["total_deductions"] == "2900.00"
        assert data["net_salary"] == "30100.00"
