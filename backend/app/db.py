"""Thread-safe pyexasol connection pool with retry and health reporting."""

from __future__ import annotations

import logging
import queue
import ssl
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import pyexasol
from pyexasol.exceptions import (
    ExaCommunicationError,
    ExaConcurrencyError,
    ExaConnectionFailedError,
    ExaError,
)

from .config import settings

logger = logging.getLogger("credenceiq.db")

_CONNECTION_ERRORS = (ExaCommunicationError, ExaConnectionFailedError, ExaConcurrencyError)


class DatabaseUnavailable(RuntimeError):
    """Raised when Exasol cannot be reached after a retry."""


class DatabaseQueryError(RuntimeError):
    """Raised when Exasol rejects a query."""


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    elapsed_ms: float


class ExasolPool:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        schema: str,
        size: int = 8,
        query_timeout: int = 60,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.schema = schema
        self.size = max(1, size)
        self.query_timeout = query_timeout
        self._pool: queue.LifoQueue[pyexasol.ExaConnection] = queue.LifoQueue(maxsize=self.size)
        self._lock = threading.Lock()
        self._created = 0
        self._checked_out = 0
        self._total_queries = 0
        self._total_query_ms = 0.0
        self._closed = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def _new_connection(self) -> pyexasol.ExaConnection:
        started = time.perf_counter()
        connection = pyexasol.connect(
            dsn=f"{self.host}:{self.port}",
            user=self.user,
            password=self.password,
            compression=True,
            encryption=True,
            # Exasol Personal ships a self-signed certificate. Production
            # deployments should pin the fingerprint or use a trusted CA.
            websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
            fetch_dict=True,
            lower_ident=True,
            connection_timeout=15,
            socket_timeout=self.query_timeout + 15,
            query_timeout=self.query_timeout,
            client_name="CredenceIQ-API",
            client_version=settings.api_version,
        )
        logger.info(
            "opened Exasol connection in %.0f ms",
            (time.perf_counter() - started) * 1000,
        )
        return connection

    def _checkout(self) -> pyexasol.ExaConnection:
        try:
            connection = self._pool.get_nowait()
            with self._lock:
                self._checked_out += 1
            return connection
        except queue.Empty:
            pass

        create = False
        with self._lock:
            if self._created < self.size:
                self._created += 1
                create = True
        if create:
            try:
                connection = self._new_connection()
            except Exception:
                with self._lock:
                    self._created -= 1
                raise
            with self._lock:
                self._checked_out += 1
            return connection

        try:
            connection = self._pool.get(timeout=15)
        except queue.Empty as exc:
            raise DatabaseUnavailable("Timed out waiting for an Exasol connection") from exc
        with self._lock:
            self._checked_out += 1
        return connection

    def _release(self, connection: pyexasol.ExaConnection) -> None:
        with self._lock:
            self._checked_out = max(0, self._checked_out - 1)
        if self._closed or getattr(connection, "is_closed", False):
            self._destroy(connection)
            return
        try:
            self._pool.put_nowait(connection)
        except queue.Full:  # pragma: no cover - defensive
            self._destroy(connection)

    def _destroy(self, connection: pyexasol.ExaConnection) -> None:
        try:
            connection.close()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
        with self._lock:
            self._created = max(0, self._created - 1)

    @contextmanager
    def acquire(self) -> Iterator[pyexasol.ExaConnection]:
        connection: pyexasol.ExaConnection | None = None
        broken = False
        try:
            connection = self._checkout()
            yield connection
        except _CONNECTION_ERRORS:
            broken = True
            raise
        except Exception as exc:
            broken = bool(getattr(connection, "is_closed", False))
            if broken:
                logger.warning("discarding closed Exasol connection: %s", exc)
            raise
        finally:
            if connection is not None:
                if broken:
                    with self._lock:
                        self._checked_out = max(0, self._checked_out - 1)
                    self._destroy(connection)
                else:
                    self._release(connection)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def query(self, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
        last_error: Exception | None = None
        for attempt in range(2):
            started = time.perf_counter()
            try:
                with self.acquire() as connection:
                    statement = connection.execute(sql, params or {})
                    rows = statement.fetchall()
                elapsed_ms = (time.perf_counter() - started) * 1000
                with self._lock:
                    self._total_queries += 1
                    self._total_query_ms += elapsed_ms
                if elapsed_ms > 1500:
                    logger.warning("slow Exasol query (%.0f ms): %.160s", elapsed_ms, sql)
                return QueryResult(rows=rows, elapsed_ms=round(elapsed_ms, 2))
            except _CONNECTION_ERRORS as exc:
                last_error = exc
                logger.warning("Exasol communication failure (attempt %s/2): %s", attempt + 1, exc)
                if attempt == 0:
                    time.sleep(0.15)
                    continue
                break
            except ExaError as exc:
                error_text = str(exc)
                logger.error("Exasol query error: %s", error_text)
                raise DatabaseQueryError(error_text) from exc
        raise DatabaseUnavailable(f"Exasol is unreachable: {last_error}")

    def query_one(self, sql: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, float]:
        result = self.query(sql, params)
        return (result.rows[0] if result.rows else None), result.elapsed_ms

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> float:
        last_error: Exception | None = None
        for attempt in range(2):
            started = time.perf_counter()
            try:
                with self.acquire() as connection:
                    connection.execute(sql, params or {})
                elapsed_ms = (time.perf_counter() - started) * 1000
                with self._lock:
                    self._total_queries += 1
                    self._total_query_ms += elapsed_ms
                return round(elapsed_ms, 2)
            except _CONNECTION_ERRORS as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.15)
                    continue
                break
            except ExaError as exc:
                raise DatabaseQueryError(str(exc)) from exc
        raise DatabaseUnavailable(f"Exasol is unreachable: {last_error}")

    def ping(self) -> tuple[bool, float]:
        started = time.perf_counter()
        try:
            self.query("SELECT 1 AS OK")
            return True, round((time.perf_counter() - started) * 1000, 2)
        except Exception:
            return False, round((time.perf_counter() - started) * 1000, 2)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            available = self._pool.qsize()
            return {
                "size": self.size,
                "created": self._created,
                "in_use": self._checked_out,
                "available": available,
                "queries": self._total_queries,
                "avg_query_ms": round(self._total_query_ms / self._total_queries, 2)
                if self._total_queries
                else 0.0,
            }

    def close(self) -> None:
        self._closed = True
        while True:
            try:
                connection = self._pool.get_nowait()
            except queue.Empty:
                break
            self._destroy(connection)


pool = ExasolPool(
    host=settings.exasol_host,
    port=settings.exasol_port,
    user=settings.exasol_user,
    password=settings.exasol_password,
    schema=settings.exasol_schema,
    size=settings.exasol_pool_size,
    query_timeout=settings.exasol_query_timeout,
)
