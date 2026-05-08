"""
Standalone smoke test for Session 8: BIQAEngineer (Agent 5).

Run from the repo root:
    python ClaudeCode_implementation/tests/test_session8_bi_qa_engineer.py

Does NOT make LLM calls. All external tool calls (DuckDBExecutor, SupabaseConnector,
WriteValidationReport, etc.) are mocked.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Stub out semantic_kernel before any metagpt import
# ---------------------------------------------------------------------------
def _stub_semantic_kernel():
    sk = types.ModuleType("semantic_kernel")
    sk.Kernel = object
    sk.__path__ = []
    sys.modules["semantic_kernel"] = sk
    for sub in [
        "semantic_kernel.orchestration",
        "semantic_kernel.orchestration.sk_function",
        "semantic_kernel.connectors",
        "semantic_kernel.connectors.ai",
        "semantic_kernel.connectors.ai.open_ai",
        "semantic_kernel.connectors.ai.open_ai.services",
        "semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion",
    ]:
        mod = types.ModuleType(sub)
        mod.__path__ = []
        sys.modules[sub] = mod
    orch_mod = sys.modules["semantic_kernel.orchestration"]
    orch_mod.sk_function = types.ModuleType("semantic_kernel.orchestration.sk_function")
    azure_mod = sys.modules["semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion"]
    azure_mod.AzureChatCompletion = object


_stub_semantic_kernel()

# ---------------------------------------------------------------------------
# Safe to import metagpt now
# ---------------------------------------------------------------------------
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.actions.bi.write_execution_report import WriteExecutionReport
from metagpt.actions.bi.write_validation_report import WriteValidationReport
from metagpt.roles.bi.bi_qa_engineer import BIQAEngineer
from metagpt.roles.di.role_zero import RoleZero
from metagpt.schema import Message
from metagpt.tools.tool_registry import TOOL_REGISTRY
from metagpt.utils.common import any_to_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inject_memory(agent: BIQAEngineer, cause_by_class, content: str):
    """Push a fake message into the agent's memory buffer."""
    msg = Message(content=content, cause_by=any_to_str(cause_by_class))
    agent.rc.memory.add(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBIQAEngineerInstantiation(unittest.TestCase):

    def setUp(self):
        self.agent = BIQAEngineer()

    def test_name_and_profile(self):
        self.assertEqual(self.agent.name, "Edward")
        self.assertEqual(self.agent.profile, "BI QA Engineer")

    def test_goal_references_brd_validation(self):
        self.assertIn("BRD", self.agent.goal)

    def test_todo_action_is_write_validation_report(self):
        self.assertEqual(self.agent.todo_action, "WriteValidationReport")

    def test_tools_list(self):
        expected = {"RoleZero", "Editor", "BIQAEngineer", "DuckDBExecutor", "SupabaseConnector"}
        self.assertEqual(set(self.agent.tools), expected)

    def test_max_react_loop(self):
        self.assertEqual(self.agent.max_react_loop, 50)

    def test_validation_round_allowed_default(self):
        self.assertEqual(self.agent.validation_round_allowed, 3)

    def test_validation_round_allowed_configurable(self):
        agent = BIQAEngineer(validation_round_allowed=5)
        self.assertEqual(agent.validation_round_allowed, 5)

    def test_initial_validation_round_is_zero(self):
        self.assertEqual(self.agent._validation_round, 0)

    def test_watches_write_execution_report(self):
        self.assertIn(any_to_str(WriteExecutionReport), self.agent.rc.watch)

    def test_does_not_watch_write_execution_plan(self):
        # DEV-61: only WriteExecutionReport triggers Edward; plan is in memory via observe_all
        self.assertNotIn(any_to_str(WriteExecutionPlan), self.agent.rc.watch)

    def test_instruction_contains_generate_validation_report(self):
        self.assertIn("BIQAEngineer.generate_validation_report", self.agent.instruction)

    def test_instruction_contains_mandatory_guard(self):
        self.assertIn("MANDATORY", self.agent.instruction)

    def test_tool_execution_map_has_generate_validation_report(self):
        self.assertIn("BIQAEngineer.generate_validation_report", self.agent.tool_execution_map)

    def test_tool_execution_map_has_duckdb_methods(self):
        expected = {
            "DuckDBExecutor.connect",
            "DuckDBExecutor.run_query",
            "DuckDBExecutor.verify_table",
            "DuckDBExecutor.list_tables",
            "DuckDBExecutor.get_table_schema",
            "DuckDBExecutor.check_pk_uniqueness",
            "DuckDBExecutor.check_fk_integrity",
        }
        for key in expected:
            self.assertIn(key, self.agent.tool_execution_map, f"Missing key: {key}")

    def test_tool_execution_map_has_supabase_methods(self):
        expected = {
            "SupabaseConnector.connect",
            "SupabaseConnector.run_query",
            "SupabaseConnector.verify_table",
            "SupabaseConnector.list_tables",
            "SupabaseConnector.get_table_schema",
            "SupabaseConnector.check_pk_uniqueness",
            "SupabaseConnector.check_fk_integrity",
        }
        for key in expected:
            self.assertIn(key, self.agent.tool_execution_map, f"Missing key: {key}")


class TestToolRegistration(unittest.TestCase):

    def test_bi_qa_engineer_in_tool_registry(self):
        self.assertTrue(TOOL_REGISTRY.has_tool("BIQAEngineer"))

    def test_generate_validation_report_schema_has_structural_results_parameter(self):
        tool = TOOL_REGISTRY.get_tool("BIQAEngineer")
        self.assertIsNotNone(tool)
        methods = tool.schemas.get("methods", {})
        schema = methods.get("generate_validation_report")
        self.assertIsNotNone(schema, "generate_validation_report must appear in schemas")
        self.assertIn("structural_validation_results", str(schema))

    def test_generate_validation_report_schema_has_traceability_results_parameter(self):
        tool = TOOL_REGISTRY.get_tool("BIQAEngineer")
        methods = tool.schemas.get("methods", {})
        schema = methods.get("generate_validation_report")
        self.assertIsNotNone(schema)
        self.assertIn("traceability_validation_results", str(schema))

    def test_generate_validation_report_schema_does_not_expose_large_doc_params(self):
        # DEV-28/DEV-59: large reference artifacts must NOT be exposed as LLM-callable parameters
        tool = TOOL_REGISTRY.get_tool("BIQAEngineer")
        methods = tool.schemas.get("methods", {})
        schema = methods.get("generate_validation_report")
        schema_str = str(schema)
        self.assertNotIn("brd_summary", schema_str)
        self.assertNotIn("logical_schema", schema_str)
        self.assertNotIn("execution_plan", schema_str)
        self.assertNotIn("dwh_connection_details", schema_str)


class TestGenerateValidationReport(unittest.IsolatedAsyncioTestCase):

    def _make_agent_with_memory(self) -> BIQAEngineer:
        agent = BIQAEngineer()
        _inject_memory(agent, WriteExecutionReport, "## Execution Report\n\n## Getting Started\nDuckDB: workspace/dwh.duckdb\n\n## Final Status\n\nCOMPLETE")
        _inject_memory(agent, WriteExecutionPlan, '[{"task_id": "1"}]')
        from metagpt.actions.bi.write_brd import WriteBRD
        from metagpt.actions.bi.write_data_model import WriteDataModel
        _inject_memory(agent, WriteBRD, "# BRD\n\n## 4. Queries\nQ1")
        _inject_memory(agent, WriteDataModel, "## Dimensional Model Specification\n\nSpec\n\n---\n\n## Conceptual Schema\n\nConc\n\n---\n\n## Logical Schema\n\nLogical")
        return agent

    async def test_accepted_outcome_saves_to_standard_path(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()
        published = []

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="# Validation Feedback Report\n\nACCEPTED"):
            with patch.object(agent, "publish_message", side_effect=published.append):
                result = await agent.generate_validation_report(
                    "All checks PASS", "All queries SUPPORTED"
                )

        self.assertIn("ACCEPTED", result)
        self.assertIn("validation_feedback_report.md", result)

    async def test_accepted_outcome_publishes_message(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()
        published = []

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="ACCEPTED"):
            with patch.object(agent, "publish_message", side_effect=published.append):
                await agent.generate_validation_report("PASS", "SUPPORTED")

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].cause_by, any_to_str(WriteValidationReport))

    async def test_accepted_message_sent_from_edward(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()
        published = []

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="ACCEPTED"):
            with patch.object(agent, "publish_message", side_effect=published.append):
                await agent.generate_validation_report("PASS", "SUPPORTED")

        self.assertEqual(published[0].sent_from, "Edward")

    async def test_rejected_below_max_rounds_publishes_message(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()
        published = []

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="REJECTED\n\nSome tables are missing."):
            with patch.object(agent, "publish_message", side_effect=published.append):
                result = await agent.generate_validation_report("FAIL on dim_date", "UNSUPPORTED")

        self.assertEqual(len(published), 1)
        self.assertIn("REJECTED", result)
        self.assertIn("validation_feedback_report.md", result)

    async def test_rejected_increments_validation_round(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="REJECTED"):
            with patch.object(agent, "publish_message"):
                await agent.generate_validation_report("FAIL", "UNSUPPORTED")

        self.assertEqual(agent._validation_round, 1)

    async def test_exhausted_rounds_saves_to_failed_path(self):
        agent = self._make_agent_with_memory()
        agent.editor = MagicMock()
        agent.validation_round_allowed = 2
        agent._validation_round = 1  # Already used 1 round; this call is round 2

        published = []

        with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                   new_callable=AsyncMock, return_value="REJECTED\n\nPersisting issues."):
            with patch.object(agent, "publish_message", side_effect=published.append):
                result = await agent.generate_validation_report("FAIL", "UNSUPPORTED")

        # Must save to failed path
        write_calls = agent.editor.write.call_args_list
        paths_written = [c.kwargs.get("path", "") for c in write_calls]
        self.assertTrue(any("failed_validation_report" in p for p in paths_written),
                        f"Expected failed path, got: {paths_written}")
        # Must NOT publish (so Analytics Engineer is not re-triggered)
        self.assertEqual(len(published), 0, "Failed report must not be published")
        self.assertIn("exhausted", result.lower())

    async def test_error_when_no_execution_report_in_memory(self):
        agent = BIQAEngineer()
        from metagpt.actions.bi.write_brd import WriteBRD
        # BRD present so that check passes; execution report absent — that must be the error
        _inject_memory(agent, WriteBRD, "BRD content")
        result = await agent.generate_validation_report("PASS", "SUPPORTED")
        self.assertIn("Error", result)
        self.assertIn("Execution Report", result)

    async def test_error_when_no_brd_in_memory(self):
        agent = BIQAEngineer()
        _inject_memory(agent, WriteExecutionReport, "Report content with ## Getting Started section")
        result = await agent.generate_validation_report("PASS", "SUPPORTED")
        self.assertIn("Error", result)
        self.assertIn("BRD", result)


class TestExtractHelpers(unittest.TestCase):

    def test_extract_logical_schema_from_combined_message(self):
        combined = (
            "## Dimensional Model Specification\n\nSpec content\n\n---\n\n"
            "## Conceptual Schema (Mermaid erDiagram)\n\nConceptual content\n\n---\n\n"
            "## Logical Schema (Mermaid erDiagram)\n\nLogical content here"
        )
        result = BIQAEngineer._extract_logical_schema(combined)
        self.assertEqual(result, "Logical content here")

    def test_extract_logical_schema_malformed_returns_full_content(self):
        content = "Single block with no separators"
        result = BIQAEngineer._extract_logical_schema(content)
        self.assertEqual(result, content)

    def test_extract_logical_schema_empty_returns_empty(self):
        self.assertEqual(BIQAEngineer._extract_logical_schema(""), "")

    def test_extract_connection_details_finds_getting_started_section(self):
        report = (
            "# Execution Report\n\n## Execution Summary\n\nTasks done.\n\n"
            "## Getting Started — Accessing Your DWH\n\nDuckDB path: workspace/dwh.duckdb\n\n"
            "## Final Status\n\nCOMPLETE"
        )
        result = BIQAEngineer._extract_connection_details(report)
        self.assertTrue(result.startswith("## Getting Started"))
        self.assertIn("workspace/dwh.duckdb", result)

    def test_extract_connection_details_fallback_returns_full_report(self):
        report = "Report with no Getting Started section"
        result = BIQAEngineer._extract_connection_details(report)
        self.assertEqual(result, report)

    def test_extract_connection_details_empty_returns_empty(self):
        self.assertEqual(BIQAEngineer._extract_connection_details(""), "")


class TestDWHLazyInit(unittest.TestCase):

    def test_get_duckdb_executor_returns_same_instance(self):
        agent = BIQAEngineer()
        exec1 = agent._get_duckdb_executor()
        exec2 = agent._get_duckdb_executor()
        self.assertIs(exec1, exec2)

    def test_get_supabase_connector_returns_same_instance(self):
        agent = BIQAEngineer()
        conn1 = agent._get_supabase_connector()
        conn2 = agent._get_supabase_connector()
        self.assertIs(conn1, conn2)


class TestValidationRoundTracking(unittest.TestCase):

    def test_multiple_rejected_calls_increment_round_counter(self):
        import asyncio
        agent = BIQAEngineer()
        agent.editor = MagicMock()
        _inject_memory(agent, WriteExecutionReport, "## Getting Started\nDuckDB\n## Final Status\nCOMPLETE")
        from metagpt.actions.bi.write_brd import WriteBRD
        _inject_memory(agent, WriteBRD, "BRD content")

        async def run_rejected():
            with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                       new_callable=AsyncMock, return_value="REJECTED"):
                with patch.object(agent, "publish_message"):
                    await agent.generate_validation_report("FAIL", "UNSUPPORTED")

        asyncio.run(run_rejected())
        self.assertEqual(agent._validation_round, 1)
        asyncio.run(run_rejected())
        self.assertEqual(agent._validation_round, 2)

    def test_accepted_call_still_increments_round_counter(self):
        import asyncio
        agent = BIQAEngineer()
        agent.editor = MagicMock()
        _inject_memory(agent, WriteExecutionReport, "## Getting Started\nDuckDB\n## Final Status\nCOMPLETE")
        from metagpt.actions.bi.write_brd import WriteBRD
        _inject_memory(agent, WriteBRD, "BRD content")

        async def run_accepted():
            with patch("metagpt.actions.bi.write_validation_report.WriteValidationReport.run",
                       new_callable=AsyncMock, return_value="ACCEPTED"):
                with patch.object(agent, "publish_message"):
                    await agent.generate_validation_report("PASS", "SUPPORTED")

        asyncio.run(run_accepted())
        self.assertEqual(agent._validation_round, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBIQAEngineerInstantiation))
    suite.addTests(loader.loadTestsFromTestCase(TestToolRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestGenerateValidationReport))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractHelpers))
    suite.addTests(loader.loadTestsFromTestCase(TestDWHLazyInit))
    suite.addTests(loader.loadTestsFromTestCase(TestValidationRoundTracking))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
