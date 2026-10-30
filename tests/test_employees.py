"""
Automated tests for Employee Management (Module 3).
Tests paginated listing, search, validation, atomic employee addition,
duplicate rejection, editing, deactivation, reactivation, and historical data preservation.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest


def authenticate_session(client, user_id=1, username="admin", role="ADMIN", token="valid_test_csrf_token_999"):
    """Helper to inject an authenticated session with a valid CSRF token."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["email"] = f"{username}@payroll.local"
        sess["role"] = role
        sess["_csrf_token"] = token
    return token


def get_csrf_token(client):
    """Helper to obtain a valid CSRF token from the active session."""
    with client.session_transaction() as sess:
        if "_csrf_token" not in sess:
            sess["_csrf_token"] = "valid_test_csrf_token_999"
        return sess["_csrf_token"]


def test_employee_index_unauthenticated_redirect(client):
    """Verify unauthenticated user cannot access employee directory."""
    response = client.get("/employees", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.location
    assert "next=/employees" in response.location or "next=%2Femployees" in response.location


def test_employee_index_renders_with_paginated_list(client):
    """Verify employee directory renders paginated list with stats and actions."""
    authenticate_session(client)

    sample_employees = [
        {
            "id": 1,
            "employee_code": "EMP001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-0101",
            "department": "Engineering",
            "designation": "Lead Software Engineer",
            "joining_date": "2023-01-15",
            "status": "ACTIVE",
            "base_salary": Decimal("85000.00"),
        },
        {
            "id": 2,
            "employee_code": "EMP002",
            "first_name": "Sarah",
            "last_name": "Jenkins",
            "email": "sarah.jenkins@example.com",
            "phone": "+1-555-0102",
            "department": "Human Resources",
            "designation": "HR Manager",
            "joining_date": "2023-03-01",
            "status": "INACTIVE",
            "base_salary": Decimal("65000.00"),
        },
    ]

    with patch("repositories.employee_repository.EmployeeRepository.get_paginated_employees", return_value=(sample_employees, 2)):
        response = client.get("/employees")
        assert response.status_code == 200
        assert b"Employee Directory" in response.data
        assert b"EMP001" in response.data
        assert b"John Doe" in response.data
        assert b"Engineering" in response.data
        assert b"EMP002" in response.data
        assert b"Sarah Jenkins" in response.data
        assert b"85,000.00" in response.data


def test_employee_search_and_filter(client):
    """Verify search and department filter arguments are passed to repository."""
    authenticate_session(client)

    with patch("repositories.employee_repository.EmployeeRepository.get_paginated_employees", return_value=([], 0)) as mock_query:
        response = client.get("/employees?search=John&department=Engineering&status=ACTIVE&page=2")
        assert response.status_code == 200
        mock_query.assert_called_once_with(
            search="John",
            status_filter="ACTIVE",
            department_filter="Engineering",
            page=2,
            per_page=10
        )


def test_employee_add_page_renders(client):
    """Verify add employee form renders with CSRF token and auto-suggested code."""
    authenticate_session(client)

    with patch("repositories.employee_repository.EmployeeRepository.generate_next_employee_code", return_value="EMP004"):
        response = client.get("/employees/add")
        assert response.status_code == 200
        assert b"Add New Employee" in response.data
        assert b"EMP004" in response.data
        assert b"Basic Monthly Salary" in response.data
        assert b"csrf_token" in response.data


def test_employee_add_success(client):
    """Verify valid form submission creates employee atomically and redirects to profile."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP004",
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@example.com",
        "phone": "+1-555-0104",
        "department": "Engineering",
        "designation": "Backend Developer",
        "joining_date": "2026-10-01",
        "base_salary": "72000.00",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.create_employee", return_value=105) as mock_create:

        response = client.post("/employees/add", data=payload, follow_redirects=False)
        assert response.status_code == 302
        assert "/employees/105" in response.location
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert args[0]["employee_code"] == "EMP004"
        assert args[0]["first_name"] == "David"
        assert args[1] == Decimal("72000.00")


def test_employee_add_duplicate_code(client):
    """Verify server rejects duplicate employee code with HTTP 422."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP001",  # already exists
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@example.com",
        "department": "Engineering",
        "designation": "Developer",
        "joining_date": "2026-10-01",
        "base_salary": "72000.00",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value={"id": 1, "employee_code": "EMP001"}):
        response = client.post("/employees/add", data=payload)
        assert response.status_code == 422
        assert b"already assigned to another employee" in response.data


def test_employee_add_duplicate_email(client):
    """Verify server rejects duplicate employee email with HTTP 422."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP004",
        "first_name": "David",
        "last_name": "Kim",
        "email": "john.doe@example.com",  # duplicate email
        "department": "Engineering",
        "designation": "Developer",
        "joining_date": "2026-10-01",
        "base_salary": "72000.00",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value={"id": 1, "email": "john.doe@example.com"}):
        response = client.post("/employees/add", data=payload)
        assert response.status_code == 422
        assert b"already registered" in response.data


def test_employee_add_invalid_salary_negative(client):
    """Verify server rejects negative salary amounts."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP004",
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@example.com",
        "department": "Engineering",
        "designation": "Developer",
        "joining_date": "2026-10-01",
        "base_salary": "-5000.00",  # negative salary
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value=None):
        response = client.post("/employees/add", data=payload)
        assert response.status_code == 422
        assert b"cannot be negative" in response.data


def test_employee_add_invalid_salary_non_numeric(client):
    """Verify server rejects non-numeric salary values."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP004",
        "first_name": "David",
        "last_name": "Kim",
        "email": "david.kim@example.com",
        "department": "Engineering",
        "designation": "Developer",
        "joining_date": "2026-10-01",
        "base_salary": "not_a_number",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value=None):
        response = client.post("/employees/add", data=payload)
        assert response.status_code == 422
        assert b"valid numeric salary" in response.data


def test_employee_add_invalid_email_format(client):
    """Verify server rejects invalid email formatting."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    payload = {
        "csrf_token": csrf_token,
        "employee_code": "EMP004",
        "first_name": "David",
        "last_name": "Kim",
        "email": "invalid-email-address",
        "department": "Engineering",
        "designation": "Developer",
        "joining_date": "2026-10-01",
        "base_salary": "72000.00",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_code", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value=None):
        response = client.post("/employees/add", data=payload)
        assert response.status_code == 422
        assert b"valid email address" in response.data


def test_employee_view_details(client):
    """Verify employee profile view renders details and historical audit metrics."""
    authenticate_session(client)

    sample_emp = {
        "id": 1,
        "employee_code": "EMP001",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-0101",
        "department": "Engineering",
        "designation": "Lead Software Engineer",
        "joining_date": "2023-01-15",
        "status": "ACTIVE",
        "base_salary": Decimal("85000.00"),
        "hra": Decimal("25500.00"),
        "transport_allowance": Decimal("3000.00"),
        "medical_allowance": Decimal("2500.00"),
        "created_at": "2023-01-15 10:00:00",
        "updated_at": "2026-10-29 12:00:00",
    }

    mock_history = {
        "has_history": True,
        "payroll_count": 3,
        "attendance_count": 6,
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=sample_emp), \
         patch("repositories.employee_repository.EmployeeRepository.has_historical_records", return_value=mock_history):

        response = client.get("/employees/1")
        assert response.status_code == 200
        assert b"John Doe" in response.data
        assert b"EMP001" in response.data
        assert b"Lead Software Engineer" in response.data
        assert b"85,000.00" in response.data
        assert b"3 records" in response.data
        assert b"6 records" in response.data
        assert b"Historical Record Preservation" in response.data


def test_employee_edit_success(client):
    """Verify editing employee details updates profile and salary atomically."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    existing_emp = {
        "id": 1,
        "employee_code": "EMP001",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "department": "Engineering",
        "designation": "Software Engineer",
        "joining_date": "2023-01-15",
        "status": "ACTIVE",
        "base_salary": Decimal("85000.00"),
    }

    update_payload = {
        "csrf_token": csrf_token,
        "first_name": "Jonathan",
        "last_name": "Doe",
        "email": "jonathan.doe@example.com",
        "phone": "+1-555-0999",
        "department": "Engineering",
        "designation": "Principal Engineer",
        "joining_date": "2023-01-15",
        "base_salary": "95000.00",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=existing_emp), \
         patch("repositories.employee_repository.EmployeeRepository.get_by_email", return_value=None), \
         patch("repositories.employee_repository.EmployeeRepository.update_employee", return_value=True) as mock_update:

        response = client.post("/employees/1/edit", data=update_payload, follow_redirects=False)
        assert response.status_code == 302
        assert "/employees/1" in response.location
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert args[0] == 1
        assert args[1]["first_name"] == "Jonathan"
        assert kwargs["base_salary"] == Decimal("95000.00")


def test_employee_deactivate(client):
    """Verify deactivation sets employee status to INACTIVE while preserving history."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    existing_emp = {
        "id": 1,
        "employee_code": "EMP001",
        "first_name": "John",
        "last_name": "Doe",
        "status": "ACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=existing_emp), \
         patch("repositories.employee_repository.EmployeeRepository.set_employee_status", return_value=True) as mock_status:

        response = client.post("/employees/1/deactivate", data={"csrf_token": csrf_token}, follow_redirects=False)
        assert response.status_code == 302
        mock_status.assert_called_once_with(1, "INACTIVE")


def test_employee_reactivate(client):
    """Verify reactivation sets inactive employee status back to ACTIVE."""
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    existing_emp = {
        "id": 2,
        "employee_code": "EMP002",
        "first_name": "Sarah",
        "last_name": "Jenkins",
        "status": "INACTIVE",
    }

    with patch("repositories.employee_repository.EmployeeRepository.get_by_id", return_value=existing_emp), \
         patch("repositories.employee_repository.EmployeeRepository.set_employee_status", return_value=True) as mock_status:

        response = client.post("/employees/2/reactivate", data={"csrf_token": csrf_token}, follow_redirects=False)
        assert response.status_code == 302
        mock_status.assert_called_once_with(2, "ACTIVE")


def test_preservation_of_payroll_history_blocks_deletion(client):
    """
    Verify hard deletion is strictly rejected when an employee has historical
    payroll statements, preserving accounting audit compliance.
    """
    authenticate_session(client)
    csrf_token = get_csrf_token(client)

    with patch(
        "repositories.employee_repository.EmployeeRepository.delete_employee",
        return_value=(False, "Cannot delete employee. Historical records exist (3 payroll, 6 attendance). Deactivate the employee instead.")
    ) as mock_del:

        response = client.post("/employees/1/delete", data={"csrf_token": csrf_token}, follow_redirects=False)
        assert response.status_code == 302
        assert "/employees/1" in response.location
        mock_del.assert_called_once_with(1)
