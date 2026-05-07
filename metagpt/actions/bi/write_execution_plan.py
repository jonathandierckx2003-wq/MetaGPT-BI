import json

from metagpt.actions.action import Action
from metagpt.bi_task_type import BITaskType
from metagpt.logs import logger
from metagpt.tools.tool_registry import register_tool

PROMPT_TEMPLATE = """
## Context

You are completing your task as the BI Solution Architect. The following artifacts have been published in the shared message pool and form the basis for the DWH Technical Execution Plan you must now produce based exclusively on these.

### Business Requirement Document (BRD)

{brd_content}

### Dimensional Model Specification

{dimensional_model_specification}

### Logical Schema

{logical_schema}

## Available BI Task Types

{bi_task_type_desc}

## Required JSON schema — exact field names

Every task in the output array MUST include these exact field names. Do NOT use alternative names like "title", "description", "dependencies", or "tooling" — those names are wrong and will fail validation.

Concrete example of two valid tasks:

[
  {{
    "task_id": "1",
    "dependent_task_ids": [],
    "instruction": "Initialize a DuckDB database file at the project workspace path.",
    "task_type": "INSTANTIATION",
    "tool": "DuckDBExecutor",
    "tool_args": {{
      "db_path": "workspace/dwh.duckdb"
    }}
  }},
  {{
    "task_id": "2",
    "dependent_task_ids": ["1"],
    "instruction": "Load sales_transactions.csv into the staging_sales table in DuckDB.",
    "task_type": "DATA_INGESTION",
    "tool": "PandasLoader",
    "tool_args": {{
      "file_path": "ClaudeCode_implementation/test_data/sales_transactions.csv",
      "target_table": "staging_sales",
      "db_path": "workspace/dwh.duckdb"
    }}
  }}
]

Use these tool names in the "tool" field (required for all tasks except CREDENTIAL_REQUEST):
- DuckDBExecutor — INSTANTIATION (init DuckDB file), SCHEMA_CREATION (CREATE TABLE DDL)
- PandasLoader — DATA_INGESTION of CSV or Excel flat files into DuckDB
- DbtRunner — TRANSFORMATION tasks that use dbt SQL models (one task per dimensional table)
- SupabaseConnector — if Supabase is selected: INSTANTIATION, SCHEMA_CREATION, DATA_INGESTION
- AirbyteConnector — if Airbyte is selected: CONNECTION_SETUP, DATA_INGESTION from cloud sources

For CREDENTIAL_REQUEST tasks, set "tool" to null and "tool_args" to null:
{{
  "task_id": "3",
  "dependent_task_ids": ["2"],
  "instruction": "Ask the user for the Supabase project URL, API key, and postgres connection string.",
  "task_type": "CREDENTIAL_REQUEST",
  "tool": null,
  "tool_args": null
}}

## Task

Based on the context above, produce a complete DWH Technical Execution Plan following the three sequential reasoning steps defined in your role instruction (select tools → identify tasks → order tasks and resolve dependencies).

Output the JSON array only. Start directly with [ and end with ]. No preamble, no explanation, no markdown code fences.

CRITICAL: Use the EXACT field names shown above — task_id, dependent_task_ids, instruction, task_type, tool, tool_args.
Every task except CREDENTIAL_REQUEST must have a specific tool name from the list above and concrete tool_args with actual file paths, table names, or connection details derived from the BRD and Logical Schema above.
"""

_BI_TASK_TYPE_DESC = "\n".join(
    f"- {t.value}" for t in BITaskType
)

_REQUIRED_FIELDS = {"task_id", "dependent_task_ids", "instruction", "task_type"}


@register_tool(include_functions=["run"])
class WriteExecutionPlan(Action):
    """Action that produces the DWH Technical Execution Plan JSON from the dimensional design artifacts."""

    name: str = "WriteExecutionPlan"

    async def run(
        self,
        brd_content: str,
        dimensional_model_specification: str,
        logical_schema: str,
    ) -> str:
        """Generate and return the validated execution plan JSON string.

        Args:
            brd_content: Full text of the Business Requirement Document.
            dimensional_model_specification: Full text of the Dimensional Model Specification.
            logical_schema: Full text of the Logical Schema (Mermaid erDiagram).

        Returns:
            The raw JSON string of the execution plan after validation.
        """
        prompt = PROMPT_TEMPLATE.format(
            brd_content=brd_content,
            dimensional_model_specification=dimensional_model_specification,
            logical_schema=logical_schema,
            bi_task_type_desc=_BI_TASK_TYPE_DESC,
        )
        raw = await self._aask(prompt)

        # Strip markdown fences if the LLM wrapped the output
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        self._validate_plan(cleaned)
        return cleaned

    def _validate_plan(self, json_str: str) -> None:
        valid_types = {t.value for t in BITaskType}
        try:
            tasks = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"WriteExecutionPlan produced invalid JSON: {e}") from e

        if not isinstance(tasks, list) or len(tasks) == 0:
            raise ValueError("WriteExecutionPlan must return a non-empty JSON array of tasks.")

        errors = []
        for task in tasks:
            task_id = task.get("task_id", "?")

            # Required fields
            missing = _REQUIRED_FIELDS - set(task.keys())
            if missing:
                errors.append(
                    f"Task {task_id}: missing required fields {sorted(missing)}. "
                    f"Use exact names: task_id, dependent_task_ids, instruction, task_type, tool, tool_args."
                )
                continue

            # Valid task_type
            task_type = task.get("task_type", "")
            if task_type not in valid_types:
                errors.append(
                    f"Task {task_id}: invalid task_type '{task_type}'. "
                    f"Must be one of: {sorted(valid_types)}"
                )

            # Non-CREDENTIAL_REQUEST tasks must have a tool
            if task_type != "CREDENTIAL_REQUEST" and not task.get("tool"):
                errors.append(
                    f"Task {task_id} (type={task_type}): missing 'tool' field. "
                    f"Use one of: DuckDBExecutor, PandasLoader, DbtRunner, SupabaseConnector, AirbyteConnector."
                )

        if errors:
            raise ValueError(
                "WriteExecutionPlan validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        logger.info(f"WriteExecutionPlan: validated {len(tasks)} tasks, all required fields and task_types are valid.")
