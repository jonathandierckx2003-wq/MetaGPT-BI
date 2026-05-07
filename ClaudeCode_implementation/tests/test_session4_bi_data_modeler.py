"""
Standalone smoke test for Session 4: BIDataModeler (Agent 2).

Run from the repo root:
    python ClaudeCode_implementation/tests/test_session4_bi_data_modeler.py

Does NOT make LLM calls. All external dependencies (WriteDataModel, Editor) are mocked.
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
from metagpt.roles.bi.bi_data_modeler import BIDataModeler
from metagpt.schema import Message
from metagpt.tools.tool_registry import TOOL_REGISTRY
from metagpt.utils.common import any_to_str


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBIDataModelerInstantiation(unittest.TestCase):

    def setUp(self):
        self.agent = BIDataModeler()

    def test_name_and_profile(self):
        self.assertEqual(self.agent.name, "Bob")
        self.assertEqual(self.agent.profile, "BI Data Modeler")

    def test_goal_set(self):
        self.assertIn("BRD", self.agent.goal)
        self.assertIn("dimensional", self.agent.goal.lower())

    def test_todo_action_is_write_data_model(self):
        self.assertEqual(self.agent.todo_action, "WriteDataModel")

    def test_tools_list(self):
        expected = {"RoleZero", "Editor", "BIDataModeler"}
        self.assertEqual(set(self.agent.tools), expected)

    def test_watches_write_brd(self):
        self.assertIn(any_to_str(WriteBRD), self.agent.rc.watch)

    def test_generate_data_model_in_tool_execution_map(self):
        self.assertIn("BIDataModeler.generate_data_model", self.agent.tool_execution_map)

    def test_instruction_contains_extra_instruction(self):
        self.assertIn("Step 1", self.agent.instruction)
        self.assertIn("Step 2", self.agent.instruction)
        self.assertIn("Step 3", self.agent.instruction)
        self.assertIn("Step 4", self.agent.instruction)
        self.assertIn("generate_data_model", self.agent.instruction)

    def test_instruction_uses_qualified_method_name(self):
        self.assertIn("BIDataModeler.generate_data_model()", self.agent.instruction)


class TestToolRegistration(unittest.TestCase):

    def test_generate_data_model_registered_in_tool_registry(self):
        self.assertTrue(
            TOOL_REGISTRY.has_tool("BIDataModeler"),
            "BIDataModeler must be present in TOOL_REGISTRY",
        )

    def test_generate_data_model_schema_has_no_required_params(self):
        tool = TOOL_REGISTRY.get_tool("BIDataModeler")
        self.assertIsNotNone(tool, "BIDataModeler tool must exist")
        schemas = tool.schemas
        methods = schemas.get("methods", {})
        func_schema = methods.get("generate_data_model")
        self.assertIsNotNone(
            func_schema,
            f"generate_data_model must appear in tool schemas. methods: {list(methods.keys())}",
        )
        # The method takes no arguments — confirm brd_content is NOT in the schema
        schema_str = str(func_schema)
        self.assertNotIn("brd_content", schema_str,
                         "generate_data_model must not expose brd_content as a parameter (DEV-28)")


class TestGenerateDataModel(unittest.IsolatedAsyncioTestCase):

    async def test_generate_data_model_saves_three_files_and_publishes(self):
        """generate_data_model() with a mocked LLM call."""
        from metagpt.tools.libs.editor import Editor

        agent = BIDataModeler()

        mock_spec = "# Dimensional Model Specification\n## 1. Schema type decision\nStar schema chosen."
        mock_conceptual = (
            "erDiagram\n"
            "    FACT_SALES }o--|| DIM_PRODUCT : references\n"
            "    FACT_SALES }o--|| DIM_DATE : references"
        )
        mock_logical = (
            "erDiagram\n"
            "    FACT_SALES {\n"
            "        int sale_id PK\n"
            "        int product_id FK\n"
            "        int date_id FK\n"
            "        decimal amount\n"
            "    }\n"
            "    DIM_PRODUCT {\n"
            "        int product_id PK\n"
            "        string product_name\n"
            "    }"
        )
        mock_artifacts = {
            "dimensional_model_specification": mock_spec,
            "conceptual_schema": mock_conceptual,
            "logical_schema": mock_logical,
        }

        mock_brd_msg = Message(
            content="# BRD\n## 1. Project overview\nSales BI project.",
            cause_by=any_to_str(WriteBRD),
            sent_from="Alice",
        )
        agent.rc.memory.add(mock_brd_msg)

        editor_write_calls = []

        def capture_write(path, content):
            editor_write_calls.append({"path": path, "content": content})

        published_messages = []

        def capture_publish(msg):
            published_messages.append(msg)

        with (
            patch.object(WriteDataModel, "run", new_callable=AsyncMock, return_value=mock_artifacts),
            patch.object(Editor, "write", side_effect=capture_write),
            patch.object(agent, "publish_message", side_effect=capture_publish),
        ):
            result = await agent.generate_data_model()

        # Three separate editor.write() calls — one per artifact
        self.assertEqual(len(editor_write_calls), 3,
                         f"Expected 3 editor.write() calls, got {len(editor_write_calls)}")

        paths_written = [c["path"] for c in editor_write_calls]
        self.assertTrue(any("dimensional_model_specification" in p for p in paths_written),
                        f"dimensional_model_specification.md not written. Paths: {paths_written}")
        self.assertTrue(any("conceptual_schema" in p for p in paths_written),
                        f"conceptual_schema.mermaid not written. Paths: {paths_written}")
        self.assertTrue(any("logical_schema" in p for p in paths_written),
                        f"logical_schema.mermaid not written. Paths: {paths_written}")

        # Check file extensions
        mermaid_paths = [p for p in paths_written if p.endswith(".mermaid")]
        self.assertEqual(len(mermaid_paths), 2,
                         f"Expected 2 .mermaid files, got: {mermaid_paths}")
        md_paths = [p for p in paths_written if p.endswith(".md")]
        self.assertEqual(len(md_paths), 1,
                         f"Expected 1 .md file, got: {md_paths}")

        # Correct content written to each path
        spec_call = next(c for c in editor_write_calls if "dimensional_model_specification" in c["path"])
        self.assertEqual(spec_call["content"], mock_spec)
        conceptual_call = next(c for c in editor_write_calls if "conceptual_schema" in c["path"])
        self.assertEqual(conceptual_call["content"], mock_conceptual)
        logical_call = next(c for c in editor_write_calls if "logical_schema" in c["path"])
        self.assertEqual(logical_call["content"], mock_logical)

        # Message published with cause_by=WriteDataModel
        self.assertEqual(len(published_messages), 1)
        published_msg = published_messages[0]
        self.assertEqual(published_msg.cause_by, any_to_str(WriteDataModel))
        self.assertEqual(published_msg.sent_from, "Bob")
        # Combined content should contain all three artifacts
        self.assertIn("Dimensional Model Specification", published_msg.content)
        self.assertIn("Conceptual Schema", published_msg.content)
        self.assertIn("Logical Schema", published_msg.content)

        # Return string confirms all three save paths
        self.assertIn("dimensional_model_specification.md", result)
        self.assertIn("conceptual_schema.mermaid", result)
        self.assertIn("logical_schema.mermaid", result)

    async def test_generate_data_model_no_brd_in_memory(self):
        """generate_data_model() returns an error when no WriteBRD message is in memory."""
        agent = BIDataModeler()
        # Do NOT add a WriteBRD message — memory is empty
        result = await agent.generate_data_model()
        self.assertIn("Error", result)
        self.assertIn("BRD", result)

    async def test_generate_data_model_retrieves_brd_from_memory(self):
        """generate_data_model() passes the BRD content from memory to WriteDataModel.run()."""
        from metagpt.tools.libs.editor import Editor

        agent = BIDataModeler()
        brd_text = "# BRD\nThis is the full BRD content for retrieval verification."

        agent.rc.memory.add(Message(
            content=brd_text,
            cause_by=any_to_str(WriteBRD),
            sent_from="Alice",
        ))

        captured_brd = {}

        async def capture_run(brd_content):
            captured_brd["value"] = brd_content
            return {
                "dimensional_model_specification": "spec",
                "conceptual_schema": "erDiagram",
                "logical_schema": "erDiagram",
            }

        with (
            patch.object(WriteDataModel, "run", side_effect=capture_run),
            patch.object(Editor, "write"),
            patch.object(agent, "publish_message"),
        ):
            await agent.generate_data_model()

        self.assertEqual(captured_brd.get("value"), brd_text,
                         "BRD content retrieved from memory must be passed unchanged to WriteDataModel.run()")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Session 4 Smoke Test: BIDataModeler")
    print("=" * 60)
    unittest.main(verbosity=2)
