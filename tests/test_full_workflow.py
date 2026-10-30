"""
Automated End-to-End Workflow & Integration Test Suite (Module 9).
Verifies the complete 15-step business workflow:
1. Create a Finance Manager account.
2. Log in.
3. Add an employee.
4. Edit and search the employee.
5. Enter monthly attendance.
6. Configure allowances and deduction rules.
7. Preview salary and verify the calculation manually.
8. Generate payroll.
9. Prevent duplicate payroll generation.
10. Approve payroll.
11. Record a payment.
12. Display the correct payment status.
13. Generate and print the salary slip (HTML and ReportLab PDF).
14. View monthly reports.
15. Log out and verify protected pages are inaccessible.
"""

from decimal import Decimal
import io
import csv
from unittest.mock import patch, MagicMock
import pytest
import werkzeug.security as ws

from modules.salary.services import SalaryCalculationEngine
from repositories.user_repository import UserRepository
from repositories.employee_repository import EmployeeRepository
from repositories.attendance_repository import AttendanceRepository
from repositories.salary_repository import SalaryRepository
from repositories.payroll_repository import PayrollRepository
from repositories.payment_repository import PaymentRepository
from repositories.reports_repository import ReportsRepository


# Shared Mock Fixtures
MOCK_USER = {
    "id": 10,
    "username": "finance_mgr",
    "email": "finance@payroll.local",
    "password_hash": ws.generate_password_hash("FinancePass123!"),
    "role": "ACCOUNTANT",
    "is_active": True,
}

MOCK_EMPLOYEE = {
    "id": 99,
    "employee_code": "EMP999",
    "first_name": "Ananya",
    "last_name": "Sharma",
    "full_name": "Ananya Sharma",
    "email": "ananya.sharma@example.com",
    "phone": "+91 9876543210",
    "department": "Finance",
    "designation": "Financial Analyst",
    "joining_date": "2025-04-01",
    "status": "ACTIVE",
    "base_salary": Decimal("50000.00"),
    "hourly_rate": Decimal("300.00"),
}

MOCK_ATTENDANCE = {
    "id": 88,
    "employee_id": 99,
    "year": 2026,
    "month": 10,
    "total_working_days": 25,
    "present_days": Decimal("22.0"),
    "days_worked": Decimal("22.0"),
    "absent_days": Decimal("3.0"),
    "paid_leaves": Decimal("1.0"),
    "unpaid_leaves": Decimal("2.0"),
    "overtime_hours": Decimal("10.00"),
    "overtime_rate": Decimal("300.00"),
    "notes": "October attendance verified",
}

MOCK_SALARY_SETTINGS = {
    "id": 77,
    "employee_id": 99,
    "employee_code": "EMP999",
    "first_name": "Ananya",
    "last_name": "Sharma",
    "department": "Finance",
    "designation": "Financial Analyst",
    "base_salary": Decimal("50000.00"),
    "hourly_rate": Decimal("300.00"),
    "hra": Decimal("10000.00"),
    "transport_allowance": Decimal("3000.00"),
    "medical_allowance": Decimal("2000.00"),
    "other_allowances": Decimal("0.00"),
    "tax_deduction_rate": Decimal("5.00"),
    "pf_deduction_rate": Decimal("10.00"),
    "other_deductions": Decimal("1000.00"),
    "effective_from": "2026-01-01",
}

MOCK_PAYROLL = {
    "id": 66,
    "payroll_id": 66,
    "payroll_code": "PAY-2026-10-EMP999",
    "employee_id": 99,
    "employee_code": "EMP999",
    "first_name": "Ananya",
    "last_name": "Sharma",
    "employee_name": "Ananya Sharma",
    "full_name": "Ananya Sharma",
    "department": "Finance",
    "designation": "Financial Analyst",
    "year": 2026,
    "month": 10,
    "basic_pay": Decimal("50000.00"),
    "allowances_total": Decimal("15000.00"),
    "overtime_pay": Decimal("3000.00"),
    "gross_pay": Decimal("68000.00"),
    "leave_deduction": Decimal("4000.00"),
    "tax_deduction": Decimal("2500.00"),
    "pf_deduction": Decimal("5000.00"),
    "other_deductions": Decimal("1000.00"),
    "total_deductions": Decimal("12500.00"),
    "net_pay": Decimal("55500.00"),
    "status": "DRAFT",
    "payroll_status": "DRAFT",
    "generated_date": "2026-10-28",
    "payment_due_date": "2026-11-05",
    "remarks": "Generated in monthly run",
}

MOCK_PAYMENT = {
    "id": 55,
    "payroll_id": 66,
    "payment_reference": "TXN-202610-FIN01",
    "payment_method": "BANK_TRANSFER",
    "amount_paid": Decimal("55500.00"),
    "payment_date": "2026-10-29",
    "status": "SUCCESSFUL",
    "payment_status": "SUCCESSFUL",
    "transaction_notes": "Direct bank credit",
}


def authenticate_client(client, user=MOCK_USER, token="valid_test_csrf_token_999"):
    """Helper to inject an authenticated session with a valid CSRF token."""
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["username"] = user["username"]
        sess["email"] = user["email"]
        sess["role"] = user["role"]
        sess["_csrf_token"] = token
    return token


# ==============================================================================
# Individual Step Tests (1 through 15)
# ==============================================================================

def test_step_1_create_finance_manager_account(runner):
    """Step 1: Create Finance Manager account via CLI."""
    with patch.object(UserRepository, "get_by_username", return_value=None), \
         patch.object(UserRepository, "get_by_email", return_value=None), \
         patch.object(UserRepository, "create_user", return_value=10) as mock_create:

        result = runner.invoke(
            args=[
                "create-user",
                "--username", "finance_mgr",
                "--email", "finance@payroll.local",
                "--password", "FinancePass123!",
                "--role", "ACCOUNTANT",
            ]
        )
        assert result.exit_code == 0
        assert "created successfully" in result.output
        mock_create.assert_called_once_with(
            username="finance_mgr",
            email="finance@payroll.local",
            password="FinancePass123!",
            role="ACCOUNTANT",
            is_active=True,
        )


def test_step_2_login_finance_manager(client):
    """Step 2: Log in as Finance Manager."""
    client.get("/login")
    with client.session_transaction() as sess:
        csrf_token = sess.get("_csrf_token")

    with patch.object(UserRepository, "get_by_username", return_value=MOCK_USER):
        response = client.post(
            "/login",
            data={
                "username": "finance_mgr",
                "password": "FinancePass123!",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.location

        with client.session_transaction() as sess:
            assert sess.get("user_id") == 10
            assert sess.get("username") == "finance_mgr"
            assert sess.get("role") == "ACCOUNTANT"


def test_step_3_add_employee_atomic(client):
    """Step 3: Add employee with atomic profile and compensation creation."""
    token = authenticate_client(client)

    with patch.object(EmployeeRepository, "get_all_departments", return_value=["Finance"]), \
         patch.object(EmployeeRepository, "get_by_code", return_value=None), \
         patch.object(EmployeeRepository, "get_by_email", return_value=None), \
         patch.object(EmployeeRepository, "create_employee", return_value=99) as mock_add:

        response = client.post(
            "/employees/add",
            data={
                "employee_code": "EMP999",
                "first_name": "Ananya",
                "last_name": "Sharma",
                "email": "ananya.sharma@example.com",
                "phone": "+91 9876543210",
                "department": "Finance",
                "designation": "Financial Analyst",
                "joining_date": "2025-04-01",
                "status": "ACTIVE",
                "base_salary": "50000.00",
                "hourly_rate": "300.00",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/employees/99" in response.location
        mock_add.assert_called_once()


def test_step_4_edit_and_search_employee(client):
    """Step 4: Search and edit employee profile."""
    token = authenticate_client(client)

    # 4a: Search
    with patch.object(EmployeeRepository, "get_paginated_employees", return_value=([MOCK_EMPLOYEE], 1)), \
         patch.object(EmployeeRepository, "get_all_departments", return_value=["Finance"]):

        response = client.get("/employees?search=EMP999")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Ananya Sharma" in html
        assert "EMP999" in html
        assert "Finance" in html

    # 4b: Edit (/employees/<id>/edit)
    with patch.object(EmployeeRepository, "get_by_id", return_value=MOCK_EMPLOYEE), \
         patch.object(EmployeeRepository, "get_by_email", return_value=None), \
         patch.object(EmployeeRepository, "get_by_code", return_value=MOCK_EMPLOYEE), \
         patch.object(EmployeeRepository, "get_all_departments", return_value=["Finance"]), \
         patch.object(EmployeeRepository, "update_employee", return_value=True):

        edit_res = client.post(
            "/employees/99/edit",
            data={
                "first_name": "Ananya",
                "last_name": "Sharma",
                "email": "ananya.sharma@example.com",
                "phone": "+91 9999999999",
                "department": "Finance",
                "designation": "Senior Financial Analyst",
                "joining_date": "2025-04-01",
                "base_salary": "55000.00",
                "status": "ACTIVE",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert edit_res.status_code == 302
        assert "/employees/99" in edit_res.location


def test_step_5_enter_monthly_attendance(client):
    """Step 5: Enter monthly attendance summary."""
    token = authenticate_client(client)

    with patch("modules.attendance.routes.service") as mock_service:
        mock_service.get_active_employees.return_value = [MOCK_EMPLOYEE]
        mock_service.create_attendance_record.return_value = (88, {})

        response = client.post(
            "/attendance/add",
            data={
                "employee_id": 99,
                "year": 2026,
                "month": 10,
                "total_working_days": 25,
                "present_days": "22.0",
                "paid_leaves": "1.0",
                "unpaid_leaves": "2.0",
                "overtime_hours": "10.00",
                "overtime_rate": "300.00",
                "notes": "October attendance verified",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/attendance" in response.location
        mock_service.create_attendance_record.assert_called_once()


def test_step_6_configure_allowances_and_deductions(client):
    """Step 6: Configure monthly allowances and statutory deduction rules."""
    token = authenticate_client(client)

    with patch("modules.salary.routes.service") as mock_service:
        mock_service.get_salary_configuration.return_value = MOCK_SALARY_SETTINGS
        mock_service.update_salary_configuration.return_value = (True, {})

        response = client.post(
            "/salary/99/edit",
            data={
                "base_salary": "50000.00",
                "hourly_rate": "300.00",
                "hra": "10000.00",
                "transport_allowance": "3000.00",
                "medical_allowance": "2000.00",
                "other_allowances": "0.00",
                "tax_deduction_rate": "5.00",
                "pf_deduction_rate": "10.00",
                "other_deductions": "1000.00",
                "effective_from": "2026-01-01",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/salary" in response.location
        mock_service.update_salary_configuration.assert_called_once()


def test_step_7_preview_salary_and_manual_calculation_verification(client):
    """Step 7: Preview salary and mathematically verify calculation formula."""
    token = authenticate_client(client)

    # 1. Manual Math Verification via Service Engine
    engine = SalaryCalculationEngine()
    result = engine.calculate_salary(
        basic_salary=Decimal("50000.00"),
        total_working_days=25,
        unpaid_leave_days=Decimal("2.0"),
        allowances=Decimal("15000.00"),
        overtime_hours=Decimal("10.0"),
        overtime_rate=Decimal("300.00"),
        other_deductions=Decimal("1000.00"),
    )

    # Verify each exact mathematical step:
    # Daily rate = 50,000 / 25 = 2,000.00
    assert result.daily_salary == Decimal("2000.00")
    # Leave deduction = 2,000.00 * 2.0 = 4,000.00
    assert result.leave_deduction == Decimal("4000.00")
    # Overtime payment = 10.0 * 300.00 = 3,000.00
    assert result.overtime_payment == Decimal("3000.00")
    # Gross salary = 50,000 + 15,000 + 3,000 = 68,000.00
    assert result.gross_salary == Decimal("68000.00")
    # Total deductions = 4,000 + 1,000 = 5,000.00 (before statutory taxes)
    assert result.total_deductions == Decimal("5000.00")
    # Net salary = 68,000 - 5,000 = 63,000.00
    assert result.net_salary == Decimal("63000.00")

    # 2. Preview Route Verification
    with patch("modules.salary.routes.service") as mock_service:
        mock_service.get_active_employees.return_value = [MOCK_EMPLOYEE]
        mock_service.attendance_repo.get_available_years.return_value = [2026]
        mock_service.preview_salary_calculation.return_value = {
            "employee": MOCK_EMPLOYEE,
            "attendance": MOCK_ATTENDANCE,
            "salary_cfg": MOCK_SALARY_SETTINGS,
            "calculation": result,
            "has_attendance": True,
            "has_salary_cfg": True,
            "is_valid": True,
        }

        response = client.get("/salary/preview?employee_id=99&year=2026&month=10")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Ananya Sharma" in html
        assert "EMP999" in html
        assert "Salary Preview" in html


def test_step_8_generate_payroll(client):
    """Step 8: Generate individual employee monthly payroll record."""
    token = authenticate_client(client)

    with patch("modules.payroll.routes.service") as mock_service:
        mock_service.generate_single_payroll.return_value = 66

        response = client.post(
            "/payroll/generate",
            data={
                "employee_id": 99,
                "year": 2026,
                "month": 10,
                "remarks": "Generated in monthly run",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/payroll/66" in response.location
        mock_service.generate_single_payroll.assert_called_once_with(
            employee_id=99, year=2026, month=10, remarks="Generated in monthly run"
        )


def test_step_9_prevent_duplicate_payroll_generation(client):
    """Step 9: Prevent duplicate monthly payroll generation."""
    token = authenticate_client(client)

    from modules.payroll.services import DuplicatePayrollError

    with patch("modules.payroll.routes.service") as mock_service:
        mock_service.generate_single_payroll.side_effect = DuplicatePayrollError(
            "Payroll record already exists for this employee in October 2026."
        )

        response = client.post(
            "/payroll/generate",
            data={
                "employee_id": 99,
                "year": 2026,
                "month": 10,
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        # Verify redirect back to payroll index with warning
        assert response.status_code == 302
        assert "/payroll" in response.location


def test_step_10_approve_payroll(client):
    """Step 10: Approve payroll statement via valid state transition."""
    token = authenticate_client(client)

    with patch("modules.payroll.routes.service") as mock_service:
        mock_service.transition_payroll_status.return_value = (True, "Payroll statement #66 approved successfully.")

        response = client.post(
            "/payroll/66/status",
            data={
                "action": "approve",
                "reason": "Approved by Finance Manager",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/payroll/66" in response.location
        mock_service.transition_payroll_status.assert_called_once_with(
            payroll_id=66,
            target_status="APPROVED",
            reason="Approved by Finance Manager",
        )


def test_step_11_record_payment(client):
    """Step 11: Record payment disbursement and transition payroll to PAID."""
    token = authenticate_client(client)

    approved_payroll = dict(MOCK_PAYROLL, status="APPROVED")

    with patch("modules.payments.routes.service") as mock_service:
        mock_service.payroll_repo.get_by_id.return_value = approved_payroll
        mock_service.record_payment.return_value = 55

        response = client.post(
            "/payments/record/66",
            data={
                "amount": "55500.00",
                "payment_method": "BANK_TRANSFER",
                "payment_reference": "TXN-202610-FIN01",
                "payment_date": "2026-10-29",
                "status": "SUCCESSFUL",
                "transaction_notes": "Direct bank credit",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/payments/55" in response.location
        mock_service.record_payment.assert_called_once()


def test_step_12_display_correct_payment_status(client):
    """Step 12: Verify payment record and status displayed correctly in ledger."""
    authenticate_client(client)

    mock_row = dict(
        MOCK_PAYMENT,
        first_name="Ananya",
        last_name="Sharma",
        employee_name="Ananya Sharma",
        employee_code="EMP999",
        payroll_code="PAY-2026-10-EMP999",
        department="Finance",
        designation="Financial Analyst",
    )

    with patch("modules.payments.routes.service") as mock_service:
        mock_service.get_payment_history.return_value = ([mock_row], 1)
        mock_service.payment_repo.get_payment_summary.return_value = {
            "total_records": 1,
            "total_disbursed": Decimal("55500.00"),
            "successful_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "reversed_count": 0,
        }
        mock_service.payment_repo.get_available_years.return_value = [2026]

        response = client.get("/payments?search=TXN-202610-FIN01")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "TXN-202610-FIN01" in html
        assert "Payment Management" in html
        assert "₹55,500.00" in html


def test_step_13_generate_and_print_salary_slip(client):
    """Step 13: View HTML salary slip and generate ReportLab PDF."""
    authenticate_client(client)

    slip_data = {
        "payroll": dict(MOCK_PAYROLL, status="PAID"),
        "employee": MOCK_EMPLOYEE,
        "payment": MOCK_PAYMENT,
        "attendance": MOCK_ATTENDANCE,
        "month_name": "October",
        "year": 2026,
    }

    # 13a: View HTML slip
    with patch("modules.payments.routes.service") as mock_service:
        mock_service.get_salary_slip_data.return_value = slip_data

        html_res = client.get("/payments/slip/66")
        assert html_res.status_code == 200
        html = html_res.data.decode("utf-8")
        assert "Salary Slip" in html
        assert "Ananya Sharma" in html
        assert "PAY-2026-10-EMP999" in html
        assert "Download PDF" in html
        assert "Print Salary Slip" in html

    # 13b: Download PDF slip
    with patch("modules.payments.routes.service") as mock_service:
        mock_service.generate_salary_slip_pdf.return_value = b"%PDF-1.4 Mocked Salary Slip PDF"
        mock_service.payroll_repo.get_by_id.return_value = dict(MOCK_PAYROLL, status="PAID")

        pdf_res = client.get("/payments/slip/66/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.mimetype == "application/pdf"
        assert "attachment; filename=" in pdf_res.headers["Content-Disposition"]
        assert pdf_res.data.startswith(b"%PDF-")


def test_step_14_view_monthly_reports(client):
    """Step 14: View analytical monthly reports across all categories."""
    authenticate_client(client)

    from tests.test_reports import setup_mock_service_defaults

    with patch("modules.reports.routes.service") as mock_service:
        setup_mock_service_defaults(mock_service)

        # Tab: Payroll Summary
        r_pay = client.get("/reports?tab=payroll")
        assert r_pay.status_code == 200
        assert "Financial &amp; Statutory Reports" in r_pay.data.decode("utf-8") or "Financial & Statutory Reports" in r_pay.data.decode("utf-8")

        # Tab: Attendance
        r_att = client.get("/reports?tab=attendance")
        assert r_att.status_code == 200

        # Tab: Salary History
        r_hist = client.get("/reports?tab=salary_history")
        assert r_hist.status_code == 200

        # Tab: Status & Method Distributions
        r_stat = client.get("/reports?tab=status")
        assert r_stat.status_code == 200

        # Tab: Department Workforce
        r_dept = client.get("/reports?tab=departments")
        assert r_dept.status_code == 200

        # CSV Export
        mock_service.generate_payroll_csv.return_value = "Payroll Code,Net Pay\nPAY-001,55500.00\n"
        r_csv = client.get("/reports/export/payroll.csv")
        assert r_csv.status_code == 200
        assert r_csv.mimetype == "text/csv"


def test_step_15_logout_and_verify_protected_pages_inaccessible(client):
    """Step 15: Log out and verify all protected endpoints strictly redirect to /login."""
    authenticate_client(client)

    # Logout
    logout_res = client.get("/logout", follow_redirects=False)
    assert logout_res.status_code == 302
    assert "/login" in logout_res.location

    # Verify session cleared
    with client.session_transaction() as sess:
        assert "user_id" not in sess

    # Verify protected endpoints redirect to /login
    protected_endpoints = [
        "/dashboard",
        "/employees",
        "/attendance",
        "/salary",
        "/payroll",
        "/payments",
        "/reports",
        "/reports/export/payroll.csv",
        "/payments/awaiting",
    ]

    for ep in protected_endpoints:
        res = client.get(ep, follow_redirects=False)
        assert res.status_code == 302, f"Endpoint {ep} did not redirect!"
        assert "/login" in res.location, f"Endpoint {ep} did not redirect to /login!"


# ==============================================================================
# Holistic End-to-End Workflow Integration Test
# ==============================================================================

def test_full_integrated_lifecycle_end_to_end(client, runner):
    """
    Holistic End-to-End Integration Test:
    Executes all 15 stages in a single continuous lifecycle flow!
    """
    # Stage 1: Account Creation
    with patch.object(UserRepository, "get_by_username", return_value=None), \
         patch.object(UserRepository, "get_by_email", return_value=None), \
         patch.object(UserRepository, "create_user", return_value=10):
        res1 = runner.invoke(args=["create-user", "--username", "finance_mgr", "--email", "finance@payroll.local", "--password", "FinancePass123!", "--role", "ACCOUNTANT"])
        assert res1.exit_code == 0

    # Stage 2: Login
    token = authenticate_client(client)

    # Stage 3: Add Employee
    with patch.object(EmployeeRepository, "get_all_departments", return_value=["Finance"]), \
         patch.object(EmployeeRepository, "get_by_code", return_value=None), \
         patch.object(EmployeeRepository, "get_by_email", return_value=None), \
         patch.object(EmployeeRepository, "create_employee", return_value=99):
        res3 = client.post("/employees/add", data={"employee_code": "EMP999", "first_name": "Ananya", "last_name": "Sharma", "email": "ananya.sharma@example.com", "department": "Finance", "designation": "Financial Analyst", "joining_date": "2025-04-01", "status": "ACTIVE", "base_salary": "50000.00", "csrf_token": token})
        assert res3.status_code == 302

    # Stage 4: Search & Edit Employee
    with patch.object(EmployeeRepository, "get_paginated_employees", return_value=([MOCK_EMPLOYEE], 1)), \
         patch.object(EmployeeRepository, "get_all_departments", return_value=["Finance"]), \
         patch.object(EmployeeRepository, "get_by_id", return_value=MOCK_EMPLOYEE), \
         patch.object(EmployeeRepository, "get_by_email", return_value=None), \
         patch.object(EmployeeRepository, "get_by_code", return_value=MOCK_EMPLOYEE), \
         patch.object(EmployeeRepository, "update_employee", return_value=True):

        res4a = client.get("/employees?search=EMP999")
        assert res4a.status_code == 200
        res4b = client.post("/employees/99/edit", data={"first_name": "Ananya", "last_name": "Sharma", "email": "ananya.sharma@example.com", "department": "Finance", "designation": "Senior Financial Analyst", "joining_date": "2025-04-01", "base_salary": "55000.00", "status": "ACTIVE", "csrf_token": token})
        assert res4b.status_code == 302

    # Stage 5: Monthly Attendance
    with patch("modules.attendance.routes.service") as att_srv:
        att_srv.get_active_employees.return_value = [MOCK_EMPLOYEE]
        att_srv.create_attendance_record.return_value = (88, {})
        res5 = client.post("/attendance/add", data={"employee_id": 99, "year": 2026, "month": 10, "total_working_days": 25, "present_days": "22.0", "paid_leaves": "1.0", "unpaid_leaves": "2.0", "overtime_hours": "10.00", "overtime_rate": "300.00", "csrf_token": token})
        assert res5.status_code == 302

    # Stage 6: Salary Settings
    with patch("modules.salary.routes.service") as sal_srv:
        sal_srv.get_salary_configuration.return_value = MOCK_SALARY_SETTINGS
        sal_srv.update_salary_configuration.return_value = (True, {})
        res6 = client.post("/salary/99/edit", data={"base_salary": "50000.00", "hourly_rate": "300.00", "hra": "10000.00", "transport_allowance": "3000.00", "medical_allowance": "2000.00", "other_allowances": "0.00", "tax_deduction_rate": "5.00", "pf_deduction_rate": "10.00", "other_deductions": "1000.00", "effective_from": "2026-01-01", "csrf_token": token})
        assert res6.status_code == 302

    # Stage 7: Salary Preview Verification
    engine = SalaryCalculationEngine()
    calc = engine.calculate_salary(basic_salary=Decimal("50000.00"), total_working_days=25, unpaid_leave_days=Decimal("2.0"), allowances=Decimal("15000.00"), overtime_hours=Decimal("10.0"), overtime_rate=Decimal("300.00"), other_deductions=Decimal("1000.00"))
    assert calc.net_salary == Decimal("63000.00")

    # Stage 8: Generate Payroll
    with patch("modules.payroll.routes.service") as pay_srv:
        pay_srv.generate_single_payroll.return_value = 66
        res8 = client.post("/payroll/generate", data={"employee_id": 99, "year": 2026, "month": 10, "csrf_token": token})
        assert res8.status_code == 302

    # Stage 9: Duplicate Prevention
    from modules.payroll.services import DuplicatePayrollError
    with patch("modules.payroll.routes.service") as pay_srv:
        pay_srv.generate_single_payroll.side_effect = DuplicatePayrollError("Duplicate monthly payroll rejected.")
        res9 = client.post("/payroll/generate", data={"employee_id": 99, "year": 2026, "month": 10, "csrf_token": token})
        assert res9.status_code == 302

    # Stage 10: Approve Payroll
    with patch("modules.payroll.routes.service") as pay_srv:
        pay_srv.transition_payroll_status.return_value = (True, "Approved.")
        res10 = client.post("/payroll/66/status", data={"action": "approve", "csrf_token": token})
        assert res10.status_code == 302

    # Stage 11: Record Payment
    with patch("modules.payments.routes.service") as pmt_srv:
        pmt_srv.payroll_repo.get_by_id.return_value = dict(MOCK_PAYROLL, status="APPROVED")
        pmt_srv.record_payment.return_value = 55
        res11 = client.post("/payments/record/66", data={"amount": "55500.00", "payment_method": "BANK_TRANSFER", "payment_reference": "TXN-202610-FIN01", "payment_date": "2026-10-29", "status": "SUCCESSFUL", "csrf_token": token})
        assert res11.status_code == 302

    # Stage 12: Display Payment Status
    with patch("modules.payments.routes.service") as pmt_srv:
        pmt_srv.get_payment_history.return_value = ([dict(MOCK_PAYMENT, first_name="Ananya", last_name="Sharma", employee_name="Ananya Sharma", employee_code="EMP999", payroll_code="PAY-2026-10-EMP999")], 1)
        pmt_srv.payment_repo.get_payment_summary.return_value = {"total_records": 1, "total_disbursed": Decimal("55500.00"), "successful_count": 1, "pending_count": 0, "failed_count": 0, "reversed_count": 0}
        pmt_srv.payment_repo.get_available_years.return_value = [2026]
        res12 = client.get("/payments?search=TXN-202610-FIN01")
        assert res12.status_code == 200
        assert "TXN-202610-FIN01" in res12.data.decode("utf-8")

    # Stage 13: Salary Slip (HTML + PDF)
    with patch("modules.payments.routes.service") as pmt_srv:
        pmt_srv.get_salary_slip_data.return_value = {"payroll": dict(MOCK_PAYROLL, status="PAID"), "employee": MOCK_EMPLOYEE, "payment": MOCK_PAYMENT, "attendance": MOCK_ATTENDANCE, "month_name": "October", "year": 2026}
        pmt_srv.generate_salary_slip_pdf.return_value = b"%PDF-1.4 Mocked Slip"
        pmt_srv.payroll_repo.get_by_id.return_value = dict(MOCK_PAYROLL, status="PAID")

        res13a = client.get("/payments/slip/66")
        assert res13a.status_code == 200
        res13b = client.get("/payments/slip/66/pdf")
        assert res13b.status_code == 200
        assert res13b.data.startswith(b"%PDF-")

    # Stage 14: Reports
    from tests.test_reports import setup_mock_service_defaults
    with patch("modules.reports.routes.service") as rep_srv:
        setup_mock_service_defaults(rep_srv)
        res14 = client.get("/reports?tab=payroll")
        assert res14.status_code == 200

    # Stage 15: Logout & Inaccessibility
    res15 = client.get("/logout")
    assert res15.status_code == 302
    assert "/login" in res15.location
    res15_check = client.get("/dashboard")
    assert res15_check.status_code == 302
    assert "/login" in res15_check.location
