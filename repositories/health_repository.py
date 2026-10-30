"""
Health Repository for diagnostic checks and database verification.
Safely queries database connectivity, schema tables, and row counts.
"""

from typing import Any, Dict, List
import logging
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "users",
    "employees",
    "attendance",
    "salary_settings",
    "payroll",
    "payments",
]


class HealthRepository(BaseRepository):
    """Repository handling system diagnostic and database verification queries."""

    def test_database_connectivity(self) -> Dict[str, Any]:
        """Runs an isolated ping probe against the MySQL database."""
        return self.db.ping()

    def get_schema_verification(self) -> Dict[str, Any]:
        """
        Inspects information_schema to verify required tables and record counts.
        Returns a structured dictionary indicating schema completeness.
        """
        ping_result = self.test_database_connectivity()
        if not ping_result.get("connected"):
            return {
                "verified": False,
                "error": ping_result.get("message"),
                "tables_found": [],
                "missing_tables": REQUIRED_TABLES,
                "table_counts": {},
            }

        database_name = ping_result.get("database") or "employee_payroll"
        table_counts: Dict[str, int] = {}
        tables_found: List[str] = []

        try:
            # Query existing tables in current database
            query_tables = """
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s;
            """
            rows = self.db.execute_query(query_tables, (database_name,), fetch_all=True)
            if rows:
                tables_found = [row["TABLE_NAME"].lower() for row in rows if "TABLE_NAME" in row]

            # For each required table, check existence and row count
            for table in REQUIRED_TABLES:
                if table.lower() in tables_found:
                    count_row = self.db.execute_query(
                        f"SELECT COUNT(*) AS total FROM `{table}`;",
                        fetch_one=True
                    )
                    table_counts[table] = count_row.get("total", 0) if count_row else 0
                else:
                    table_counts[table] = -1  # indicates table missing

            missing = [t for t in REQUIRED_TABLES if t.lower() not in tables_found]

            return {
                "verified": len(missing) == 0,
                "database_name": database_name,
                "tables_found": tables_found,
                "missing_tables": missing,
                "table_counts": table_counts,
                "server_version": ping_result.get("server_version"),
            }
        except Exception as e:
            logger.error("Error verifying schema tables: %s", e)
            return {
                "verified": False,
                "error": str(e),
                "tables_found": tables_found,
                "missing_tables": [t for t in REQUIRED_TABLES if t not in tables_found],
                "table_counts": table_counts,
            }
