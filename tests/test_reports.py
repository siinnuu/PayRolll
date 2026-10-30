"""
Automated unit and integration tests for Module 8: Reports and DBMS Academic Documentation.
Tests:
- Analytical SQL queries in ReportsRepository (Payroll, Attendance, Salary History, Department workforce, Distributions).
- Handling empty database states gracefully with zero counts and Decimal('0.00').
- Month, year, department, and employee filtering across reports.
- ReportsService aggregation coordination and RFC-4180 CSV generation.
- CSV export endpoints with valid MIME types and Content-Disposition headers.
- Route authorization checks (redirects unauthenticated users to /login).
- Academic DBMS Documentation page rendering and content completeness.
"""

from decimal import Decimal
import io
import csv
from unittest.mock import patch, MagicMock
import pytest

from repositories.reports_repository import ReportsRepository
from modules.reports.services import ReportsService


def authenticate_session(client, user_id=1, username="reports_analyst", role="ACCOUNTANT", token="valid_test_csrf_token_888"):
    """Helper to inject an authenticated session with a valid CSRF token."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["email"] = f"{username}@payroll.local"
        sess["role"] = role
        sess["_csrf_token"] = token
    return token


# Mock Analytical Records
MOCK_PAYROLL_SUMMARY = {
    "total_statements": 5,
    "total_basic": Decimal("250000.00"),
    "total_allowances": Decimal("75000.00"),
    "total_overtime": Decimal("25000.00"),
    "total_gross": Decimal("350000.00"),
    "total_leave_deductions": Decimal("20000.00"),
    "total_other_deductions": Decimal("25000.00"),
    "total_deductions": Decimal("45000.00"),
    "total_net": Decimal("305000.00"),
    "avg_net_pay": Decimal("61000.00"),
    "draft_count": 1,
    "approved_count": 1,
    "paid_count": 3,
    "cancelled_count": 0,
}

MOCK_SALARY_HISTORY = [
    {
        "id": 101,
        "payroll_id": 101,
        "payroll_code": "PAY-2026-10-EMP001",
        "employee_id": 1,
        "employee_code": "EMP001",
        "first_name": "Rajesh",
        "last_name": "Kumar",
        "full_name": "Rajesh Kumar",
        "employee_name": "Rajesh Kumar",
        "department": "Engineering",
        "designation": "Senior Engineer",
        "year": 2026,
        "month": 10,
        "basic_pay": Decimal("75000.00"),
        "allowances_total": Decimal("18000.00"),
        "overtime_pay": Decimal("2500.00"),
        "gross_pay": Decimal("95500.00"),
        "leave_deduction": Decimal("5000.00"),
        "total_deductions": Decimal("5000.00"),
        "net_pay": Decimal("90500.00"),
        "payroll_status": "PAID",
        "status": "PAID",
        "generated_date": "2026-10-28",
        "payment_date": "2026-10-29",
        "payment_method": "BANK_TRANSFER",
        "payment_reference": "TXN-202610-001",
    }
]

MOCK_ATTENDANCE_SUMMARY = [
    {
        "id": 51,
        "employee_id": 1,
        "employee_code": "EMP001",
        "first_name": "Rajesh",
        "last_name": "Kumar",
        "full_name": "Rajesh Kumar",
        "employee_name": "Rajesh Kumar",
        "department": "Engineering",
        "designation": "Senior Engineer",
        "year": 2026,
        "month": 10,
        "total_working_days": 30,
        "present_days": Decimal("26.0"),
        "days_worked": Decimal("26.0"),
        "absent_days": Decimal("4.0"),
        "paid_leaves": Decimal("2.0"),
        "unpaid_leaves": Decimal("2.0"),
        "overtime_hours": Decimal("5.00"),
        "overtime_rate": Decimal("500.00"),
        "notes": "Verified",
    }
]

MOCK_ATTENDANCE_METRICS = {
    "total_records": 1,
    "total_working_days": 30,
    "total_days_worked": Decimal("26.0"),
    "total_paid_leaves": Decimal("2.0"),
    "total_unpaid_leaves": Decimal("2.0"),
    "total_overtime_hours": Decimal("5.00"),
}

MOCK_DEPARTMENT_SUMMARY = [
    {
        "department": "Engineering",
        "total_employees": 4,
        "active_count": 4,
        "inactive_count": 0,
        "total_base_payroll": Decimal("260000.00"),
        "avg_base_salary": Decimal("65000.00"),
        "total_allowances_pool": Decimal("50000.00"),
        "min_salary": Decimal("50000.00"),
        "max_salary": Decimal("85000.00"),
    },
    {
        "department": "Human Resources",
        "total_employees": 2,
        "active_count": 2,
        "inactive_count": 0,
        "total_base_payroll": Decimal("90000.00"),
        "avg_base_salary": Decimal("45000.00"),
        "total_allowances_pool": Decimal("15000.00"),
        "min_salary": Decimal("40000.00"),
        "max_salary": Decimal("50000.00"),
    },
]

MOCK_STATUS_DISTRIBUTION = [
    {"status": "DRAFT", "count": 1, "total_net": Decimal("45000.00")},
    {"status": "APPROVED", "count": 1, "total_net": Decimal("60000.00")},
    {"status": "PAID", "count": 3, "total_net": Decimal("200000.00")},
]

MOCK_PAYMENT_METHOD_DISTRIBUTION = [
    {"payment_method": "BANK_TRANSFER", "transaction_count": 2, "total_amount": Decimal("150000.00")},
    {"payment_method": "CHEQUE", "transaction_count": 1, "total_amount": Decimal("50000.00")},
]


def setup_mock_service_defaults(mock_service):
    """Set default return values on mock_service for all tab queries."""
    mock_service.employee_repo.get_all_departments.return_value = ["Engineering", "Human Resources"]
    mock_service.employee_repo.get_active_employees.return_value = []
    mock_service.payroll_repo.get_available_years.return_value = [2026, 2025]
    mock_service.get_monthly_summary.return_value = MOCK_PAYROLL_SUMMARY
    mock_service.get_employee_salary_history.return_value = ([], 0)
    mock_service.get_attendance_summary.return_value = ([], 0, {})
    mock_service.get_department_summary.return_value = []
    mock_service.get_status_and_method_distributions.return_value = {
        "status_distribution": [],
        "method_distribution": [],
    }


# ==============================================================================
# 1. Repository Tests (Using Mocked Database Manager)
# ==============================================================================

class TestReportsRepository:
    """Unit tests for analytical queries in ReportsRepository."""

    def test_get_monthly_payroll_summary(self):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = {
            "total_statements": 5,
            "total_basic": Decimal("250000.00"),
            "total_allowances": Decimal("75000.00"),
            "total_overtime": Decimal("25000.00"),
            "total_gross": Decimal("350000.00"),
            "total_leave_deductions": Decimal("20000.00"),
            "total_other_deductions": Decimal("25000.00"),
            "total_deductions": Decimal("45000.00"),
            "total_net": Decimal("305000.00"),
            "avg_net_pay": Decimal("61000.00"),
            "draft_count": 1,
            "approved_count": 1,
            "paid_count": 3,
            "cancelled_count": 0,
        }

        repo = ReportsRepository(db_manager=mock_db)
        result = repo.get_monthly_payroll_summary(year=2026, month=10)

        assert result["total_statements"] == 5
        assert result["total_gross"] == Decimal("350000.00")
        assert result["total_deductions"] == Decimal("45000.00")
        assert result["total_net"] == Decimal("305000.00")
        assert result["avg_net_pay"] == Decimal("61000.00")
        assert result["paid_count"] == 3

    def test_get_monthly_payroll_summary_empty(self):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = None

        repo = ReportsRepository(db_manager=mock_db)
        result = repo.get_monthly_payroll_summary(year=1999, month=1)

        assert result["total_statements"] == 0
        assert result["total_gross"] == Decimal("0.00")
        assert result["total_deductions"] == Decimal("0.00")
        assert result["total_net"] == Decimal("0.00")
        assert result["avg_net_pay"] == Decimal("0.00")

    def test_get_employee_salary_history_filtered(self):
        mock_db = MagicMock()
        mock_db.execute_query.side_effect = [
            {"total": 1},
            MOCK_SALARY_HISTORY,
        ]

        repo = ReportsRepository(db_manager=mock_db)
        records, total = repo.get_employee_salary_history(
            employee_id=1, department="Engineering", year=2026, page=1, per_page=10
        )

        assert total == 1
        assert len(records) == 1
        assert records[0]["employee_code"] == "EMP001"
        assert records[0]["net_pay"] == Decimal("90500.00")

    def test_get_department_summary(self):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = MOCK_DEPARTMENT_SUMMARY

        repo = ReportsRepository(db_manager=mock_db)
        departments = repo.get_department_summary()

        assert len(departments) == 2
        assert departments[0]["department"] == "Engineering"
        assert departments[0]["total_employees"] == 4
        assert departments[0]["total_base_payroll"] == Decimal("260000.00")


# ==============================================================================
# 2. Service & CSV Export Tests
# ==============================================================================

class TestReportsService:
    """Unit tests for ReportsService business coordination and RFC-4180 CSV serialization."""

    def test_generate_payroll_csv(self):
        mock_repo = MagicMock()
        mock_repo.get_payroll_export_data.return_value = [
            {
                "payroll_code": "PAY-2026-10-EMP001",
                "employee_code": "EMP001",
                "employee_name": "Rajesh Kumar",
                "department": "Engineering",
                "designation": "Senior Engineer",
                "year": 2026,
                "month": 10,
                "basic_pay": Decimal("75000.00"),
                "allowances_total": Decimal("18000.00"),
                "overtime_pay": Decimal("2500.00"),
                "gross_pay": Decimal("95500.00"),
                "leave_deduction": Decimal("5000.00"),
                "other_deductions": Decimal("0.00"),
                "total_deductions": Decimal("5000.00"),
                "net_pay": Decimal("90500.00"),
                "payroll_status": "PAID",
                "generated_date": "2026-10-28",
                "payment_reference": "TXN-202610-001",
                "payment_method": "BANK_TRANSFER",
                "payment_date": "2026-10-29",
                "payment_status": "SUCCESSFUL",
            }
        ]

        service = ReportsService(reports_repo=mock_repo)
        csv_text = service.generate_payroll_csv(year=2026, month=10)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        # Header check
        assert "Payroll Code" in rows[0]
        assert "Basic Salary (INR)" in rows[0]
        assert "Net Salary (INR)" in rows[0]

        # Data row check
        assert rows[1][0] == "PAY-2026-10-EMP001"
        assert rows[1][1] == "EMP001"
        assert rows[1][2] == "Rajesh Kumar"
        assert rows[1][14] == "90500.00"
        assert rows[1][15] == "PAID"

    def test_generate_attendance_csv(self):
        mock_repo = MagicMock()
        mock_repo.get_attendance_export_data.return_value = [
            {
                "employee_code": "EMP001",
                "employee_name": "Rajesh Kumar",
                "department": "Engineering",
                "designation": "Senior Engineer",
                "year": 2026,
                "month": 10,
                "total_working_days": 30,
                "days_worked": Decimal("26.0"),
                "paid_leaves": Decimal("2.0"),
                "unpaid_leaves": Decimal("2.0"),
                "overtime_hours": Decimal("5.00"),
                "overtime_rate": Decimal("500.00"),
                "notes": "Verified",
            }
        ]

        service = ReportsService(reports_repo=mock_repo)
        csv_text = service.generate_attendance_csv(year=2026, month=10)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        assert "Employee Code" in rows[0]
        assert "Days Worked" in rows[0]
        assert "Unpaid Leaves (LWP)" in rows[0]

        assert rows[1][0] == "EMP001"
        assert rows[1][1] == "Rajesh Kumar"
        assert rows[1][7] == "26.0"

    def test_generate_payments_csv(self):
        mock_repo = MagicMock()
        mock_repo.get_payment_export_data.return_value = [
            {
                "payment_reference": "TXN-202610-001",
                "payroll_code": "PAY-2026-10-EMP001",
                "employee_code": "EMP001",
                "employee_name": "Rajesh Kumar",
                "department": "Engineering",
                "year": 2026,
                "month": 10,
                "payment_method": "BANK_TRANSFER",
                "amount_paid": Decimal("90500.00"),
                "payment_date": "2026-10-29",
                "payment_status": "SUCCESSFUL",
                "transaction_notes": "Salary transferred successfully",
            }
        ]

        service = ReportsService(reports_repo=mock_repo)
        csv_text = service.generate_payments_csv(year=2026, month=10)

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        assert "Payment Reference" in rows[0]
        assert "Amount Paid (INR)" in rows[0]

        assert rows[1][0] == "TXN-202610-001"
        assert rows[1][8] == "90500.00"

    def test_generate_departments_csv(self):
        mock_repo = MagicMock()
        mock_repo.get_department_summary.return_value = MOCK_DEPARTMENT_SUMMARY

        service = ReportsService(reports_repo=mock_repo)
        csv_text = service.generate_departments_csv()

        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        assert "Department" in rows[0]
        assert "Total Employees" in rows[0]
        assert "Total Base Payroll (INR)" in rows[0]

        assert rows[1][0] == "Engineering"
        assert rows[1][1] == "4"
        assert rows[1][4] == "260000.00"


# ==============================================================================
# 3. Route Authorization & Rendering Tests
# ==============================================================================

class TestReportsRoutes:
    """Integration tests for reports blueprint endpoints."""

    def test_unauthenticated_access_redirects(self, client):
        """Unauthenticated requests to reports endpoints should redirect to /login."""
        endpoints = [
            "/reports",
            "/reports/",
            "/reports/export/payroll.csv",
            "/reports/export/attendance.csv",
            "/reports/export/payments.csv",
            "/reports/export/departments.csv",
            "/reports/dbms",
        ]
        for ep in endpoints:
            response = client.get(ep)
            assert response.status_code == 302
            assert "/login" in response.headers["Location"]

    @patch("modules.reports.routes.service")
    def test_reports_portal_payroll_tab(self, mock_service, client):
        """Authenticated request to /reports renders payroll tab with analytical metrics."""
        authenticate_session(client)
        setup_mock_service_defaults(mock_service)
        mock_service.get_monthly_summary.return_value = MOCK_PAYROLL_SUMMARY
        mock_service.get_status_and_method_distributions.return_value = {
            "status_distribution": MOCK_STATUS_DISTRIBUTION,
            "method_distribution": MOCK_PAYMENT_METHOD_DISTRIBUTION,
        }
        mock_service.get_department_summary.return_value = MOCK_DEPARTMENT_SUMMARY

        response = client.get("/reports?tab=payroll")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Financial &amp; Statutory Reports" in html or "Financial & Statutory Reports" in html
        assert "Total Gross Payroll" in html
        assert "Total Deductions" in html
        assert "Net Take-Home Disbursed" in html
        assert "Export Data (CSV)" in html

    @patch("modules.reports.routes.service")
    def test_reports_portal_attendance_tab(self, mock_service, client):
        """Authenticated request to /reports?tab=attendance renders attendance reconciliation."""
        authenticate_session(client)
        setup_mock_service_defaults(mock_service)
        mock_service.get_attendance_summary.return_value = (
            MOCK_ATTENDANCE_SUMMARY,
            1,
            MOCK_ATTENDANCE_METRICS,
        )

        response = client.get("/reports?tab=attendance")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Attendance &amp; Leave Reconciliation" in html or "Attendance & Leave Reconciliation" in html
        assert "Rajesh Kumar" in html
        assert "EMP001" in html

    @patch("modules.reports.routes.service")
    def test_reports_portal_salary_history_tab(self, mock_service, client):
        """Authenticated request to /reports?tab=salary_history renders employee salary history."""
        authenticate_session(client)
        setup_mock_service_defaults(mock_service)
        mock_service.get_employee_salary_history.return_value = (MOCK_SALARY_HISTORY, 1)

        response = client.get("/reports?tab=salary_history")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Employee Salary History" in html
        assert "Rajesh Kumar" in html
        assert "PAY-2026-10-EMP001" in html

    @patch("modules.reports.routes.service")
    def test_reports_portal_departments_tab(self, mock_service, client):
        """Authenticated request to /reports?tab=departments renders workforce distribution."""
        authenticate_session(client)
        setup_mock_service_defaults(mock_service)
        mock_service.get_department_summary.return_value = MOCK_DEPARTMENT_SUMMARY

        response = client.get("/reports?tab=departments")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Department Headcount &amp; Compensation Commitment" in html or "Department Headcount & Compensation Commitment" in html
        assert "Engineering" in html
        assert "Human Resources" in html

    @patch("modules.reports.routes.service")
    def test_export_payroll_csv_endpoint(self, mock_service, client):
        """Authenticated request to /reports/export/payroll.csv downloads RFC-4180 CSV."""
        authenticate_session(client)
        mock_service.generate_payroll_csv.return_value = "Payroll Code,Employee Code,Net Pay\nPAY-001,EMP001,50000.00\n"

        response = client.get("/reports/export/payroll.csv?year=2026&month=10")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert b"Payroll Code,Employee Code,Net Pay" in response.data

    @patch("modules.reports.routes.service")
    def test_export_attendance_csv_endpoint(self, mock_service, client):
        """Authenticated request to /reports/export/attendance.csv downloads RFC-4180 CSV."""
        authenticate_session(client)
        mock_service.generate_attendance_csv.return_value = "Employee Code,Present Days\nEMP001,26.0\n"

        response = client.get("/reports/export/attendance.csv?year=2026&month=10")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert b"Employee Code,Present Days" in response.data

    @patch("modules.reports.routes.service")
    def test_export_payments_csv_endpoint(self, mock_service, client):
        """Authenticated request to /reports/export/payments.csv downloads RFC-4180 CSV."""
        authenticate_session(client)
        mock_service.generate_payments_csv.return_value = "Payment Reference,Amount Paid\nTXN-001,50000.00\n"

        response = client.get("/reports/export/payments.csv?year=2026&month=10")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert b"Payment Reference,Amount Paid" in response.data

    @patch("modules.reports.routes.service")
    def test_export_departments_csv_endpoint(self, mock_service, client):
        """Authenticated request to /reports/export/departments.csv downloads RFC-4180 CSV."""
        authenticate_session(client)
        mock_service.generate_departments_csv.return_value = "Department,Total Headcount\nEngineering,4\n"

        response = client.get("/reports/export/departments.csv")
        assert response.status_code == 200
        assert response.mimetype == "text/csv"
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert b"Department,Total Headcount" in response.data

    def test_academic_dbms_documentation_page(self, client):
        """Authenticated request to /reports/dbms renders the complete academic documentation."""
        authenticate_session(client)

        response = client.get("/reports/dbms")
        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify key academic sections
        assert "Database Management System (DBMS) Academic Documentation" in html
        assert "1. Project Overview &amp; Problem Statement" in html or "1. Project Overview & Problem Statement" in html
        assert "2. Entity-Relationship (ER) Diagram" in html
        assert "3. Relational Schema Notation" in html
        assert "4. Table Specifications &amp; Data Dictionary" in html or "4. Table Specifications & Data Dictionary" in html
        assert "5. Entity Relationships &amp; Referential Integrity" in html or "5. Entity Relationships & Referential Integrity" in html
        assert "6. Normalization Analysis &amp; Decomposition Proofs" in html or "6. Normalization Analysis & Decomposition Proofs" in html
        assert "7. Parameterized CRUD Operations" in html
        assert "8. Multi-Table Analytical JOIN Queries" in html
        assert "9. Aggregations, GROUP BY &amp; Conditional Metrics" in html or "9. Aggregations, GROUP BY & Conditional Metrics" in html
        assert "10. Monthly Salary Calculation Model &amp; SQL Implementation" in html or "10. Monthly Salary Calculation Model & SQL Implementation" in html
        assert "11. Transaction Architecture &amp; ACID Guarantees" in html or "11. Transaction Architecture & ACID Guarantees" in html
        assert "12. Sample Dataset &amp; Mathematical Verification" in html or "12. Sample Dataset & Mathematical Verification" in html
        assert "13. Comprehensive Index of Demonstrated DBMS Concepts" in html

        # Verify Mermaid.js integration
        assert "mermaid" in html
        assert "erDiagram" in html
        assert "USERS" in html
        assert "EMPLOYEES" in html
        assert "SALARY_SETTINGS" in html
        assert "ATTENDANCE" in html
        assert "PAYROLL" in html
        assert "PAYMENTS" in html

        # Verify SQL examples and ACID details
        assert "START TRANSACTION" in html or "conn.commit()" in html
        assert "ON DELETE RESTRICT" in html
        assert "REPEATABLE READ" in html
