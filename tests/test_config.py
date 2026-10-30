"""
Tests for configuration settings and environment variable bindings.
"""

from config import Config, DevelopmentConfig, TestingConfig, ProductionConfig, config_by_name


def test_base_config_attributes():
    """Verify default base configuration attributes and types."""
    assert hasattr(Config, "SECRET_KEY")
    assert hasattr(Config, "DB_HOST")
    assert hasattr(Config, "DB_PORT")
    assert isinstance(Config.DB_PORT, int)
    assert hasattr(Config, "DB_USER")
    assert hasattr(Config, "DB_NAME")
    assert Config.DB_NAME == "employee_payroll"
    assert hasattr(Config, "DB_POOL_NAME")
    assert isinstance(Config.DB_POOL_SIZE, int)


def test_db_credentials_helper():
    """Verify DB credentials dictionary returns required keys for mysql.connector."""
    creds = Config.get_db_credentials()
    assert "host" in creds
    assert "port" in creds
    assert "user" in creds
    assert "password" in creds
    assert "database" in creds
    assert creds["charset"] == "utf8mb4"
    assert creds["collation"] == "utf8mb4_unicode_ci"
    assert creds["use_pure"] is True
    assert creds["autocommit"] is False


def test_testing_config():
    """Verify testing configuration parameters."""
    assert TestingConfig.TESTING is True
    assert TestingConfig.DEBUG is True
    assert TestingConfig.DB_POOL_SIZE == 2
    assert "test" in TestingConfig.DB_POOL_NAME.lower()


def test_production_config():
    """Verify production configuration flags."""
    assert ProductionConfig.DEBUG is False
    assert ProductionConfig.TESTING is False


def test_config_by_name_mapping():
    """Verify config_by_name dictionary maps expected keys."""
    assert "development" in config_by_name
    assert "testing" in config_by_name
    assert "production" in config_by_name
    assert "default" in config_by_name
    assert config_by_name["development"] is DevelopmentConfig
    assert config_by_name["testing"] is TestingConfig
    assert config_by_name["production"] is ProductionConfig
