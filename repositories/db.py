"""
Database Manager and Connection Helper for MySQL using mysql-connector-python.
Provides connection pooling, safe context managers, transaction management,
and health-check probing.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
import mysql.connector
from mysql.connector import Error, errorcode, pooling
from flask import Flask, current_app, g

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages MySQL connections, pooling, transactions, and safe resource cleanup.
    """

    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._config: Dict[str, Any] = {}
        self.pool_name = "payroll_pool"
        self.pool_size = 5
        self.pool_reset_session = True
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize database manager with Flask application context."""
        self.app = app
        app.extensions = getattr(app, "extensions", {})
        app.extensions["db"] = self

        self._config = {
            "host": app.config.get("DB_HOST", "127.0.0.1"),
            "port": int(app.config.get("DB_PORT", 3306)),
            "user": app.config.get("DB_USER", "root"),
            "password": app.config.get("DB_PASSWORD", ""),
            "database": app.config.get("DB_NAME", "employee_payroll"),
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
            "use_pure": True,
            "autocommit": False,
        }

        self.pool_name = app.config.get("DB_POOL_NAME", "payroll_pool")
        self.pool_size = int(app.config.get("DB_POOL_SIZE", 5))
        self.pool_reset_session = app.config.get("DB_POOL_RESET_SESSION", True)

        # Register teardown function to clean up any request-bound connections
        app.teardown_appcontext(self._teardown_request_connection)

        # Attempt pool creation lazily or on startup (non-blocking for app boot)
        self._init_pool()

    def _init_pool(self) -> bool:
        """Attempts to initialize the MySQL connection pool."""
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name=self.pool_name,
                pool_size=self.pool_size,
                pool_reset_session=self.pool_reset_session,
                **self._config
            )
            logger.info("MySQL connection pool '%s' initialized (size=%d).", self.pool_name, self.pool_size)
            return True
        except Error as err:
            logger.warning("Could not initialize MySQL connection pool at startup: %s", err)
            self._pool = None
            return False

    def _get_raw_connection(self):
        """
        Retrieves a connection from the pool, or creates a standalone connection
        if the pool is unavailable.
        """
        # If pool exists, try getting connection from pool
        if self._pool is not None:
            try:
                return self._pool.get_connection()
            except Error as err:
                logger.warning("Failed to get connection from pool: %s. Trying direct connection.", err)

        # Attempt to re-initialize pool or make a direct connection
        if self._config:
            return mysql.connector.connect(**self._config)
        raise RuntimeError("DatabaseManager has not been initialized with database configuration.")

    def _teardown_request_connection(self, exception=None) -> None:
        """Flask teardown handler: safely closes request-scoped database connection."""
        conn = g.pop("db_connection", None)
        if conn is not None:
            try:
                if conn.is_connected():
                    conn.close()
            except Exception as e:
                logger.error("Error closing request database connection: %s", e)

    @contextmanager
    def get_connection(self):
        """
        Context manager for acquiring and safely releasing a database connection.
        Ensures connection is closed back to pool even if an exception occurs.
        """
        conn = None
        try:
            conn = self._get_raw_connection()
            yield conn
        finally:
            if conn is not None:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception as err:
                    logger.error("Error while releasing database connection: %s", err)

    @contextmanager
    def get_cursor(self, dictionary: bool = True, prepared: bool = False):
        """
        Context manager for obtaining a database cursor with automatic cleanup
        of both cursor and underlying connection.
        """
        with self.get_connection() as conn:
            cursor = None
            try:
                cursor = conn.cursor(dictionary=dictionary, prepared=prepared)
                yield cursor, conn
            finally:
                if cursor is not None:
                    try:
                        cursor.close()
                    except Exception as err:
                        logger.error("Error while closing cursor: %s", err)

    @contextmanager
    def transaction(self):
        """
        Transaction context manager.
        - Begins a database transaction.
        - Commits automatically if the block finishes without errors.
        - Rolls back automatically on unhandled exceptions.
        - Guarantees cursor and connection cleanup.
        """
        with self.get_connection() as conn:
            cursor = None
            try:
                conn.autocommit = False
                cursor = conn.cursor(dictionary=True)
                yield cursor, conn
                conn.commit()
            except Exception as exc:
                try:
                    conn.rollback()
                    logger.warning("Transaction rolled back due to error: %s", exc)
                except Exception as rb_err:
                    logger.error("Error during transaction rollback: %s", rb_err)
                raise exc
            finally:
                if cursor is not None:
                    try:
                        cursor.close()
                    except Exception as c_err:
                        logger.error("Error closing transaction cursor: %s", c_err)

    def execute_query(
        self,
        query: str,
        params: Optional[Union[Tuple, Dict]] = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        dictionary: bool = True,
        commit: bool = False
    ) -> Any:
        """
        Safe query executor helper.
        Supports SELECT (fetch_one/fetch_all) and INSERT/UPDATE/DELETE (commit=True).
        """
        with self.get_cursor(dictionary=dictionary) as (cursor, conn):
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
                return cursor.lastrowid or cursor.rowcount
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            return cursor.rowcount

    def ping(self) -> Dict[str, Any]:
        """
        Safe health check probe.
        Checks database connectivity without raising unhandled exceptions or leaking sensitive secrets.
        """
        # If pool is not initialized, try initializing it once
        if self._pool is None and self._config:
            self._init_pool()

        status: Dict[str, Any] = {
            "connected": False,
            "host": self._config.get("host", "unknown"),
            "port": self._config.get("port", 3306),
            "database": self._config.get("database", "unknown"),
            "user": self._config.get("user", "unknown"),
            "server_version": None,
            "pool_active": self._pool is not None,
            "message": "Database not tested",
            "error_code": None,
        }

        try:
            with self.get_cursor(dictionary=True) as (cursor, conn):
                cursor.execute("SELECT VERSION() AS ver, DATABASE() AS current_db, NOW() AS db_time;")
                result = cursor.fetchone()
                if result:
                    status["connected"] = True
                    status["server_version"] = result.get("ver")
                    status["current_db"] = result.get("current_db")
                    status["db_time"] = str(result.get("db_time"))
                    status["message"] = f"Successfully connected to MySQL Server {result.get('ver')}"
        except Error as err:
            status["connected"] = False
            status["error_code"] = err.errno
            status["message"] = f"MySQL Error [{err.errno}]: {err.msg}"
            logger.warning("Database ping failed: %s", status["message"])
        except Exception as exc:
            status["connected"] = False
            status["message"] = f"Connection error: {str(exc)}"
            logger.warning("Database ping failed with general exception: %s", exc)

        return status
