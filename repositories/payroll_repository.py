"""
Payroll Repository for MySQL operations on the `payroll` table.
Handles parameterized queries, transactions, status transitions,
concurrency safeguards, pagination, and financial summaries.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PayrollRepository(BaseRepository):
    """Repository handling CRUD, status transitions, and queries for monthly payroll."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self._ensure_schema_columns()

    def _ensure_schema_columns(self) -> None:
        """
        Verify that `leave_deduction` column exists on the payroll table.
        Gracefully handles migrations if initialized on a legacy schema.
        """
        try:
            check_col_query = """
                SELECT COUNT(*) AS cnt 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'payroll' 
                  AND COLUMN_NAME = 'leave_deduction';
            """
            res = self.execute_query(check_col_query, fetch_one=True)
            if res and int(res.get("cnt", 0)) == 0:
                alter_sql = """
                    ALTER TABLE payroll 
                    ADD COLUMN leave_deduction DECIMAL(12,2) NOT NULL DEFAULT 0.00 
                    AFTER gross_pay;
                """
                self.execute_query(alter_sql, commit=True)
                logger.info("Successfully added 'leave_deduction' column to payroll table.")
        except Exception as e:
            logger.debug("Schema column verification notice on payroll: %s", e)

    def generate_payroll_code(self, year: int, month: int, employee_code: str) -> str:
        """Standardized unique payroll statement identifier."""
        return f"PAY-{year}-{month:02d}-{employee_code.upper()}"

    def get_by_id(self, payroll_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single payroll record by its ID joined with employee information."""
        try:
            query = """
                SELECT 
                    p.id,
                    p.id AS payroll_id,
                    p.payroll_code,
                    p.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.status AS employee_status,
                    p.year,
                    p.month,
                    p.basic_pay,
                    p.allowances_total,
                    p.overtime_pay,
                    p.gross_pay,
                    COALESCE(p.leave_deduction, 0.00) AS leave_deduction,
                    COALESCE(p.tax_deduction, 0.00) AS tax_deduction,
                    COALESCE(p.pf_deduction, 0.00) AS pf_deduction,
                    COALESCE(p.other_deductions, 0.00) AS other_deductions,
                    p.total_deductions,
                    p.net_pay,
                    p.status,
                    p.generated_date,
                    p.payment_due_date,
                    p.remarks,
                    p.created_at,
                    p.updated_at
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                WHERE p.id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (payroll_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching payroll ID %s: %s", payroll_id, e)
            return None

    def get_by_employee_and_period(
        self, employee_id: int, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        """Look up existing payroll record for an employee in a given month and year."""
        try:
            query = """
                SELECT 
                    p.id,
                    p.id AS payroll_id,
                    p.payroll_code,
                    p.employee_id,
                    p.year,
                    p.month,
                    p.basic_pay,
                    p.allowances_total,
                    p.overtime_pay,
                    p.gross_pay,
                    COALESCE(p.leave_deduction, 0.00) AS leave_deduction,
                    COALESCE(p.tax_deduction, 0.00) AS tax_deduction,
                    COALESCE(p.pf_deduction, 0.00) AS pf_deduction,
                    COALESCE(p.other_deductions, 0.00) AS other_deductions,
                    p.total_deductions,
                    p.net_pay,
                    p.status,
                    p.generated_date,
                    p.remarks,
                    p.created_at,
                    p.updated_at
                FROM payroll p
                WHERE p.employee_id = %s AND p.year = %s AND p.month = %s
                LIMIT 1;
            """
            return self.execute_query(query, (employee_id, year, month), fetch_one=True)
        except Exception as e:
            logger.error("Error finding payroll for employee %s (%s-%s): %s", employee_id, year, month, e)
            return None

    def get_paginated_payroll(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve paginated payroll records joined with employee details.
        Supports filtering by year, month, status, employee, and text search.
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if year:
                conditions.append("p.year = %s")
                params.append(year)

            if month:
                conditions.append("p.month = %s")
                params.append(month)

            if employee_id:
                conditions.append("p.employee_id = %s")
                params.append(employee_id)

            if status and status.upper() != "ALL":
                conditions.append("p.status = %s")
                params.append(status.upper())

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("""(
                    p.payroll_code LIKE %s OR
                    e.employee_code LIKE %s OR
                    e.first_name LIKE %s OR
                    e.last_name LIKE %s OR
                    CONCAT(e.first_name, ' ', e.last_name) LIKE %s OR
                    e.department LIKE %s
                )""")
                params.extend([s, s, s, s, s, s])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 1. Total count query
            count_query = f"""
                SELECT COUNT(*) AS total 
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                {where_clause};
            """
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # 2. Paginated data query
            data_query = f"""
                SELECT 
                    p.id,
                    p.id AS payroll_id,
                    p.payroll_code,
                    p.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
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
                    p.status,
                    p.generated_date,
                    p.created_at,
                    p.updated_at
                FROM payroll p
                JOIN employees e ON p.employee_id = e.id
                {where_clause}
                ORDER BY p.year DESC, p.month DESC, p.id DESC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)

            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching paginated payroll records: %s", e)
            return [], 0

    def create_payroll_record(self, data: Dict[str, Any]) -> int:
        """
        Insert a new monthly payroll record using parameterized SQL.
        Wraps in a database transaction for ACID guarantees.
        """
        with self.transaction() as (cursor, conn):
            insert_sql = """
                INSERT INTO payroll (
                    payroll_code, employee_id, year, month,
                    basic_pay, allowances_total, overtime_pay, gross_pay,
                    leave_deduction, tax_deduction, pf_deduction, other_deductions,
                    total_deductions, net_pay, status, generated_date,
                    payment_due_date, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            params = (
                data["payroll_code"],
                int(data["employee_id"]),
                int(data["year"]),
                int(data["month"]),
                Decimal(str(data["basic_pay"])),
                Decimal(str(data["allowances_total"])),
                Decimal(str(data["overtime_pay"])),
                Decimal(str(data["gross_pay"])),
                Decimal(str(data.get("leave_deduction", "0.00"))),
                Decimal(str(data.get("tax_deduction", "0.00"))),
                Decimal(str(data.get("pf_deduction", "0.00"))),
                Decimal(str(data.get("other_deductions", "0.00"))),
                Decimal(str(data["total_deductions"])),
                Decimal(str(data["net_pay"])),
                data.get("status", "DRAFT").upper(),
                data["generated_date"],
                data.get("payment_due_date"),
                data.get("remarks"),
            )
            cursor.execute(insert_sql, params)
            return cursor.lastrowid

    def update_payroll_status(
        self,
        payroll_id: int,
        new_status: str,
        expected_current_status: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> bool:
        """
        Transition payroll status with optimistic locking / concurrency safeguard.
        Ensures a record in an unexpected state (e.g. already APPROVED or PAID)
        is not silently overwritten or invalidated.
        """
        try:
            new_status = new_status.upper()
            conditions = ["id = %s"]
            params = [new_status]

            if remarks:
                set_clause = "status = %s, remarks = %s"
                params.append(remarks)
            else:
                set_clause = "status = %s"

            params.append(payroll_id)

            if expected_current_status:
                conditions.append("status = %s")
                params.append(expected_current_status.upper())

            query = f"UPDATE payroll SET {set_clause} WHERE {' AND '.join(conditions)};"
            affected = self.execute_query(query, tuple(params), commit=True)
            return bool(affected)
        except Exception as e:
            logger.error("Error updating status for payroll #%s to %s: %s", payroll_id, new_status, e)
            return False

    def get_monthly_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """Aggregate totals across all records or for a selected month/year."""
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
                    COUNT(*) AS total_records,
                    COALESCE(SUM(gross_pay), 0.00) AS total_gross,
                    COALESCE(SUM(total_deductions), 0.00) AS total_deductions,
                    COALESCE(SUM(net_pay), 0.00) AS total_net,
                    COALESCE(SUM(CASE WHEN status = 'DRAFT' THEN 1 ELSE 0 END), 0) AS draft_count,
                    COALESCE(SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END), 0) AS approved_count,
                    COALESCE(SUM(CASE WHEN status = 'PAID' THEN 1 ELSE 0 END), 0) AS paid_count,
                    COALESCE(SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END), 0) AS cancelled_count
                FROM payroll
                {where_clause};
            """
            res = self.execute_query(query, tuple(params), fetch_one=True)
            if not res:
                return {
                    "total_records": 0,
                    "total_gross": Decimal("0.00"),
                    "total_deductions": Decimal("0.00"),
                    "total_net": Decimal("0.00"),
                    "draft_count": 0,
                    "approved_count": 0,
                    "paid_count": 0,
                    "cancelled_count": 0,
                }
            return {
                "total_records": int(res.get("total_records", 0)),
                "total_gross": Decimal(str(res.get("total_gross", "0.00"))),
                "total_deductions": Decimal(str(res.get("total_deductions", "0.00"))),
                "total_net": Decimal(str(res.get("total_net", "0.00"))),
                "draft_count": int(res.get("draft_count", 0)),
                "approved_count": int(res.get("approved_count", 0)),
                "paid_count": int(res.get("paid_count", 0)),
                "cancelled_count": int(res.get("cancelled_count", 0)),
            }
        except Exception as e:
            logger.error("Error computing monthly payroll summary: %s", e)
            return {
                "total_records": 0,
                "total_gross": Decimal("0.00"),
                "total_deductions": Decimal("0.00"),
                "total_net": Decimal("0.00"),
                "draft_count": 0,
                "approved_count": 0,
                "paid_count": 0,
                "cancelled_count": 0,
            }

    def get_available_years(self) -> List[int]:
        """Fetch distinct years present in payroll, including current year."""
        from datetime import datetime
        current_year = datetime.now().year
        try:
            query = "SELECT DISTINCT year FROM payroll ORDER BY year DESC;"
            rows = self.execute_query(query, fetch_all=True)
            years = [int(r["year"]) for r in rows if r and r.get("year")]
            if current_year not in years:
                years.append(current_year)
            return sorted(list(set(years)), reverse=True)
        except Exception as e:
            logger.warning("Error fetching available payroll years: %s", e)
            return [current_year, current_year - 1]
