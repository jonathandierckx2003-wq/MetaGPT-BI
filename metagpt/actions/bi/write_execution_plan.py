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

## Task

Based on the context above, produce a complete DWH Technical Execution Plan following the three sequential reasoning steps defined in your role instruction (select tools -> identify tasks -> order tasks and resolve dependencies -> produce JSON output).

The plan must be output as a valid JSON array where each task strictly conforms to the schema defined in your role instruction. Output the JSON array only, starting directly with [ and ending with ]. Do not include any preamble, explanation, or markdown code fences around the JSON.
"""

_BI_TASK_TYPE_DESC = "\n".join(
    f"- {t.value}" for t in BITaskType
)


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

        for task in tasks:
            task_type = task.get("task_type", "")
            if task_type not in valid_types:
                raise ValueError(
                    f"Task {task.get('task_id')} has invalid task_type '{task_type}'. "
                    f"Must be one of: {sorted(valid_types)}"
                )
        logger.info(f"WriteExecutionPlan: validated {len(tasks)} tasks, all task_types are valid.")
