"""
Salary Settings Repository for MySQL operations on the `salary_settings` table.
Handles parameterized querying, salary profile retrieval, updating,
and compensation aggregations.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SalaryRepository(BaseRepository):
    """Repository handling CRUD and queries for employee salary settings and structures."""

    def get_by_employee_id(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch salary configuration for a specific employee joined with employee profile.
        """
        try:
            query = """
                SELECT 
                    s.id,
                    s.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.status AS employee_status,
                    COALESCE(s.base_salary, 0.00) AS base_salary,
                    COALESCE(s.hourly_rate, 0.00) AS hourly_rate,
                    COALESCE(s.hra, 0.00) AS hra,
                    COALESCE(s.transport_allowance, 0.00) AS transport_allowance,
                    COALESCE(s.medical_allowance, 0.00) AS medical_allowance,
                    COALESCE(s.other_allowances, 0.00) AS other_allowances,
                    (COALESCE(s.hra, 0.00) + COALESCE(s.transport_allowance, 0.00) + 
                     COALESCE(s.medical_allowance, 0.00) + COALESCE(s.other_allowances, 0.00)) AS total_allowances,
                    COALESCE(s.tax_deduction_rate, 0.00) AS tax_deduction_rate,
                    COALESCE(s.pf_deduction_rate, 0.00) AS pf_deduction_rate,
                    COALESCE(s.other_deductions, 0.00) AS other_deductions,
                    s.effective_from,
                    s.created_at,
                    s.updated_at
                FROM salary_settings s
                JOIN employees e ON s.employee_id = e.id
                WHERE s.employee_id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (employee_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching salary settings for employee %s: %s", employee_id, e)
            return None

    def get_all_paginated(
        self,
        search: Optional[str] = None,
        department: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve paginated list of all employees and their configured salary structures.
        Supports search by name, code, department.
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("""(
                    e.employee_code LIKE %s OR
                    e.first_name LIKE %s OR
                    e.last_name LIKE %s OR
                    CONCAT(e.first_name, ' ', e.last_name) LIKE %s OR
                    e.department LIKE %s
                )""")
                params.extend([s, s, s, s, s])

            if department and department.strip() and department.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department.strip())

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Count query
            count_query = f"""
                SELECT COUNT(*) AS total
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                {where_clause};
            """
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # Data query
            data_query = f"""
                SELECT 
                    e.id AS employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.status AS employee_status,
                    s.id AS salary_setting_id,
                    COALESCE(s.base_salary, 0.00) AS base_salary,
                    COALESCE(s.hourly_rate, 0.00) AS hourly_rate,
                    COALESCE(s.hra, 0.00) AS hra,
                    COALESCE(s.transport_allowance, 0.00) AS transport_allowance,
                    COALESCE(s.medical_allowance, 0.00) AS medical_allowance,
                    COALESCE(s.other_allowances, 0.00) AS other_allowances,
                    (COALESCE(s.hra, 0.00) + COALESCE(s.transport_allowance, 0.00) + 
                     COALESCE(s.medical_allowance, 0.00) + COALESCE(s.other_allowances, 0.00)) AS total_allowances,
                    COALESCE(s.other_deductions, 0.00) AS other_deductions,
                    s.effective_from,
                    s.updated_at
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                {where_clause}
                ORDER BY e.status ASC, e.first_name ASC, e.last_name ASC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)

            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching paginated salary settings: %s", e)
            return [], 0

    def upsert_salary_settings(self, employee_id: int, data: Dict[str, Any]) -> bool:
        """
        Update or insert salary structure for an employee using parameterized SQL.
        Wraps in a transaction.
        """
        with self.transaction() as (cursor, conn):
            upsert_sql = """
                INSERT INTO salary_settings (
                    employee_id, base_salary, hourly_rate, hra,
                    transport_allowance, medical_allowance, other_allowances,
                    tax_deduction_rate, pf_deduction_rate, other_deductions,
                    effective_from
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    base_salary = VALUES(base_salary),
                    hourly_rate = VALUES(hourly_rate),
                    hra = VALUES(hra),
                    transport_allowance = VALUES(transport_allowance),
                    medical_allowance = VALUES(medical_allowance),
                    other_allowances = VALUES(other_allowances),
                    tax_deduction_rate = VALUES(tax_deduction_rate),
                    pf_deduction_rate = VALUES(pf_deduction_rate),
                    other_deductions = VALUES(other_deductions),
                    effective_from = VALUES(effective_from);
            """
            params = (
                employee_id,
                Decimal(str(data.get("base_salary", "0.00"))),
                Decimal(str(data.get("hourly_rate", "0.00"))),
                Decimal(str(data.get("hra", "0.00"))),
                Decimal(str(data.get("transport_allowance", "0.00"))),
                Decimal(str(data.get("medical_allowance", "0.00"))),
                Decimal(str(data.get("other_allowances", "0.00"))),
                Decimal(str(data.get("tax_deduction_rate", "0.00"))),
                Decimal(str(data.get("pf_deduction_rate", "0.00"))),
                Decimal(str(data.get("other_deductions", "0.00"))),
                data["effective_from"],
            )
            cursor.execute(upsert_sql, params)
            return True

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Aggregate total basic monthly salary payroll and average compensation."""
        try:
            query = """
                SELECT 
                    COUNT(DISTINCT e.id) AS total_employees,
                    COALESCE(SUM(s.base_salary), 0.00) AS total_base_payroll,
                    COALESCE(AVG(s.base_salary), 0.00) AS avg_base_salary,
                    COALESCE(SUM(s.hra + s.transport_allowance + s.medical_allowance + s.other_allowances), 0.00) AS total_allowances_pool,
                    COALESCE(SUM(s.other_deductions), 0.00) AS total_other_deductions
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                WHERE e.status = 'ACTIVE';
            """
            res = self.execute_query(query, fetch_one=True)
            if not res:
                return {
                    "total_employees": 0,
                    "total_base_payroll": Decimal("0.00"),
                    "avg_base_salary": Decimal("0.00"),
                    "total_allowances_pool": Decimal("0.00"),
                    "total_other_deductions": Decimal("0.00"),
                }
            return {
                "total_employees": int(res.get("total_employees", 0)),
                "total_base_payroll": Decimal(str(res.get("total_base_payroll", "0.00"))),
                "avg_base_salary": Decimal(str(res.get("avg_base_salary", "0.00"))),
                "total_allowances_pool": Decimal(str(res.get("total_allowances_pool", "0.00"))),
                "total_other_deductions": Decimal(str(res.get("total_other_deductions", "0.00"))),
            }
        except Exception as e:
            logger.error("Error computing salary summary metrics: %s", e)
            return {
                "total_employees": 0,
                "total_base_payroll": Decimal("0.00"),
                "avg_base_salary": Decimal("0.00"),
                "total_allowances_pool": Decimal("0.00"),
                "total_other_deductions": Decimal("0.00"),
            }
