from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from metagpt.tools.tool_registry import register_tool

TAGS = ["bi", "ingestion", "pandas"]


@register_tool(tags=TAGS)
class PandasLoader:
    """Load flat files (CSV, Excel) into a DuckDB staging table via pandas.

    All I/O happens through pandas DataFrames so the LLM does not need to
    know the underlying file format — it passes the file path and target table
    name and the tool handles the rest.
    """

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

    def _read_file(self, file_path: str) -> pd.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        ext = path.suffix.lower()
        if ext == ".csv":
            return pd.read_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path)
        else:
            raise ValueError(
                f"Unsupported file extension '{ext}'. "
                f"Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

    def load_file(self, file_path: str, target_table: str, db_path: str) -> dict[str, Any]:
        """Load a flat file into a DuckDB table, creating or replacing the table.

        Uses pandas to read the file and DuckDB's native DataFrame ingestion to
        write it — no intermediate files needed.

        Args:
            file_path: Absolute or relative path to the CSV or Excel file.
            target_table: Name of the DuckDB table to create (or replace).
            db_path: Path to the target DuckDB database file.

        Returns:
            Dict with 'table' (str), 'rows_loaded' (int), 'columns' (list[str]).
        """
        df = self._read_file(file_path)
        conn = duckdb.connect(db_path)
        try:
            conn.execute(f"CREATE OR REPLACE TABLE {target_table} AS SELECT * FROM df")
            rows = conn.execute(f"SELECT COUNT(*) FROM {target_table}").fetchone()[0]
        finally:
            conn.close()
        return {
            "table": target_table,
            "rows_loaded": rows,
            "columns": df.columns.tolist(),
        }

    def infer_schema(self, file_path: str) -> list[dict[str, str]]:
        """Infer column names and pandas dtypes from a flat file without loading it to a DB.

        Useful for Agent 1 (DataSourceInspector) and for pre-validation before loading.

        Args:
            file_path: Path to the CSV or Excel file.

        Returns:
            List of dicts with keys 'name' (column name) and 'dtype' (pandas dtype string).
        """
        df = self._read_file(file_path)
        return [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns]

    def get_row_count(self, file_path: str) -> int:
        """Return the number of data rows in a flat file (headers not counted).

        Args:
            file_path: Path to the CSV or Excel file.

        Returns:
            Integer row count.
        """
        df = self._read_file(file_path)
        return len(df)
