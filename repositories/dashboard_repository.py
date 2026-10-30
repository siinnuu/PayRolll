"""
Dashboard Repository for calculating financial metrics and operational activity.
Uses parameterized queries and handles empty or partially populated databases safely.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DashboardRepository(BaseRepository):
    """Repository providing metrics and aggregations for the Finance Manager dashboard."""

    def get_active_employee_count(self) -> int:
        """
        Count active employees.
        Returns 0 if table is empty or database is unreachable.
        """
        try:
            query = "SELECT COUNT(*) AS total FROM employees WHERE status = 'ACTIVE';"
            result = self.execute_query(query, fetch_one=True)
            return int(result.get("total", 0)) if result else 0
        except Exception as e:
            logger.warning("Error fetching active employee count: %s", e)
            return 0

    def get_monthly_payroll_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        Calculate gross pay total, total deductions, net salary, and net salary paid for the specified month.
        Also tallies counts for generated (draft), approved, and paid statements.
        Returns zeroed financial values if no records match or database is empty.
        """
        defaults = {
            "gross_total": Decimal("0.00"),
            "deductions_total": Decimal("0.00"),
            "net_total": Decimal("0.00"),
            "net_paid_total": Decimal("0.00"),
            "record_count": 0,
            "generated_count": 0,
            "approved_count": 0,
            "paid_count": 0,
        }
        try:
            # Note: net_paid_total strictly calculates records that have status 'PAID'
            query = """
                SELECT 
                    COALESCE(SUM(gross_pay), 0.00) AS gross_total,
                    COALESCE(SUM(total_deductions), 0.00) AS deductions_total,
                    COALESCE(SUM(net_pay), 0.00) AS net_total,
                    COALESCE(SUM(CASE WHEN status = 'PAID' THEN net_pay ELSE 0.00 END), 0.00) AS net_paid_total,
                    COUNT(*) AS record_count,
                    COALESCE(SUM(CASE WHEN status IN ('DRAFT', 'GENERATED') THEN 1 ELSE 0 END), 0) AS generated_count,
                    COALESCE(SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END), 0) AS approved_count,
                    COALESCE(SUM(CASE WHEN status = 'PAID' THEN 1 ELSE 0 END), 0) AS paid_count
                FROM payroll
                WHERE year = %s AND month = %s;
            """
            result = self.execute_query(query, (year, month), fetch_one=True)
            if result:
                return {
                    "gross_total": Decimal(str(result.get("gross_total") or "0.00")),
                    "deductions_total": Decimal(str(result.get("deductions_total") or "0.00")),
                    "net_total": Decimal(str(result.get("net_total") or "0.00")),
                    "net_paid_total": Decimal(str(result.get("net_paid_total") or "0.00")),
                    "record_count": int(result.get("record_count") or 0),
                    "generated_count": int(result.get("generated_count") or 0),
                    "approved_count": int(result.get("approved_count") or 0),
                    "paid_count": int(result.get("paid_count") or 0),
                }
            return defaults
        except Exception as e:
            logger.warning("Error fetching monthly payroll summary for %04d-%02d: %s", year, month, e)
            return defaults

    def get_awaiting_approval_count(self) -> int:
        """Count payroll records awaiting approval (status in 'DRAFT', 'GENERATED')."""
        try:
            query = "SELECT COUNT(*) AS total FROM payroll WHERE status IN ('DRAFT', 'GENERATED');"
            result = self.execute_query(query, fetch_one=True)
            return int(result.get("total", 0)) if result else 0
        except Exception as e:
            logger.warning("Error fetching awaiting approval count: %s", e)
            return 0

    def get_approved_awaiting_payment_count(self) -> int:
        """Count approved payroll records awaiting payment (status = 'APPROVED')."""
        try:
            query = "SELECT COUNT(*) AS total FROM payroll WHERE status = 'APPROVED';"
            result = self.execute_query(query, fetch_one=True)
            return int(result.get("total", 0)) if result else 0
        except Exception as e:
            logger.warning("Error fetching approved awaiting payment count: %s", e)
            return 0

    def get_pending_payroll_count(self, year: Optional[int] = None, month: Optional[int] = None) -> int:
        """
        Count payroll records awaiting processing (status in 'DRAFT', 'GENERATED').
        Optionally filters by year and month.
        """
        try:
            if year is not None and month is not None:
                query = """
                    SELECT COUNT(*) AS total 
                    FROM payroll 
                    WHERE status IN ('DRAFT', 'GENERATED') AND year = %s AND month = %s;
                """
                result = self.execute_query(query, (year, month), fetch_one=True)
            else:
                query = """
                    SELECT COUNT(*) AS total 
                    FROM payroll 
                    WHERE status IN ('DRAFT', 'GENERATED');
                """
                result = self.execute_query(query, fetch_one=True)
            return int(result.get("total", 0)) if result else 0
        except Exception as e:
            logger.warning("Error fetching pending payroll count: %s", e)
            return 0

    def get_recent_payroll_activity(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Retrieve recent payroll calculation and payment records joined with employee names.
        Returns empty list if no activity exists.
        """
        try:
            query = """
                SELECT 
                    p.id,
                    p.payroll_code,
                    p.year,
                    p.month,
                    p.gross_pay,
                    p.total_deductions,
                    p.net_pay,
                    p.status,
                    p.generated_date,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.department
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                ORDER BY p.id DESC
                LIMIT %s;
            """
            rows = self.execute_query(query, (limit,), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.warning("Error fetching recent payroll activity: %s", e)
            return []

    def get_monthly_payroll_trend(self, limit_months: int = 6) -> List[Dict[str, Any]]:
        """
        Retrieve aggregated monthly payroll trends (gross and net totals) for Chart.js.
        Returns chronologically sorted list of months.
        """
        try:
            query = """
                SELECT 
                    year,
                    month,
                    COALESCE(SUM(gross_pay), 0.00) AS gross_total,
                    COALESCE(SUM(net_pay), 0.00) AS net_total,
                    COUNT(*) AS employee_count
                FROM payroll
                GROUP BY year, month
                ORDER BY year DESC, month DESC
                LIMIT %s;
            """
            rows = self.execute_query(query, (limit_months,), fetch_all=True)
            if not rows:
                return []

            # Format for Chart.js and order chronologically (oldest to newest)
            data = []
            for row in reversed(rows):
                year = int(row["year"])
                month = int(row["month"])
                data.append({
                    "period": f"{year}-{month:02d}",
                    "gross_total": float(row.get("gross_total") or 0.0),
                    "net_total": float(row.get("net_total") or 0.0),
                    "employee_count": int(row.get("employee_count") or 0),
                })
            return data
        except Exception as e:
            logger.warning("Error fetching monthly payroll trend: %s", e)
            return []

    def get_available_payroll_periods(self) -> List[Dict[str, int]]:
        """Retrieve distinct year/month combinations present in payroll table for filter selector."""
        try:
            query = """
                SELECT DISTINCT year, month 
                FROM payroll 
                ORDER BY year DESC, month DESC;
            """
            rows = self.execute_query(query, fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.warning("Error fetching available payroll periods: %s", e)
            return []
