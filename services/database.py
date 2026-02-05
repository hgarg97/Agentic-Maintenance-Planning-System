"""
Database Service
================
Async PostgreSQL connection pool and query helpers using psycopg3.
Uses psycopg3 (not asyncpg) for compatibility with LangGraph's AsyncPostgresSaver.
"""

import logging
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config.settings import get_database_url, DATABASE

logger = logging.getLogger(__name__)


class DatabaseService:
    """Async PostgreSQL database service with connection pooling."""

    _pool: Optional[AsyncConnectionPool] = None

    @classmethod
    async def initialize(cls) -> None:
        """Initialize the connection pool."""
        if cls._pool is not None:
            return

        dsn = get_database_url()
        cls._pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=DATABASE["min_connections"],
            max_size=DATABASE["max_connections"],
            kwargs={"row_factory": dict_row},
        )
        await cls._pool.open()
        logger.info("Database connection pool initialized")

    @classmethod
    async def close(cls) -> None:
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

    @classmethod
    async def fetch_one(
        cls, query: str, params: Optional[tuple] = None
    ) -> Optional[dict[str, Any]]:
        """Execute a query and return a single row as a dict."""
        async with cls._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return dict(row) if row else None

    @classmethod
    async def fetch_all(
        cls, query: str, params: Optional[tuple] = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as a list of dicts."""
        async with cls._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [dict(row) for row in rows]

    @classmethod
    async def execute(
        cls, query: str, params: Optional[tuple] = None
    ) -> None:
        """Execute a query without returning results (INSERT, UPDATE, DELETE)."""
        async with cls._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
            await conn.commit()

    @classmethod
    async def execute_returning(
        cls, query: str, params: Optional[tuple] = None
    ) -> Optional[dict[str, Any]]:
        """Execute a query and return the first row (for INSERT ... RETURNING)."""
        async with cls._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
            await conn.commit()
            return dict(row) if row else None

    @classmethod
    async def execute_many(
        cls, query: str, params_list: list[tuple]
    ) -> None:
        """Execute a query for multiple parameter sets."""
        async with cls._pool.connection() as conn:
            async with conn.cursor() as cur:
                for params in params_list:
                    await cur.execute(query, params)
            await conn.commit()

    @classmethod
    def get_dsn(cls) -> str:
        """Get the database connection string (for LangGraph checkpointer)."""
        return get_database_url()
