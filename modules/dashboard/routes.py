"""
Finance Manager Dashboard routes for Employee Payroll Management System.
Aggregates active employee count, monthly payroll sums, deductions, net paid,
pending records, recent activity, and Chart.js trend datasets.
"""

from datetime import datetime, timezone
import json
from flask import Blueprint, render_template, request, session, current_app
from modules.auth.services import login_required, get_current_user
from repositories.dashboard_repository import DashboardRepository

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
dashboard_repo = DashboardRepository()


@dashboard_bp.route("")
@dashboard_bp.route("/")
@login_required
def index():
    """
    Finance Manager Dashboard view.
    Displays financial KPIs, monthly filters, recent payroll activity, and Chart.js trends.
    """
    current_user = get_current_user()
    available_periods = dashboard_repo.get_available_payroll_periods()

    # Determine default or user-selected year and month
    now = datetime.now()
    default_year = available_periods[0]["year"] if available_periods else now.year
    default_month = available_periods[0]["month"] if available_periods else now.month

    try:
        selected_year = int(request.args.get("year", default_year))
        selected_month = int(request.args.get("month", default_month))
        if selected_month < 1 or selected_month > 12:
            selected_month = default_month
    except (ValueError, TypeError):
        selected_year = default_year
        selected_month = default_month

    # Retrieve metrics safely using parameterized database queries
    active_employees = dashboard_repo.get_active_employee_count()
    payroll_summary = dashboard_repo.get_monthly_payroll_summary(selected_year, selected_month)
    pending_records_count = dashboard_repo.get_pending_payroll_count()
    awaiting_approval_count = dashboard_repo.get_awaiting_approval_count()
    awaiting_payment_count = dashboard_repo.get_approved_awaiting_payment_count()
    recent_activity = dashboard_repo.get_recent_payroll_activity(limit=6)
    chart_trends = dashboard_repo.get_monthly_payroll_trend(limit_months=6)

    # Format data for Chart.js
    chart_labels = [row["period"] for row in chart_trends]
    chart_gross_data = [row["gross_total"] for row in chart_trends]
    chart_net_data = [row["net_total"] for row in chart_trends]

    # Month names mapping for friendly display
    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    return render_template(
        "dashboard/index.html",
        current_user=current_user,
        active_employees=active_employees,
        payroll_summary=payroll_summary,
        pending_records_count=pending_records_count,
        awaiting_approval_count=awaiting_approval_count,
        awaiting_payment_count=awaiting_payment_count,
        recent_activity=recent_activity,
        chart_labels_json=json.dumps(chart_labels),
        chart_gross_json=json.dumps(chart_gross_data),
        chart_net_json=json.dumps(chart_net_data),
        has_chart_data=len(chart_trends) > 0,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_month_name=month_names.get(selected_month, str(selected_month)),
        available_periods=available_periods,
    )
