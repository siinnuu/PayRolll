"""
Tests for database connection helper, context managers, and transaction handling.
"""

from unittest.mock import MagicMock, patch
import pytest
from repositories.db import DatabaseManager


def test_db_manager_ping_disconnected_safe(app):
    """Verify ping() does not crash or raise when database is unreachable."""
    db_mgr = DatabaseManager()
    db_mgr._config = {
        "host": "127.0.0.1",
        "port": 3399,  # non-existent port
        "user": "invalid_user",
        "password": "invalid_password",
        "database": "non_existent_db",
    }
    status = db_mgr.ping()
    assert isinstance(status, dict)
    assert status["connected"] is False
    assert "message" in status


def test_db_transaction_commit_success():
    """Verify transaction commits when no exception is raised."""
    db_mgr = DatabaseManager()
    
    mock_conn = MagicMock()
    mock_conn.is_connected.return_value = True
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    with patch.object(db_mgr, "_get_raw_connection", return_value=mock_conn):
        with db_mgr.transaction() as (cursor, conn):
            cursor.execute("UPDATE test SET val = 1")
            
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


def test_db_transaction_rollback_on_error():
    """Verify transaction rolls back when an exception is raised."""
    db_mgr = DatabaseManager()
    
    mock_conn = MagicMock()
    mock_conn.is_connected.return_value = True
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    with patch.object(db_mgr, "_get_raw_connection", return_value=mock_conn):
        with pytest.raises(ValueError, match="Simulated failure"):
            with db_mgr.transaction() as (cursor, conn):
                cursor.execute("UPDATE test SET val = 2")
                raise ValueError("Simulated failure")
                
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


def test_execute_query_fetch_one_mock():
    """Verify execute_query fetch_one returns expected record."""
    db_mgr = DatabaseManager()
    
    mock_conn = MagicMock()
    mock_conn.is_connected.return_value = True
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"val": 42}
    mock_conn.cursor.return_value = mock_cursor
    
    with patch.object(db_mgr, "_get_raw_connection", return_value=mock_conn):
        result = db_mgr.execute_query("SELECT 42 AS val", fetch_one=True)
        assert result == {"val": 42}
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
