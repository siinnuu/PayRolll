"""
Employee Repository for MySQL operations on the `employees` and `salary_settings` tables.
Handles parameterized querying, pagination, searching, transactions, and historical checks.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class EmployeeRepository(BaseRepository):
    """Repository handling CRUD, search, pagination, and status operations for employees."""

    def get_paginated_employees(
        self,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        department_filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve a paginated list of employees joined with basic salary from salary_settings.
        Supports search across code, full name, email, and department.
        Returns: (employees_list, total_count)
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            # Search condition (code, first name, last name, combined name, email, department)
            if search and search.strip():
                s = f"%{search.strip()}%"
                conditions.append("""(
                    e.employee_code LIKE %s OR
                    e.first_name LIKE %s OR
                    e.last_name LIKE %s OR
                    CONCAT(e.first_name, ' ', e.last_name) LIKE %s OR
                    e.email LIKE %s OR
                    e.department LIKE %s
                )""")
                params.extend([s, s, s, s, s, s])

            # Status filter
            if status_filter and status_filter.upper() != "ALL":
                conditions.append("e.status = %s")
                params.append(status_filter.upper())

            # Department filter
            if department_filter and department_filter.strip() and department_filter.upper() != "ALL":
                conditions.append("e.department = %s")
                params.append(department_filter.strip())

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 1. Total matching count
            count_query = f"SELECT COUNT(*) AS total FROM employees e {where_clause};"
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # 2. Paginated data query
            data_query = f"""
                SELECT 
                    e.id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.email,
                    e.phone,
                    e.department,
                    e.designation,
                    e.joining_date,
                    e.status,
                    e.created_at,
                    e.updated_at,
                    COALESCE(s.base_salary, 0.00) AS base_salary
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                {where_clause}
                ORDER BY e.id DESC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)

            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching paginated employees: %s", e)
            return [], 0

    def get_by_id(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """Fetch employee by primary key ID joined with salary settings."""
        try:
            query = """
                SELECT 
                    e.id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    e.email,
                    e.phone,
                    e.department,
                    e.designation,
                    e.joining_date,
                    e.status,
                    e.user_id,
                    e.created_at,
                    e.updated_at,
                    COALESCE(s.base_salary, 0.00) AS base_salary,
                    COALESCE(s.hra, 0.00) AS hra,
                    COALESCE(s.transport_allowance, 0.00) AS transport_allowance,
                    COALESCE(s.medical_allowance, 0.00) AS medical_allowance,
                    COALESCE(s.tax_deduction_rate, 0.00) AS tax_deduction_rate,
                    COALESCE(s.pf_deduction_rate, 0.00) AS pf_deduction_rate
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                WHERE e.id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (employee_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching employee ID %s: %s", employee_id, e)
            return None

    def get_by_code(self, employee_code: str) -> Optional[Dict[str, Any]]:
        """Fetch employee by unique employee code."""
        try:
            query = """
                SELECT id, employee_code, first_name, last_name, email, status
                FROM employees
                WHERE LOWER(employee_code) = LOWER(%s)
                LIMIT 1;
            """
            return self.execute_query(query, (employee_code.strip(),), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching employee code %s: %s", employee_code, e)
            return None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch employee by unique email."""
        try:
            query = """
                SELECT id, employee_code, first_name, last_name, email, status
                FROM employees
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1;
            """
            return self.execute_query(query, (email.strip(),), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching employee email %s: %s", email, e)
            return None

    def generate_next_employee_code(self) -> str:
        """
        Automatically generates the next sequential employee identifier.
        e.g. EMP001, EMP002 ... EMP004.
        """
        try:
            query = """
                SELECT employee_code 
                FROM employees 
                WHERE employee_code LIKE 'EMP%'
                ORDER BY id DESC 
                LIMIT 1;
            """
            row = self.execute_query(query, fetch_one=True)
            if row and row.get("employee_code"):
                last_code = row["employee_code"].strip()
                digits = "".join(filter(str.isdigit, last_code))
                if digits:
                    next_num = int(digits) + 1
                    return f"EMP{next_num:03d}"
            
            # Default fallback if no EMP pattern exists
            count_row = self.execute_query("SELECT COUNT(*) AS total FROM employees;", fetch_one=True)
            next_id = (count_row.get("total", 0) if count_row else 0) + 1
            return f"EMP{next_id:03d}"
        except Exception as e:
            logger.warning("Error generating next employee code: %s", e)
            return "EMP001"

    def create_employee(self, data: Dict[str, Any], base_salary: Decimal) -> int:
        """
        Atomic creation of an employee and their corresponding salary_settings.
        Uses a database transaction to ensure either both are saved or both rollback.
        Returns the newly created employee ID.
        """
        with self.transaction() as (cursor, conn):
            # 1. Insert into employees
            emp_insert_sql = """
                INSERT INTO employees (
                    employee_code, first_name, last_name, email,
                    phone, department, designation, joining_date, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            emp_params = (
                data["employee_code"].strip().upper(),
                data["first_name"].strip(),
                data["last_name"].strip(),
                data["email"].strip().lower(),
                data.get("phone", "").strip() or None,
                data["department"].strip(),
                data["designation"].strip(),
                data["joining_date"],
                data.get("status", "ACTIVE").upper(),
            )
            cursor.execute(emp_insert_sql, emp_params)
            employee_id = cursor.lastrowid

            # 2. Insert into salary_settings
            salary_insert_sql = """
                INSERT INTO salary_settings (
                    employee_id, base_salary, effective_from
                ) VALUES (%s, %s, %s);
            """
            salary_params = (
                employee_id,
                Decimal(str(base_salary)),
                data["joining_date"],
            )
            cursor.execute(salary_insert_sql, salary_params)

            return employee_id

    def update_employee(
        self,
        employee_id: int,
        data: Dict[str, Any],
        base_salary: Optional[Decimal] = None
    ) -> bool:
        """
        Atomic update of an employee's profile and salary settings.
        Executes within a transaction.
        """
        with self.transaction() as (cursor, conn):
            # 1. Update employees profile
            emp_update_sql = """
                UPDATE employees SET
                    first_name = %s,
                    last_name = %s,
                    email = %s,
                    phone = %s,
                    department = %s,
                    designation = %s,
                    joining_date = %s,
                    status = %s
                WHERE id = %s;
            """
            emp_params = (
                data["first_name"].strip(),
                data["last_name"].strip(),
                data["email"].strip().lower(),
                data.get("phone", "").strip() or None,
                data["department"].strip(),
                data["designation"].strip(),
                data["joining_date"],
                data.get("status", "ACTIVE").upper(),
                employee_id,
            )
            cursor.execute(emp_update_sql, emp_params)

            # 2. Update base_salary in salary_settings if supplied
            if base_salary is not None:
                salary_upsert_sql = """
                    INSERT INTO salary_settings (employee_id, base_salary, effective_from)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE base_salary = VALUES(base_salary);
                """
                cursor.execute(
                    salary_upsert_sql,
                    (employee_id, Decimal(str(base_salary)), data.get("joining_date"))
                )

            return True

    def set_employee_status(self, employee_id: int, status: str) -> bool:
        """Update employee employment status (e.g. 'ACTIVE' or 'INACTIVE')."""
        try:
            status = status.upper()
            if status not in ("ACTIVE", "INACTIVE", "TERMINATED", "ON_LEAVE"):
                raise ValueError(f"Invalid status: {status}")

            query = "UPDATE employees SET status = %s WHERE id = %s;"
            return bool(self.execute_query(query, (status, employee_id), commit=True))
        except Exception as e:
            logger.error("Error setting status for employee %s: %s", employee_id, e)
            return False

    def has_historical_records(self, employee_id: int) -> Dict[str, Any]:
        """
        Check whether an employee has historical records in payroll or attendance.
        Used to prevent hard deletion of records with financial history.
        """
        try:
            payroll_res = self.execute_query(
                "SELECT COUNT(*) AS total FROM payroll WHERE employee_id = %s;",
                (employee_id,),
                fetch_one=True
            )
            payroll_count = int(payroll_res.get("total", 0)) if payroll_res else 0

            attendance_res = self.execute_query(
                "SELECT COUNT(*) AS total FROM attendance WHERE employee_id = %s;",
                (employee_id,),
                fetch_one=True
            )
            attendance_count = int(attendance_res.get("total", 0)) if attendance_res else 0

            has_history = (payroll_count > 0 or attendance_count > 0)
            return {
                "has_history": has_history,
                "payroll_count": payroll_count,
                "attendance_count": attendance_count,
            }
        except Exception as e:
            logger.error("Error checking historical records for employee %s: %s", employee_id, e)
            # Safe default: assume history exists if probe fails to prevent accidental deletion
            return {"has_history": True, "payroll_count": 0, "attendance_count": 0}

    def delete_employee(self, employee_id: int) -> Tuple[bool, str]:
        """
        Permanently delete an employee ONLY if no historical payroll or attendance exists.
        Returns: (success: bool, message: str)
        """
        history = self.has_historical_records(employee_id)
        if history.get("has_history"):
            payroll_cnt = history.get("payroll_count", 0)
            att_cnt = history.get("attendance_count", 0)
            msg = (
                f"Cannot delete employee. Historical records exist ({payroll_cnt} payroll, {att_cnt} attendance). "
                "Deactivate the employee instead to preserve statutory audit history."
            )
            return False, msg

        try:
            with self.transaction() as (cursor, conn):
                # Delete salary_settings first to respect foreign key constraint
                cursor.execute("DELETE FROM salary_settings WHERE employee_id = %s;", (employee_id,))
                cursor.execute("DELETE FROM employees WHERE id = %s;", (employee_id,))
            return True, "Employee permanently removed."
        except Exception as e:
            logger.error("Error deleting employee %s: %s", employee_id, e)
            return False, f"Failed to delete employee: {str(e)}"

    def get_all_departments(self) -> List[str]:
        """Retrieve distinct existing departments for filter and select controls."""
        try:
            query = """
                SELECT DISTINCT department 
                FROM employees 
                WHERE department IS NOT NULL AND department != '' 
                ORDER BY department ASC;
            """
            rows = self.execute_query(query, fetch_all=True)
            departments = [r["department"] for r in rows if r and r.get("department")]
            
            # Default standard departments if table has few or none
            standard_depts = ["Engineering", "Human Resources", "Finance", "Operations", "Sales", "Marketing"]
            for d in standard_depts:
                if d not in departments:
                    departments.append(d)
            return sorted(departments)
        except Exception as e:
            logger.warning("Error fetching departments: %s", e)
            return ["Engineering", "Human Resources", "Finance", "Operations", "Sales", "Marketing"]

    def get_active_employees(self) -> List[Dict[str, Any]]:
        """
        Retrieve all currently ACTIVE employees for dropdown selectors and form lookups.
        Includes base salary and hourly rate from salary_settings.
        """
        try:
            query = """
                SELECT 
                    e.id, 
                    e.employee_code, 
                    e.first_name, 
                    e.last_name, 
                    e.email,
                    e.department, 
                    e.designation,
                    e.status,
                    COALESCE(s.hourly_rate, 0.00) AS hourly_rate,
                    COALESCE(s.base_salary, 0.00) AS base_salary
                FROM employees e
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                WHERE e.status = 'ACTIVE'
                ORDER BY e.first_name ASC, e.last_name ASC;
            """
            rows = self.execute_query(query, fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching active employees: %s", e)
            return []
