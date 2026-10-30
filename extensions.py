"""
Flask Extensions module for Employee Payroll Management System.
Instantiates shared extensions for use across application blueprints.
"""

from repositories.db import DatabaseManager

# Shared database manager instance initialized via create_app()
db = DatabaseManager()
