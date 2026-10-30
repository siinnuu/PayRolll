"""
Database initialization script for Employee Payroll Management System.
Connects to MySQL, creates the database, applies schema.sql, and loads seed data.
Usage:
    python init_db.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import mysql.connector

# Load environment configuration
load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "employee_payroll")

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"
SEED_FILE = BASE_DIR / "seed.sql"


def main():
    print("=" * 70)
    print("Employee Payroll Management System - Database Initializer")
    print("=" * 70)
    print(f"Target Server : {DB_HOST}:{DB_PORT}")
    print(f"Database User : {DB_USER}")
    print(f"Database Name : {DB_NAME}")
    print("-" * 70)

    # Step 1: Connect to MySQL Server (without selecting specific DB)
    print("Step 1/3: Connecting to MySQL Server...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        print(f"  [SUCCESS] Connected to MySQL Server version: {version}")

        # Ensure database exists
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        print(f"  [SUCCESS] Database '{DB_NAME}' created or verified.")
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"  [FAILED] Could not connect to MySQL Server: {err}")
        print("\nPlease update your database password in .env and retry.")
        sys.exit(1)

    # Step 2: Execute schema.sql
    print("\nStep 2/3: Applying schema.sql (InnoDB, constraints, indexes)...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        cursor = conn.cursor()

        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
        for stmt in statements:
            cursor.execute(stmt)

        conn.commit()
        print(f"  [SUCCESS] Executed {len(statements)} SQL statements from schema.sql.")
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"  [FAILED] Error applying schema.sql: {err}")
        sys.exit(1)

    # Step 3: Execute seed.sql
    print("\nStep 3/3: Populating seed.sql sample data (employees, attendance, payroll)...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        cursor = conn.cursor(dictionary=True)

        with open(SEED_FILE, "r", encoding="utf-8") as f:
            seed_sql = f.read()

        statements = [stmt.strip() for stmt in seed_sql.split(";") if stmt.strip()]
        for stmt in statements:
            cursor.execute(stmt)

        conn.commit()
        print(f"  [SUCCESS] Executed {len(statements)} SQL statements from seed.sql.")

        # Print summary of tables and row counts
        print("\nDatabase Schema Summary:")
        tables = ["users", "employees", "attendance", "salary_settings", "payroll", "payments"]
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}`;")
            row = cursor.fetchone()
            count = row["total"] if row else 0
            print(f"  - {table:<16}: {count} records")

        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"  [FAILED] Error applying seed.sql: {err}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Database initialization completed successfully!")
    print("You can now run: flask run")
    print("=" * 70)


if __name__ == "__main__":
    main()
