from metagpt.actions.action import Action

PROMPT_TEMPLATE = """
## Task

You are completing Phase 2 of your instructions. The elicitation dialogue with the business user is now complete and all mandatory topics have been covered. Based on the information collected below, write a complete and formal Business Requirement Document (BRD).

## Elicitation conversation history

{elicitation_history}

## Data source schemas retrieved during elicitation

{schema_summaries}

## Instructions
- Write the BRD strictly following the output format defined in your role instruction.
- Base all content exclusively on information provided by the user in the elicitation history above and on data source schemas retrieved by DataSourceInspector as shown above.
- When the user's answers are ambiguous or incomplete despite follow-up, flag this explicitly in Section 8 as an open question requiring future clarification.
- Ensure all queries in Section 4 are linkable to at least one goal in Section 3 or KPI in Section 5.
- Always use the same language as the business user, and only that language.
- Output the complete BRD now, starting directly with the document title, without any explanation or other content before the document.
"""


class WriteBRD(Action):
    """Action that produces the Business Requirement Document from the elicitation conversation."""

    name: str = "WriteBRD"

    async def run(self, elicitation_history: str, schema_summaries: str) -> str:
        prompt = PROMPT_TEMPLATE.format(
            elicitation_history=elicitation_history,
            schema_summaries=schema_summaries if schema_summaries.strip() else "No data sources were inspected.",
        )
        brd_content = await self._aask(prompt)
        return brd_content
