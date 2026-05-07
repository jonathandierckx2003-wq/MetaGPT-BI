from __future__ import annotations

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.logs import logger
from metagpt.prompts.bi.bi_solution_architect import BI_SOLUTION_ARCHITECT_INSTRUCTION
from metagpt.roles.di.role_zero import RoleZero
from metagpt.schema import Message
from metagpt.tools.tool_registry import register_tool
from metagpt.utils.common import any_to_name, any_to_str


@register_tool(include_functions=["generate_execution_plan"])
class BISolutionArchitect(RoleZero):
    """Agent 3: Translates dimensional design artifacts into a DWH Technical Execution Plan.

    Executes three sequential reasoning steps (select tools → identify tasks →
    order & resolve dependencies → call generate_execution_plan()) and produces
    a dependency-ordered JSON task list for the BI Analytics Engineer.
    """

    name: str = "Eve"
    profile: str = "BI Solution Architect"
    goal: str = (
        "Produce a complete, dependency-ordered DWH Technical Execution Plan task list in "
        "structured JSON format, selecting the appropriate external tools for each task and "
        "flagging all human-in-the-loop credential collection checkpoints."
    )
    constraints: str = (
        "Always use the same language as the original BRD. Base all planning decisions exclusively "
        "on the BRD and on the dimensional design artifacts published in the shared message pool. "
        "The execution plan must be produced as valid JSON conforming to the defined schema. "
        "Every task must be assigned exactly one task type from the BITaskType enum. Every task "
        "that requires an external tool must have a non-empty tool field. Tasks must be ordered "
        "so that all dependencies are resolvable, and no task may depend on a task with a higher "
        "task ID."
    )
    instruction: str = BI_SOLUTION_ARCHITECT_INSTRUCTION
    tools: list[str] = ["RoleZero", "Editor", "BISolutionArchitect"]
    todo_action: str = any_to_name(WriteExecutionPlan)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # RoleZero sets observe_all_msg_from_buffer=True which prevents the automatic
        # _watch([UserRequirement]) call in Role.__init__, so we call it explicitly here (DEV-16).
        # WriteDataModel is the trigger; the WriteBRD message is also in memory via
        # observe_all_msg_from_buffer=True since all messages are stored regardless of watch filter.
        self._watch([WriteDataModel])

    async def _quick_think(self):
        # Execution planning is a structured multi-step task — never shortcut via QUICK/AMBIGUOUS (DEV-22).
        return None, "TASK"

    async def reply_to_human(self, content: str) -> str:
        """Reply to the business user with a status update or completion notice."""
        # RoleZero.reply_to_human only works inside MGXEnv. Override for terminal visibility (DEV-32 pattern).
        print(f"\n[Eve - BI Solution Architect]: {content}\n")
        return content

    def _update_tool_execution(self):
        # DEV-21: TOOL_REGISTRY provides schemas for the LLM recommender; actual callables
        # must be wired into tool_execution_map for the RoleZero dispatcher to find them.
        self.tool_execution_map.update({
            "BISolutionArchitect.generate_execution_plan": self.generate_execution_plan,
        })

    @staticmethod
    def _extract_section(text: str) -> str:
        """Strip the '## Heading\n\n' prefix from a WriteDataModel combined-message section."""
        idx = text.find("\n\n")
        return text[idx + 2:] if idx != -1 else text

    async def generate_execution_plan(self) -> str:
        """Generate and save the DWH Technical Execution Plan from the dimensional design artifacts.

        Retrieves the BRD and all three data model artifacts from the shared message pool memory
        (DEV-28 pattern — no large documents passed as arguments), calls WriteExecutionPlan to
        produce a validated JSON execution plan, saves it to file, and publishes a message to
        trigger the BI Analytics Engineer.

        Returns:
            Confirmation message listing the saved artifact path.
        """
        # --- Retrieve BRD from memory (DEV-28 pattern) ---
        brd_content = ""
        for msg in reversed(self.rc.memory.get()):
            if msg.cause_by == any_to_str(WriteBRD):
                brd_content = msg.content
                break

        if not brd_content:
            return "Error: No BRD found in memory. Cannot produce execution plan without a BRD."

        # --- Retrieve combined data model content from memory (DEV-28 pattern) ---
        data_model_content = ""
        for msg in reversed(self.rc.memory.get()):
            if msg.cause_by == any_to_str(WriteDataModel):
                data_model_content = msg.content
                break

        if not data_model_content:
            return "Error: No data model found in memory. Cannot produce execution plan without a data model."

        # --- Extract the Dimensional Model Specification and Logical Schema from combined message ---
        # BIDataModeler.generate_data_model() publishes a combined message in the format:
        #   "## Dimensional Model Specification\n\n{spec}\n\n---\n\n"
        #   "## Conceptual Schema (Mermaid erDiagram)\n\n{conceptual}\n\n---\n\n"
        #   "## Logical Schema (Mermaid erDiagram)\n\n{logical}"
        # Splitting on "\n\n---\n\n" yields exactly 3 parts.
        parts = data_model_content.split("\n\n---\n\n")
        if len(parts) == 3:
            dimensional_model_specification = self._extract_section(parts[0])
            logical_schema = self._extract_section(parts[2])
        else:
            logger.warning(
                f"WriteDataModel message has unexpected structure ({len(parts)} parts, expected 3). "
                "Attempting to continue with full combined content as specification."
            )
            dimensional_model_specification = data_model_content
            logical_schema = ""

        # --- Call WriteExecutionPlan to produce the validated JSON plan ---
        write_execution_plan = WriteExecutionPlan()
        try:
            plan_json = await write_execution_plan.run(
                brd_content=brd_content,
                dimensional_model_specification=dimensional_model_specification,
                logical_schema=logical_schema,
            )
        except ValueError as exc:
            return (
                f"Error: The generated execution plan failed schema validation: {exc}\n\n"
                f"Please call BISolutionArchitect.generate_execution_plan() again to produce a corrected plan. "
                f"Use ONLY the exact field names: task_id, dependent_task_ids, instruction, task_type, tool, tool_args. "
                f"Every non-CREDENTIAL_REQUEST task must have a specific tool name."
            )

        # --- Save to file via Editor (writes to workspace/docs/ — DEV-27) ---
        plan_path = "docs/execution_plan.json"
        self.editor.write(path=plan_path, content=plan_json)

        # --- Publish so BIAnalyticsEngineer can observe and trigger on WriteExecutionPlan ---
        self.publish_message(Message(
            content=plan_json,
            cause_by=any_to_str(WriteExecutionPlan),
            sent_from=self.name,
        ))

        logger.info(f"Execution plan saved to workspace/{plan_path}")
        return (
            f"DWH Technical Execution Plan complete. Artifact saved:\n"
            f"  1. {plan_path}"
        )
