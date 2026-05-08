from __future__ import annotations

from pathlib import Path

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.actions.bi.write_execution_report import WriteExecutionReport
from metagpt.actions.bi.write_validation_report import WriteValidationReport
from metagpt.logs import logger
from metagpt.prompts.bi.bi_qa_engineer import BI_QA_ENGINEER_INSTRUCTION
from metagpt.roles.di.role_zero import RoleZero
from metagpt.schema import Message
from metagpt.tools.bi.duckdb_executor import DuckDBExecutor
from metagpt.tools.bi.supabase_connector import SupabaseConnector
from metagpt.tools.tool_registry import register_tool
from metagpt.utils.common import any_to_name, any_to_str


@register_tool(include_functions=["generate_validation_report"])
class BIQAEngineer(RoleZero):
    """Agent 5: Validates the DWH against the BRD and dimensional design artifacts.

    Executes two sequential validation phases (structural/technical checks + requirements
    traceability checks), then calls generate_validation_report() to produce, save and
    publish a Validation Feedback Report. Triggers the BI Analytics Engineer for correction
    if the DWH is REJECTED; stops (saving to failed_validation_report.md) if
    validation_round_allowed rounds are exhausted.
    """

    name: str = "Edward"
    profile: str = "BI QA Engineer"
    goal: str = (
        "Validate the produced DWH against the BRD by running structural integrity checks "
        "and requirements traceability checks, and produce a Validation Feedback Report that "
        "either confirms acceptance and delivers DWH connection instructions to the human user, "
        "or details all issues for the BI Analytics Engineer to address."
    )
    constraints: str = (
        "Base all validation checks exclusively on the BRD and on the dimensional design "
        "artifacts published in the shared message pool. Never modify the DWH, the Execution "
        "Plan or any other previously produced artifact. Only run read-only queries against "
        "the DWH. Always produce a complete Validation Feedback Report."
    )
    instruction: str = BI_QA_ENGINEER_INSTRUCTION
    tools: list[str] = ["RoleZero", "Editor", "BIQAEngineer", "DuckDBExecutor", "SupabaseConnector"]
    todo_action: str = any_to_name(WriteValidationReport)
    max_react_loop: int = 50
    # Configurable max correction rounds; defaults to 3. Override via BIQAEngineer(validation_round_allowed=N).
    validation_round_allowed: int = 3

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # DEV-16: explicit _watch required because RoleZero sets observe_all_msg_from_buffer=True
        self._watch([WriteExecutionReport])
        # Validation round counter — incremented each time generate_validation_report() is called
        self._validation_round: int = 0
        # _duckdb_executor and _supabase_connector are created lazily by getter methods (DEV-40)

    async def _quick_think(self):
        # Full validation task — never shortcut via QUICK/AMBIGUOUS (DEV-22).
        return None, "TASK"

    async def reply_to_human(self, content: str) -> str:
        """Print status update to terminal (DEV-32 pattern)."""
        # RoleZero.reply_to_human only works inside MGXEnv. Override for terminal visibility.
        print(f"\n[Edward - BI QA Engineer]: {content}\n")
        return content

    def _update_tool_execution(self):
        # DEV-21: TOOL_REGISTRY provides schemas for the LLM recommender; actual callables
        # must be wired into tool_execution_map for the RoleZero dispatcher to find them.
        executor = self._get_duckdb_executor()
        supabase = self._get_supabase_connector()
        self.tool_execution_map.update({
            "BIQAEngineer.generate_validation_report": self.generate_validation_report,
            # DuckDBExecutor read-only methods for structural + traceability validation
            "DuckDBExecutor.connect": executor.connect,
            "DuckDBExecutor.run_query": executor.run_query,
            "DuckDBExecutor.verify_table": executor.verify_table,
            "DuckDBExecutor.list_tables": executor.list_tables,
            "DuckDBExecutor.get_table_schema": executor.get_table_schema,
            "DuckDBExecutor.check_pk_uniqueness": executor.check_pk_uniqueness,
            "DuckDBExecutor.check_fk_integrity": executor.check_fk_integrity,
            # SupabaseConnector read-only methods (same surface area)
            "SupabaseConnector.connect": supabase.connect,
            "SupabaseConnector.run_query": supabase.run_query,
            "SupabaseConnector.verify_table": supabase.verify_table,
            "SupabaseConnector.list_tables": supabase.list_tables,
            "SupabaseConnector.get_table_schema": supabase.get_table_schema,
            "SupabaseConnector.check_pk_uniqueness": supabase.check_pk_uniqueness,
            "SupabaseConnector.check_fk_integrity": supabase.check_fk_integrity,
        })

    # ------------------------------------------------------------------
    # Lazy-init helpers (DEV-40: getattr guard handles Pydantic model_validator timing)
    # ------------------------------------------------------------------

    def _get_duckdb_executor(self) -> DuckDBExecutor:
        if getattr(self, "_duckdb_executor", None) is None:
            self._duckdb_executor = DuckDBExecutor()
        return self._duckdb_executor

    def _get_supabase_connector(self) -> SupabaseConnector:
        if getattr(self, "_supabase_connector", None) is None:
            self._supabase_connector = SupabaseConnector()
        return self._supabase_connector

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _get_from_memory(self, action_class) -> str:
        """Return content of the most recent message of the given action type from memory."""
        action_str = any_to_str(action_class)
        for msg in reversed(self.rc.memory.get()):
            if msg.cause_by == action_str:
                return msg.content
        return ""

    @staticmethod
    def _extract_logical_schema(data_model_content: str) -> str:
        """Extract the logical schema section from the WriteDataModel combined message.

        BIDataModeler.generate_data_model() publishes:
        '## Dimensional Model Specification\\n\\n{spec}\\n\\n---\\n\\n'
        '## Conceptual Schema...\\n\\n{conceptual}\\n\\n---\\n\\n'
        '## Logical Schema...\\n\\n{logical}'
        The third split part (index 2) is the logical schema.
        """
        if not data_model_content:
            return ""
        parts = data_model_content.split("\n\n---\n\n")
        if len(parts) == 3:
            part = parts[2]
            idx = part.find("\n\n")
            return part[idx + 2:] if idx != -1 else part
        return data_model_content

    @staticmethod
    def _extract_connection_details(execution_report: str) -> str:
        """Extract the 'Getting Started — Accessing Your DWH' section from the Execution Report."""
        if not execution_report:
            return ""
        marker = "## Getting Started"
        idx = execution_report.find(marker)
        if idx != -1:
            return execution_report[idx:]
        return execution_report

    # ------------------------------------------------------------------
    # Primary @register_tool method
    # ------------------------------------------------------------------

    async def generate_validation_report(
        self,
        structural_validation_results: str,
        traceability_validation_results: str,
    ) -> str:
        """Generate, save and publish the Validation Feedback Report.

        Retrieves BRD, logical schema, execution plan and DWH connection details
        from the shared message pool memory (DEV-28 pattern — no large documents
        passed as arguments). Calls WriteValidationReport to produce the report
        content, saves it to disk via Editor, and publishes it.

        If the outcome is REJECTED and validation_round_allowed rounds are
        exhausted, saves to docs/failed_validation_report.md WITHOUT publishing,
        so the BI Analytics Engineer is not re-triggered.

        Args:
            structural_validation_results: Summary of Phase 1 checks (PASS/FAIL per table).
            traceability_validation_results: Summary of Phase 2 checks (queries, KPIs, sources).

        Returns:
            Confirmation message with outcome and artifact path.
        """
        # --- Retrieve reference artifacts from memory (DEV-28 pattern) ---
        brd_content = self._get_from_memory(WriteBRD)
        data_model_content = self._get_from_memory(WriteDataModel)
        execution_plan = self._get_from_memory(WriteExecutionPlan)
        execution_report = self._get_from_memory(WriteExecutionReport)

        if not brd_content:
            return "Error: No BRD found in memory. Cannot produce Validation Feedback Report."
        if not execution_report:
            return "Error: No Execution Report found in memory. Cannot produce Validation Feedback Report."

        logical_schema = self._extract_logical_schema(data_model_content)
        dwh_connection_details = self._extract_connection_details(execution_report)

        # --- Call WriteValidationReport to produce the report content ---
        write_report = WriteValidationReport()
        report_content = await write_report.run(
            structural_validation_results=structural_validation_results,
            traceability_validation_results=traceability_validation_results,
            brd_summary=brd_content,
            logical_schema=logical_schema,
            execution_plan=execution_plan,
            dwh_connection_details=dwh_connection_details,
        )

        # --- Determine overall outcome from report text ---
        # Check for REJECTED first (a REJECTED report may still contain the word ACCEPTED
        # in the summary section describing what was accepted — so order matters).
        is_rejected = "REJECTED" in report_content
        is_accepted = not is_rejected and "ACCEPTED" in report_content

        # --- Increment validation round counter ---
        self._validation_round += 1

        # --- Handle exhausted-rounds case: save to failed path, do NOT publish ---
        if is_rejected and self._validation_round >= self.validation_round_allowed:
            save_path = "docs/failed_validation_report.md"
            self.editor.write(path=save_path, content=report_content)
            logger.info(
                f"Validation REJECTED after {self._validation_round} round(s). "
                f"Maximum rounds ({self.validation_round_allowed}) reached. "
                f"Saved to workspace/{save_path} — NOT published (Analytics Engineer will not be re-triggered)."
            )
            return (
                f"Validation Feedback Report written to workspace/{save_path}.\n"
                f"Outcome: REJECTED. Maximum validation rounds ({self.validation_round_allowed}) exhausted.\n"
                f"The report highlights persisting issues for human review. The pipeline stops here."
            )

        # --- Standard path: save and publish ---
        save_path = "docs/validation_feedback_report.md"
        self.editor.write(path=save_path, content=report_content)

        # Publish so BIAnalyticsEngineer observes (on REJECTED) or workflow completes (on ACCEPTED)
        self.publish_message(Message(
            content=report_content,
            cause_by=any_to_str(WriteValidationReport),
            sent_from=self.name,
        ))

        outcome = "ACCEPTED" if is_accepted else "REJECTED"
        logger.info(f"Validation Feedback Report saved to workspace/{save_path} (outcome: {outcome})")
        return (
            f"Validation Feedback Report complete (outcome: {outcome}). "
            f"Saved to workspace/{save_path} and published to the shared message pool."
        )
