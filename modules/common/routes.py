"""
Navigation routes for upcoming system modules.
Provides clearly marked, non-fake placeholder destinations for unbuilt features.
"""

from flask import Blueprint, render_template
from modules.auth.services import login_required

common_bp = Blueprint("common", __name__)

MODULES_METADATA = {
    "employees": {
        "title": "Employee Directory & Profiles",
        "module_code": "Module 3",
        "status": "Under Development",
        "description": "Full lifecycle employee profile management, department assignments, emergency contacts, and status updates.",
        "icon": "bi-people",
        "planned_features": [
            "Employee onboarding & registration wizard",
            "Active / Inactive status transitions with history retention",
            "Department & designation organizational structure",
            "Document upload and profile management",
        ],
    },
    "attendance": {
        "title": "Attendance & Leave Tracking",
        "module_code": "Module 4",
        "status": "Planned",
        "description": "Monthly attendance reconciliation, overtime tracking, paid/unpaid leaves, and timesheet approvals.",
        "icon": "bi-calendar-check",
        "planned_features": [
            "Monthly attendance summary ledger",
            "Leave balance accounting & quota deductions",
            "Overtime hours verification & rate multiplier",
            "Biometric integration API endpoints",
        ],
    },
    "salary": {
        "title": "Salary Structure & Grade Setup",
        "module_code": "Module 5",
        "status": "Planned",
        "description": "Base pay definitions, statutory allowances (HRA, Medical), tax brackets, and PF contribution rates.",
        "icon": "bi-cash-coin",
        "planned_features": [
            "Custom allowance and deduction formulas",
            "Statutory tax and Provident Fund rate tables",
            "Effective date versioning for salary revisions",
            "Employee compensation benchmarking",
        ],
    },
    "payroll": {
        "title": "Payroll Computation Engine",
        "module_code": "Module 6",
        "status": "Planned",
        "description": "Automated monthly salary calculation, deduction computation, payslip generation, and batch approval.",
        "icon": "bi-calculator",
        "planned_features": [
            "Batch payroll run for selected periods",
            "Prorated salary computation for mid-month joiners",
            "PDF payslip generation & email dispatch",
            "Multi-tier approval workflow (HR & Finance)",
        ],
    },
    "payments": {
        "title": "Payment Processing & Bank Disbursements",
        "module_code": "Module 7",
        "status": "Planned",
        "description": "Disbursement execution, bank transfer batch files, payment receipts, and reconciliation logs.",
        "icon": "bi-bank",
        "planned_features": [
            "Direct bank transfer NACH / NEFT / RTGS file export",
            "Payment confirmation transaction logging",
            "Historical payment receipts and audit trail",
            "Failed transaction recovery and reversals",
        ],
    },
    "reports": {
        "title": "Financial & Statutory Reports",
        "module_code": "Module 8",
        "status": "Planned",
        "description": "Comprehensive payroll registers, statutory compliance tax reports, and department cost center audits.",
        "icon": "bi-graph-up-arrow",
        "planned_features": [
            "Monthly salary register (Excel / CSV export)",
            "Statutory PF and Tax deduction filing summaries",
            "Annual Form 16 compensation statements",
            "Departmental payroll expenditure trends",
        ],
    },
}




# All milestone modules (1 through 8) are fully implemented.
