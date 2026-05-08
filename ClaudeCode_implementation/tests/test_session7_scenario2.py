"""
Session 7 smoke tests — Supabase + Airbyte scenario changes.

Validates (without LLM calls or live credentials):
  - AirbyteConnector.create_destination() exists and has correct signature
  - _run_airbyte() INSTANTIATION dispatches to create_destination() (DEV-47)
  - _run_airbyte() DATA_INGESTION correctly extracts job_id from trigger_sync result (DEV-46)
  - _run_dbt() CONNECTION_SETUP with db_type='postgres' calls configure_profile() (DEV-48)
  - dbt-postgres adapter is installed and importable
  - execution_plan_supabase.json exists with expected task types and structure
"""

import sys
import types
import json
import unittest
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub out semantic_kernel before any metagpt import (Session 6 pattern)
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
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer
from metagpt.tools.bi.airbyte_connector import AirbyteConnector

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLAN_PATH = REPO_ROOT / "ClaudeCode_implementation" / "test_data" / "execution_plan_supabase.json"


# ---------------------------------------------------------------------------
# TestAirbyteConnectorCreateDestination
# ---------------------------------------------------------------------------

class TestAirbyteConnectorCreateDestination(unittest.TestCase):

    def setUp(self):
        self.connector = AirbyteConnector()

    def test_create_destination_method_exists(self):
        self.assertTrue(hasattr(self.connector, "create_destination"))
        self.assertTrue(callable(self.connector.create_destination))

    def test_create_destination_signature(self):
        sig = inspect.signature(self.connector.create_destination)
        self.assertIn("destination_config", sig.parameters)

    def test_create_destination_requires_configured_client(self):
        """Should raise RuntimeError when client not configured."""
        with self.assertRaises(RuntimeError) as ctx:
            self.connector.create_destination({
                "destination_name": "test",
                "destination_definition_id": "xxx",
                "destination_connection_config": {},
            })
        self.assertIn("configure()", str(ctx.exception))

    def test_create_destination_api_failure_raises_runtime_error_with_manual_instructions(self):
        """If the Airbyte API call fails, RuntimeError must include manual-setup instructions."""
        self.connector._client = MagicMock()
        self.connector._workspace_id = "ws-123"
        self.connector._client.destinations.create_destination.side_effect = Exception("API error")

        with self.assertRaises(RuntimeError) as ctx:
            self.connector.create_destination({
                "destination_name": "Supabase DWH",
                "destination_definition_id": "25c5221d-dce2-4163-ade9-739ef790f503",
                "destination_connection_config": {"host": "db.x.supabase.co"},
            })
        msg = str(ctx.exception)
        self.assertIn("MANUAL FALLBACK", msg)
        self.assertIn("cloud.airbyte.com", msg)


# ---------------------------------------------------------------------------
# TestRunAirbyteFixes
# ---------------------------------------------------------------------------

class TestRunAirbyteFixes(unittest.TestCase):

    def setUp(self):
        self.agent = BIAnalyticsEngineer()

    def test_data_ingestion_extracts_job_id_from_dict(self):
        """DEV-46: trigger_sync() returns a dict; job_id must be extracted before wait_for_sync()."""
        mock_connector = MagicMock()
        mock_connector.trigger_sync.return_value = {"job_id": "42", "status": "pending"}
        mock_connector.wait_for_sync.return_value = {"job_id": "42", "status": "succeeded"}

        with patch("metagpt.roles.bi.bi_analytics_engineer.AirbyteConnector", return_value=mock_connector):
            result = self.agent._run_airbyte("DATA_INGESTION", {
                "api_key": "k", "workspace_id": "ws",
                "connection_id": "conn-123",
            })

        mock_connector.wait_for_sync.assert_called_once_with("42")
        self.assertIn("succeeded", str(result))

    def test_instantiation_dispatches_to_create_destination(self):
        """DEV-47: INSTANTIATION task type must call create_destination()."""
        mock_connector = MagicMock()
        mock_connector.create_destination.return_value = {
            "destination_id": "dest-abc",
            "name": "Supabase DWH",
            "status": "created",
        }

        with patch("metagpt.roles.bi.bi_analytics_engineer.AirbyteConnector", return_value=mock_connector):
            result = self.agent._run_airbyte("INSTANTIATION", {
                "api_key": "k",
                "workspace_id": "ws",
                "destination_name": "Supabase DWH",
                "destination_definition_id": "25c5221d-dce2-4163-ade9-739ef790f503",
                "destination_connection_config": {"host": "db.x.supabase.co"},
            })

        mock_connector.create_destination.assert_called_once()
        self.assertIn("dest-abc", str(result))

    def test_connection_setup_does_not_call_create_destination(self):
        """Non-INSTANTIATION tasks must not call create_destination()."""
        mock_connector = MagicMock()
        mock_connector.setup_connection.return_value = {
            "source_id": "s1", "connection_id": "c1", "streams": ["users"]
        }

        with patch("metagpt.roles.bi.bi_analytics_engineer.AirbyteConnector", return_value=mock_connector):
            self.agent._run_airbyte("CONNECTION_SETUP", {
                "api_key": "k", "workspace_id": "ws",
                "source_config": {
                    "source_name": "Faker",
                    "source_definition_id": "e1ead99e-0f8e-4f56-a8e7-5f6c2bb0a7e6",
                    "source_connection_config": {},
                    "destination_id": "dest-abc",
                },
            })

        mock_connector.create_destination.assert_not_called()
        mock_connector.setup_connection.assert_called_once()


# ---------------------------------------------------------------------------
# TestRunDbtPostgresProfile
# ---------------------------------------------------------------------------

class TestRunDbtPostgresProfile(unittest.TestCase):

    def setUp(self):
        self.agent = BIAnalyticsEngineer()

    def test_connection_setup_postgres_calls_configure_profile(self):
        """DEV-48: CONNECTION_SETUP with db_type='postgres' must call configure_profile()."""
        mock_dbt = MagicMock()
        mock_dbt._project_dir = Path("/fake/bi_dwh")
        type(mock_dbt._project_dir).name = MagicMock(return_value="bi_dwh")
        mock_dbt.configure_profile.return_value = "/fake/bi_dwh/profiles.yml"
        self.agent._dbt_runner = mock_dbt

        result = self.agent._run_dbt("CONNECTION_SETUP", {
            "db_type": "postgres",
            "host": "db.xxx.supabase.co",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "dbname": "postgres",
            "schema": "public",
        })

        mock_dbt.configure_profile.assert_called_once()
        call_kwargs = mock_dbt.configure_profile.call_args
        self.assertEqual(call_kwargs.kwargs.get("db_type") or call_kwargs.args[2] if call_kwargs.args else call_kwargs.kwargs.get("db_type"), "postgres")
        self.assertIn("postgres", result)
        self.assertIn("db.xxx.supabase.co", result)

    def test_connection_setup_without_db_type_falls_back_to_attach(self):
        """CONNECTION_SETUP without db_type should still support project_dir attachment."""
        mock_dbt = MagicMock()
        mock_dbt._project_dir = None
        mock_dbt.attach_project.return_value = "/some/project"
        self.agent._dbt_runner = mock_dbt

        self.agent._run_dbt("CONNECTION_SETUP", {
            "project_dir": "/some/project",
        })

        mock_dbt.configure_profile.assert_not_called()
        mock_dbt.attach_project.assert_called_once_with("/some/project")


# ---------------------------------------------------------------------------
# TestDbtPostgresInstalled
# ---------------------------------------------------------------------------

class TestDbtPostgresInstalled(unittest.TestCase):

    def test_dbt_postgres_adapter_importable(self):
        """dbt-postgres must be installed for the Supabase scenario."""
        try:
            import dbt.adapters.postgres  # noqa: F401
            imported = True
        except ImportError:
            imported = False
        self.assertTrue(imported, "dbt-postgres adapter not installed. Run: pip install dbt-postgres")


# ---------------------------------------------------------------------------
# TestSupabaseExecutionPlan
# ---------------------------------------------------------------------------

class TestSupabaseExecutionPlan(unittest.TestCase):

    def _load_plan(self):
        return json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    def test_plan_file_exists(self):
        self.assertTrue(PLAN_PATH.exists(), f"execution_plan_supabase.json not found at {PLAN_PATH}")

    def test_plan_is_valid_json_list(self):
        plan = self._load_plan()
        self.assertIsInstance(plan, list)
        self.assertGreater(len(plan), 0)

    def test_plan_has_required_task_types(self):
        plan = self._load_plan()
        task_types = {t["task_type"] for t in plan}
        for required in ("CREDENTIAL_REQUEST", "INSTANTIATION", "CONNECTION_SETUP",
                         "DATA_INGESTION", "TRANSFORMATION"):
            self.assertIn(required, task_types, f"Missing task type: {required}")

    def test_plan_has_all_required_fields(self):
        plan = self._load_plan()
        required_fields = {"task_id", "dependent_task_ids", "instruction", "task_type"}
        for task in plan:
            for field in required_fields:
                self.assertIn(field, task, f"Task {task.get('task_id')} missing field '{field}'")

    def test_plan_contains_supabase_and_airbyte_tasks(self):
        plan = self._load_plan()
        tools = {t.get("tool") for t in plan if t.get("tool")}
        self.assertIn("SupabaseConnector", tools)
        self.assertIn("AirbyteConnector", tools)
        self.assertIn("DbtRunner", tools)

    def test_plan_has_four_transformation_models(self):
        plan = self._load_plan()
        transform_tasks = [t for t in plan if t["task_type"] == "TRANSFORMATION"]
        model_names = {t["tool_args"].get("model_name") for t in transform_tasks}
        for expected in ("dim_customer", "dim_product", "dim_date", "fact_purchases"):
            self.assertIn(expected, model_names)

    def test_credential_request_tasks_have_no_tool(self):
        plan = self._load_plan()
        for task in plan:
            if task["task_type"] == "CREDENTIAL_REQUEST":
                self.assertIsNone(task.get("tool"),
                                  f"Task {task['task_id']} CREDENTIAL_REQUEST should have tool=null")

    def test_dependency_order_valid(self):
        """No task should depend on a task with an equal or higher task_id."""
        plan = self._load_plan()
        for task in plan:
            task_id = int(task["task_id"])
            for dep in task.get("dependent_task_ids", []):
                self.assertLess(
                    int(dep), task_id,
                    f"Task {task_id} depends on {dep} which has a higher or equal ID"
                )

    def test_dbt_connection_setup_has_db_type_postgres(self):
        """The DbtRunner CONNECTION_SETUP task must have db_type='postgres'."""
        plan = self._load_plan()
        dbt_setup_tasks = [
            t for t in plan
            if t["task_type"] == "CONNECTION_SETUP" and t.get("tool") == "DbtRunner"
        ]
        self.assertGreater(len(dbt_setup_tasks), 0, "No DbtRunner CONNECTION_SETUP task found")
        for task in dbt_setup_tasks:
            self.assertEqual(task["tool_args"].get("db_type"), "postgres",
                             f"DbtRunner CONNECTION_SETUP task {task['task_id']} missing db_type='postgres'")

    def test_airbyte_instantiation_has_destination_definition_id(self):
        """AirbyteConnector INSTANTIATION task must include destination_definition_id."""
        plan = self._load_plan()
        airbyte_init = [
            t for t in plan
            if t["task_type"] == "INSTANTIATION" and t.get("tool") == "AirbyteConnector"
        ]
        self.assertGreater(len(airbyte_init), 0, "No AirbyteConnector INSTANTIATION task found")
        for task in airbyte_init:
            self.assertIn("destination_definition_id", task["tool_args"],
                          f"Task {task['task_id']} missing destination_definition_id")


if __name__ == "__main__":
    unittest.main(verbosity=2)
