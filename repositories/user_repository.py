"""
User Repository for database operations on the `users` table.
Handles user retrieval, role assignments, and password hash persistence.
"""

from typing import Any, Dict, List, Optional
import werkzeug.security as ws
from repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository handling SQL queries for system user accounts."""

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single user by primary key ID."""
        try:
            query = """
                SELECT id, username, email, password_hash, role, is_active, created_at, updated_at
                FROM users
                WHERE id = %s
                LIMIT 1;
            """
            return self.execute_query(query, (user_id,), fetch_one=True)
        except Exception:
            return None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user by unique username (case-insensitive search)."""
        try:
            query = """
                SELECT id, username, email, password_hash, role, is_active, created_at, updated_at
                FROM users
                WHERE LOWER(username) = LOWER(%s)
                LIMIT 1;
            """
            return self.execute_query(query, (username,), fetch_one=True)
        except Exception:
            return None

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch a single user by unique email."""
        try:
            query = """
                SELECT id, username, email, password_hash, role, is_active, created_at, updated_at
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1;
            """
            return self.execute_query(query, (email,), fetch_one=True)
        except Exception:
            return None

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "ACCOUNTANT",
        is_active: bool = True
    ) -> int:
        """
        Create a new user record with securely hashed password using Werkzeug.
        Returns the auto-generated user primary key ID.
        """
        password_hash = ws.generate_password_hash(password)
        query = """
            INSERT INTO users (username, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, %s);
        """
        return self.execute_query(
            query,
            (username.strip(), email.strip().lower(), password_hash, role.upper(), is_active),
            commit=True
        )

    def count_users(self) -> int:
        """Count total registered users."""
        query = "SELECT COUNT(*) AS total FROM users;"
        result = self.execute_query(query, fetch_one=True)
        return result.get("total", 0) if result else 0
