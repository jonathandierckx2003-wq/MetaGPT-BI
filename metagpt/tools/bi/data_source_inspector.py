from __future__ import annotations

from pathlib import Path
from typing import Any

from metagpt.tools.tool_registry import register_tool

TAGS = ["bi", "inspection", "requirements"]


@register_tool(tags=TAGS)
class DataSourceInspector:
    """Inspect data sources and return their structure (tables, columns, dtypes, row counts).

    Used exclusively by BIRequirementsAnalyst (Agent 1) during elicitation to understand
    what data the client has available before writing the BRD.
    """

    def inspect_csv(self, file_path: str) -> dict[str, Any]:
        """Inspect a CSV file and return its column structure and row count.

        Args:
            file_path: Path to the CSV file.

        Returns:
            Dict with 'file', 'row_count', and 'columns' (list of {name, dtype, sample}).
        """
        import pandas as pd

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_csv(file_path, nrows=5)
        full_df = pd.read_csv(file_path)

        columns = []
        for col in full_df.columns:
            null_count = int(full_df[col].isna().sum())
            if null_count == len(full_df):
                continue  # skip entirely-null columns — no useful schema info
            samples = []
            for v in df[col].tolist():
                s = str(v)
                samples.append(s[:60] + "…" if len(s) > 60 else s)
            columns.append({
                "name": col,
                "dtype": str(full_df[col].dtype),
                "sample": samples,
                "null_count": null_count,
            })
        return {
            "file": str(path.resolve()),
            "format": "csv",
            "row_count": len(full_df),
            "columns": columns,
        }

    def inspect_excel(self, file_path: str) -> dict[str, Any]:
        """Inspect an Excel file (.xlsx / .xls) and return the structure of each sheet.

        Args:
            file_path: Path to the Excel file.

        Returns:
            Dict with 'file', 'sheets' (list of {sheet_name, row_count, columns}).
        """
        import pandas as pd

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        xl = pd.ExcelFile(file_path)
        sheets = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            columns = [
                {
                    "name": col,
                    "dtype": str(df[col].dtype),
                    "null_count": int(df[col].isna().sum()),
                }
                for col in df.columns
            ]
            sheets.append(
                {
                    "sheet_name": sheet_name,
                    "row_count": len(df),
                    "columns": columns,
                }
            )
        return {
            "file": str(path.resolve()),
            "format": "excel",
            "sheets": sheets,
        }

    def inspect_duckdb(self, db_path: str) -> dict[str, Any]:
        """Inspect a DuckDB database file and return all tables with their columns and row counts.

        Args:
            db_path: Path to the DuckDB .duckdb file.

        Returns:
            Dict with 'db_path' and 'tables' (list of {table_name, row_count, columns}).
        """
        import duckdb

        conn = duckdb.connect(db_path, read_only=True)
        try:
            table_rows = conn.execute(
                "SELECT table_schema, table_name "
                "FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "ORDER BY table_schema, table_name"
            ).fetchall()

            tables = []
            for schema, table in table_rows:
                full_name = f"{schema}.{table}"
                desc = conn.execute(f"DESCRIBE {full_name}").fetchall()
                columns = [{"name": r[0], "type": r[1]} for r in desc]
                row_count = conn.execute(f"SELECT COUNT(*) FROM {full_name}").fetchone()[0]
                tables.append(
                    {
                        "table_name": full_name,
                        "row_count": row_count,
                        "columns": columns,
                    }
                )
        finally:
            conn.close()

        return {"db_path": db_path, "tables": tables}

    def inspect_postgres(self, connection_string: str) -> dict[str, Any]:
        """Inspect a PostgreSQL database and return all public tables with column info and row counts.

        Args:
            connection_string: libpq-style connection string, e.g.
                'postgresql://user:password@host:5432/dbname'

        Returns:
            Dict with 'host', 'dbname', and 'tables' (list of {table_name, row_count, columns}).
        """
        import psycopg2
        from psycopg2 import sql as pg_sql
        from urllib.parse import urlparse

        parsed = urlparse(connection_string)
        conn = psycopg2.connect(connection_string)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
            table_names = [r[0] for r in cur.fetchall()]

            tables = []
            for table_name in table_names:
                cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s "
                    "ORDER BY ordinal_position",
                    (table_name,),
                )
                columns = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]

                cur.execute(
                    pg_sql.SQL("SELECT COUNT(*) FROM public.{}").format(
                        pg_sql.Identifier(table_name)
                    )
                )
                row_count = cur.fetchone()[0]

                tables.append(
                    {
                        "table_name": f"public.{table_name}",
                        "row_count": row_count,
                        "columns": columns,
                    }
                )
        finally:
            conn.close()

        return {
            "host": parsed.hostname,
            "dbname": parsed.path.lstrip("/"),
            "tables": tables,
        }
