from __future__ import annotations

import asyncio
from pathlib import Path

from metagpt.actions import UserRequirement
from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.logs import logger
from metagpt.prompts.bi.bi_requirements_analyst import BI_REQUIREMENTS_ANALYST_INSTRUCTION
from metagpt.roles.di.role_zero import RoleZero
from metagpt.schema import Message
from metagpt.tools.tool_registry import register_tool
from metagpt.utils.common import any_to_name, any_to_str

# Import to ensure DataSourceInspector is registered in TOOL_REGISTRY before the
# BM25ToolRecommender validates the tools list on instantiation.
from metagpt.tools.bi.data_source_inspector import DataSourceInspector


@register_tool(include_functions=["generate_brd"])
class BIRequirementsAnalyst(RoleZero):
    """Agent 1: Conducts structured elicitation with the business user and produces the BRD.

    Operates in two sequential phases:
      Phase 1 — iterative elicitation dialogue using ask_human
      Phase 2 — BRD generation via generate_brd()
    """

    name: str = "Alice"
    profile: str = "BI Requirements Analyst"
    goal: str = (
        "Conduct a structured, iterative requirements elicitation dialogue with the business user, "
        "analyze the structure of available data sources and produce a complete, formal Business "
        "Requirement Document (BRD) that captures all information needed for the development of a "
        "Business Intelligence solution."
    )
    constraints: str = (
        "Always use the same language as the business user, during conversation and in the BRD. "
        "Never make assumptions about unstated requirements and metrics, but ask instead. "
        "Do not continue to BRD writing before all mandatory elicitation topics have been covered. "
        "The BRD must strictly follow the defined output format."
    )
    instruction: str = BI_REQUIREMENTS_ANALYST_INSTRUCTION
    tools: list[str] = ["RoleZero", "Editor", "DataSourceInspector", "BIRequirementsAnalyst"]
    todo_action: str = any_to_name(WriteBRD)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # RoleZero sets observe_all_msg_from_buffer=True which prevents the automatic
        # _watch([UserRequirement]) call in Role.__init__, so we call it explicitly here.
        self._watch([UserRequirement])

    async def _quick_think(self):
        # Elicitation is always a multi-turn structured task — never shortcut via QUICK/AMBIGUOUS.
        return None, "TASK"

    def _update_tool_execution(self):
        inspector = DataSourceInspector()
        self.tool_execution_map.update({
            "BIRequirementsAnalyst.generate_brd": self.generate_brd,
            "DataSourceInspector.inspect_csv": inspector.inspect_csv,
            "DataSourceInspector.inspect_excel": inspector.inspect_excel,
            "DataSourceInspector.inspect_duckdb": inspector.inspect_duckdb,
            "DataSourceInspector.inspect_postgres": inspector.inspect_postgres,
        })

    async def ask_human(self, question: str) -> str:
        """Send an elicitation question to the business user and wait for their response.

        Use this during Phase 1 requirements elicitation to ask the user about their BI needs.
        """
        # RoleZero.ask_human only works inside MGXEnv. Override to use stdin/stdout for terminal.
        print(f"\n[Alice - BI Requirements Analyst]: {question}\n")
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, input, "Your response: ")
        return response.strip()

    async def reply_to_human(self, content: str) -> str:
        """Reply to the business user with a message or status update."""
        # RoleZero.reply_to_human only works inside MGXEnv. Override for terminal output.
        print(f"\n[Alice - BI Requirements Analyst]: {content}\n")
        return content

    async def generate_brd(self, elicitation_history: str, schema_summaries: str) -> str:
        """Generate and save the Business Requirement Document from the completed elicitation.

        Call this method once all seven mandatory elicitation topics have been covered and the
        business user has provided sufficient information to write a complete BRD.

        Args:
            elicitation_history: Full elicitation conversation history between agent and user,
                including all questions asked and answers given across all turns.
            schema_summaries: Data source schema summaries from DataSourceInspector calls made
                during elicitation. Pass an empty string if no data sources were inspected.

        Returns:
            Confirmation message with the path where the BRD was saved.
        """
        write_brd = WriteBRD()
        brd_content = await write_brd.run(
            elicitation_history=elicitation_history,
            schema_summaries=schema_summaries,
        )

        brd_path = Path("docs") / "business_requirement_document.md"
        brd_path.parent.mkdir(parents=True, exist_ok=True)
        self.editor.write(path=str(brd_path), content=brd_content)

        # Publish with cause_by=WriteBRD so BIDataModeler observes and triggers next phase.
        self.publish_message(Message(
            content=brd_content,
            cause_by=any_to_str(WriteBRD),
            sent_from=self.name,
        ))

        logger.info(f"BRD generated and saved to {brd_path}")
        return f"BRD successfully generated and saved to {brd_path}."
