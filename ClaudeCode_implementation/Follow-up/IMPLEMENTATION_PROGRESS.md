# MetaGPT-BI Implementation Progress

## Project overview

A transposition of the MetaGPT Software Company multi-agent system into the Business Intelligence (BI) development domain. Five specialized BI agents collaborate via a document-driven, publish-subscribe shared message pool to autonomously execute a full BI back-end development workflow: from requirements elicitation to a validated, ready-to-use Data Warehouse (DWH).

**Repository root:** `c:\Users\jonat\MetaGPT-BI\`

---

## Session plan

| Session | Scope | Status |
|---------|-------|--------|
| 1 | BITaskType enum + 5 prompt files + 4 action classes | ✅ Complete |
| 2 | 6 tool classes (DuckDBExecutor, DbtRunner, PandasLoader, AirbyteConnector, SupabaseConnector, DataSourceInspector) | ✅ Complete |
| 3 | BIRequirementsAnalyst (Agent 1) + standalone test | ⏳ Pending |
| 4 | BIDataModeler (Agent 2) + standalone test | ⏳ Pending |
| 5 | BISolutionArchitect (Agent 3) + standalone test | ⏳ Pending |
| 6 | BIAnalyticsEngineer (Agent 4) + standalone test | ⏳ Pending |
| 7 | BIQAEngineer (Agent 5) + bi_team.py + end-to-end test | ⏳ Pending |

---

## Session 1 — Foundation layer

**Goal:** Create all shared foundational files that downstream role and tool classes will depend on. No runtime dependencies; pure Python structure.

### Files created

#### `metagpt/bi_task_type.py`
Defines the `BITaskType` enum with 6 values used by Agent 3 (BISolutionArchitect) to type-stamp every task in the DWH Technical Execution Plan, and enforced by Agent 4 (BIAnalyticsEngineer) for task dispatch routing.

| Value | Meaning |
|-------|---------|
| `INSTANTIATION` | Creating a new DWH/tool instance (e.g. init DuckDB file, scaffold dbt project) |
| `CONNECTION_SETUP` | Establishing connections between stack components (e.g. dbt profile → DWH) |
| `CREDENTIAL_REQUEST` | Human-in-the-loop checkpoint: agent pauses and asks user for credentials/file paths |
| `SCHEMA_CREATION` | DDL execution to create empty fact/dimension tables in the DWH |
| `DATA_INGESTION` | Loading raw source data into staging tables (Extract + Load of ELT) |
| `TRANSFORMATION` | SQL-based transformations to populate dimensional tables from staging (Transform of ELT) |

#### `metagpt/prompts/bi/`
One file per agent, each exporting an `EXTRA_INSTRUCTION` string constant. Combined with the inherited `ROLE_INSTRUCTION` from `metagpt.prompts.di.role_zero`, this forms each agent's full `instruction` attribute (the system-level prompt sent to the LLM at every ReAct thinking step).

| File | Agent | Key content |
|------|-------|-------------|
| `bi_requirements_analyst.py` | Agent 1 (Alice) | Two-phase operating mode: Phase 1 = structured elicitation conversation, Phase 2 = BRD generation with Editor |
| `bi_data_modeler.py` | Agent 2 (Bob) | Four-step reasoning: Analyze BRD → Choose schema type → Identify facts/dims/measures → Produce 3 artifacts |
| `bi_solution_architect.py` | Agent 3 (Eve) | Three-step reasoning: Select tools → Identify tasks → Order & resolve dependencies → Output JSON plan |
| `bi_analytics_engineer.py` | Agent 4 (Alex) | Full ELT execution protocol per task type + dynamic state injection + correction loop on Validation Feedback Report |
| `bi_qa_engineer.py` | Agent 5 (Edward) | Two-phase validation: structural/technical checks + requirements traceability checks → Validation Feedback Report |

#### `metagpt/actions/bi/`
Four Action classes. Each:
- Inherits from `metagpt.actions.Action`
- Holds a `PROMPT_TEMPLATE` string constant (the action-level prompt)
- Has a `run()` method that formats the template with context, calls the LLM, uses Editor to save the artifact, and returns a summary
- Is used for `cause_by` message routing in the shared message pool (downstream agents watch for these action types)

| File | Class | Triggered by | Output artifact |
|------|-------|--------------|-----------------|
| `write_brd.py` | `WriteBRD` | Agent 1 when Phase 1 (elicitation) is complete | `docs/business_requirement_document.md` |
| `write_data_model.py` | `WriteDataModel` | Agent 2 when BRD message observed | `docs/dimensional_model_specification.md`, `docs/conceptual_schema.mermaid`, `docs/logical_schema.mermaid` |
| `write_execution_plan.py` | `WriteExecutionPlan` | Agent 3 when WriteDataModel output observed | `docs/execution_plan.json` |
| `write_validation_report.py` | `WriteValidationReport` | Agent 5 after both validation phases complete | `docs/validation_feedback_report.md` |

**How action-level prompts integrate with RoleZero's ReAct loop:**
Each agent has a `@register_tool`-decorated method on its role class (e.g. `generate_brd()` on BIRequirementsAnalyst) that:
1. Collects the required context from agent memory (elicitation history, schema summaries, BRD content, etc.)
2. Formats the `PROMPT_TEMPLATE` with that context
3. Makes a focused LLM call (`self.llm.aask(prompt)`)
4. Uses `self.editor` to save the artifact to disk
5. Publishes a message with `cause_by=WriteBRD` (etc.) to the shared message pool

The EXTRA_INSTRUCTION tells the LLM when to call this method (e.g. "once all elicitation topics are covered, call `generate_brd()`"). Both the role-level prompt (EXTRA_INSTRUCTION) and the action-level prompt (PROMPT_TEMPLATE) are thus used by the LLM: the former governs general behaviour, the latter guides the concrete document generation.

**Prompt text changes made vs. original EXTRA_INSTRUCTION files:**
Several targeted wording changes were applied to make the EXTRA_INSTRUCTION files consistent with the implemented architecture. Full details are in DEVIATIONS_AND_CLARIFICATIONS.md (DEV-03, DEV-05, DEV-06). Summary:
- Agent 1 (`bi_requirements_analyst.py`): `reply to human` → `ask_human` in Phase 1; Phase 2 document entry point changed from "Use the Editor tool to write and save the BRD" → "Call generate_brd(elicitation_history, schema_summaries)"
- Agent 2 (`bi_data_modeler.py`): Step 4 document entry point changed from "Use the Editor tool to write and save the three deliverables" → "Call generate_data_model(brd_content)"
- Agent 4 (`bi_analytics_engineer.py`): Each task type's dispatch instruction changed from "Call the appropriate tool" → "Call execute_BI_task(task)" — aligning the prompt with the thesis's dispatch-router design (the original EXTRA_INSTRUCTION file contradicted the thesis here)
- Agent 5 (`bi_qa_engineer.py`): Phase 3 document entry point changed from "Use Editor to write and save the report" → "Call generate_validation_report(...)"

---

## Session 2 — Tool classes

**Goal:** Create all 6 external tool classes in `metagpt/tools/bi/`. Each class is decorated with `@register_tool` so MetaGPT's global tool registry auto-generates LLM-readable schemas from the method docstrings.

### Packages installed

| Package | Version | Purpose |
|---------|---------|---------|
| `duckdb` | 1.5.2 | Default DWH for PoC |
| `dbt-core` | 1.11.8 | SQL transformation tool |
| `dbt-duckdb` | 1.10.1 | dbt adapter for DuckDB |
| `supabase` | 2.29.0 | Cloud DWH client (PostgreSQL) |
| `airbyte-api` | 0.53.0 | Airbyte API SDK for data ingestion |
| `websockets` | 15.0.1 | Required by supabase realtime |

> Dependency note: `dbt-core` upgraded `pydantic` (2.13.4), `typing-extensions` (4.15.0) and `typing-inspect` (0.9.0) beyond what MetaGPT's requirements specify. These conflicts produce pip warnings but do not break runtime functionality (confirmed by smoke test).

### Files created

#### `metagpt/tools/bi/__init__.py`
Empty package marker.

#### `metagpt/tools/bi/duckdb_executor.py` — DuckDBExecutor
Interacts with a DuckDB database file. Holds an open `duckdb.DuckDBPyConnection` across calls.

| Method | Description |
|--------|-------------|
| `connect(db_path)` | Open or create a DuckDB database file |
| `disconnect()` | Close the active connection |
| `run_ddl(ddl)` | Execute DDL statements; retries up to 3× on transient errors |
| `run_query(sql)` | Execute SELECT; returns list of row dicts |
| `verify_table(table_name)` | Check existence + return column definitions |
| `list_tables()` | Return all table names in the connected DB |
| `get_table_schema(table_name)` | Return column list for a table |
| `check_pk_uniqueness(table, pk_col)` | Verify no duplicate PK values |
| `check_fk_integrity(fact_table, fk_col, dim_table, pk_col)` | Count orphan rows in a FK join |

#### `metagpt/tools/bi/pandas_loader.py` — PandasLoader
Reads CSV and Excel flat files via pandas and loads them into DuckDB via DuckDB's native DataFrame ingestion (no intermediate file writes).

| Method | Description |
|--------|-------------|
| `load_file(file_path, target_table, db_path)` | Read file → write to DuckDB table (CREATE OR REPLACE) |
| `infer_schema(file_path)` | Return column names + pandas dtypes without DB load |
| `get_row_count(file_path)` | Return number of data rows in a flat file |

#### `metagpt/tools/bi/data_source_inspector.py` — DataSourceInspector
Inspects available data sources and returns their structure (table names, column names, data types, row counts). Used by BIRequirementsAnalyst during elicitation.

| Method | Description |
|--------|-------------|
| `inspect_csv(file_path)` | Inspect CSV: row count + column names/dtypes/null counts + 5-row sample |
| `inspect_excel(file_path)` | Inspect Excel: per-sheet row count + column info |
| `inspect_duckdb(db_path)` | Inspect DuckDB: all tables with columns + row counts (read-only) |
| `inspect_postgres(connection_string)` | Inspect PostgreSQL public schema via psycopg2 |

#### `metagpt/tools/bi/dbt_runner.py` — DbtRunner
Wraps dbt Core CLI commands. Each instance binds to a single project directory after `init_project()` or `attach_project()`. SQL content is generated by the LLM in the ReAct loop and passed to `write_model()`.

**dbt projects location:** `<repo_root>/dbt_projects/<project_name>/` (configurable via `project_dir` arg).

| Method | Description |
|--------|-------------|
| `init_project(project_name, project_dir?, profiles_dir?)` | Run `dbt init --skip-profile-setup`, bind to new project |
| `attach_project(project_dir)` | Bind runner to an existing project directory |
| `configure_profile(profile_name, target_name, db_type, ...)` | Write `profiles.yml` inside project dir; supports `duckdb` and `postgres` |
| `write_model(model_name, sql)` | Write LLM-generated SQL to `models/<model_name>.sql` |
| `write_schema(schema_name, yaml_content)` | Write YAML to `models/<schema_name>.yml` (sources, tests, docs) |
| `compile_model(model_name)` | Run `dbt compile --select` (syntax check, no DB write) |
| `run_model(model_name)` | Run `dbt run --select` (materialise transformation) |
| `run_tests(model_name?)` | Run `dbt test` for a model or all models |
| `get_results(run_id?)` | Read `target/run_results.json` and return structured result rows |

#### `metagpt/tools/bi/supabase_connector.py` — SupabaseConnector
Connects to a Supabase (PostgreSQL) project via direct psycopg2 for full DDL support. Also exposes `supabase_client()` for REST API access via the official Python SDK.

| Method | Description |
|--------|-------------|
| `connect(url, key, postgres_url?)` | Connect using Supabase project URL + key; `postgres_url` required for DDL |
| `run_ddl(ddl)` | Execute DDL; retries up to 3× |
| `run_query(sql)` | Execute SELECT; returns list of row dicts |
| `verify_table(table_name)` | Check existence + return column definitions |
| `list_tables(schema?)` | List all tables in a schema (default: `public`) |
| `get_table_schema(table_name)` | Return column list for a table |
| `check_pk_uniqueness(table, pk_col)` | Verify no duplicate PK values |
| `check_fk_integrity(fact_table, fk_col, dim_table, pk_col)` | Count orphan FK rows |
| `supabase_client()` | Return initialized supabase-py REST client |
| `disconnect()` | Close PostgreSQL connection |

#### `metagpt/tools/bi/airbyte_connector.py` — AirbyteConnector
Wraps the `airbyte-api` Python SDK (v0.53.0) for Airbyte Cloud and self-hosted instances.

| Method | Description |
|--------|-------------|
| `configure(api_key, workspace_id, base_url?)` | Initialise Airbyte API client |
| `setup_connection(source_config)` | Create source + connection pointing to an existing destination |
| `trigger_sync(connection_id)` | Start a sync job; returns `job_id` |
| `get_sync_status(job_id)` | Poll job status (pending / running / succeeded / failed / cancelled) |
| `wait_for_sync(job_id)` | Blocking poll until terminal state (used when LLM doesn't need to interleave) |
| `list_connections()` | List all connections in the configured workspace |

### Smoke test results

All 6 classes:
- Import cleanly with `@register_tool` decorator applied
- Are present in `TOOL_REGISTRY` with correct method schemas visible to LLMs
- DuckDBExecutor, PandasLoader, DataSourceInspector, DbtRunner: functionally tested with real data
- SupabaseConnector, AirbyteConnector: import-tested (require live credentials for functional test)

### Cross-file consistency fixes applied after Session 2 audit

| Fix | File changed |
|-----|-------------|
| DEV-11: Added Supabase postgres_url + Airbyte API key CREDENTIAL_REQUEST guidance to Step 1 | `metagpt/prompts/bi/bi_solution_architect.py` |
| DEV-12: TRANSFORMATION step: "Use Editor" → "Call DbtRunner.write_model()" | `metagpt/prompts/bi/bi_analytics_engineer.py` |
| DEV-13: `generate_validation_report()` parameter names aligned with WriteValidationReport.run() | `metagpt/prompts/bi/bi_qa_engineer.py` |
| DEV-14: psycopg2-binary installed for SupabaseConnector + DataSourceInspector.inspect_postgres | environment |

---

## Session 3 — BIRequirementsAnalyst (Agent 1)

*(To be filled in during Session 3)*

---

## Session 4 — BIDataModeler (Agent 2)

*(To be filled in during Session 4)*

---

## Session 5 — BISolutionArchitect (Agent 3)

*(To be filled in during Session 5)*

---

## Session 6 — BIAnalyticsEngineer (Agent 4)

*(To be filled in during Session 6)*

---

## Session 7 — BIQAEngineer (Agent 5) + bi_team.py + end-to-end test

*(To be filled in during Session 7)*
