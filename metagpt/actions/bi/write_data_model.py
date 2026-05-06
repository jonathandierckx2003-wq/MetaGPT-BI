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
- Use the Editor tool to write and save the three deliverables as separate files in the project's docs folder, by using the file names defined in your role instruction:
    - docs/dimensional_model_specification.md
    - docs/conceptual_schema.mermaid
    - docs/logical_schema.mermaid
- When the BRD content is ambiguous or incomplete, flag this explicitly in Section 6 (Open questions) of the Dimensional Model Specification, instead of making assumptions.
- Always use the same language as the original BRD throughout the specification document.
- After saving all three files, inform the user that the dimensional design is complete and provide the file paths of the three saved artifacts.
"""


class WriteDataModel(Action):
    """Action that produces the three dimensional modeling artifacts from the BRD."""

    name: str = "WriteDataModel"

    async def run(self, brd_content: str) -> str:
        prompt = PROMPT_TEMPLATE.format(brd_content=brd_content)
        result = await self._aask(prompt)
        return result
