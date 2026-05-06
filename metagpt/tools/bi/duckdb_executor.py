from __future__ import annotations

import time
from typing import Any

import duckdb

from metagpt.tools.tool_registry import register_tool

TAGS = ["bi", "duckdb", "dwh"]


@register_tool(tags=TAGS)
class DuckDBExecutor:
    """Interact with a DuckDB database file: DDL execution, queries, and data quality checks.

    The connection is opened lazily on first use and held open for the lifetime
    of the instance.  Call disconnect() when finished to release the file lock.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(self):
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._db_path: str | None = None

    def connect(self, db_path: str) -> str:
        """Open (or create) a DuckDB database file.

        Args:
            db_path: Filesystem path to the .duckdb file.
                     Use ':memory:' for an in-process ephemeral database.

        Returns:
            A confirmation string with the resolved path.
        """
        self._db_path = db_path
        self._conn = duckdb.connect(db_path)
        return f"Connected to DuckDB at '{db_path}'."

    def disconnect(self) -> str:
        """Close the active connection.

        Returns:
            Confirmation string.
        """
        if self._conn:
            self._conn.close()
            self._conn = None
        return "DuckDB connection closed."

    def _require_connection(self) -> None:
        if self._conn is None:
            raise RuntimeError("No active DuckDB connection. Call connect(db_path) first.")

    def run_ddl(self, ddl: str) -> str:
        """Execute a DDL statement (CREATE TABLE, CREATE SCHEMA, ALTER TABLE, DROP …).

        Retries up to MAX_RETRIES times on transient errors.

        Args:
            ddl: The DDL SQL string to execute.

        Returns:
            'OK' on success, or raises RuntimeError with the error message.
        """
        self._require_connection()
        last_exc = None
        for attempt in range(self.MAX_RETRIES):
            try:
                self._conn.execute(ddl)
                return "OK"
            except Exception as exc:
                last_exc = exc
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        raise RuntimeError(f"DDL failed after {self.MAX_RETRIES} attempts: {last_exc}") from last_exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SELECT query and return the results as a list of row dicts.

        Args:
            sql: The SELECT SQL string.

        Returns:
            List of dicts, one per row, with column names as keys.

        Raises:
            RuntimeError: On query failure.
        """
        self._require_connection()
        try:
            rel = self._conn.execute(sql)
            columns = [desc[0] for desc in rel.description]
            rows = rel.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"Query failed: {exc}") from exc

    def verify_table(self, table_name: str) -> dict[str, Any]:
        """Check that a table exists and return its column definitions.

        Args:
            table_name: Table name, optionally schema-qualified (e.g. 'main.fact_sales').

        Returns:
            Dict with keys 'exists' (bool) and 'columns' (list of {name, type}).
        """
        self._require_connection()
        try:
            rows = self.run_query(f"DESCRIBE {table_name}")
            columns = [{"name": r["column_name"], "type": r["column_type"]} for r in rows]
            return {"exists": True, "columns": columns}
        except Exception:
            return {"exists": False, "columns": []}

    def list_tables(self) -> list[str]:
        """Return a list of all table names in the connected database.

        Returns:
            List of fully-qualified table names (schema.table).
        """
        self._require_connection()
        rows = self.run_query(
            "SELECT table_schema || '.' || table_name AS full_name "
            "FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' "
            "ORDER BY full_name"
        )
        return [r["full_name"] for r in rows]

    def get_table_schema(self, table_name: str) -> list[dict[str, str]]:
        """Return column definitions for a table.

        Args:
            table_name: Table name, optionally schema-qualified.

        Returns:
            List of dicts with keys 'name' and 'type'.

        Raises:
            RuntimeError: If the table does not exist.
        """
        self._require_connection()
        result = self.verify_table(table_name)
        if not result["exists"]:
            raise RuntimeError(f"Table '{table_name}' does not exist.")
        return result["columns"]

    def check_pk_uniqueness(self, table: str, pk_col: str) -> dict[str, Any]:
        """Verify that a column has no duplicate values (primary-key uniqueness check).

        Args:
            table: Table name.
            pk_col: Column name to check.

        Returns:
            Dict with 'unique' (bool) and 'duplicate_count' (int).
        """
        self._require_connection()
        rows = self.run_query(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT {pk_col}) AS distinct_count "
            f"FROM {table}"
        )
        total = rows[0]["total"]
        distinct = rows[0]["distinct_count"]
        duplicates = total - distinct
        return {"unique": duplicates == 0, "duplicate_count": duplicates}

    def check_fk_integrity(
        self,
        fact_table: str,
        fk_col: str,
        dim_table: str,
        pk_col: str,
    ) -> dict[str, Any]:
        """Verify referential integrity between a fact table FK and a dimension table PK.

        Args:
            fact_table: Fact table containing the foreign-key column.
            fk_col: Foreign-key column in fact_table.
            dim_table: Dimension table containing the referenced primary key.
            pk_col: Primary-key column in dim_table.

        Returns:
            Dict with 'valid' (bool) and 'orphan_count' (int — rows in fact with no
            matching row in dim).
        """
        self._require_connection()
        rows = self.run_query(
            f"SELECT COUNT(*) AS orphan_count "
            f"FROM {fact_table} f "
            f"LEFT JOIN {dim_table} d ON f.{fk_col} = d.{pk_col} "
            f"WHERE d.{pk_col} IS NULL"
        )
        orphan_count = rows[0]["orphan_count"]
        return {"valid": orphan_count == 0, "orphan_count": orphan_count}
