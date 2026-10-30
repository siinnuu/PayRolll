"""
Core routes for the Employee Payroll Management System.
Renders the primary application dashboard, architectural overview, and module readiness.
"""

from flask import Blueprint, render_template, current_app
from repositories.health_repository import HealthRepository

core_bp = Blueprint("core", __name__)
health_repo = HealthRepository()


@core_bp.route("/")
def index():
    """
    Main landing dashboard for Module 1.
    Displays architectural status, registered blueprints, database status, and setup instructions.
    """
    db_status = health_repo.test_database_connectivity()
    schema_status = health_repo.get_schema_verification() if db_status.get("connected") else {
        "verified": False,
        "missing_tables": ["users", "employees", "attendance", "salary_settings", "payroll", "payments"],
        "table_counts": {},
    }

    modules_info = [
        {
            "id": 1,
            "name": "Module 1: Architecture & Foundation",
            "status": "COMPLETED",
            "badge_class": "success",
            "description": "Flask factory pattern, MySQL schema (6 tables), connection helper, connection pool, seed data, and health diagnostics.",
        },
        {
            "id": 2,
            "name": "Module 2: Employee & Salary Profiles",
            "status": "PLANNED",
            "badge_class": "secondary",
            "description": "CRUD operations for employees, salary structure configuration, and statutory rate setups.",
        },
        {
            "id": 3,
            "name": "Module 3: Attendance Tracking",
            "status": "PLANNED",
            "badge_class": "secondary",
            "description": "Monthly attendance summaries, leave tracking, and overtime calculation.",
        },
        {
            "id": 4,
            "name": "Module 4: Payroll Computation Engine",
            "status": "PLANNED",
            "badge_class": "secondary",
            "description": "Gross pay, deductions, tax calculation, and monthly payslip generation.",
        },
        {
            "id": 5,
            "name": "Module 5: Payment Processing & Reporting",
            "status": "PLANNED",
            "badge_class": "secondary",
            "description": "Payment disbursement logs, bank reports, and financial summaries.",
        },
    ]

    tables_info = [
        {"name": "users", "desc": "Authentication & role-based credentials (hashed passwords)", "engine": "InnoDB"},
        {"name": "employees", "desc": "Employee master records with status tracking", "engine": "InnoDB"},
        {"name": "salary_settings", "desc": "Base pay, allowances, and statutory deduction rates", "engine": "InnoDB"},
        {"name": "attendance", "desc": "Monthly attendance summary (1 record/employee/month)", "engine": "InnoDB"},
        {"name": "payroll", "desc": "Main payroll calculation (1 record/employee/month)", "engine": "InnoDB"},
        {"name": "payments", "desc": "Disbursement records preserved against historical payroll", "engine": "InnoDB"},
    ]

    return render_template(
        "index.html",
        db_status=db_status,
        schema_status=schema_status,
        modules=modules_info,
        tables=tables_info,
        app_name=current_app.config.get("APP_NAME"),
        app_version=current_app.config.get("APP_VERSION"),
    )
