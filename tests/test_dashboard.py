"""
Automated tests for Finance Manager Dashboard (Module 2).
Tests dashboard rendering, KPI calculations, empty database resilience,
period filtering, and unfinished module placeholders.
"""

from decimal import Decimal
from unittest.mock import patch


def authenticate_client_session(client, user_id=1, username="michael.fin", role="ACCOUNTANT"):
    """Helper to inject an authenticated Finance Manager session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["email"] = f"{username}@example.com"
        sess["role"] = role


def test_dashboard_unauthenticated_redirect(client):
    """Verify unauthenticated user cannot access dashboard."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location


def test_dashboard_empty_database_graceful_handling(client):
    """
    Verify dashboard renders smoothly with HTTP 200 and zeroed figures
    when the database contains zero employees and zero payroll records.
    """
    authenticate_client_session(client)

    empty_summary = {
        "gross_total": Decimal("0.00"),
        "deductions_total": Decimal("0.00"),
        "net_paid_total": Decimal("0.00"),
        "record_count": 0,
    }

    with patch("repositories.dashboard_repository.DashboardRepository.get_active_employee_count", return_value=0), \
         patch("repositories.dashboard_repository.DashboardRepository.get_monthly_payroll_summary", return_value=empty_summary), \
         patch("repositories.dashboard_repository.DashboardRepository.get_pending_payroll_count", return_value=0), \
         patch("repositories.dashboard_repository.DashboardRepository.get_recent_payroll_activity", return_value=[]), \
         patch("repositories.dashboard_repository.DashboardRepository.get_monthly_payroll_trend", return_value=[]), \
         patch("repositories.dashboard_repository.DashboardRepository.get_available_payroll_periods", return_value=[]):

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Finance Management Dashboard" in response.data
        assert b"$0.00" in response.data
        assert b"No recent payroll transactions found" in response.data
        assert b"No Historical Payroll Records" in response.data


def test_dashboard_with_populated_records(client):
    """Verify dashboard correctly formats and displays actual financial metrics."""
    authenticate_client_session(client)

    populated_summary = {
        "gross_total": Decimal("117976.29"),
        "deductions_total": Decimal("22497.63"),
        "net_paid_total": Decimal("95478.66"),
        "record_count": 3,
    }

    mock_activity = [
        {
            "id": 1,
            "payroll_code": "PAY-2026-09-EMP001",
            "year": 2026,
            "month": 9,
            "gross_pay": Decimal("117976.29"),
            "total_deductions": Decimal("22497.63"),
            "net_pay": Decimal("95478.66"),
            "status": "PAID",
            "generated_date": "2026-09-30",
            "employee_code": "EMP001",
            "first_name": "John",
            "last_name": "Doe",
            "department": "Engineering",
        }
    ]

    mock_trends = [
        {"period": "2026-09", "gross_total": 117976.29, "net_total": 95478.66, "employee_count": 3}
    ]

    with patch("repositories.dashboard_repository.DashboardRepository.get_active_employee_count", return_value=3), \
         patch("repositories.dashboard_repository.DashboardRepository.get_monthly_payroll_summary", return_value=populated_summary), \
         patch("repositories.dashboard_repository.DashboardRepository.get_pending_payroll_count", return_value=2), \
         patch("repositories.dashboard_repository.DashboardRepository.get_recent_payroll_activity", return_value=mock_activity), \
         patch("repositories.dashboard_repository.DashboardRepository.get_monthly_payroll_trend", return_value=mock_trends), \
         patch("repositories.dashboard_repository.DashboardRepository.get_available_payroll_periods", return_value=[{"year": 2026, "month": 9}]):

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"117,976.29" in response.data
        assert b"95,478.66" in response.data
        assert b"22,497.63" in response.data
        assert b"2 Payroll Record(s) Awaiting Processing" in response.data
        assert b"PAY-2026-09-EMP001" in response.data
        assert b"John Doe" in response.data


def test_dashboard_month_year_filter_query_params(client):
    """Verify period filter arguments update the dashboard calculation."""
    authenticate_client_session(client)

    empty_summary = {
        "gross_total": Decimal("0.00"),
        "deductions_total": Decimal("0.00"),
        "net_paid_total": Decimal("0.00"),
        "record_count": 0,
    }

    with patch("repositories.dashboard_repository.DashboardRepository.get_monthly_payroll_summary", return_value=empty_summary) as mock_calc:
        response = client.get("/dashboard?year=2026&month=5")
        assert response.status_code == 200
        mock_calc.assert_called_once_with(2026, 5)


def test_unfinished_modules_clearly_marked(client):
    """
    Verify all core production modules (Employees, Attendance, Salary, Payroll, Payments, Reports)
    are accessible and active without 404 or unhandled errors.
    """
    authenticate_client_session(client)

    endpoints = [
        "/reports",
        "/payments",
        "/payroll",
        "/salary",
        "/attendance",
        "/employees",
    ]

    for url in endpoints:
        response = client.get(url)
        assert response.status_code == 200, f"Expected 200 for {url}"
