"""
Reports Repository for MySQL aggregation, multi-table joins, and statistical analysis.
Demonstrates:
- Multi-table INNER and LEFT JOINs across employees, attendance, salary_settings, payroll, and payments.
- Aggregations (SUM, AVG, COUNT, MIN, MAX, CASE WHEN).
- GROUP BY, HAVING, and ORDER BY clauses.
- Parameterized period, department, and employee filters.
- Pagination and export datasets.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ReportsRepository(BaseRepository):
    """Repository handling SQL reporting aggregations, analytical joins, and export queries."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def get_monthly_payroll_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculates aggregate payroll metrics for a selected month/year or all-time.
        Demonstrates SUM, COUNT, and CASE WHEN conditional aggregations.
        """
        try:
            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    COUNT(*) AS total_statements,
                    COALESCE(SUM(p.basic_pay), 0.00) AS total_basic,
                    COALESCE(SUM(p.allowances_total), 0.00) AS total_allowances,
                    COALESCE(SUM(p.overtime_pay), 0.00) AS total_overtime,
                    COALESCE(SUM(p.gross_pay), 0.00) AS total_gross,
                    COALESCE(SUM(p.leave_deduction), 0.00) AS total_leave_deductions,
                    COALESCE(SUM(p.other_deductions), 0.00) AS total_other_deductions,
                    COALESCE(SUM(p.total_deductions), 0.00) AS total_deductions,
                    COALESCE(SUM(p.net_pay), 0.00) AS total_net,
                    COALESCE(AVG(p.net_pay), 0.00) AS avg_net_pay,
                    COALESCE(SUM(CASE WHEN p.status = 'DRAFT' THEN 1 ELSE 0 END), 0) AS draft_count,
                    COALESCE(SUM(CASE WHEN p.status = 'APPROVED' THEN 1 ELSE 0 END), 0) AS approved_count,
                    COALESCE(SUM(CASE WHEN p.status = 'PAID' THEN 1 ELSE 0 END), 0) AS paid_count,
                    COALESCE(SUM(CASE WHEN p.status = 'CANCELLED' THEN 1 ELSE 0 END), 0) AS cancelled_count
                FROM payroll p
                {where_clause};
            """
            res = self.execute_query(query, tuple(params), fetch_one=True)
            if not res:
                return self._empty_payroll_summary()

            return {
                "total_statements": int(res.get("total_statements", 0)),
                "total_basic": Decimal(str(res.get("total_basic", "0.00"))),
                "total_allowances": Decimal(str(res.get("total_allowances", "0.00"))),
                "total_overtime": Decimal(str(res.get("total_overtime", "0.00"))),
                "total_gross": Decimal(str(res.get("total_gross", "0.00"))),
                "total_leave_deductions": Decimal(str(res.get("total_leave_deductions", "0.00"))),
                "total_other_deductions": Decimal(str(res.get("total_other_deductions", "0.00"))),
                "total_deductions": Decimal(str(res.get("total_deductions", "0.00"))),
                "total_net": Decimal(str(res.get("total_net", "0.00"))),
                "avg_net_pay": Decimal(str(res.get("avg_net_pay", "0.00"))),
                "draft_count": int(res.get("draft_count", 0)),
                "approved_count": int(res.get("approved_count", 0)),
                "paid_count": int(res.get("paid_count", 0)),
                "cancelled_count": int(res.get("cancelled_count", 0)),
            }
        except Exception as e:
            logger.error("Error computing monthly payroll summary: %s", e)
            return self._empty_payroll_summary()

    def _empty_payroll_summary(self) -> Dict[str, Any]:
        return {
            "total_statements": 0,
            "total_basic": Decimal("0.00"),
            "total_allowances": Decimal("0.00"),
            "total_overtime": Decimal("0.00"),
            "total_gross": Decimal("0.00"),
            "total_leave_deductions": Decimal("0.00"),
            "total_other_deductions": Decimal("0.00"),
            "total_deductions": Decimal("0.00"),
            "total_net": Decimal("0.00"),
            "avg_net_pay": Decimal("0.00"),
            "draft_count": 0,
            "approved_count": 0,
            "paid_count": 0,
            "cancelled_count": 0,
        }

    def get_employee_salary_history(
        self,
        employee_id: Optional[int] = None,
        department: Optional[str] = None,
        year: Optional[int] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fetches chronological salary disbursement history for employees.
        Demonstrates INNER JOINs across payroll, employees, and LEFT JOIN on payments.
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if employee_id:
                conditions.append("p.employee_id = %s")
                params.append(employee_id)

            if department and department.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department)

            if year:
                conditions.append("p.year = %s")
                params.append(year)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) AS total 
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                {where_clause};
            """
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # Data query
            data_query = f"""
                SELECT 
                    p.id AS payroll_id,
                    p.payroll_code,
                    p.year,
                    p.month,
                    p.basic_pay,
                    p.allowances_total,
                    p.overtime_pay,
                    p.gross_pay,
                    COALESCE(p.leave_deduction, 0.00) AS leave_deduction,
                    COALESCE(p.other_deductions, 0.00) AS other_deductions,
                    p.total_deductions,
                    p.net_pay,
                    p.status AS payroll_status,
                    p.generated_date,
                    e.id AS employee_id,
                    e.employee_code,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    pm.payment_reference,
                    pm.payment_method,
                    pm.payment_date,
                    pm.status AS payment_status
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                LEFT JOIN payments pm ON p.id = pm.payroll_id AND pm.status = 'SUCCESSFUL'
                {where_clause}
                ORDER BY p.year DESC, p.month DESC, e.first_name ASC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)
            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching employee salary history: %s", e)
            return [], 0

    def get_attendance_and_leave_summary(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
        employee_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """
        Monthly attendance reconciliation and leave analytics across staff.
        Demonstrates INNER JOIN between attendance and employees, with aggregations.
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if year:
                conditions.append("a.year = %s")
                params.append(year)
            if month:
                conditions.append("a.month = %s")
                params.append(month)
            if department and department.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department)
            if employee_id:
                conditions.append("a.employee_id = %s")
                params.append(employee_id)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 1. Total counts & metrics
            summary_query = f"""
                SELECT 
                    COUNT(*) AS total_records,
                    COALESCE(SUM(a.total_working_days), 0) AS total_working_days,
                    COALESCE(SUM(a.present_days), 0.0) AS total_days_worked,
                    COALESCE(SUM(a.paid_leaves), 0.0) AS total_paid_leaves,
                    COALESCE(SUM(a.unpaid_leaves), 0.0) AS total_unpaid_leaves,
                    COALESCE(SUM(a.overtime_hours), 0.00) AS total_overtime_hours,
                    COALESCE(AVG(a.present_days), 0.0) AS avg_days_worked
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                {where_clause};
            """
            s_res = self.execute_query(summary_query, tuple(params), fetch_one=True)
            total_count = int(s_res.get("total_records", 0)) if s_res else 0

            summary_totals = {
                "total_records": total_count,
                "total_working_days": int(s_res.get("total_working_days", 0)) if s_res else 0,
                "total_days_worked": Decimal(str(s_res.get("total_days_worked", "0.0"))) if s_res else Decimal("0.0"),
                "total_paid_leaves": Decimal(str(s_res.get("total_paid_leaves", "0.0"))) if s_res else Decimal("0.0"),
                "total_unpaid_leaves": Decimal(str(s_res.get("total_unpaid_leaves", "0.0"))) if s_res else Decimal("0.0"),
                "total_overtime_hours": Decimal(str(s_res.get("total_overtime_hours", "0.00"))) if s_res else Decimal("0.00"),
                "avg_days_worked": Decimal(str(s_res.get("avg_days_worked", "0.0"))) if s_res else Decimal("0.0"),
            }

            # 2. Paginated rows
            data_query = f"""
                SELECT 
                    a.id AS attendance_id,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    a.overtime_hours,
                    a.overtime_rate,
                    a.notes,
                    e.id AS employee_id,
                    e.employee_code,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                {where_clause}
                ORDER BY a.year DESC, a.month DESC, a.unpaid_leaves DESC, e.first_name ASC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)
            return rows if rows else [], total_count, summary_totals
        except Exception as e:
            logger.error("Error fetching attendance and leave summary: %s", e)
            return [], 0, {
                "total_records": 0,
                "total_working_days": 0,
                "total_days_worked": Decimal("0.0"),
                "total_paid_leaves": Decimal("0.0"),
                "total_unpaid_leaves": Decimal("0.0"),
                "total_overtime_hours": Decimal("0.00"),
                "avg_days_worked": Decimal("0.0"),
            }

    def get_department_summary(self) -> List[Dict[str, Any]]:
        """
        Employee distribution, headcount, and compensation commitment by department.
        Demonstrates GROUP BY, COUNT, SUM, AVG across employees and salary_settings.
        """
        try:
            query = """
                SELECT 
                    e.department,
                    COUNT(e.id) AS total_employees,
                    SUM(CASE WHEN e.status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_count,
                    SUM(CASE WHEN e.status = 'INACTIVE' THEN 1 ELSE 0 END) AS inactive_count,
                    COALESCE(SUM(s.base_salary), 0.00) AS total_base_payroll,
                    COALESCE(AVG(s.base_salary), 0.00) AS avg_base_salary,
                    COALESCE(SUM(s.hra + s.transport_allowance + s.medical_allowance + s.other_allowances), 0.00) AS total_allowances_pool,
                    COALESCE(MIN(s.base_salary), 0.00) AS min_salary,
                    COALESCE(MAX(s.base_salary), 0.00) AS max_salary
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                GROUP BY e.department
                ORDER BY total_employees DESC, e.department ASC;
            """
            rows = self.execute_query(query, fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error computing department summary: %s", e)
            return []

    def get_payroll_status_distribution(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Distribution of payroll records grouped by status.
        Demonstrates GROUP BY on ENUM column with COUNT and SUM.
        """
        try:
            conditions = []
            params = []

            if year:
                conditions.append("year = %s")
                params.append(year)
            if month:
                conditions.append("month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    status,
                    COUNT(*) AS count,
                    COALESCE(SUM(gross_pay), 0.00) AS gross_total,
                    COALESCE(SUM(net_pay), 0.00) AS net_total
                FROM payroll
                {where_clause}
                GROUP BY status
                ORDER BY count DESC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching payroll status distribution: %s", e)
            return []

    def get_payment_method_distribution(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Distribution of payments by disbursement method.
        Demonstrates GROUP BY on payment_method joined with payroll for period filter.
        """
        try:
            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    pm.payment_method,
                    pm.status AS payment_status,
                    COUNT(pm.id) AS transaction_count,
                    COALESCE(SUM(pm.amount_paid), 0.00) AS total_amount
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                {where_clause}
                GROUP BY pm.payment_method, pm.status
                ORDER BY total_amount DESC, transaction_count DESC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching payment method distribution: %s", e)
            return []

    def get_payroll_export_data(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export dataset for Monthly Payroll Register CSV."""
        try:
            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)
            if department and department.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    p.payroll_code,
                    e.employee_code,
                    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                    e.department,
                    e.designation,
                    p.year,
                    p.month,
                    p.basic_pay,
                    p.allowances_total,
                    p.overtime_pay,
                    p.gross_pay,
                    COALESCE(p.leave_deduction, 0.00) AS leave_deduction,
                    COALESCE(p.other_deductions, 0.00) AS other_deductions,
                    p.total_deductions,
                    p.net_pay,
                    p.status AS payroll_status,
                    p.generated_date,
                    pm.payment_reference,
                    pm.payment_method,
                    pm.payment_date,
                    pm.status AS payment_status
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                LEFT JOIN payments pm ON p.id = pm.payroll_id AND pm.status = 'SUCCESSFUL'
                {where_clause}
                ORDER BY p.year DESC, p.month DESC, e.department ASC, e.first_name ASC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching payroll export data: %s", e)
            return []

    def get_attendance_export_data(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Export dataset for Monthly Attendance Summary CSV."""
        try:
            conditions = []
            params = []

            if year:
                conditions.append("a.year = %s")
                params.append(year)
            if month:
                conditions.append("a.month = %s")
                params.append(month)
            if department and department.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    e.employee_code,
                    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                    e.department,
                    e.designation,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days AS days_worked,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    a.overtime_hours,
                    a.overtime_rate,
                    a.notes
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                {where_clause}
                ORDER BY a.year DESC, a.month DESC, e.department ASC, e.first_name ASC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching attendance export data: %s", e)
            return []

    def get_payment_export_data(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Export dataset for Payment History CSV."""
        try:
            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)
            if month:
                conditions.append("p.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    pm.payment_reference,
                    p.payroll_code,
                    e.employee_code,
                    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                    e.department,
                    p.year,
                    p.month,
                    pm.payment_method,
                    pm.amount_paid,
                    pm.payment_date,
                    pm.status AS payment_status,
                    pm.transaction_notes
                FROM payments pm
                JOIN payroll p ON pm.payroll_id = p.id
                JOIN employees e ON p.employee_id = e.id
                {where_clause}
                ORDER BY pm.payment_date DESC, pm.id DESC;
            """
            rows = self.execute_query(query, tuple(params), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching payment export data: %s", e)
            return []
