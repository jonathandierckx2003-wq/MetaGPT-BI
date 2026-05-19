from __future__ import annotations

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.config2 import Config
from metagpt.logs import logger
from metagpt.prompts.bi.bi_data_modeler import BI_DATA_MODELER_INSTRUCTION
from metagpt.roles.bi.bi_base_role import BIBaseRole
from metagpt.schema import Message
from metagpt.tools.tool_registry import register_tool
from metagpt.utils.common import any_to_name, any_to_str
from metagpt.utils.mermaid import mermaid_to_file


@register_tool(include_functions=["generate_data_model"])
class BIDataModeler(BIBaseRole):
    """Agent 2: Translates the BRD into a complete dimensional design for the DWH.

    Executes four sequential reasoning steps (analyze BRD → choose schema type →
    identify facts/dims/measures/hierarchies → call generate_data_model()) and
    produces three output artifacts: Dimensional Model Specification, Conceptual
    Schema (Mermaid erDiagram), and Logical Schema (Mermaid erDiagram).
    """

    name: str = "Bob"
    profile: str = "BI Data Modeler"
    goal: str = (
        "Translate the Business Requirement Document (BRD) produced by the BI Requirements Analyst "
        "into a complete dimensional design for the future Data Warehouse. This includes the choice of "
        "an appropriate dimensional schema type, the identification of all required facts, dimensions, "
        "measures and hierarchies and the production of a conceptual ER schema and a logical Relational "
        "schema for the envisioned DWH."
    )
    constraints: str = (
        "Always use the same language as the original BRD. Base all design decisions exclusively on "
        "the content of the published BRD. Never assume or invent requirements that are not stated. "
        "The chosen dimensional schema type must be explicitly justified using the decision criteria "
        "provided in the role instruction. The produced conceptual and logical schemas must strictly "
        "follow the Mermaid erDiagram syntax rules defined in the role instruction."
    )
    instruction: str = BI_DATA_MODELER_INSTRUCTION
    tools: list[str] = ["RoleZero", "Editor", "BIDataModeler"]
    todo_action: str = any_to_name(WriteDataModel)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # RoleZero sets observe_all_msg_from_buffer=True which prevents the automatic
        # _watch([UserRequirement]) call in Role.__init__, so we call it explicitly here (DEV-16).
        self._watch([WriteBRD])

    async def _quick_think(self):
        # Dimensional modeling is a structured multi-step task — never shortcut via QUICK/AMBIGUOUS.
        return None, "TASK"

    async def reply_to_human(self, content: str) -> str:
        """Reply to the business user with a status update or completion notice."""
        # RoleZero.reply_to_human only works inside MGXEnv. Override for terminal visibility (DEV-15).
        print(f"\n[Bob - BI Data Modeler]: {content}\n")
        return content

    def _update_tool_execution(self):
        self.tool_execution_map.update({
            "BIDataModeler.generate_data_model": self.generate_data_model,
        })

    async def _render_mermaid_schemas(self, conceptual_code: str, logical_code: str) -> None:
        """Render both Mermaid schemas to SVG inside workspace/docs/.

        Uses the Mermaid engine configured in config/config2.yaml (default: nodejs).
        Silently skips if the engine is set to 'none' or if the rendering tool is not available.
        The .mermaid text files are always saved regardless of whether rendering succeeds.
        """
        config = Config.default()
        if config.mermaid.engine == "none":
            return
        try:
            # DEV-72: use editor.working_dir so SVGs land in the per-run directory
            # (set by bi_team.py after DEV-71). Falls back to workspace/docs/ when
            # editor.working_dir is still DEFAULT_WORKSPACE_ROOT (single-agent tests).
            docs_dir = str(self.editor.working_dir / "docs")
            await mermaid_to_file(
                engine=config.mermaid.engine,
                mermaid_code=conceptual_code,
                output_file_without_suffix=f"{docs_dir}/conceptual_schema",
                suffixes=["svg"],
                config=config,
            )
            await mermaid_to_file(
                engine=config.mermaid.engine,
                mermaid_code=logical_code,
                output_file_without_suffix=f"{docs_dir}/logical_schema",
                suffixes=["svg"],
                config=config,
            )
            logger.info(f"Mermaid schemas rendered to SVG in {docs_dir}")
        except Exception as exc:
            logger.warning(
                f"Mermaid rendering skipped ({config.mermaid.engine} engine unavailable or failed): {exc}. "
                "Diagrams are still available as .mermaid text files."
            )

    async def generate_data_model(self) -> str:
        """Generate and save the three dimensional modeling artifacts from the BRD.

        Retrieves the BRD from the shared message pool memory, calls WriteDataModel to
        produce the Dimensional Model Specification, Conceptual Schema and Logical Schema,
        saves all three as separate files, and publishes a message to trigger the BI Solution
        Architect.

        Returns:
            Confirmation message listing the three artifact paths that were saved.
        """
        # Retrieve BRD content from the latest WriteBRD message in memory (DEV-28).
        # This avoids asking the LLM to copy the entire BRD text into a function argument,
        # which wastes tokens and risks truncation.
        brd_content = ""
        for msg in reversed(self.rc.memory.get()):
            if msg.cause_by == any_to_str(WriteBRD):
                brd_content = msg.content
                break

        if not brd_content:
            return "Error: No BRD found in memory. Cannot produce dimensional model without a BRD."

        write_data_model = WriteDataModel()
        artifacts = await write_data_model.run(brd_content=brd_content)

        spec_content = artifacts.get("dimensional_model_specification", "")
        conceptual_content = artifacts.get("conceptual_schema", "")
        logical_content = artifacts.get("logical_schema", "")

        if not spec_content:
            logger.warning("WriteDataModel returned empty dimensional_model_specification. Raw LLM output stored.")

        spec_path = "docs/dimensional_model_specification.md"
        conceptual_path = "docs/conceptual_schema.mermaid"
        logical_path = "docs/logical_schema.mermaid"

        self.editor.write(path=spec_path, content=spec_content)
        self.editor.write(path=conceptual_path, content=conceptual_content)
        self.editor.write(path=logical_path, content=logical_content)

        # Attempt to render the two Mermaid schemas to SVG for human readability.
        # Gracefully skip if no rendering engine is available (text files are always saved above).
        await self._render_mermaid_schemas(conceptual_content, logical_content)

        # Publish all three artifacts combined so BISolutionArchitect has them in memory
        # when it observes this WriteDataModel message.
        combined_content = (
            f"## Dimensional Model Specification\n\n{spec_content}\n\n"
            f"---\n\n"
            f"## Conceptual Schema (Mermaid erDiagram)\n\n{conceptual_content}\n\n"
            f"---\n\n"
            f"## Logical Schema (Mermaid erDiagram)\n\n{logical_content}"
        )
        self.publish_message(Message(
            content=combined_content,
            cause_by=any_to_str(WriteDataModel),
            sent_from=self.name,
        ))

        logger.info(
            f"Data model artifacts generated and saved: {spec_path}, {conceptual_path}, {logical_path}"
        )
        return (
            f"Dimensional modeling complete. Three artifacts saved:\n"
            f"  1. {spec_path}\n"
            f"  2. {conceptual_path}\n"
            f"  3. {logical_path}"
        )
