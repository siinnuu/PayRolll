"""
Base Repository class providing standard SQL helper methods.
All domain-specific repositories inherit from this class.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from extensions import db
from repositories.db import DatabaseManager


class BaseRepository:
    """Base repository with database connection and transaction access."""

    def __init__(self, database_manager: Optional[DatabaseManager] = None):
        self.db = database_manager or db

    def execute_query(
        self,
        query: str,
        params: Optional[Union[Tuple, Dict]] = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        dictionary: bool = True,
        commit: bool = False
    ) -> Any:
        """Executes a SQL query through the configured database manager."""
        return self.db.execute_query(
            query=query,
            params=params,
            fetch_one=fetch_one,
            fetch_all=fetch_all,
            dictionary=dictionary,
            commit=commit
        )

    def transaction(self):
        """Context manager for multi-query atomic transactions."""
        return self.db.transaction()
