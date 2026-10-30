# Employee Payroll Management System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/Flask-3.0.3-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL 8.0](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3.3-7952B3?style=flat&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Tests-166%20Passed-brightgreen?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org/)

A reliable, secure, and user-friendly **Employee Payroll Management System** built with **Python Flask**, **MySQL 8.0**, and **Bootstrap 5**. Designed specifically for a Finance Manager to handle monthly payroll generation, attendance & leave reconciliation, salary structures, payment disbursements, and printable salary slips.

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technologies Used](#technologies-used)
3. [Main Application Features](#main-application-features)
4. [Salary Calculation Formulas](#salary-calculation-formulas)
5. [Installation & Setup](#installation--setup)
6. [MySQL Database Setup](#mysql-database-setup)
7. [Running the Application](#running-the-application)
8. [User Accounts & Login Setup](#user-accounts--login-setup)
9. [Running Automated Tests](#running-automated-tests)
10. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Project Overview

The Employee Payroll Management System streamlines the compensation lifecycle from employee onboarding to monthly salary disbursement. It enforces relational database constraints to prevent duplicate payroll records, guarantees exact monetary calculations using fixed-point decimal arithmetic, and provides a clear workflow tailored for daily finance operations:

* **1. Dashboard**: High-level financial KPIs, approval alerts, workflow shortcuts, and monthly trends.
* **2. Employees**: Workforce directory, department assignments, contact records, and salary grade initialization.
* **3. Attendance**: Monthly working day tracking, overtime accounting, and distinct paid vs. unpaid leave accounting.
* **4. Payroll**: Controlled monthly batch runs with employee eligibility audit, and single-employee generation.
* **5. Payroll History**: Comprehensive, searchable history of generated, approved, and settled monthly payroll statements.

---

## Technologies Used

* **Backend**: Python 3.10+ with [Flask 3.0](https://flask.palletsprojects.com/) (Application Factory pattern, Blueprints)
* **Database**: [MySQL Server 8.0+](https://www.mysql.com/) (InnoDB engine, foreign key referential integrity, composite unique constraints)
* **Database Connector**: `mysql-connector-python` with connection pooling (`MySQLConnectionPool`)
* **Frontend**: Bootstrap 5.3, Bootstrap Icons, HTML5, CSS3, Jinja2 templating, and Chart.js
* **PDF Generation**: [ReportLab](https://www.reportlab.com/) for downloadable, printable PDF salary slips
* **Security**: Cryptographic CSRF session protection, Werkzeug password hashing (Scrypt / PBKDF2), parameterized SQL queries
* **Testing**: [pytest](https://docs.pytest.org/) automated unit and end-to-end integration test suite

---

## Main Application Features

### 1. Finance Manager Dashboard
* Real-time metrics computed directly from MySQL:
  * **Active Employees Count**
  * **Gross Payroll Total** for the selected month
  * **Total Deductions**
  * **Net Disbursed / Payable Salary**
  * **Payroll Awaiting Approval**
  * **Approved Payroll Awaiting Payment**
* Dynamic month and year filter toolbar.
* Interactive Gross vs. Net Pay trend visualization with Chart.js.
* Quick workflow action buttons: *Process Monthly Payroll*, *Add Employee*, *Record Attendance*, and *View Payroll*.

### 2. Employee Management
* Searchable employee directory by name, employee code, email, or department.
* Status filters (`ACTIVE`, `INACTIVE`, `ALL`) and department dropdown filters.
* Add & Edit Employee profiles with server-side validation (email format, positive salary values).
* Atomic database transaction initializing employee records and salary structures simultaneously.
* Safe employee deactivation: preserves historical attendance and payroll history without broken foreign keys.

### 3. Attendance & Leave Tracking
* Monthly reconciliation tracking:
  * Total working days in month
  * Days worked / present
  * Paid leave days (full base salary and allowances preserved)
  * Unpaid leave days (LWP - triggers configured leave deduction)
  * Overtime hours and overtime hourly rate
* Server-side reconciliation validation: total accounted days cannot exceed working days.
* Unique composite constraint (`employee_id, year, month`) preventing duplicate monthly attendance records.

### 4. Salary Settings & Preview Engine
* Basic monthly salary, HRA, transport allowance, medical allowance, other allowances, and fixed deductions.
* Interactive salary preview engine computing step-by-step earnings, daily rate, leave deductions, and net salary prior to finalizing payroll.
* Support for two configurable unpaid leave deduction methods.

### 5. Monthly Payroll Processing & Batch Runs
* **Controlled Batch Run**: Audits workforce readiness (verifies attendance record exists and salary structure is configured) and processes all eligible employees in a single transactional batch.
* **Individual Generator**: Single-employee calculation preview and generation.
* **Duplicate Prevention**: Composite unique constraint (`employee_id, year, month`) guarantees an employee cannot be paid twice for the same period.
* **Snapshot Preservation**: Once generated, statements lock salary components to guarantee historical compensation records are immutable.
* **Approval Lifecycle**: `DRAFT` &rarr; `APPROVED` &rarr; `PAID` (or `CANCELLED`).

### 6. Payroll History & Salary Slips
* Searchable ledger of all past and current payroll statements with status badges and filter tools.
* Detailed payslip statement view with itemized gross earnings and deductions.
* Clean physical printing via `@media print` (hides sidebar, navbar, and buttons).
* One-click publication-quality PDF salary slip download powered by ReportLab.

### 7. Security & Input Validation
* Server-side authentication and `@login_required` route guards.
* Cryptographic session-bound CSRF token validation on all state-changing requests (POST/PUT/DELETE).
* Zero hardcoded secret keys: enforced startup validation for `SECRET_KEY` in production/development.
* Parameterized SQL queries eliminating SQL injection risks.
* Minimal public `/api/health` monitoring endpoint without leaking infrastructure or database credentials.

---

## Salary Calculation Formulas

All monetary calculations use Python `Decimal` with consistent `ROUND_HALF_UP` rounding to two decimal places.

### 1. Unpaid Leave Deductions

The system supports two configurable leave deduction policies:

#### Method A: Daily-Rate Calculation (Default)
$$\text{Daily Rate} = \frac{\text{Basic Monthly Salary}}{\text{Total Working Days}}$$

$$\text{Leave Deduction} = \text{Daily Rate} \times \text{Unpaid Leave Days}$$

*Note: Paid leave days strictly incur ₹0.00 deduction.*

#### Method B: Percentage-Based Calculation
$$\text{Daily Leave Deduction} = \frac{\text{Basic Monthly Salary} \times \text{Daily Deduction Percentage}}{100}$$

$$\text{Total Leave Deduction} = \text{Daily Leave Deduction} \times \text{Unpaid Leave Days}$$

### 2. Overtime Earnings
$$\text{Overtime Payment} = \text{Overtime Hours} \times \text{Overtime Hourly Rate}$$

### 3. Gross Salary
$$\text{Gross Salary} = \text{Basic Salary} + \text{Allowances} + \text{Overtime Payment}$$

Where allowances equal:
$$\text{Allowances} = \text{HRA} + \text{Transport} + \text{Medical} + \text{Other Allowances}$$

### 4. Total Deductions
$$\text{Total Deductions} = \text{Leave Deduction} + \text{Other Deductions}$$

### 5. Net Payable Salary
$$\text{Net Salary} = \text{Gross Salary} - \text{Total Deductions}$$

---

## Installation & Setup

### 1. Prerequisites
* **Python**: 3.10, 3.11, 3.12, or 3.13 (`python --version`)
* **MySQL Server**: 8.0+ running on port 3306
* **Terminal**: Windows PowerShell or standard Bash shell

### 2. Clone / Open Directory & Create Virtual Environment
In PowerShell, navigate to the project directory:
```powershell
Set-Location "d:\PayRoll"

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables (`.env`)
Copy the sample environment file:
```powershell
Copy-Item .env.example .env
```
Generate a secure 256-bit secret key:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
Edit `.env` with your MySQL connection credentials:
```ini
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=paste_your_generated_random_hex_key_here

# MySQL Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=employee_payroll
DB_USER=root
DB_PASSWORD=YourMySQLPasswordHere

# Connection Pool Settings
DB_POOL_NAME=payroll_pool
DB_POOL_SIZE=5
```

---

## MySQL Database Setup

### 1. Create the Database
Log into the MySQL command line client:
```powershell
mysql -u root -p
```
Run the following SQL statement:
```sql
CREATE DATABASE IF NOT EXISTS employee_payroll
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
EXIT;
```

### 2. Initialize Schema & Import Seed Data
Execute the schema creation and seed scripts:
```powershell
# Method A: Via Flask CLI
python -m flask init-db

# Method B: Via Standalone Script
python init_db.py

# Import demonstration records (employees, attendance, payroll)
mysql -u root -p employee_payroll < seed.sql
```

---

## Running the Application

Start the Flask development server:
```powershell
python -m flask run --host=127.0.0.1 --port=5000
```
Or start via Python directly:
```powershell
python app.py
```

Open your browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

* Unauthenticated users are redirected automatically to `/auth/login`.
* Authenticated users land on `/dashboard`.

---

## User Accounts & Login Setup

### 1. Create a New Finance Manager Account
You can create accounts using the Flask CLI or interactive script:
```powershell
# Create an Accountant / Finance Manager account
python -m flask create-user --username finance_mgr --email finance@payroll.local --password "FinancePass@2026" --role ACCOUNTANT

# Or run the interactive prompt
python create_user.py
```

### 2. Pre-seeded Demonstration Accounts
If you imported `seed.sql`, the following accounts are ready to use:

| Username | Password | Role | Description |
|:---|:---|:---|:---|
| `michael.fin` | `User@123` | `ACCOUNTANT` | Primary Finance Manager |
| `admin` | `Admin@123` | `ADMIN` | System Administrator |
| `sarah.hr` | `User@123` | `HR` | Human Resources Officer |

---

## Running Automated Tests

The application includes automated unit and integration tests verifying authentication, calculations, attendance reconciliation, payroll lifecycles, and database constraints.

Execute the test suite with pytest:
```powershell
# Run the complete test suite
python -m pytest

# Run with verbose output
python -m pytest -v

# Run salary calculation tests specifically
python -m pytest tests/test_salary.py
```

---

## Troubleshooting & FAQ

### 1. Database Connection Failure: Access Denied
* **Symptom**: `mysql.connector.errors.ProgrammingError: 1045: Access denied for user 'root'@'localhost'`
* **Solution**: Check the `DB_USER` and `DB_PASSWORD` values in your `.env` file. Verify you can log in via PowerShell with `mysql -u root -p`.

### 2. MySQL Server Unavailable
* **Symptom**: `mysql.connector.errors.DatabaseError: 2003: Can't connect to MySQL server on '127.0.0.1:3306'`
* **Solution**: Verify the MySQL service is running in Windows Services (`services.msc`), or start it via Administrator command prompt: `net start MySQL80`.

### 3. Port Already in Use
* **Symptom**: `OSError: [Errno 10048] Address already in use`
* **Solution**: Launch Flask on a different port:
  ```powershell
  python -m flask run --port 5001
  ```

### 4. PowerShell Script Execution Disabled
* **Symptom**: `File ... Activate.ps1 cannot be loaded because running scripts is disabled`
* **Solution**: Set PowerShell execution policy for the current user:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
