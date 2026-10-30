"""
Application configuration classes for Employee Payroll Management System.
Supports development, testing, and production environments with safe defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env in workspace root if present
basedir = Path(__file__).resolve().parent
env_path = basedir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Config:
    """Base configuration class with environment-driven variables."""
    SECRET_KEY = os.environ.get("SECRET_KEY")
    
    # MySQL Database Settings
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", 3306))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "employee_payroll")
    
    # MySQL Connection Pool Settings
    DB_POOL_NAME = os.environ.get("DB_POOL_NAME", "payroll_pool")
    DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", 5))
    DB_POOL_RESET_SESSION = os.environ.get("DB_POOL_RESET_SESSION", "True").lower() in ("true", "1", "yes")
    
    # Application Metadata
    APP_NAME = "Employee Payroll Management System"
    APP_VERSION = "1.0.0"
    MODULE_NAME = "Module 1 - Architecture & Database Foundation"

    @classmethod
    def get_db_credentials(cls) -> dict:
        """Returns MySQL connection parameters formatted for mysql.connector."""
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "database": cls.DB_NAME,
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
            "use_pure": True,
            "autocommit": False,
        }


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "test-testing-secret-key-fixture-32chars-min")
    DB_NAME = os.environ.get("TEST_DB_NAME", "employee_payroll_test")
    DB_POOL_NAME = "payroll_test_pool"
    DB_POOL_SIZE = 2


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
