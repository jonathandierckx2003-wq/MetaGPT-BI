from __future__ import annotations

import time
from typing import Any

from metagpt.tools.tool_registry import register_tool

TAGS = ["bi", "supabase", "dwh", "postgres"]


@register_tool(tags=TAGS)
class SupabaseConnector:
    """Interact with a Supabase (PostgreSQL) database: DDL, queries, and data quality checks.

    Supabase exposes a standard PostgreSQL connection that this class accesses
    directly via psycopg2.  The connect() method accepts either the PostgreSQL
    connection string (recommended for DDL) or the Supabase project URL + service
    role key, from which the PostgreSQL URL is inferred.

    For read-only SELECT queries the supabase-py REST client is also available
    via the supabase_client() helper, but all methods on this class use the
    direct PostgreSQL connection for full DDL support.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(self):
        self._conn = None
        self._project_url: str | None = None
        self._api_key: str | None = None

    def connect(
        self,
        url: str,
        key: str,
        postgres_url: str | None = None,
    ) -> str:
        """Establish a connection to a Supabase project.

        Args:
            url: Supabase project URL, e.g. 'https://xxxx.supabase.co'.
            key: Supabase service role API key.
            postgres_url: Full PostgreSQL connection string, e.g.
                'postgresql://postgres:[password]@db.xxxx.supabase.co:5432/postgres'.
                Required for DDL execution.  If omitted, only REST API operations
                (which do not support DDL) will be available.

        Returns:
            Confirmation string.
        """
        import psycopg2

        self._project_url = url.rstrip("/")
        self._api_key = key

        if postgres_url:
            self._conn = psycopg2.connect(postgres_url)
            self._conn.autocommit = True
            return f"Connected to Supabase at '{url}' via direct PostgreSQL connection."

        return (
            f"Supabase REST client configured for '{url}'. "
            "Note: DDL operations require a postgres_url — provide it to enable full access."
        )

    def _require_connection(self) -> None:
        if self._conn is None:
            raise RuntimeError(
                "No active PostgreSQL connection. "
                "Call connect(url, key, postgres_url=...) with a postgres_url first."
            )

    def run_ddl(self, ddl: str) -> str:
        """Execute a DDL statement (CREATE TABLE, CREATE SCHEMA, ALTER TABLE, DROP …).

        Args:
            ddl: The DDL SQL string.

        Returns:
            'OK' on success.

        Raises:
            RuntimeError: After MAX_RETRIES failed attempts.
        """
        self._require_connection()
        last_exc = None
        for attempt in range(self.MAX_RETRIES):
            try:
                cur = self._conn.cursor()
                cur.execute(ddl)
                cur.close()
                return "OK"
            except Exception as exc:
                last_exc = exc
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        raise RuntimeError(f"DDL failed after {self.MAX_RETRIES} attempts: {last_exc}") from last_exc

    def run_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as a list of row dicts.

        Args:
            sql: SELECT SQL string.

        Returns:
            List of dicts, one per row, column names as keys.
        """
        self._require_connection()
        try:
            cur = self._conn.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            cur.close()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"Query failed: {exc}") from exc

    def verify_table(self, table_name: str) -> dict[str, Any]:
        """Check that a table exists and return its column definitions.

        Args:
            table_name: Table name, optionally schema-qualified (e.g. 'public.fact_sales').

        Returns:
            Dict with 'exists' (bool) and 'columns' (list of {name, type}).
        """
        parts = table_name.split(".")
        schema = parts[0] if len(parts) == 2 else "public"
        table = parts[-1]
        try:
            rows = self.run_query(
                f"SELECT column_name, data_type "
                f"FROM information_schema.columns "
                f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
                f"ORDER BY ordinal_position"
            )
            if not rows:
                return {"exists": False, "columns": []}
            columns = [{"name": r["column_name"], "type": r["data_type"]} for r in rows]
            return {"exists": True, "columns": columns}
        except Exception:
            return {"exists": False, "columns": []}

    def list_tables(self, schema: str = "public") -> list[str]:
        """Return a list of all table names in the given schema.

        Args:
            schema: PostgreSQL schema name (default 'public').

        Returns:
            List of schema-qualified table names (e.g. 'public.fact_sales').
        """
        rows = self.run_query(
            f"SELECT table_schema || '.' || table_name AS full_name "
            f"FROM information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE' "
            f"ORDER BY table_name"
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
        result = self.verify_table(table_name)
        if not result["exists"]:
            raise RuntimeError(f"Table '{table_name}' does not exist.")
        return result["columns"]

    def check_pk_uniqueness(self, table: str, pk_col: str) -> dict[str, Any]:
        """Verify that a column has no duplicate values (primary-key uniqueness check).

        Args:
            table: Table name (optionally schema-qualified).
            pk_col: Column name to check.

        Returns:
            Dict with 'unique' (bool) and 'duplicate_count' (int).
        """
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
            Dict with 'valid' (bool) and 'orphan_count' (int).
        """
        rows = self.run_query(
            f"SELECT COUNT(*) AS orphan_count "
            f"FROM {fact_table} f "
            f"LEFT JOIN {dim_table} d ON f.{fk_col} = d.{pk_col} "
            f"WHERE d.{pk_col} IS NULL"
        )
        orphan_count = rows[0]["orphan_count"]
        return {"valid": orphan_count == 0, "orphan_count": orphan_count}

    def supabase_client(self):
        """Return an initialized supabase-py client for REST API operations.

        Useful for table inserts/upserts via the PostgREST API when a direct
        PostgreSQL connection is not available or desired.

        Returns:
            A supabase.Client instance.

        Raises:
            RuntimeError: If connect() has not been called.
        """
        from supabase import create_client

        if not self._project_url or not self._api_key:
            raise RuntimeError("Call connect(url, key) first.")
        return create_client(self._project_url, self._api_key)

    def disconnect(self) -> str:
        """Close the active PostgreSQL connection.

        Returns:
            Confirmation string.
        """
        if self._conn:
            self._conn.close()
            self._conn = None
        return "Supabase PostgreSQL connection closed."
