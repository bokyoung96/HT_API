import asyncpg
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime

from .config import DatabaseConfig
from .schemas import ALL_TABLES


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.config.postgres_url,
                min_size=self.config.pool_settings.get("min_size", 1),
                max_size=self.config.pool_settings.get("max_size", 10),
                server_settings=self.config.pool_settings.get(
                    "server_settings", {'jit': 'off'})
            )

            await self._create_tables()
            logging.info("✅ Database connection and table creation completed")

        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
            raise

    async def _create_tables(self) -> None:
        async with self.pool.acquire() as conn:
            for table_sql in ALL_TABLES:
                await conn.execute(table_sql)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logging.info("🔌 Database connection closed")

    async def execute_query(self, query: str, *args) -> Any:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def health_check(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logging.error(f"❌ Database health check failed: {e}")
            return False
