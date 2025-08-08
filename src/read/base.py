from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence

from database.connection import DatabaseConnection


class BaseReader:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    async def fetch_one(self, query: str, *args: Any) -> Optional[Dict]:
        return await self._db.fetch_one(query, *args)

    async def fetch_all(self, query: str, *args: Any) -> List[Dict]:
        return await self._db.fetch_all(query, *args)

    async def list_tables(self, like: Optional[str] = None) -> List[str]:
        pattern_clause = ""
        args: Sequence[Any] = []
        if like:
            pattern_clause = " WHERE tablename ILIKE $1"
            args = [like]
        rows = await self._db.fetch_all(
            f"SELECT tablename FROM pg_catalog.pg_tables{pattern_clause} ORDER BY tablename", *args
        )
        return [r["tablename"] for r in rows]