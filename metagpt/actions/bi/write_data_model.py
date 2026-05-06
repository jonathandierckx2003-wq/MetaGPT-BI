import re

from metagpt.actions.action import Action

PROMPT_TEMPLATE = """
## Task

You are completing your task as the BI Data Modeler. The Business Requirement Document (BRD) below has been published by the BI Requirements Analyst.
Based exclusively on the content of this BRD, produce the three required output artifacts (Dimensional Model Specification, Conceptual Schema and
Logical Schema) by closely following the format and rules defined in your role instruction and in the Instructions below.

## Business Requirement Document

{brd_content}

## Instructions
- Follow the four sequential reasoning steps defined in your role instruction (Analyze the BRD -> Choose the schema type -> Identify facts, dimensions, measures and hierarchies -> Produce the three artifacts).
- Base all design decisions exclusively on the BRD content above. Do not invent or infer any requirements that are not explicitly stated in the BRD.
- When the BRD content is ambiguous or incomplete, flag this explicitly in Section 6 (Open questions) of the Dimensional Model Specification, instead of making assumptions.
- Always use the same language as the original BRD throughout the specification document.

## Output format

Return all three artifacts in a single response, each wrapped in the XML tags shown below. Do not include any text outside these tags.

<dimensional_model_specification>
[Full Dimensional Model Specification document in Markdown, following the format defined in your role instruction]
</dimensional_model_specification>

<conceptual_schema>
[Full Conceptual Schema in Mermaid syntax]
</conceptual_schema>

<logical_schema>
[Full Logical Schema in Mermaid syntax]
</logical_schema>
"""

_TAG_PATTERN = re.compile(
    r"<dimensional_model_specification>(.*?)</dimensional_model_specification>"
    r".*?"
    r"<conceptual_schema>(.*?)</conceptual_schema>"
    r".*?"
    r"<logical_schema>(.*?)</logical_schema>",
    re.DOTALL,
)


class WriteDataModel(Action):
    """Action that produces the three dimensional modeling artifacts from the BRD."""

    name: str = "WriteDataModel"

    async def run(self, brd_content: str) -> dict:
        """Call the LLM and return the three artifacts as a parsed dict.

        Returns:
            dict with keys: dimensional_model_specification, conceptual_schema, logical_schema
        """
        prompt = PROMPT_TEMPLATE.format(brd_content=brd_content)
        result = await self._aask(prompt)

        match = _TAG_PATTERN.search(result)
        if match:
            return {
                "dimensional_model_specification": match.group(1).strip(),
                "conceptual_schema": match.group(2).strip(),
                "logical_schema": match.group(3).strip(),
            }

        # Fallback: return raw text under the first key so callers can inspect it.
        return {
            "dimensional_model_specification": result.strip(),
            "conceptual_schema": "",
            "logical_schema": "",
        }
