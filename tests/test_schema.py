"""
Tests for schema.sql and seed.sql validation and architectural constraints.
"""

from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = BASE_DIR / "schema.sql"
SEED_FILE = BASE_DIR / "seed.sql"


def test_schema_file_exists():
    """Verify schema.sql exists in workspace root."""
    assert SCHEMA_FILE.exists(), "schema.sql must be present in the project root."


def test_seed_file_exists():
    """Verify seed.sql exists in workspace root."""
    assert SEED_FILE.exists(), "seed.sql must be present in the project root."


def test_schema_required_tables_present():
    """Verify all 6 required tables are defined in schema.sql."""
    content = SCHEMA_FILE.read_text(encoding="utf-8").lower()
    required_tables = [
        "users",
        "employees",
        "attendance",
        "salary_settings",
        "payroll",
        "payments"
    ]
    for table in required_tables:
        pattern = rf"create\s+table\s+[`]?{table}[`]?"
        assert re.search(pattern, content), f"Required table '{table}' missing from schema.sql"


def test_schema_uses_innodb_engine():
    """Verify all table creations specify ENGINE=InnoDB."""
    content = SCHEMA_FILE.read_text(encoding="utf-8")
    table_blocks = re.findall(r"CREATE\s+TABLE\s+[`]?(\w+)[`]?\s*\((.*?)\)\s*ENGINE=InnoDB", content, re.DOTALL | re.IGNORECASE)
    assert len(table_blocks) == 6, f"Expected 6 tables with ENGINE=InnoDB, found {len(table_blocks)}"


def test_schema_monetary_decimal_precision():
    """Verify monetary columns use DECIMAL(12,2)."""
    content = SCHEMA_FILE.read_text(encoding="utf-8")
    assert "DECIMAL(12,2)" in content or "decimal(12,2)" in content.lower()
    
    # Specific checks on salary_settings, payroll, payments
    assert "base_salary` DECIMAL(12,2)" in content or "`base_salary` decimal(12,2)" in content.lower()
    assert "net_pay` DECIMAL(12,2)" in content or "`net_pay` decimal(12,2)" in content.lower()
    assert "amount_paid` DECIMAL(12,2)" in content or "`amount_paid` decimal(12,2)" in content.lower()


def test_schema_one_attendance_and_payroll_per_month_constraint():
    """
    Verify unique constraints enforcing:
    1 attendance summary per employee per month
    1 main payroll record per employee per month
    """
    content = SCHEMA_FILE.read_text(encoding="utf-8").lower()
    assert "uq_attendance_employee_month_year" in content
    assert "uq_payroll_employee_month_year" in content
    
    # Check that (employee_id, year, month) is part of unique constraint
    assert re.search(r"unique\s+key\s+[`]?\w+[`]?\s*\(\s*[`]?employee_id[`]?\s*,\s*[`]?year[`]?\s*,\s*[`]?month[`]?\s*\)", content)


def test_schema_preserves_historical_records_on_delete_restrict():
    """Verify foreign keys use ON DELETE RESTRICT to protect historical records."""
    content = SCHEMA_FILE.read_text(encoding="utf-8").lower()
    assert "on delete restrict" in content
    
    # Specifically ensure attendance, payroll, and payments restrict deletion
    assert "fk_attendance_employee" in content
    assert "fk_payroll_employee" in content
    assert "fk_payments_payroll" in content


def test_seed_contains_fictional_employees_and_attendance():
    """Verify seed.sql contains at least 3 fictional employees and attendance records."""
    content = SEED_FILE.read_text(encoding="utf-8")
    assert "EMP001" in content
    assert "EMP002" in content
    assert "EMP003" in content
    assert "INSERT INTO `attendance`" in content or "insert into `attendance`" in content.lower()
    assert "INSERT INTO `employees`" in content or "insert into `employees`" in content.lower()


def test_seed_no_plaintext_passwords():
    """Verify seed.sql does not contain plaintext passwords for users."""
    content = SEED_FILE.read_text(encoding="utf-8")
    # Should use Werkzeug scrypt/pbkdf2 hash format: scrypt: or pbkdf2:
    assert "scrypt:" in content or "pbkdf2:" in content
    # Ensure plaintext 'Admin@123' is NOT inserted directly in the SQL statement
    assert "'Admin@123'" not in content
    assert "'User@123'" not in content
