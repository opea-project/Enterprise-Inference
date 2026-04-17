"""
Database utilities and helper functions
"""

import asyncpg
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection pool manager with context manager support"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
        timeout: int = 30,
        command_timeout: int = 60
    ):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=min_size,
                max_size=max_size,
                timeout=timeout,
                command_timeout=command_timeout
            )
            logger.info("Database connection pool created successfully")

            # Verify connection
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")

            logger.info("Database connection verified successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a database connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")

        async with self.pool.acquire() as connection:
            yield connection

    async def fetch_one(self, query: str, *args, timeout: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Execute query and fetch one result with optional timeout"""
        async with self.acquire() as conn:
            if timeout:
                row = await conn.fetchrow(query, *args, timeout=timeout)
            else:
                row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args, timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute query and fetch all results with optional timeout"""
        async with self.acquire() as conn:
            if timeout:
                rows = await conn.fetch(query, *args, timeout=timeout)
            else:
                rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute(self, query: str, *args, timeout: Optional[int] = None) -> str:
        """Execute query without returning results"""
        async with self.acquire() as conn:
            if timeout:
                return await conn.execute(query, *args, timeout=timeout)
            return await conn.execute(query, *args)

    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Execute query multiple times with different parameters"""
        async with self.acquire() as conn:
            await conn.executemany(query, args_list)


# Global database manager instance
db_manager = DatabaseManager()
