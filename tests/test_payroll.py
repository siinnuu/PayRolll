"""
Automated unit and integration tests for Module 6: Monthly Payroll Processing.
Tests:
- Eligible employees audit for period
- Payroll calculation preview delegation
- Single payroll generation with accurate snapshot preservation
- Duplicate monthly payroll rejection
- Missing attendance and missing salary settings rejection
- Controlled batch payroll execution
- Status transitions lifecycle:
  - DRAFT -> APPROVED
  - DRAFT -> CANCELLED
  - APPROVED -> DRAFT (with explicit adjustment reason)
  - Protected PAID status (cannot be transitioned in Module 6)
  - Forbidden PAID direct assignment (reserved for Module 7)
- Optimistic locking / concurrency safeguards
- Snapshot preservation test (modifying future salary structure does not alter approved payroll)
- Route access control and authenticated rendering (in INR ₹)
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest

from modules.payroll.services import (
    PayrollService,
    DuplicatePayrollError,
    MissingPayrollInputsError,
    InvalidStatusTransitionError,
    PayrollProcessingError,
)
from repositories.payroll_repository import PayrollRepository


def authenticate_session(client, user_id=1, username="accountant", role="ACCOUNTANT", token="valid_test_csrf_token_888"):
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
    "first_name": "Rajesh",
    "last_name": "Kumar",
    "email": "rajesh.kumar@example.com",
    "department": "Engineering",
    "designation": "Senior Engineer",
    "status": "ACTIVE",
    "joining_date": "2023-01-15",
    "hourly_rate": Decimal("200.00"),
    "base_salary": Decimal("30000.00"),
}

MOCK_SALARY_SETTINGS = {
    "id": 1,
    "employee_id": 1,
    "employee_code": "EMP001",
    "first_name": "Rajesh",
    "last_name": "Kumar",
    "department": "Engineering",
    "designation": "Senior Engineer",
    "base_salary": Decimal("30000.00"),
    "hourly_rate": Decimal("200.00"),
    "hra": Decimal("1000.00"),
    "transport_allowance": Decimal("500.00"),
    "medical_allowance": Decimal("300.00"),
    "other_allowances": Decimal("200.00"),
    "total_allowances": Decimal("2000.00"),
    "tax_deduction_rate": Decimal("0.00"),
    "pf_deduction_rate": Decimal("0.00"),
    "other_deductions": Decimal("500.00"),
    "effective_from": "2023-01-15",
}

MOCK_ATTENDANCE = {
    "id": 10,
    "employee_id": 1,
    "year": 2026,
    "month": 10,
    "total_working_days": 25,
    "present_days": Decimal("23.0"),
    "days_worked": Decimal("23.0"),
    "absent_days": Decimal("0.0"),
    "paid_leaves": Decimal("0.0"),
    "paid_leave_days": Decimal("0.0"),
    "unpaid_leaves": Decimal("2.0"),
    "unpaid_leave_days": Decimal("2.0"),
    "overtime_hours": Decimal("5.00"),
    "overtime_rate": Decimal("200.00"),
    "notes": "October regular attendance",
}

MOCK_PAYROLL_RECORD = {
    "id": 101,
    "payroll_id": 101,
    "payroll_code": "PAY-2026-10-EMP001",
    "employee_id": 1,
    "employee_code": "EMP001",
    "first_name": "Rajesh",
    "last_name": "Kumar",
    "full_name": "Rajesh Kumar",
    "department": "Engineering",
    "designation": "Senior Engineer",
    "employee_status": "ACTIVE",
    "year": 2026,
    "month": 10,
    "basic_pay": Decimal("30000.00"),
    "allowances_total": Decimal("2000.00"),
    "overtime_pay": Decimal("1000.00"),
    "gross_pay": Decimal("33000.00"),
    "leave_deduction": Decimal("2400.00"),
    "tax_deduction": Decimal("0.00"),
    "pf_deduction": Decimal("0.00"),
    "other_deductions": Decimal("500.00"),
    "total_deductions": Decimal("2900.00"),
    "net_pay": Decimal("30100.00"),
    "status": "DRAFT",
    "generated_date": "2026-10-29",
    "payment_due_date": None,
    "remarks": "Monthly payroll for October 2026",
    "created_at": "2026-10-29 10:00:00",
    "updated_at": "2026-10-29 10:00:00",
}


# =========================================================================
# 1. Service Layer Tests
# =========================================================================

def test_get_eligible_employees_audit():
    """Verify employee audit correctly classifies eligibility based on inputs and status."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    # 3 active employees:
    # Emp 1: has attendance & salary & no payroll -> ELIGIBLE
    # Emp 2: missing attendance -> INELIGIBLE
    # Emp 3: has existing approved payroll -> INELIGIBLE
    emp1 = {"id": 1, "employee_code": "EMP001", "first_name": "A", "last_name": "One"}
    emp2 = {"id": 2, "employee_code": "EMP002", "first_name": "B", "last_name": "Two"}
    emp3 = {"id": 3, "employee_code": "EMP003", "first_name": "C", "last_name": "Three"}

    emp_repo.get_active_employees.return_value = [emp1, emp2, emp3]

    att_repo.get_by_employee_and_period.side_effect = lambda eid, y, m: (
        MOCK_ATTENDANCE if eid in (1, 3) else None
    )
    sal_repo.get_by_employee_id.side_effect = lambda eid: (
        MOCK_SALARY_SETTINGS if eid in (1, 3) else None
    )
    payroll_repo.get_by_employee_and_period.side_effect = lambda eid, y, m: (
        {"id": 99, "status": "APPROVED", "payroll_code": "PAY-2026-10-EMP003"} if eid == 3 else None
    )

    audited = service.get_eligible_employees_for_period(2026, 10)
    assert len(audited) == 3

    assert audited[0]["employee"]["id"] == 1
    assert audited[0]["is_eligible"] is True

    assert audited[1]["employee"]["id"] == 2
    assert audited[1]["is_eligible"] is False
    assert audited[1]["has_attendance"] is False

    assert audited[2]["employee"]["id"] == 3
    assert audited[2]["is_eligible"] is False
    assert audited[2]["existing_payroll"] is not None


def test_generate_single_payroll_success():
    """Test successful single employee payroll generation with correct formula results."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    payroll_repo.get_by_employee_and_period.return_value = None
    payroll_repo.generate_payroll_code.return_value = "PAY-2026-10-EMP001"
    payroll_repo.create_payroll_record.return_value = 101

    emp_repo.get_by_id.return_value = MOCK_EMPLOYEE
    att_repo.get_by_employee_and_period.return_value = MOCK_ATTENDANCE
    sal_repo.get_by_employee_id.return_value = MOCK_SALARY_SETTINGS

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    payroll_id = service.generate_single_payroll(employee_id=1, year=2026, month=10)
    assert payroll_id == 101

    payroll_repo.create_payroll_record.assert_called_once()
    payload = payroll_repo.create_payroll_record.call_args[0][0]

    assert payload["payroll_code"] == "PAY-2026-10-EMP001"
    assert payload["basic_pay"] == Decimal("30000.00")
    assert payload["allowances_total"] == Decimal("2000.00")
    assert payload["overtime_pay"] == Decimal("1000.00")
    assert payload["gross_pay"] == Decimal("33000.00")
    assert payload["leave_deduction"] == Decimal("2400.00")
    assert payload["other_deductions"] == Decimal("500.00")
    assert payload["total_deductions"] == Decimal("2900.00")
    assert payload["net_pay"] == Decimal("30100.00")
    assert payload["status"] == "DRAFT"


def test_generate_single_payroll_duplicate_rejected():
    """Test duplicate payroll for same employee and period is strictly rejected."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    payroll_repo.get_by_employee_and_period.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "APPROVED",
    }

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    with pytest.raises(DuplicatePayrollError) as exc_info:
        service.generate_single_payroll(employee_id=1, year=2026, month=10)

    assert "already exists" in str(exc_info.value)
    payroll_repo.create_payroll_record.assert_not_called()


def test_generate_single_payroll_missing_attendance_rejected():
    """Test generation without attendance logs raises MissingPayrollInputsError."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    payroll_repo.get_by_employee_and_period.return_value = None
    emp_repo.get_by_id.return_value = MOCK_EMPLOYEE
    att_repo.get_by_employee_and_period.return_value = None  # Missing attendance
    sal_repo.get_by_employee_id.return_value = MOCK_SALARY_SETTINGS

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    with pytest.raises(MissingPayrollInputsError) as exc_info:
        service.generate_single_payroll(employee_id=1, year=2026, month=10)

    assert "No attendance record found" in str(exc_info.value)
    payroll_repo.create_payroll_record.assert_not_called()


def test_generate_single_payroll_missing_salary_settings_rejected():
    """Test generation without salary settings raises MissingPayrollInputsError."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    payroll_repo.get_by_employee_and_period.return_value = None
    emp_repo.get_by_id.return_value = MOCK_EMPLOYEE
    att_repo.get_by_employee_and_period.return_value = MOCK_ATTENDANCE
    sal_repo.get_by_employee_id.return_value = None  # Missing salary settings

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    with pytest.raises(MissingPayrollInputsError) as exc_info:
        service.generate_single_payroll(employee_id=1, year=2026, month=10)

    assert "No salary structure configured" in str(exc_info.value)
    payroll_repo.create_payroll_record.assert_not_called()


def test_batch_payroll_run_execution():
    """Test batch payroll run generates records for eligible staff and skips ineligible ones."""
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    emp1 = {"id": 1, "employee_code": "EMP001", "first_name": "Rajesh", "last_name": "Kumar"}
    emp2 = {"id": 2, "employee_code": "EMP002", "first_name": "Priya", "last_name": "Sharma"}

    emp_repo.get_active_employees.return_value = [emp1, emp2]
    # Emp 1 eligible, Emp 2 missing attendance
    att_repo.get_by_employee_and_period.side_effect = lambda eid, y, m: (
        MOCK_ATTENDANCE if eid == 1 else None
    )
    sal_repo.get_by_employee_id.side_effect = lambda eid: (
        MOCK_SALARY_SETTINGS if eid in (1, 2) else None
    )
    payroll_repo.get_by_employee_and_period.return_value = None
    payroll_repo.generate_payroll_code.return_value = "PAY-2026-10-EMP001"
    payroll_repo.create_payroll_record.return_value = 101

    emp_repo.get_by_id.side_effect = lambda eid: emp1 if eid == 1 else emp2

    res = service.generate_batch_payroll_run(year=2026, month=10)

    assert res["total_candidates"] == 2
    assert res["successful_count"] == 1
    assert res["skipped_count"] == 1
    assert res["successful"][0]["employee_id"] == 1
    assert res["skipped"][0]["employee_id"] == 2
    assert "Missing attendance" in res["skipped"][0]["reason"]


# =========================================================================
# 2. Status Lifecycle & Safeguard Tests
# =========================================================================

def test_transition_draft_to_approved():
    """Test transition from DRAFT to APPROVED."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "DRAFT",
    }
    payroll_repo.update_payroll_status.return_value = True

    success, msg = service.transition_payroll_status(payroll_id=101, target_status="APPROVED")
    assert success is True
    assert "successfully approved" in msg
    payroll_repo.update_payroll_status.assert_called_once_with(
        payroll_id=101,
        new_status="APPROVED",
        expected_current_status="DRAFT",
        remarks=f"Approved on {date.today().isoformat()}",
    )


def test_transition_draft_to_cancelled():
    """Test transition from DRAFT to CANCELLED."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "DRAFT",
    }
    payroll_repo.update_payroll_status.return_value = True

    success, msg = service.transition_payroll_status(payroll_id=101, target_status="CANCELLED")
    assert success is True
    assert "has been cancelled" in msg


def test_transition_approved_to_draft_requires_reason():
    """Test reopening an APPROVED statement as DRAFT requires explicit reason."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "APPROVED",
    }

    # Attempt without reason
    success, msg = service.transition_payroll_status(
        payroll_id=101, target_status="DRAFT", reason=None
    )
    assert success is False
    assert "explicit correction or adjustment reason is required" in msg

    # With reason
    payroll_repo.update_payroll_status.return_value = True
    success, msg = service.transition_payroll_status(
        payroll_id=101, target_status="DRAFT", reason="Adjustment per HR email"
    )
    assert success is True
    assert "reopened as DRAFT" in msg


def test_transition_paid_record_is_immutable():
    """Test that records in PAID status can never be altered or cancelled."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "PAID",
    }

    success, msg = service.transition_payroll_status(payroll_id=101, target_status="CANCELLED")
    assert success is False
    assert "cannot be altered or cancelled" in msg
    payroll_repo.update_payroll_status.assert_not_called()


def test_transition_to_paid_directly_in_module_6_is_forbidden():
    """Test that payroll cannot be marked PAID directly in Module 6."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "APPROVED",
    }

    success, msg = service.transition_payroll_status(payroll_id=101, target_status="PAID")
    assert success is False
    assert "Cannot mark payroll as PAID directly in the Payroll module" in msg
    payroll_repo.update_payroll_status.assert_not_called()


def test_invalid_status_transition_raises_error():
    """Test invalid status transitions raise InvalidStatusTransitionError."""
    payroll_repo = MagicMock()
    service = PayrollService(payroll_repo=payroll_repo)

    payroll_repo.get_by_id.return_value = {
        "id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "status": "APPROVED",
    }

    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        service.transition_payroll_status(payroll_id=101, target_status="CANCELLED")

    assert "Invalid payroll status transition" in str(exc_info.value)


# =========================================================================
# 3. Snapshot Preservation Test
# =========================================================================

def test_salary_snapshot_preservation():
    """
    Verify that finalized/approved payroll records preserve salary components
    even if the employee's salary settings change afterwards.
    """
    payroll_repo = MagicMock()
    emp_repo = MagicMock()
    att_repo = MagicMock()
    sal_repo = MagicMock()

    service = PayrollService(
        payroll_repo=payroll_repo,
        employee_repo=emp_repo,
        attendance_repo=att_repo,
        salary_repo=sal_repo,
    )

    # 1. Generate payroll when base salary is ₹30,000
    payroll_repo.get_by_employee_and_period.return_value = None
    payroll_repo.generate_payroll_code.return_value = "PAY-2026-10-EMP001"
    payroll_repo.create_payroll_record.return_value = 101

    emp_repo.get_by_id.return_value = MOCK_EMPLOYEE
    att_repo.get_by_employee_and_period.return_value = MOCK_ATTENDANCE
    sal_repo.get_by_employee_id.return_value = MOCK_SALARY_SETTINGS

    new_id = service.generate_single_payroll(employee_id=1, year=2026, month=10)
    created_payload = payroll_repo.create_payroll_record.call_args[0][0]

    # Stored snapshot has basic_pay = 30000, net_pay = 30100
    assert created_payload["basic_pay"] == Decimal("30000.00")
    assert created_payload["net_pay"] == Decimal("30100.00")

    # 2. Simulate subsequent promotion / salary increment: base salary raised to ₹50,000
    updated_salary_settings = dict(MOCK_SALARY_SETTINGS)
    updated_salary_settings["base_salary"] = Decimal("50000.00")
    sal_repo.get_by_employee_id.return_value = updated_salary_settings

    # 3. Retrieve payroll statement via get_payroll_details
    payroll_repo.get_by_id.return_value = dict(MOCK_PAYROLL_RECORD)
    details = service.get_payroll_details(101)

    # The persisted payroll record remains exactly as snapshotted (₹30,000 base, ₹30,100 net)
    assert details["payroll"]["basic_pay"] == Decimal("30000.00")
    assert details["payroll"]["net_pay"] == Decimal("30100.00")
    # Current salary settings reflect the new ₹50,000
    assert details["salary_settings"]["base_salary"] == Decimal("50000.00")


# =========================================================================
# 4. Route Integration Tests
# =========================================================================

def test_unauthenticated_payroll_access_redirects(client):
    """Test that all payroll routes redirect unauthenticated users to /login."""
    routes = [
        "/payroll",
        "/payroll/run",
        "/payroll/generate",
        "/payroll/101",
    ]
    for r in routes:
        resp = client.get(r, follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


@patch("modules.payroll.routes.service")
def test_payroll_index_rendering(mock_service, client):
    """Test authenticated rendering of payroll index with INR summary cards."""
    authenticate_session(client)

    mock_service.payroll_repo.get_paginated_payroll.return_value = ([MOCK_PAYROLL_RECORD], 1)
    mock_service.payroll_repo.get_monthly_summary.return_value = {
        "total_records": 1,
        "total_gross": Decimal("33000.00"),
        "total_deductions": Decimal("2900.00"),
        "total_net": Decimal("30100.00"),
        "draft_count": 1,
        "approved_count": 0,
        "paid_count": 0,
        "cancelled_count": 0,
    }
    mock_service.employee_repo.get_active_employees.return_value = [MOCK_EMPLOYEE]
    mock_service.payroll_repo.get_available_years.return_value = [2026, 2025]

    resp = client.get("/payroll")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Monthly Payroll Processing" in html
    assert "₹33,000.00" in html
    assert "₹30,100.00" in html
    assert "PAY-2026-10-EMP001" in html
    assert "Rajesh Kumar" in html


@patch("modules.payroll.routes.service")
def test_payroll_batch_run_get_audit(mock_service, client):
    """Test GET /payroll/run renders candidate audit checklist."""
    authenticate_session(client)

    mock_service.get_eligible_employees_for_period.return_value = [
        {
            "employee": MOCK_EMPLOYEE,
            "has_attendance": True,
            "attendance": MOCK_ATTENDANCE,
            "has_salary_settings": True,
            "salary_settings": MOCK_SALARY_SETTINGS,
            "existing_payroll": None,
            "is_eligible": True,
        }
    ]
    mock_service.payroll_repo.get_available_years.return_value = [2026]

    resp = client.get("/payroll/run?year=2026&month=10")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Controlled Batch Payroll Run" in html
    assert "Rajesh Kumar" in html
    assert "Execute Batch Run" in html


@patch("modules.payroll.routes.service")
def test_payroll_batch_run_post_execution(mock_service, client):
    """Test POST /payroll/run executes batch run and flashes result."""
    csrf_token = authenticate_session(client)

    mock_service.generate_batch_payroll_run.return_value = {
        "year": 2026,
        "month": 10,
        "successful_count": 1,
        "skipped_count": 0,
    }
    mock_service.payroll_repo.get_paginated_payroll.return_value = ([], 0)
    mock_service.payroll_repo.get_monthly_summary.return_value = {
        "total_records": 0,
        "total_gross": Decimal("0.00"),
        "total_deductions": Decimal("0.00"),
        "total_net": Decimal("0.00"),
        "draft_count": 0,
        "approved_count": 0,
        "paid_count": 0,
        "cancelled_count": 0,
    }
    mock_service.employee_repo.get_active_employees.return_value = []
    mock_service.payroll_repo.get_available_years.return_value = [2026]

    resp = client.post(
        "/payroll/run",
        data={
            "csrf_token": csrf_token,
            "year": "2026",
            "month": "10",
            "selected_employee_ids": ["1"],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Batch payroll run complete" in html


@patch("modules.payroll.routes.service")
def test_payroll_view_rendering(mock_service, client):
    """Test detailed payslip statement rendering with INR breakdowns."""
    authenticate_session(client)

    mock_service.get_payroll_details.return_value = {
        "payroll": MOCK_PAYROLL_RECORD,
        "attendance": MOCK_ATTENDANCE,
        "salary_settings": MOCK_SALARY_SETTINGS,
    }

    resp = client.get("/payroll/101")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "PAY-2026-10-EMP001" in html
    assert "₹30,100.00" in html
    assert "Approve Payroll" in html
    assert "Cancel Draft" in html


@patch("modules.payroll.routes.service")
def test_payroll_status_transition_post(mock_service, client):
    """Test POST /payroll/<id>/status transitions statement and flashes message."""
    csrf_token = authenticate_session(client)

    mock_service.transition_payroll_status.return_value = (
        True,
        "Payroll statement PAY-2026-10-EMP001 successfully approved.",
    )
    mock_service.get_payroll_details.return_value = {
        "payroll": MOCK_PAYROLL_RECORD,
        "attendance": MOCK_ATTENDANCE,
        "salary_settings": MOCK_SALARY_SETTINGS,
    }

    resp = client.post(
        "/payroll/101/status",
        data={
            "csrf_token": csrf_token,
            "action": "approve",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "successfully approved" in html
