from __future__ import annotations

from pathlib import Path

from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.actions.bi.write_execution_report import WriteExecutionReport
from metagpt.actions.bi.write_validation_report import WriteValidationReport
from metagpt.logs import logger
from metagpt.prompts.bi.bi_analytics_engineer import BI_ANALYTICS_ENGINEER_INSTRUCTION, CURRENT_STATE
from metagpt.roles.di.role_zero import RoleZero
from metagpt.schema import Message
from metagpt.tools.bi.airbyte_connector import AirbyteConnector
from metagpt.tools.bi.dbt_runner import DbtRunner
from metagpt.tools.bi.duckdb_executor import DuckDBExecutor
from metagpt.tools.bi.pandas_loader import PandasLoader
from metagpt.tools.bi.supabase_connector import SupabaseConnector
from metagpt.tools.tool_registry import register_tool
from metagpt.utils.common import any_to_name, any_to_str


@register_tool(include_functions=["execute_BI_task", "publish_execution_report"])
class BIAnalyticsEngineer(RoleZero):
    """Agent 4: Executes the DWH Technical Execution Plan task by task against external tools.

    Dispatches each task from the execution plan to the correct Tool class based on
    task_type and tool fields. Maintains execution state (completed/active/failed task IDs)
    injected into the LLM prompt at every reasoning step via cmd_prompt_current_state.
    Publishes the Execution Report when all tasks are complete to trigger BIQAEngineer.
    """

    name: str = "Alex"
    profile: str = "BI Analytics Engineer"
    goal: str = (
        "Execute the DWH Technical Execution Plan by performing each task in the received "
        "JSON file, in strict dependency order. Upon completion, deliver a completed Execution Report."
    )
    constraints: str = (
        "Execute tasks strictly in the dependency order defined in the Execution Plan. "
        "Never skip a task or change its type. Use only the tools explicitly assigned to each "
        "task type. For CREDENTIAL_REQUEST tasks, always call RoleZero.ask_human before proceeding. "
        "Always write and run tests alongside each TRANSFORMATION task."
    )
    instruction: str = BI_ANALYTICS_ENGINEER_INSTRUCTION
    tools: list[str] = ["RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner"]
    todo_action: str = any_to_name(WriteExecutionReport)
    max_react_loop: int = 50

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # DEV-16: explicit _watch required because RoleZero sets observe_all_msg_from_buffer=True
        self._watch([WriteExecutionPlan, WriteValidationReport])
        # Execution state — updated by execute_BI_task after each dispatch
        self._completed_task_ids: list[str] = []
        self._active_task_id: str = ""
        self._failed_task_ids: list[str] = []
        # _dbt_runner and _duckdb_executor are created lazily by _get_dbt_runner() /
        # _get_duckdb_executor() — NOT initialized here because _update_tool_execution()
        # (called by RoleZero's model_validator during __init__) already creates them.

    async def _think(self) -> bool:
        """Inject current execution state into cmd_prompt_current_state before each LLM call."""
        self.cmd_prompt_current_state = CURRENT_STATE.format(
            completed_task_ids=self._completed_task_ids if self._completed_task_ids else "none",
            active_task_id=self._active_task_id or "none",
            failed_task_ids=self._failed_task_ids if self._failed_task_ids else "none",
        ).strip()
        return await super()._think()

    async def _quick_think(self):
        # Full task execution — never shortcut via QUICK/AMBIGUOUS (DEV-22).
        return None, "TASK"

    async def reply_to_human(self, content: str) -> str:
        """Print status update to terminal (DEV-32 pattern)."""
        print(f"\n[Alex - BI Analytics Engineer]: {content}\n")
        return content

    def _get_dbt_runner(self) -> DbtRunner:
        """Lazy-create and cache the DbtRunner instance.

        Uses getattr with a default to safely handle the case where this is called
        from _update_tool_execution() during RoleZero's model_validator — before the
        instance attribute is set in __init__.
        """
        if getattr(self, "_dbt_runner", None) is None:
            self._dbt_runner = DbtRunner()
        return self._dbt_runner

    def _get_duckdb_executor(self) -> DuckDBExecutor:
        """Lazy-create and cache the DuckDBExecutor instance."""
        if getattr(self, "_duckdb_executor", None) is None:
            self._duckdb_executor = DuckDBExecutor()
        return self._duckdb_executor

    def _update_tool_execution(self):
        # DEV-21: wire own @register_tool methods and all DbtRunner bound methods into dispatch map.
        # DbtRunner methods are wired because the LLM calls DbtRunner.write_model() directly
        # for TRANSFORMATION tasks (write SQL before calling execute_BI_task to compile and run).
        dbt = self._get_dbt_runner()
        self.tool_execution_map.update({
            "BIAnalyticsEngineer.execute_BI_task": self.execute_BI_task,
            "BIAnalyticsEngineer.publish_execution_report": self.publish_execution_report,
            # DEV-44: init_project and attach_project removed from callable map — dbt project
            # setup is fully automatic (write_model auto-inits; _run_dbt configures profile).
            # Exposing these caused the LLM to manually re-initialize with wrong name/location.
            "DbtRunner.configure_profile": dbt.configure_profile,
            "DbtRunner.write_model": dbt.write_model,
            "DbtRunner.write_schema": dbt.write_schema,
            "DbtRunner.compile_model": dbt.compile_model,
            "DbtRunner.run_model": dbt.run_model,
            "DbtRunner.run_tests": dbt.run_tests,
            "DbtRunner.get_results": dbt.get_results,
        })

    async def execute_BI_task(self, task: dict) -> str:
        """Execute a single task from the DWH Technical Execution Plan.

        Acts as a dispatch router: reads task['tool'] and task['task_type'] and routes
        to the correct Tool class. Updates internal execution state after each call so
        that cmd_prompt_current_state is accurate at every subsequent reasoning step.

        Args:
            task: A task dict from the execution plan with fields task_id, task_type,
                  tool, tool_args, instruction, and dependent_task_ids.

        Returns:
            Execution result string: success summary with row counts or test results,
            or an error message prefixed with [Task N] FAILED if dispatch raised.
        """
        task_id = task.get("task_id", "?")
        task_type = task.get("task_type", "")
        tool_name = task.get("tool") or ""
        tool_args = task.get("tool_args") or {}

        self._active_task_id = str(task_id)

        try:
            result = self._dispatch(task_type, tool_name, tool_args)
            self._completed_task_ids.append(str(task_id))
            self._active_task_id = ""
            return f"[Task {task_id}] COMPLETE — {result}"
        except Exception as exc:
            self._failed_task_ids.append(str(task_id))
            self._active_task_id = ""
            error_msg = f"[Task {task_id}] FAILED — {exc}"
            logger.error(error_msg)
            return error_msg

    def _dispatch(self, task_type: str, tool_name: str, tool_args: dict) -> str:
        """Route task to the appropriate Tool class based on task_type and tool_name."""
        if task_type == "CREDENTIAL_REQUEST":
            return (
                "CREDENTIAL_REQUEST task: do NOT call execute_BI_task for this task type. "
                "Call RoleZero.ask_human with a clearly worded message specifying exactly which "
                "credential is needed and for which system."
            )

        if tool_name == "DuckDBExecutor":
            return self._run_duckdb(task_type, tool_args)

        if tool_name == "PandasLoader":
            return self._run_pandas(tool_args)

        if tool_name == "DbtRunner":
            return self._run_dbt(task_type, tool_args)

        if tool_name == "SupabaseConnector":
            return self._run_supabase(task_type, tool_args)

        if tool_name == "AirbyteConnector":
            return self._run_airbyte(task_type, tool_args)

        return f"Unknown tool '{tool_name}' for task_type '{task_type}'."

    def _run_duckdb(self, task_type: str, tool_args: dict) -> str:
        executor = self._get_duckdb_executor()
        db_path = tool_args.get("db_path", "")

        if task_type == "INSTANTIATION":
            return executor.connect(db_path)

        if task_type == "SCHEMA_CREATION":
            # Ensure a connection is open (INSTANTIATION task normally precedes this)
            if executor._conn is None:
                executor.connect(db_path)
            ddl = tool_args.get("ddl", "")
            if isinstance(ddl, list):
                # DEV-37: ddl may arrive as a JSON array of CREATE TABLE strings; join before run_ddl()
                ddl = "\n".join(ddl)
            return executor.run_ddl(ddl)

        return f"Unsupported DuckDBExecutor task_type: '{task_type}'."

    def _run_pandas(self, tool_args: dict) -> str:
        loader = PandasLoader()
        return loader.load_file(
            file_path=tool_args.get("file_path", ""),
            target_table=tool_args.get("target_table", ""),
            db_path=tool_args.get("db_path", ""),
        )

    def _run_dbt(self, task_type: str, tool_args: dict) -> str:
        dbt = self._get_dbt_runner()
        db_path = tool_args.get("db_path", "")
        model_name = tool_args.get("model_name", "")

        if task_type == "TRANSFORMATION":
            # DEV-44: Disconnect DuckDBExecutor before dbt runs — DuckDB only allows one
            # read-write connection; dbt-duckdb needs exclusive access to the file.
            executor = self._get_duckdb_executor()
            if getattr(executor, "_conn", None) is not None:
                try:
                    executor.disconnect()
                except Exception:
                    pass

            # Auto-initialize project if not yet done (Option A — transparent to the LLM).
            # write_model() already calls init_project() lazily, so _project_dir may already
            # be set here. Only init if still None.
            if dbt._project_dir is None:
                dbt.init_project("bi_dwh")

            # Configure profile if profiles.yml does not exist yet (decoupled from init so
            # it works whether the LLM or write_model() triggered the project creation).
            # Use project dir name as profile_name so it matches dbt_project.yml's profile key.
            profiles_path = dbt._project_dir / "profiles.yml"
            if not profiles_path.exists():
                abs_db_path = str(Path(db_path).resolve()) if db_path else db_path
                dbt.configure_profile(
                    profile_name=dbt._project_dir.name,
                    target_name="dev",
                    db_type="duckdb",
                    db_path=abs_db_path,
                )
            run_result = dbt.run_model(model_name)
            test_result = dbt.run_tests(model_name)
            return f"Model '{model_name}': run={run_result} | tests={test_result}"

        if task_type == "CONNECTION_SETUP":
            db_type = tool_args.get("db_type", "")
            # DEV-48: if db_type='postgres' is specified, auto-init project and configure
            # a postgres profile so TRANSFORMATION tasks run against Supabase instead of DuckDB.
            # The auto-configure guard in the TRANSFORMATION branch checks if profiles.yml already
            # exists and skips DuckDB config — so this must run before the first TRANSFORMATION.
            if db_type == "postgres":
                if dbt._project_dir is None:
                    dbt.init_project("bi_dwh")
                dbt.configure_profile(
                    profile_name=dbt._project_dir.name,
                    target_name="dev",
                    db_type="postgres",
                    host=tool_args.get("host", ""),
                    port=int(tool_args.get("port", 5432)),
                    user=tool_args.get("user", ""),
                    password=tool_args.get("password", ""),
                    dbname=tool_args.get("dbname", "postgres"),
                    schema=tool_args.get("schema", "public"),
                )
                return f"dbt postgres profile configured for host: {tool_args.get('host', '')} (schema: {tool_args.get('schema', 'public')})"
            project_dir = tool_args.get("project_dir", "")
            if project_dir:
                return dbt.attach_project(project_dir)
            return "CONNECTION_SETUP: no db_type or project_dir provided."

        return f"Unsupported DbtRunner task_type: '{task_type}'."

    def _run_supabase(self, task_type: str, tool_args: dict) -> str:
        connector = SupabaseConnector()
        result = connector.connect(
            url=tool_args.get("url", ""),
            key=tool_args.get("key", ""),
            postgres_url=tool_args.get("postgres_url"),
        )
        if task_type == "SCHEMA_CREATION":
            ddl = tool_args.get("ddl", "")
            if isinstance(ddl, list):
                ddl = "\n".join(ddl)
            ddl_result = connector.run_ddl(ddl)
            return f"{result} | {ddl_result}"
        return result

    def _run_airbyte(self, task_type: str, tool_args: dict) -> str:
        connector = AirbyteConnector()
        connector.configure(
            api_key=tool_args.get("api_key", ""),
            workspace_id=tool_args.get("workspace_id", ""),
        )
        # DEV-47: INSTANTIATION creates the Airbyte destination (e.g. Supabase PostgreSQL)
        if task_type == "INSTANTIATION":
            return str(connector.create_destination(tool_args.get("destination_config", tool_args)))
        if task_type == "CONNECTION_SETUP":
            return str(connector.setup_connection(tool_args.get("source_config", {})))
        if task_type == "DATA_INGESTION":
            connection_id = tool_args.get("connection_id", "")
            # DEV-46: trigger_sync() returns {"job_id": ..., "status": ...}; extract before wait_for_sync()
            trigger_result = connector.trigger_sync(connection_id)
            job_id = str(trigger_result["job_id"])
            return str(connector.wait_for_sync(job_id))
        return f"Unsupported AirbyteConnector task_type: '{task_type}'."

    async def publish_execution_report(self) -> str:
        """Read the saved execution report and publish it to trigger the BI QA Engineer.

        Reads workspace/docs/execution_report.md from disk and publishes a Message with
        cause_by=WriteExecutionReport so BIQAEngineer can observe and begin validation.

        Returns:
            Confirmation message, or an error if the file does not exist yet.
        """
        report_path = Path("workspace") / "docs" / "execution_report.md"
        if not report_path.exists():
            return (
                "Error: workspace/docs/execution_report.md not found. "
                "Save the report using Editor.write before calling publish_execution_report()."
            )
        report_content = report_path.read_text(encoding="utf-8")
        self.publish_message(Message(
            content=report_content,
            cause_by=any_to_str(WriteExecutionReport),
            sent_from=self.name,
        ))
        logger.info("Execution report published — BIQAEngineer will begin validation.")
        return "Execution report published successfully. BIQAEngineer will now begin validation."
