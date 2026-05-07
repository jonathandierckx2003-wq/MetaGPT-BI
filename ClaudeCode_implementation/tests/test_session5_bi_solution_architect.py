"""
Standalone smoke test for Session 5: BISolutionArchitect (Agent 3).

Run from the repo root:
    python ClaudeCode_implementation/tests/test_session5_bi_solution_architect.py

Does NOT make LLM calls. All external dependencies (WriteExecutionPlan, Editor) are mocked.
"""

import sys
import types
import unittest
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
from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.roles.bi.bi_solution_architect import BISolutionArchitect
from metagpt.schema import Message
from metagpt.tools.tool_registry import TOOL_REGISTRY
from metagpt.utils.common import any_to_str


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

FAKE_BRD = "# Business Requirement Document\n\n## 1. Project overview\n\nTest BRD content."

FAKE_SPEC = (
    "# Dimensional Model Specification\n\n## 1. Schema type decision\n\nStar schema chosen."
)
FAKE_CONCEPTUAL = "erDiagram\n    DIM_DATE ||--o{ FACT_SALES : \"dates\""
FAKE_LOGICAL = (
    "erDiagram\n    FACT_SALES {\n        int sales_fact_key PK\n        int date_key FK\n    }"
)
FAKE_COMBINED = (
    f"## Dimensional Model Specification\n\n{FAKE_SPEC}\n\n---\n\n"
    f"## Conceptual Schema (Mermaid erDiagram)\n\n{FAKE_CONCEPTUAL}\n\n---\n\n"
    f"## Logical Schema (Mermaid erDiagram)\n\n{FAKE_LOGICAL}"
)
FAKE_PLAN_JSON = (
    '[{"task_id": "1", "dependent_task_ids": [], "instruction": "Init DuckDB", '
    '"task_type": "INSTANTIATION", "tool": "DuckDBExecutor", "tool_args": {"db_path": "dwh.duckdb"}}]'
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBISolutionArchitectInstantiation(unittest.TestCase):

    def setUp(self):
        self.agent = BISolutionArchitect()

    def test_name_and_profile(self):
        self.assertEqual(self.agent.name, "Eve")
        self.assertEqual(self.agent.profile, "BI Solution Architect")

    def test_goal_set(self):
        self.assertIn("execution plan", self.agent.goal.lower())
        self.assertIn("JSON", self.agent.goal)

    def test_todo_action_is_write_execution_plan(self):
        self.assertEqual(self.agent.todo_action, "WriteExecutionPlan")

    def test_tools_list(self):
        expected = {"RoleZero", "Editor", "BISolutionArchitect"}
        self.assertEqual(set(self.agent.tools), expected)

    def test_watches_write_data_model(self):
        self.assertIn(any_to_str(WriteDataModel), self.agent.rc.watch)

    def test_does_not_watch_write_brd_directly(self):
        # WriteBRD is in memory via observe_all_msg_from_buffer=True, not via watch filter.
        # If WriteBRD were in rc.watch, Eve would trigger prematurely before the data model exists.
        self.assertNotIn(any_to_str(WriteBRD), self.agent.rc.watch)

    def test_tool_execution_map_has_generate_execution_plan(self):
        self.assertIn(
            "BISolutionArchitect.generate_execution_plan",
            self.agent.tool_execution_map,
        )

    def test_instruction_contains_generate_execution_plan(self):
        self.assertIn("BISolutionArchitect.generate_execution_plan", self.agent.instruction)

    def test_instruction_contains_mandatory_guard(self):
        self.assertIn("MANDATORY", self.agent.instruction)


class TestToolRegistration(unittest.TestCase):

    def test_bi_solution_architect_in_tool_registry(self):
        self.assertTrue(TOOL_REGISTRY.has_tool("BISolutionArchitect"))

    def test_generate_execution_plan_schema_has_no_parameters(self):
        tool = TOOL_REGISTRY.get_tool("BISolutionArchitect")
        self.assertIsNotNone(tool, "BISolutionArchitect tool must exist")
        methods = tool.schemas.get("methods", {})
        gen_schema = methods.get("generate_execution_plan")
        self.assertIsNotNone(
            gen_schema,
            f"generate_execution_plan must appear in tool schemas. methods: {list(methods.keys())}",
        )
        # The method takes no arguments — confirm no large document params are exposed (DEV-30 pattern)
        schema_str = str(gen_schema)
        self.assertNotIn("brd_content", schema_str,
                         "generate_execution_plan must not expose brd_content as a parameter (DEV-30)")
        self.assertNotIn("dimensional_model_specification", schema_str,
                         "generate_execution_plan must not expose dimensional_model_specification as a parameter")


class TestGenerateExecutionPlan(unittest.IsolatedAsyncioTestCase):

    def _make_agent_with_memory(self, brd_content, data_model_content):
        agent = BISolutionArchitect()
        brd_msg = Message(
            content=brd_content,
            cause_by=any_to_str(WriteBRD),
            sent_from="Alice",
        )
        dm_msg = Message(
            content=data_model_content,
            cause_by=any_to_str(WriteDataModel),
            sent_from="Bob",
        )
        agent.rc.memory.add(brd_msg)
        agent.rc.memory.add(dm_msg)
        return agent

    async def test_saves_json_file_with_correct_path(self):
        agent = self._make_agent_with_memory(FAKE_BRD, FAKE_COMBINED)
        agent.editor = MagicMock()
        with patch.object(WriteExecutionPlan, "run", new_callable=AsyncMock, return_value=FAKE_PLAN_JSON):
            with patch.object(agent, "publish_message"):
                await agent.generate_execution_plan()
        agent.editor.write.assert_called_once()
        call_args = agent.editor.write.call_args
        saved_path = call_args.kwargs.get("path") or call_args.args[0]
        self.assertTrue(
            str(saved_path).endswith(".json"),
            f"Expected a .json file path, got: {saved_path}",
        )
        self.assertIn("execution_plan", str(saved_path))

    async def test_publishes_message_with_correct_cause_by_and_sender(self):
        agent = self._make_agent_with_memory(FAKE_BRD, FAKE_COMBINED)
        agent.editor = MagicMock()
        published = []
        with patch.object(WriteExecutionPlan, "run", new_callable=AsyncMock, return_value=FAKE_PLAN_JSON):
            with patch.object(agent, "publish_message", side_effect=published.append):
                await agent.generate_execution_plan()
        self.assertEqual(len(published), 1)
        msg = published[0]
        self.assertEqual(msg.cause_by, any_to_str(WriteExecutionPlan))
        self.assertEqual(msg.sent_from, "Eve")

    async def test_returns_confirmation_with_artifact_path(self):
        agent = self._make_agent_with_memory(FAKE_BRD, FAKE_COMBINED)
        agent.editor = MagicMock()
        with patch.object(WriteExecutionPlan, "run", new_callable=AsyncMock, return_value=FAKE_PLAN_JSON):
            with patch.object(agent, "publish_message"):
                result = await agent.generate_execution_plan()
        self.assertIn("execution_plan", result.lower())

    async def test_error_when_no_brd_in_memory(self):
        agent = BISolutionArchitect()
        dm_msg = Message(
            content=FAKE_COMBINED,
            cause_by=any_to_str(WriteDataModel),
            sent_from="Bob",
        )
        agent.rc.memory.add(dm_msg)
        result = await agent.generate_execution_plan()
        self.assertIn("Error", result)
        self.assertIn("BRD", result)

    async def test_error_when_no_data_model_in_memory(self):
        agent = BISolutionArchitect()
        brd_msg = Message(
            content=FAKE_BRD,
            cause_by=any_to_str(WriteBRD),
            sent_from="Alice",
        )
        agent.rc.memory.add(brd_msg)
        result = await agent.generate_execution_plan()
        self.assertIn("Error", result)
        self.assertIn("data model", result.lower())

    async def test_write_execution_plan_called_with_correct_sections(self):
        """Verify that the dimensional model spec and logical schema are correctly
        extracted from the combined WriteDataModel message and passed to WriteExecutionPlan.run()."""
        agent = self._make_agent_with_memory(FAKE_BRD, FAKE_COMBINED)
        agent.editor = MagicMock()
        captured_args = {}

        async def _capture_run(brd_content, dimensional_model_specification, logical_schema):
            captured_args["brd_content"] = brd_content
            captured_args["dimensional_model_specification"] = dimensional_model_specification
            captured_args["logical_schema"] = logical_schema
            return FAKE_PLAN_JSON

        with patch.object(WriteExecutionPlan, "run", side_effect=_capture_run):
            with patch.object(agent, "publish_message"):
                await agent.generate_execution_plan()

        # BRD content passed unchanged
        self.assertEqual(captured_args["brd_content"], FAKE_BRD)

        # Dimensional model spec — should be just the content, not the "## Dimensional Model..." heading
        self.assertNotIn("## Dimensional Model Specification", captured_args["dimensional_model_specification"])
        self.assertIn("Star schema", captured_args["dimensional_model_specification"])

        # Logical schema — should be just the Mermaid content, not the "## Logical Schema..." heading
        self.assertNotIn("## Logical Schema", captured_args["logical_schema"])
        self.assertIn("erDiagram", captured_args["logical_schema"])
        self.assertIn("FACT_SALES", captured_args["logical_schema"])

    async def test_published_message_content_is_plan_json(self):
        agent = self._make_agent_with_memory(FAKE_BRD, FAKE_COMBINED)
        agent.editor = MagicMock()
        published = []
        with patch.object(WriteExecutionPlan, "run", new_callable=AsyncMock, return_value=FAKE_PLAN_JSON):
            with patch.object(agent, "publish_message", side_effect=published.append):
                await agent.generate_execution_plan()
        self.assertEqual(published[0].content, FAKE_PLAN_JSON)


class TestExtractSection(unittest.TestCase):

    def test_extract_spec_section(self):
        text = "## Dimensional Model Specification\n\nStar schema content here."
        result = BISolutionArchitect._extract_section(text)
        self.assertEqual(result, "Star schema content here.")

    def test_extract_logical_section(self):
        text = "## Logical Schema (Mermaid erDiagram)\n\nerDiagram\n    FACT_SALES {}"
        result = BISolutionArchitect._extract_section(text)
        self.assertEqual(result, "erDiagram\n    FACT_SALES {}")

    def test_no_double_newline_returns_full_text(self):
        text = "No heading here"
        result = BISolutionArchitect._extract_section(text)
        self.assertEqual(result, "No heading here")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBISolutionArchitectInstantiation))
    suite.addTests(loader.loadTestsFromTestCase(TestToolRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestGenerateExecutionPlan))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractSection))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
