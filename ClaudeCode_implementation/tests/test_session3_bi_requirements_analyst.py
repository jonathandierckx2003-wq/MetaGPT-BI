"""
Standalone smoke test for Session 3: BIRequirementsAnalyst (Agent 1).

Run from the repo root:
    python ClaudeCode_implementation/tests/test_session3_bi_requirements_analyst.py

Requires:
    - config/config2.yaml with a valid LLM API key (used only in test_generate_brd_live)
    - The semantic_kernel stub workaround below (same pattern as Session 2 tests)
"""

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out semantic_kernel before any metagpt import to avoid broken pydantic
# compatibility in the installed version.
# ---------------------------------------------------------------------------
def _stub_semantic_kernel():
    sk = types.ModuleType("semantic_kernel")
    sk.Kernel = object
    sk.__path__ = []  # make it look like a package so sub-imports work
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
# Now safe to import metagpt
# ---------------------------------------------------------------------------
from metagpt.actions import UserRequirement
from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.roles.bi.bi_requirements_analyst import BIRequirementsAnalyst
from metagpt.tools.tool_registry import TOOL_REGISTRY
from metagpt.utils.common import any_to_str


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBIRequirementsAnalystInstantiation(unittest.TestCase):

    def setUp(self):
        self.agent = BIRequirementsAnalyst()

    def test_name_and_profile(self):
        self.assertEqual(self.agent.name, "Alice")
        self.assertEqual(self.agent.profile, "BI Requirements Analyst")

    def test_goal_set(self):
        self.assertIn("BRD", self.agent.goal)

    def test_todo_action_is_write_brd(self):
        self.assertEqual(self.agent.todo_action, "WriteBRD")

    def test_tools_list(self):
        expected = {"RoleZero", "Editor", "DataSourceInspector", "BIRequirementsAnalyst"}
        self.assertEqual(set(self.agent.tools), expected)

    def test_watches_user_requirement(self):
        self.assertIn(any_to_str(UserRequirement), self.agent.rc.watch)

    def test_generate_brd_in_tool_execution_map(self):
        self.assertIn("BIRequirementsAnalyst.generate_brd", self.agent.tool_execution_map)

    def test_instruction_contains_extra_instruction(self):
        # The instruction should contain both ROLE_INSTRUCTION and EXTRA_INSTRUCTION content.
        self.assertIn("Phase 1", self.agent.instruction)
        self.assertIn("Phase 2", self.agent.instruction)
        self.assertIn("generate_brd", self.agent.instruction)


class TestToolRegistration(unittest.TestCase):

    def test_generate_brd_registered_in_tool_registry(self):
        self.assertTrue(TOOL_REGISTRY.has_tool("BIRequirementsAnalyst"),
                        "BIRequirementsAnalyst must be present in TOOL_REGISTRY")

    def test_generate_brd_schema_has_correct_params(self):
        tool = TOOL_REGISTRY.get_tool("BIRequirementsAnalyst")
        self.assertIsNotNone(tool, "BIRequirementsAnalyst tool must exist")
        schemas = tool.schemas
        # Methods are nested under the 'methods' key
        methods = schemas.get("methods", {})
        func_schema = methods.get("generate_brd")
        self.assertIsNotNone(
            func_schema,
            f"generate_brd must appear in tool schemas under 'methods'. Keys: {list(schemas.keys())}, methods: {list(methods.keys())}"
        )
        # func_schema is either a dict (structured) or a string (docstring-based)
        schema_str = str(func_schema)
        self.assertIn("elicitation_history", schema_str)
        self.assertIn("schema_summaries", schema_str)


class TestAskHumanOverride(unittest.IsolatedAsyncioTestCase):

    async def test_ask_human_uses_stdin(self):
        agent = BIRequirementsAnalyst()
        with patch("builtins.input", return_value="weekly sales analysis"):
            response = await agent.ask_human("What is your main business goal?")
        self.assertEqual(response, "weekly sales analysis")

    async def test_reply_to_human_returns_content(self):
        agent = BIRequirementsAnalyst()
        result = await agent.reply_to_human("I have all the information I need.")
        self.assertEqual(result, "I have all the information I need.")


class TestGenerateBRD(unittest.IsolatedAsyncioTestCase):

    async def test_generate_brd_saves_file_and_publishes(self):
        """Test generate_brd with a mocked LLM call."""
        from metagpt.tools.libs.editor import Editor

        agent = BIRequirementsAnalyst()

        mock_brd_content = (
            "# Business Requirement Document (BRD)\n\n"
            "## 1. Project overview\n- Project: Sales BI\n\n"
            "## 2. End-user definition\n- Sales managers\n"
        )

        editor_write_calls = []

        def capture_write(path, content):
            editor_write_calls.append({"path": path, "content": content})

        published_messages = []

        def capture_publish(msg):
            published_messages.append(msg)

        with (
            patch.object(WriteBRD, "run", new_callable=AsyncMock, return_value=mock_brd_content),
            patch.object(Editor, "write", side_effect=capture_write),
            patch.object(agent, "publish_message", side_effect=capture_publish),
        ):
            result = await agent.generate_brd(
                elicitation_history="User: I need sales analysis.\nAlice: Who are the users?",
                schema_summaries="sales_transactions.csv: 8 columns, 1000 rows.",
            )

        # Verify the editor was asked to write the BRD
        self.assertEqual(len(editor_write_calls), 1)
        self.assertEqual(editor_write_calls[0]["content"], mock_brd_content)
        self.assertIn("business_requirement_document.md", editor_write_calls[0]["path"])

        # Verify the message was published with cause_by=WriteBRD
        self.assertEqual(len(published_messages), 1)
        published_msg = published_messages[0]
        self.assertEqual(published_msg.cause_by, any_to_str(WriteBRD))
        self.assertEqual(published_msg.content, mock_brd_content)
        self.assertEqual(published_msg.sent_from, "Alice")

        # Verify return string confirms save path
        self.assertIn("business_requirement_document.md", result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Session 3 Smoke Test: BIRequirementsAnalyst")
    print("=" * 60)
    unittest.main(verbosity=2)
