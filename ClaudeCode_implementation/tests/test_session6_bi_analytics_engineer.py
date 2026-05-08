"""
Standalone smoke test for Session 6: BIAnalyticsEngineer (Agent 4).

Run from the repo root:
    python ClaudeCode_implementation/tests/test_session6_bi_analytics_engineer.py

Does NOT make LLM calls. All external tool calls (DuckDBExecutor, PandasLoader,
DbtRunner, etc.) are mocked.
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
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer
from metagpt.roles.di.role_zero import RoleZero
from metagpt.tools.tool_registry import TOOL_REGISTRY
from metagpt.utils.common import any_to_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id, task_type, tool, tool_args, deps=None):
    return {
        "task_id": str(task_id),
        "task_type": task_type,
        "tool": tool,
        "tool_args": tool_args,
        "instruction": f"Test task {task_id}",
        "dependent_task_ids": deps or [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBIAnalyticsEngineerInstantiation(unittest.TestCase):

    def setUp(self):
        self.agent = BIAnalyticsEngineer()

    def test_name_and_profile(self):
        self.assertEqual(self.agent.name, "Alex")
        self.assertEqual(self.agent.profile, "BI Analytics Engineer")

    def test_goal_references_execution_plan(self):
        self.assertIn("Execution Plan", self.agent.goal)

    def test_todo_action_is_write_execution_report(self):
        self.assertEqual(self.agent.todo_action, "WriteExecutionReport")

    def test_tools_list(self):
        expected = {"RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner"}
        self.assertEqual(set(self.agent.tools), expected)

    def test_max_react_loop(self):
        self.assertEqual(self.agent.max_react_loop, 50)

    def test_watches_write_execution_plan(self):
        self.assertIn(any_to_str(WriteExecutionPlan), self.agent.rc.watch)

    def test_watches_write_validation_report(self):
        self.assertIn(any_to_str(WriteValidationReport), self.agent.rc.watch)

    def test_instruction_contains_execute_bi_task(self):
        self.assertIn("BIAnalyticsEngineer.execute_BI_task", self.agent.instruction)

    def test_instruction_contains_publish_execution_report(self):
        self.assertIn("BIAnalyticsEngineer.publish_execution_report", self.agent.instruction)

    def test_instruction_contains_mandatory_guard(self):
        self.assertIn("MANDATORY", self.agent.instruction)

    def test_tool_execution_map_has_execute_bi_task(self):
        self.assertIn("BIAnalyticsEngineer.execute_BI_task", self.agent.tool_execution_map)

    def test_tool_execution_map_has_publish_execution_report(self):
        self.assertIn("BIAnalyticsEngineer.publish_execution_report", self.agent.tool_execution_map)

    def test_tool_execution_map_has_dbt_runner_methods(self):
        # DEV-44: init_project and attach_project removed — auto-init handles them
        expected_dbt_keys = {
            "DbtRunner.write_model",
            "DbtRunner.run_model",
            "DbtRunner.run_tests",
            "DbtRunner.configure_profile",
        }
        for key in expected_dbt_keys:
            self.assertIn(key, self.agent.tool_execution_map, f"Missing key: {key}")
        self.assertNotIn("DbtRunner.init_project", self.agent.tool_execution_map)
        self.assertNotIn("DbtRunner.attach_project", self.agent.tool_execution_map)


class TestToolRegistration(unittest.TestCase):

    def test_bi_analytics_engineer_in_tool_registry(self):
        self.assertTrue(TOOL_REGISTRY.has_tool("BIAnalyticsEngineer"))

    def test_execute_bi_task_schema_has_task_parameter(self):
        tool = TOOL_REGISTRY.get_tool("BIAnalyticsEngineer")
        self.assertIsNotNone(tool)
        methods = tool.schemas.get("methods", {})
        schema = methods.get("execute_BI_task")
        self.assertIsNotNone(schema, f"execute_BI_task must appear in schemas. Got: {list(methods.keys())}")
        self.assertIn("task", str(schema))

    def test_publish_execution_report_schema_has_no_required_parameters(self):
        tool = TOOL_REGISTRY.get_tool("BIAnalyticsEngineer")
        self.assertIsNotNone(tool)
        methods = tool.schemas.get("methods", {})
        schema = methods.get("publish_execution_report")
        self.assertIsNotNone(schema, "publish_execution_report must appear in schemas")
        # No large document parameters should be exposed (DEV-28 pattern)
        # Note: "execution_report" appears in the method name itself, so only check
        # that no parameter named report_content or report_path is exposed
        schema_str = str(schema)
        self.assertNotIn("report_content", schema_str)
        self.assertNotIn("report_path", schema_str)


class TestExecuteBITask(unittest.IsolatedAsyncioTestCase):

    async def test_instantiation_routes_to_duckdb_connect(self):
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor.connect.return_value = "Connected to DuckDB at 'workspace/dwh.duckdb'."
        agent._duckdb_executor = mock_executor

        task = _make_task("1", "INSTANTIATION", "DuckDBExecutor", {"db_path": "workspace/dwh.duckdb"})
        result = await agent.execute_BI_task(task)

        mock_executor.connect.assert_called_once_with("workspace/dwh.duckdb")
        self.assertIn("COMPLETE", result)
        self.assertIn("1", result)

    async def test_schema_creation_runs_ddl(self):
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor._conn = MagicMock()  # already connected
        mock_executor.run_ddl.return_value = "DDL executed."
        agent._duckdb_executor = mock_executor

        task = _make_task("2", "SCHEMA_CREATION", "DuckDBExecutor", {
            "db_path": "workspace/dwh.duckdb",
            "ddl": "CREATE TABLE foo (id INT);",
        })
        result = await agent.execute_BI_task(task)

        mock_executor.run_ddl.assert_called_once_with("CREATE TABLE foo (id INT);")
        self.assertIn("COMPLETE", result)

    async def test_schema_creation_ddl_as_list_is_joined(self):
        """DEV-37: ddl arriving as a JSON array must be joined into a single string."""
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor._conn = MagicMock()
        mock_executor.run_ddl.return_value = "DDL executed."
        agent._duckdb_executor = mock_executor

        ddl_list = [
            "CREATE TABLE dim_date (date_key INT PRIMARY KEY);",
            "CREATE TABLE dim_product (product_key INT PRIMARY KEY);",
        ]
        task = _make_task("2", "SCHEMA_CREATION", "DuckDBExecutor", {
            "db_path": "workspace/dwh.duckdb",
            "ddl": ddl_list,
        })
        await agent.execute_BI_task(task)

        call_args = mock_executor.run_ddl.call_args
        ddl_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("ddl", "")
        # Must be a string, not a list
        self.assertIsInstance(ddl_arg, str, "run_ddl must receive a string, not a list")
        # Must contain both DDL statements
        self.assertIn("dim_date", ddl_arg)
        self.assertIn("dim_product", ddl_arg)
        # Must not contain list representation characters
        self.assertNotIn("[", ddl_arg)

    async def test_data_ingestion_routes_to_pandas_loader(self):
        agent = BIAnalyticsEngineer()
        with patch("metagpt.roles.bi.bi_analytics_engineer.PandasLoader") as MockLoader:
            mock_instance = MagicMock()
            mock_instance.load_file.return_value = "Loaded 500 rows into staging_interaction_raw."
            MockLoader.return_value = mock_instance

            task = _make_task("3", "DATA_INGESTION", "PandasLoader", {
                "file_path": "ClaudeCode_implementation/test_data/E-commerece sales data 2024.csv",
                "target_table": "staging_interaction_raw",
                "db_path": "workspace/dwh.duckdb",
            })
            result = await agent.execute_BI_task(task)

        mock_instance.load_file.assert_called_once_with(
            file_path="ClaudeCode_implementation/test_data/E-commerece sales data 2024.csv",
            target_table="staging_interaction_raw",
            db_path="workspace/dwh.duckdb",
        )
        self.assertIn("COMPLETE", result)

    async def test_credential_request_returns_redirect_without_dispatch(self):
        agent = BIAnalyticsEngineer()
        task = _make_task("99", "CREDENTIAL_REQUEST", None, None)
        result = await agent.execute_BI_task(task)

        # Should return the redirect message, not crash or dispatch to a tool
        self.assertIn("ask_human", result)
        self.assertIn("COMPLETE", result)  # it completes (the redirect is the result)
        self.assertIn("99", agent._completed_task_ids)

    async def test_unknown_tool_returns_error_string(self):
        agent = BIAnalyticsEngineer()
        task = _make_task("5", "INSTANTIATION", "UnknownTool", {"db_path": "x"})
        result = await agent.execute_BI_task(task)

        self.assertIn("Unknown tool", result)
        self.assertIn("COMPLETE", result)  # the dispatch result is returned as a COMPLETE (not FAILED)

    async def test_successful_task_added_to_completed_ids(self):
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor.connect.return_value = "Connected."
        agent._duckdb_executor = mock_executor

        task = _make_task("1", "INSTANTIATION", "DuckDBExecutor", {"db_path": "workspace/dwh.duckdb"})
        await agent.execute_BI_task(task)

        self.assertIn("1", agent._completed_task_ids)
        self.assertNotIn("1", agent._failed_task_ids)

    async def test_failed_task_added_to_failed_ids(self):
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor.connect.side_effect = RuntimeError("disk full")
        agent._duckdb_executor = mock_executor

        task = _make_task("1", "INSTANTIATION", "DuckDBExecutor", {"db_path": "workspace/dwh.duckdb"})
        result = await agent.execute_BI_task(task)

        self.assertIn("1", agent._failed_task_ids)
        self.assertNotIn("1", agent._completed_task_ids)
        self.assertIn("FAILED", result)

    async def test_active_task_id_cleared_after_execution(self):
        agent = BIAnalyticsEngineer()
        mock_executor = MagicMock()
        mock_executor.connect.return_value = "Connected."
        agent._duckdb_executor = mock_executor

        task = _make_task("1", "INSTANTIATION", "DuckDBExecutor", {"db_path": "workspace/dwh.duckdb"})
        await agent.execute_BI_task(task)

        self.assertEqual(agent._active_task_id, "")


class TestPublishExecutionReport(unittest.IsolatedAsyncioTestCase):

    async def test_error_when_report_file_not_found(self):
        agent = BIAnalyticsEngineer()
        with patch.object(Path, "exists", return_value=False):
            result = await agent.publish_execution_report()
        self.assertIn("Error", result)
        self.assertIn("execution_report.md", result)

    async def test_publishes_message_with_write_execution_report_cause_by(self):
        agent = BIAnalyticsEngineer()
        fake_content = "# Execution Report\n\nAll tasks complete."
        published = []

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=fake_content):
                with patch.object(agent, "publish_message", side_effect=published.append):
                    await agent.publish_execution_report()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].cause_by, any_to_str(WriteExecutionReport))

    async def test_published_message_sent_from_alex(self):
        agent = BIAnalyticsEngineer()
        fake_content = "# Execution Report\n\nAll tasks complete."
        published = []

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=fake_content):
                with patch.object(agent, "publish_message", side_effect=published.append):
                    await agent.publish_execution_report()

        self.assertEqual(published[0].sent_from, "Alex")


class TestStateInjection(unittest.IsolatedAsyncioTestCase):

    async def test_think_injects_completed_and_active_task_ids(self):
        agent = BIAnalyticsEngineer()
        agent._completed_task_ids = ["1", "2", "3"]
        agent._active_task_id = "4"
        agent._failed_task_ids = []

        with patch.object(RoleZero, "_think", new_callable=AsyncMock, return_value=True):
            await agent._think()

        state = agent.cmd_prompt_current_state
        self.assertIn("1", state)
        self.assertIn("2", state)
        self.assertIn("3", state)
        self.assertIn("4", state)

    async def test_think_shows_none_when_no_tasks_completed(self):
        agent = BIAnalyticsEngineer()

        with patch.object(RoleZero, "_think", new_callable=AsyncMock, return_value=True):
            await agent._think()

        state = agent.cmd_prompt_current_state
        self.assertIn("none", state)


class TestDbtRunnerLazyInit(unittest.TestCase):

    def test_get_dbt_runner_returns_same_instance(self):
        agent = BIAnalyticsEngineer()
        runner1 = agent._get_dbt_runner()
        runner2 = agent._get_dbt_runner()
        self.assertIs(runner1, runner2)

    def test_get_duckdb_executor_returns_same_instance(self):
        agent = BIAnalyticsEngineer()
        exec1 = agent._get_duckdb_executor()
        exec2 = agent._get_duckdb_executor()
        self.assertIs(exec1, exec2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBIAnalyticsEngineerInstantiation))
    suite.addTests(loader.loadTestsFromTestCase(TestToolRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestExecuteBITask))
    suite.addTests(loader.loadTestsFromTestCase(TestPublishExecutionReport))
    suite.addTests(loader.loadTestsFromTestCase(TestStateInjection))
    suite.addTests(loader.loadTestsFromTestCase(TestDbtRunnerLazyInit))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
