"""
Database Layer.

Design pattern: Repository (DBClient exposes query/execute methods, hiding
raw SQLAlchemy Engine/Connection details from tests) + a context-managed
transaction() for explicit rollback control in tests that need to seed
data and guarantee cleanup even on assertion failure.

Multi-driver support (Postgres/MySQL/SQL Server/Oracle/SQLite) comes from
SQLAlchemy's dialect system — DBClient only needs the right connection
string prefix per driver; the query API stays identical.

Connection pooling: SQLAlchemy's QueuePool (the default for these dialects)
reuses connections across the many DB assertions a regression suite makes,
instead of opening/closing a TCP connection per query.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Row
from sqlalchemy.pool import QueuePool

from src.core.config import DBConfig
from src.core.logger import get_logger

logger = get_logger(__name__)

_DRIVER_DIALECTS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "sqlserver": "mssql+pyodbc",
    "oracle": "oracle+cx_oracle",
    "sqlite": "sqlite",
}


def _build_connection_string(db: DBConfig) -> str:
    dialect = _DRIVER_DIALECTS.get(db.driver)
    if not dialect:
        raise ValueError(
            f"Unsupported DB driver '{db.driver}'. Supported: {list(_DRIVER_DIALECTS)}"
        )

    if dialect == "sqlite":
        return f"sqlite:///{db.name}"

    return f"{dialect}://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}"


class DBClient:
    def __init__(self, db_config: DBConfig, pool_size: int = 5, max_overflow: int = 10) -> None:
        conn_str = _build_connection_string(db_config)
        kwargs: dict[str, Any] = {}
        if db_config.driver != "sqlite":
            kwargs = dict(poolclass=QueuePool, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True)

        self._engine: Engine = create_engine(conn_str, **kwargs)
        logger.info(
            "DB engine created: driver=%s host=%s db=%s pool_size=%s",
            db_config.driver,
            db_config.host or "(file)",
            db_config.name,
            pool_size,
        )

    def query(self, sql: str, params: dict[str, Any] | None = None) -> Sequence[Row]:
        """Read-only parameterized query. Always use :named params — never f-string SQL."""
        logger.debug("QUERY: %s | params=%s", sql, params)
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return result.fetchall()

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> int:
        """Write query (INSERT/UPDATE/DELETE) auto-committed. Returns rowcount."""
        logger.debug("EXECUTE: %s | params=%s", sql, params)
        with self._engine.begin() as conn:  # begin() auto-commits on success, rolls back on exception
            result = conn.execute(text(sql), params or {})
            return result.rowcount

    @contextmanager
    def transaction(self) -> Generator["_TransactionHandle", None, None]:
        """
        Explicit transaction scope for test data setup that must be rolled
        back regardless of test outcome — keeps the DB clean across a
        10k-test suite without a teardown step in every single test.

        Usage:
            with db.transaction() as tx:
                tx.execute("INSERT INTO orders (...) VALUES (:id)", {"id": 1})
                # ... run test assertions ...
            # rolled back automatically on exit
        """
        conn = self._engine.connect()
        trans = conn.begin()
        handle = _TransactionHandle(conn)
        try:
            yield handle
        finally:
            trans.rollback()
            conn.close()
            logger.debug("Transaction rolled back (test-data isolation)")

    def dispose(self) -> None:
        self._engine.dispose()


class _TransactionHandle:
    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> int:
        result = self._conn.execute(text(sql), params or {})
        return result.rowcount

    def query(self, sql: str, params: dict[str, Any] | None = None) -> Sequence[Row]:
        result = self._conn.execute(text(sql), params or {})
        return result.fetchall()
