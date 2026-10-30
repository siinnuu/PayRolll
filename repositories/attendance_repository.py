"""
Attendance Repository for MySQL operations on the `attendance` table.
Handles parameterized queries, pagination, search, summary calculations,
validation lookups, transactions, and employee attendance history.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AttendanceRepository(BaseRepository):
    """Repository handling CRUD, search, pagination, history, and summaries for attendance."""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self._ensure_schema_columns()

    def _ensure_schema_columns(self) -> None:
        """
        Verify that `overtime_rate` column exists on the attendance table.
        Gracefully handles migrations if initialized on a legacy schema.
        """
        try:
            # Query column information
            check_col_query = """
                SELECT COUNT(*) AS cnt 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = 'attendance' 
                  AND COLUMN_NAME = 'overtime_rate';
            """
            res = self.execute_query(check_col_query, fetch_one=True)
            if res and int(res.get("cnt", 0)) == 0:
                alter_sql = """
                    ALTER TABLE attendance 
                    ADD COLUMN overtime_rate DECIMAL(10,2) NOT NULL DEFAULT 0.00 
                    AFTER overtime_hours;
                """
                self.execute_query(alter_sql, commit=True)
                logger.info("Successfully added 'overtime_rate' column to attendance table.")
        except Exception as e:
            # Safe ignore if table doesn't exist yet (e.g. mock test) or permission restricted
            logger.debug("Schema column verification notice: %s", e)

    def get_paginated_attendance(
        self,
        employee_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve a paginated list of monthly attendance records joined with
        employee details and salary rate settings.
        
        Returns:
            (records_list, total_count)
        """
        try:
            page = max(1, page)
            per_page = max(1, min(100, per_page))
            offset = (page - 1) * per_page

            conditions = []
            params = []

            if employee_id:
                conditions.append("a.employee_id = %s")
                params.append(employee_id)

            if year:
                conditions.append("a.year = %s")
                params.append(year)

            if month:
                conditions.append("a.month = %s")
                params.append(month)

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

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 1. Total count query
            count_query = f"""
                SELECT COUNT(*) AS total 
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                {where_clause};
            """
            count_res = self.execute_query(count_query, tuple(params), fetch_one=True)
            total_count = int(count_res.get("total", 0)) if count_res else 0

            # 2. Paginated data query
            data_query = f"""
                SELECT 
                    a.id,
                    a.id AS attendance_id,
                    a.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.status AS employee_status,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days,
                    a.absent_days,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    (a.paid_leaves + a.unpaid_leaves) AS total_leaves,
                    a.overtime_hours,
                    COALESCE(a.overtime_rate, s.hourly_rate, 0.00) AS overtime_rate,
                    (a.overtime_hours * COALESCE(a.overtime_rate, s.hourly_rate, 0.00)) AS estimated_overtime_pay,
                    a.notes,
                    a.created_at,
                    a.updated_at
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                {where_clause}
                ORDER BY a.year DESC, a.month DESC, e.last_name ASC, e.first_name ASC
                LIMIT %s OFFSET %s;
            """
            data_params = tuple(params + [per_page, offset])
            rows = self.execute_query(data_query, data_params, fetch_all=True)

            return rows if rows else [], total_count
        except Exception as e:
            logger.error("Error fetching paginated attendance: %s", e)
            return [], 0

    def get_by_id(self, attendance_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single attendance record by its ID joined with employee and salary info."""
        try:
            query = """
                SELECT 
                    a.id,
                    a.id AS attendance_id,
                    a.employee_id,
                    e.employee_code,
                    e.first_name,
                    e.last_name,
                    CONCAT(e.first_name, ' ', e.last_name) AS full_name,
                    e.department,
                    e.designation,
                    e.status AS employee_status,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days,
                    a.absent_days,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    (a.paid_leaves + a.unpaid_leaves) AS total_leaves,
                    a.overtime_hours,
                    COALESCE(a.overtime_rate, s.hourly_rate, 0.00) AS overtime_rate,
                    (a.overtime_hours * COALESCE(a.overtime_rate, s.hourly_rate, 0.00)) AS estimated_overtime_pay,
                    a.notes,
                    a.created_at,
                    a.updated_at
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                WHERE a.id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (attendance_id,), fetch_one=True)
        except Exception as e:
            logger.error("Error fetching attendance ID %s: %s", attendance_id, e)
            return None

    def get_by_employee_and_period(
        self, employee_id: int, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        """Look up existing attendance summary for an employee in a specific year and month."""
        try:
            query = """
                SELECT 
                    a.id,
                    a.id AS attendance_id,
                    a.employee_id,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days,
                    a.absent_days,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    a.overtime_hours,
                    a.overtime_rate,
                    a.notes
                FROM attendance a
                WHERE a.employee_id = %s AND a.year = %s AND a.month = %s
                LIMIT 1;
            """
            return self.execute_query(query, (employee_id, year, month), fetch_one=True)
        except Exception as e:
            logger.error(
                "Error finding attendance for employee %s (%s-%s): %s",
                employee_id, year, month, e
            )
            return None

    def get_attendance_history_for_employee(
        self, employee_id: int, limit: int = 36
    ) -> List[Dict[str, Any]]:
        """Retrieve historical monthly attendance summaries for an employee in descending order."""
        try:
            query = """
                SELECT 
                    a.id,
                    a.id AS attendance_id,
                    a.employee_id,
                    a.year,
                    a.month,
                    a.total_working_days,
                    a.present_days,
                    a.absent_days,
                    a.paid_leaves,
                    a.unpaid_leaves,
                    (a.paid_leaves + a.unpaid_leaves) AS total_leaves,
                    a.overtime_hours,
                    COALESCE(a.overtime_rate, s.hourly_rate, 0.00) AS overtime_rate,
                    (a.overtime_hours * COALESCE(a.overtime_rate, s.hourly_rate, 0.00)) AS estimated_overtime_pay,
                    a.notes,
                    a.created_at,
                    a.updated_at
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                WHERE a.employee_id = %s
                ORDER BY a.year DESC, a.month DESC
                LIMIT %s;
            """
            rows = self.execute_query(query, (employee_id, limit), fetch_all=True)
            return rows if rows else []
        except Exception as e:
            logger.error("Error fetching attendance history for employee %s: %s", employee_id, e)
            return []

    def create_attendance(self, data: Dict[str, Any]) -> int:
        """
        Insert a new monthly attendance record using parameterized SQL.
        Wraps in a transaction for transactional consistency.
        
        Returns:
            The newly created attendance record ID.
        """
        with self.transaction() as (cursor, conn):
            # Calculate unaccounted absence if not explicitly supplied
            working_days = Decimal(str(data["total_working_days"]))
            present_days = Decimal(str(data["present_days"]))
            paid_leaves = Decimal(str(data.get("paid_leaves", 0)))
            unpaid_leaves = Decimal(str(data.get("unpaid_leaves", 0)))
            absent_days = max(Decimal("0.0"), working_days - (present_days + paid_leaves + unpaid_leaves))

            insert_sql = """
                INSERT INTO attendance (
                    employee_id, year, month, total_working_days,
                    present_days, absent_days, paid_leaves, unpaid_leaves,
                    overtime_hours, overtime_rate, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            params = (
                int(data["employee_id"]),
                int(data["year"]),
                int(data["month"]),
                int(working_days),
                present_days,
                absent_days,
                paid_leaves,
                unpaid_leaves,
                Decimal(str(data.get("overtime_hours", "0.00"))),
                Decimal(str(data.get("overtime_rate", "0.00"))),
                (data.get("notes") or "").strip() or None,
            )
            cursor.execute(insert_sql, params)
            return cursor.lastrowid

    def update_attendance(self, attendance_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an existing monthly attendance record using parameterized SQL.
        Wraps in a transaction.
        """
        with self.transaction() as (cursor, conn):
            working_days = Decimal(str(data["total_working_days"]))
            present_days = Decimal(str(data["present_days"]))
            paid_leaves = Decimal(str(data.get("paid_leaves", 0)))
            unpaid_leaves = Decimal(str(data.get("unpaid_leaves", 0)))
            absent_days = max(Decimal("0.0"), working_days - (present_days + paid_leaves + unpaid_leaves))

            update_sql = """
                UPDATE attendance SET
                    total_working_days = %s,
                    present_days = %s,
                    absent_days = %s,
                    paid_leaves = %s,
                    unpaid_leaves = %s,
                    overtime_hours = %s,
                    overtime_rate = %s,
                    notes = %s
                WHERE id = %s;
            """
            params = (
                int(working_days),
                present_days,
                absent_days,
                paid_leaves,
                unpaid_leaves,
                Decimal(str(data.get("overtime_hours", "0.00"))),
                Decimal(str(data.get("overtime_rate", "0.00"))),
                (data.get("notes") or "").strip() or None,
                attendance_id,
            )
            cursor.execute(update_sql, params)
            return True

    def get_monthly_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate aggregated attendance metrics for the selected period.
        
        Returns:
            Dictionary with aggregated statistics:
            total_records, total_working_days, total_present_days,
            total_paid_leaves, total_unpaid_leaves, total_leaves,
            total_absent_days, total_overtime_hours, attendance_rate
        """
        try:
            conditions = []
            params = []
            if year:
                conditions.append("a.year = %s")
                params.append(year)
            if month:
                conditions.append("a.month = %s")
                params.append(month)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT 
                    COUNT(*) AS total_records,
                    COALESCE(SUM(a.total_working_days), 0) AS total_working_days,
                    COALESCE(SUM(a.present_days), 0.0) AS total_present_days,
                    COALESCE(SUM(a.paid_leaves), 0.0) AS total_paid_leaves,
                    COALESCE(SUM(a.unpaid_leaves), 0.0) AS total_unpaid_leaves,
                    COALESCE(SUM(a.paid_leaves + a.unpaid_leaves), 0.0) AS total_leaves,
                    COALESCE(SUM(a.absent_days), 0.0) AS total_absent_days,
                    COALESCE(SUM(a.overtime_hours), 0.0) AS total_overtime_hours,
                    COALESCE(SUM(a.overtime_hours * COALESCE(a.overtime_rate, s.hourly_rate, 0.00)), 0.00) AS total_overtime_cost
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                LEFT JOIN salary_settings s ON e.id = s.employee_id
                {where_clause};
            """
            res = self.execute_query(query, tuple(params), fetch_one=True)
            if not res:
                return {
                    "total_records": 0,
                    "total_working_days": 0,
                    "total_present_days": Decimal("0.0"),
                    "total_paid_leaves": Decimal("0.0"),
                    "total_unpaid_leaves": Decimal("0.0"),
                    "total_leaves": Decimal("0.0"),
                    "total_absent_days": Decimal("0.0"),
                    "total_overtime_hours": Decimal("0.00"),
                    "total_overtime_cost": Decimal("0.00"),
                    "attendance_rate": 0.0,
                }

            total_records = int(res.get("total_records", 0))
            total_working_days = float(res.get("total_working_days", 0))
            total_present = float(res.get("total_present_days", 0.0))

            attendance_rate = 0.0
            if total_working_days > 0:
                attendance_rate = round((total_present / total_working_days) * 100, 1)

            return {
                "total_records": total_records,
                "total_working_days": int(res.get("total_working_days", 0)),
                "total_present_days": Decimal(str(res.get("total_present_days", 0.0))),
                "total_paid_leaves": Decimal(str(res.get("total_paid_leaves", 0.0))),
                "total_unpaid_leaves": Decimal(str(res.get("total_unpaid_leaves", 0.0))),
                "total_leaves": Decimal(str(res.get("total_leaves", 0.0))),
                "total_absent_days": Decimal(str(res.get("total_absent_days", 0.0))),
                "total_overtime_hours": Decimal(str(res.get("total_overtime_hours", 0.0))),
                "total_overtime_cost": Decimal(str(res.get("total_overtime_cost", 0.0))),
                "attendance_rate": attendance_rate,
            }
        except Exception as e:
            logger.error("Error computing monthly summary: %s", e)
            return {
                "total_records": 0,
                "total_working_days": 0,
                "total_present_days": Decimal("0.0"),
                "total_paid_leaves": Decimal("0.0"),
                "total_unpaid_leaves": Decimal("0.0"),
                "total_leaves": Decimal("0.0"),
                "total_absent_days": Decimal("0.0"),
                "total_overtime_hours": Decimal("0.00"),
                "total_overtime_cost": Decimal("0.00"),
                "attendance_rate": 0.0,
            }

    def get_available_years(self) -> List[int]:
        """Fetch distinct years present in attendance, ensuring current year is included."""
        from datetime import datetime
        current_year = datetime.now().year
        try:
            query = "SELECT DISTINCT year FROM attendance ORDER BY year DESC;"
            rows = self.execute_query(query, fetch_all=True)
            years = [int(r["year"]) for r in rows if r and r.get("year")]
            if current_year not in years:
                years.append(current_year)
            return sorted(list(set(years)), reverse=True)
        except Exception as e:
            logger.warning("Error fetching available years: %s", e)
            return [current_year, current_year - 1]
