from metagpt.actions.action import Action

PROMPT_TEMPLATE = """
## Task

You are completing Phase 3 of your instructions as the BI QA Engineer.
Both validation phases (Phases 1 and 2) are now complete. Based on the results collected below,
produce a complete and structured Validation Feedback Report.

## Validation results

### Phase 1: Structural and technical validation results

{structural_validation_results}

### Phase 2: Requirements traceability validation results

{traceability_validation_results}

## Reference artifacts

### BRD (Sections 4, 5 and 6 summary)

{brd_summary}

### Logical Schema

{logical_schema}

### DWH Technical Execution Plan

{execution_plan}

### DWH connection details (from Execution Report)

{dwh_connection_details}

## Instructions
- Determine the overall validation outcome: ACCEPTED if all checks in both phases pass, REJECTED otherwise.
- Write the Validation Feedback Report strictly following the output format below.
- For REJECTED outcomes: describe each failure with enough precision for the BI Analytics Engineer to identify the root cause and the specific task(s) to re-execute, without needing additional context.
- For ACCEPTED outcomes: include the DWH connection details, inform the human user that the BI back-end development is complete and ready for use, and where (at which path) the BRD, Schemas and other artifacts created in the process can be retrieved.
- Always use the same language as the original BRD.

## Output format

# Validation Feedback Report

## Overall outcome

ACCEPTED / REJECTED

## Phase 1: Structural and technical validation

For each table in the created DWH: table name | check performed | PASS/FAIL | details

## Phase 2: Requirements traceability validation

### Queries and analyses (BRD Section 4)

For each query: query name | SUPPORTED/UNSUPPORTED | details

### KPIs and metrics (BRD Section 5)

For each KPI: KPI name | COMPUTABLE/NOT_COMPUTABLE | details

### Data sources (BRD Section 6)

For each source: source name | INGESTED/MISSING | details

## Summary and next steps

If ACCEPTED: confirmation that the DWH is validated, followed by DWH connection details.

If REJECTED: numbered list of all failures, each with:
- The specific check or item that failed
- What was found vs. what was expected
- The task ID(s) from the Execution Plan that should be re-executed to fix it
"""


class WriteValidationReport(Action):
    """Action that produces the Validation Feedback Report from both validation phases."""

    name: str = "WriteValidationReport"

    async def run(
        self,
        structural_validation_results: str,
        traceability_validation_results: str,
        brd_summary: str,
        logical_schema: str,
        execution_plan: str,
        dwh_connection_details: str,
    ) -> str:
        prompt = PROMPT_TEMPLATE.format(
            structural_validation_results=structural_validation_results,
            traceability_validation_results=traceability_validation_results,
            brd_summary=brd_summary,
            logical_schema=logical_schema,
            execution_plan=execution_plan,
            dwh_connection_details=dwh_connection_details,
        )
        report_content = await self._aask(prompt)
        return report_content
