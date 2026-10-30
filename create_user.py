"""
Safe user creation script for Employee Payroll Management System.
Allows creating initial Finance Manager (ACCOUNTANT) or Administrator accounts
without storing plaintext passwords or hardcoding credentials in repository code.

Usage:
    python create_user.py
    python create_user.py --username finance_mgr --email finance@payroll.local --role ACCOUNTANT
"""

import argparse
import getpass
import sys
from dotenv import load_dotenv
import werkzeug.security as ws
import mysql.connector
from config import Config

load_dotenv()


def create_user_direct(username, email, password, role="ACCOUNTANT"):
    """Insert new user directly into MySQL database with Werkzeug hash."""
    db_config = Config.get_db_credentials()
    password_hash = ws.generate_password_hash(password)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Check existing username
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s);", (username,))
        if cursor.fetchone():
            print(f"[ERROR] User with username '{username}' already exists.")
            return False

        # Check existing email
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s);", (email,))
        if cursor.fetchone():
            print(f"[ERROR] User with email '{email}' already exists.")
            return False

        # Insert user
        query = """
            INSERT INTO users (username, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, TRUE);
        """
        cursor.execute(query, (username.strip(), email.strip().lower(), password_hash, role.upper()))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()

        print(f"[SUCCESS] User '{username}' created successfully!")
        print(f"  User ID : {user_id}")
        print(f"  Role    : {role.upper()}")
        print(f"  Email   : {email}")
        print("  Security: Password encrypted using Werkzeug Scrypt hash.")
        return True
    except mysql.connector.Error as err:
        print(f"[ERROR] Database error: {err}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Create initial user account for Employee Payroll System")
    parser.add_argument("--username", help="Username for user")
    parser.add_argument("--email", help="Email for user")
    parser.add_argument("--password", help="Password for user (leave blank to be prompted securely)")
    parser.add_argument("--role", default="ACCOUNTANT", choices=["ACCOUNTANT", "ADMIN", "HR", "EMPLOYEE"],
                        help="Role for user (default: ACCOUNTANT)")

    args = parser.parse_args()

    print("=" * 65)
    print("Employee Payroll Management System - Account Creator")
    print("=" * 65)

    username = args.username
    if not username:
        username = input("Enter username: ").strip()

    email = args.email
    if not email:
        email = input("Enter email address: ").strip()

    role = args.role.upper()

    password = args.password
    if not password:
        password = getpass.getpass("Enter password: ")
        confirm_pwd = getpass.getpass("Confirm password: ")
        if password != confirm_pwd:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)

    if not username or not email or not password:
        print("[ERROR] Username, email, and password cannot be empty.")
        sys.exit(1)

    create_user_direct(username, email, password, role)


if __name__ == "__main__":
    main()
