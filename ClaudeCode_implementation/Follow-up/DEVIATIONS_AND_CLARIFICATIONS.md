# Deviations and Clarifications vs. Theoretical Design

This file tracks every place where the implementation deviates from, extends, or clarifies the theoretical design given in:
- `ClaudeCode_implementation/IMPLEMENTATION_SPEC.md`
- `ClaudeCode_implementation/thesis_section_4.2.pdf` (converted to `thesis_section_4.2.txt`)
- `ClaudeCode_implementation/prompts/` (individual prompt files)

Each entry states: what the theoretical design said, what was implemented instead, and why.

---

## Session 1 deviations

### DEV-01 — Action classes are not registered as ReAct tools (except WriteExecutionPlan)

**Theoretical design:**  
The spec lists `WriteExecutionPlan` in Agent 3's tools list, implying action classes may be directly callable from the ReAct loop. The spec and thesis are silent on whether WriteBRD, WriteDataModel, and WriteValidationReport are also callable tools.

**Implementation:**  
Action classes (`WriteBRD`, `WriteDataModel`, `WriteExecutionPlan`, `WriteValidationReport`) serve two distinct purposes:
1. **Message routing:** their type is used as the `cause_by` field on published messages, so downstream agents can `watch` for them.
2. **Document generation:** their `PROMPT_TEMPLATE` and `run()` method are called from within `@register_tool`-decorated methods on the role class itself (e.g. `generate_brd()` on `BIRequirementsAnalyst`), which is then listed in the role's tools and callable by the LLM.

This means the LLM never directly calls `WriteBRD.run()` — it calls `BIRequirementsAnalyst.generate_brd()`, which internally calls `WriteBRD.run()`. This is consistent with the `Engineer2.write_new_code` pattern described explicitly for Agent 4 in the thesis, and applied consistently to all agents.

**Why:**  
`Action` classes do not have `self.llm` set when instantiated standalone (they need to be attached to a role). Routing the LLM call through a `@register_tool` method on the role gives the method access to `self.llm` and `self.editor` cleanly.

---

### DEV-02 — WriteBRD and WriteDataModel not in their respective agent's tools list

**Theoretical design:**  
Agent 1's tools: `["RoleZero", "Editor", "DataSourceInspector"]` — WriteBRD not listed.  
Agent 2's tools: `["RoleZero", "Editor"]` — WriteDataModel not listed.  
Agent 5's tools: `["RoleZero", "DuckDBExecutor", "SupabaseConnector", "Editor"]` — WriteValidationReport not listed.

**Implementation:**  
Each agent's role class has a `@register_tool`-decorated method (`generate_brd`, `generate_data_model`, `generate_validation_report`) that wraps the Action class call. This method IS added to the agent's tools list. The Action class itself is not added.

Concretely:
- Agent 1 tools: `["RoleZero", "Editor", "DataSourceInspector", "BIRequirementsAnalyst"]`
- Agent 2 tools: `["RoleZero", "Editor", "BIDataModeler"]`
- Agent 3 tools: `["RoleZero", "Editor", "WriteExecutionPlan"]` *(unchanged — WriteExecutionPlan is the Action here)*
- Agent 5 tools: `["RoleZero", "DuckDBExecutor", "SupabaseConnector", "Editor", "BIQAEngineer"]`

**Why:**  
Consistency with the Engineer2 / execute_BI_task pattern. The role class name appears in the tools list (as in `Engineer2`), making the decorated method callable by the LLM.

*(Note: Agent 3's WriteExecutionPlan IS listed as a tool in the spec, suggesting a different pattern there. WriteExecutionPlan will be decorated with `@register_tool` directly on the Action class for Agent 3.)*

---

### DEV-03 — `reply_to_human` overridden in BIRequirementsAnalyst for terminal visibility

**Theoretical design:**  
The thesis and original EXTRA_INSTRUCTION specify that Agent 1 uses `reply_to_human` to send questions to the human user and wait for responses during elicitation (Core tools section lists "reply to human", Phase 1 says "using reply to human").

**Implementation:**  
In `MGXEnv`, `reply_to_human()` does not print content to the terminal — it only returns a success string. The content would be invisible in a terminal PoC run. Additionally, `reply_to_human` does not block for input — it is a one-way send. Only `ask_human` actually blocks and reads a console response.

To fix this: `BIRequirementsAnalyst` overrides `reply_to_human()` to also print the content to stdout before returning. The EXTRA_INSTRUCTION is also updated so the LLM uses `ask_human` (which truly blocks for user input) for elicitation questions that require a response.

**Consequent prompt change in `metagpt/prompts/bi/bi_requirements_analyst.py`:**

| Location | Original text | Implemented text |
|----------|--------------|-----------------|
| Core tools, item 3 | `reply to human: For sending question messages to the business user and waiting for their response` | `ask_human: For sending question messages to the business user and waiting for their response` |
| Phase 1 opening | `conduct a structured elicitation dialogue with the business user using reply to human` | `conduct a structured elicitation dialogue with the business user using ask_human` |

**Why:**  
Purely practical: `Team()` already uses `MGXEnv` by default, which is correct. But in terminal mode, the agent's messages must be visible, and `reply_to_human` does not block for input. Using `ask_human` ensures proper interactive elicitation in a terminal PoC. In the full MGX product, `reply_to_human` would go to a web UI and would be paired with a human-response mechanism — the intent is equivalent.

---

### DEV-04 — `WriteExecutionPlan` decorated with `@register_tool` as a standalone Action class

**Theoretical design:**  
Agent 3's tools list explicitly includes `WriteExecutionPlan`, implying it is callable as a tool from the ReAct loop.

**Implementation:**  
`WriteExecutionPlan` (the Action class in `metagpt/actions/bi/write_execution_plan.py`) is decorated with `@register_tool(include_functions=["run"])`. Its `run()` method formats the `PROMPT_TEMPLATE` with BRD + dimensional model + logical schema, calls the LLM, validates that the output JSON only uses `BITaskType` enum values, and saves the plan with Editor.

This makes it directly callable by `BISolutionArchitect` in the ReAct loop, consistent with the spec's tools list for Agent 3.

**Why:**  
For Agent 3, the spec is explicit. The pattern differs slightly from Agents 1, 2, 5 (DEV-01/02) because the Solution Architect's entire job IS the plan generation — there is no separate interactive phase that needs a wrapper method on the role class.

---

### DEV-05 — Agent 4 prompt: dispatch via `execute_BI_task` instead of direct tool calls

**Theoretical design (original EXTRA_INSTRUCTION file):**  
For each task type in Step 2, the original prompt says the LLM should call individual tools directly:
- INSTANTIATION: *"Call the appropriate tool to create the required instance."*
- CONNECTION_SETUP: *"Call the appropriate connector tool to establish the connection described in tool_args."*
- SCHEMA_CREATION: *"Call the appropriate tool to run schema creation in the external system, with the parameters in tool_args."*
- DATA_INGESTION: *"Call the appropriate ingestion tool with the parameters in tool_args."*
- TRANSFORMATION: *"call the transformation tool to compile and execute the generated model."*

**Thesis design:**  
The thesis (section 4.2.3.4) is explicit: `execute_BI_task()` acts as a **Tool dispatch router** — the LLM calls this one method with a task object, and it reads the `task_type` / `tool` / `tool_args` fields to dispatch internally to the correct Tool class. The LLM's job is to select which task to execute next; `execute_BI_task` then routes it.

There is a direct contradiction between the original EXTRA_INSTRUCTION file and the thesis text. The thesis takes precedence since it describes the architectural intent.

**Implementation:**  
The EXTRA_INSTRUCTION in `metagpt/prompts/bi/bi_analytics_engineer.py` follows the thesis. For each task type, the LLM is told to call `execute_BI_task(task)`:

| Task type | Original text | Implemented text |
|-----------|--------------|-----------------|
| INSTANTIATION | `Call the appropriate tool to create the required instance.` | `Call execute_BI_task(task) with the task object. The method will dispatch to the appropriate tool to create the required instance.` |
| CONNECTION_SETUP | `Call the appropriate connector tool to establish the connection described in tool_args.` | `Call execute_BI_task(task) with the task object. The method will dispatch to the appropriate connector tool.` |
| SCHEMA_CREATION | `Call the appropriate tool to run schema creation in the external system, with the parameters in tool_args.` | `Call execute_BI_task(task) with the task object. The method will dispatch to the appropriate DWH tool to run DDL.` |
| DATA_INGESTION | `Call the appropriate ingestion tool with the parameters in tool_args.` | `Call execute_BI_task(task) with the task object. The method will dispatch to the appropriate ingestion tool.` |
| TRANSFORMATION | `call the transformation tool to compile and execute the generated model` | `call execute_BI_task(task) to compile and run the model and its tests` |

The CREDENTIAL_REQUEST and Execution Report instructions are also tightened: CREDENTIAL_REQUEST now says "Do not call execute_BI_task. Instead, call RoleZero.reply_to_human..." (clarifying the exception), and the Execution Report step specifies `docs/execution_report.md` as the explicit save path.

**Why:**  
The thesis explicitly designs execute_BI_task as the single dispatch entry point. Having the LLM call individual tools directly would bypass the routing logic, make the role harder to extend with new tools, and contradict the thesis's stated architectural intent. Prompting the LLM to call execute_BI_task is the only way to make the described architecture work correctly.

---

### DEV-06 — Prompt text changes in Agents 1, 2, and 5 to reflect the `@register_tool` method pattern (consequence of DEV-01/02)

**Theoretical design:**  
The original EXTRA_INSTRUCTION files for Agents 1, 2, and 5 instruct the LLM to use the Editor tool directly when it is time to produce the output document:
- Agent 1 Phase 2: *"Use the Editor tool to write and save the BRD as a structured markdown document."*
- Agent 2 Step 4: *"Use the Editor tool to write and save the three deliverables as separate files in the project's docs folder."*
- Agent 5 Phase 3: *"Use Editor to write and save the report following the output format defined in the WriteValidationReport action prompt."*

**Implementation:**  
Since DEV-01/02 introduces `@register_tool`-decorated methods on each role class (`generate_brd`, `generate_data_model`, `generate_validation_report`) as the document-generation entry points, the EXTRA_INSTRUCTION must instruct the LLM to call those methods — not Editor directly. The method internally handles the LLM call (using WriteBRD/WriteDataModel/WriteValidationReport PROMPT_TEMPLATE) and the Editor save.

**Consequent prompt changes:**

| File | Location | Original text | Implemented text |
|------|----------|--------------|-----------------|
| `bi_requirements_analyst.py` | Phase 2 | `Use the Editor tool to write and save the BRD as a structured markdown document.` | `Call generate_brd(elicitation_history, schema_summaries) to write and save the BRD.` |
| `bi_data_modeler.py` | Step 4 | `Use the Editor tool to write and save the three deliverables as separate files in the project's docs folder. Inform the user once all three files are saved.` | `Call generate_data_model(brd_content) to write and save the three deliverables as separate files in the project's docs folder. Inform the user once all three files are saved.` |
| `bi_qa_engineer.py` | Phase 3 | `Use Editor to write and save the report following the output format defined in the WriteValidationReport action prompt. After saving, publish the report in the shared message pool.` | `Call generate_validation_report(structural_results, traceability_results, brd_summary, logical_schema, execution_plan, dwh_connection_details) to write and save the report. After saving, publish the report in the shared message pool.` |

**Why:**  
The LLM can only call tools it knows about. If the EXTRA_INSTRUCTION says "use Editor to write the BRD", the LLM will try to compose the BRD content itself and call Editor.write() — bypassing the WriteBRD PROMPT_TEMPLATE entirely. Pointing the LLM to `generate_brd()` ensures the focused action-level LLM call (with the structured PROMPT_TEMPLATE) is always used for document production.

---

## Session 2 deviations

### DEV-07 — SupabaseConnector requires a `postgres_url` parameter in addition to `url` + `key`

**Theoretical design:**  
The spec defines `connect(url: str, key: str)` using Supabase project URL and API key — the standard Supabase client pattern.

**Implementation:**  
The Supabase Python client (`supabase-py`) uses PostgREST under the hood, which does not support arbitrary DDL statements (CREATE TABLE, DROP TABLE, etc.). For a DWH use case where the Analytics Engineer must create schema, run DDL, and execute arbitrary SQL, a direct PostgreSQL connection is required.

`connect()` therefore accepts an optional `postgres_url` parameter (the direct PostgreSQL connection string, e.g. `postgresql://postgres:[password]@db.xxxx.supabase.co:5432/postgres`). When provided, a `psycopg2` connection is opened and used for all `run_ddl()` / `run_query()` / `verify_table()` etc. calls. The Supabase REST API client is still accessible via `supabase_client()` for table-level inserts if needed.

**Why:**  
Without direct PostgreSQL access, DDL execution (SCHEMA_CREATION task type) is impossible via the Supabase REST API. The `postgres_url` is requested from the user as a CREDENTIAL_REQUEST task in the execution plan.

---

### DEV-08 — AirbyteConnector requires `configure()` call before any other method

**Theoretical design:**  
The spec lists `setup_connection(source_config)`, `trigger_sync(connection_id)`, `get_sync_status(sync_id)` as the three methods. No explicit initialisation step is mentioned.

**Implementation:**  
A `configure(api_key, workspace_id, base_url?)` method is added to initialise the Airbyte API client. This is required because the API key and workspace ID are credentials that must be collected from the user via a CREDENTIAL_REQUEST task before the connector can be used. Making them constructor parameters would force the LLM to instantiate a new class with credentials; making them a separate `configure()` call follows the same pattern as DuckDBExecutor's `connect()` and SupabaseConnector's `connect()`.

Additional method `wait_for_sync(job_id)` is added as a convenience for polling without requiring the LLM to loop explicitly, and `list_connections()` is added for inspecting the workspace state.

**Why:**  
Credential collection is a first-class concern in the architecture (CREDENTIAL_REQUEST task type). Keeping credentials out of `__init__()` parameters makes the pattern consistent with all other connector tools.

---

### DEV-09 — DbtRunner uses `attach_project()` for pre-existing projects and stores project dir on instance

**Theoretical design:**  
The spec lists `init_project(project_name: str)` as the only project-setup method.

**Implementation:**  
`attach_project(project_dir: str)` is added alongside `init_project()`. This allows the Analytics Engineer to bind the runner to a project that was scaffolded in an earlier INSTANTIATION task and resume from it in a subsequent CONNECTION_SETUP or TRANSFORMATION task within the same execution plan. `configure_profile()` writes `profiles.yml` directly inside the project directory (not the `~/.dbt/` user home) to keep the project fully self-contained and portable.

**Why:**  
Multi-step dbt workflows span multiple ReAct loop iterations and potentially multiple `execute_BI_task()` calls. The runner must be re-attachable across these iterations. Storing profiles inside the project directory (via `--profiles-dir` flag on all CLI calls) avoids polluting the user's global `~/.dbt/` directory and makes the project directory a single self-contained artifact.

---

### DEV-11 — bi_solution_architect.py prompt updated to explicitly trigger CREDENTIAL_REQUEST tasks for Supabase postgres_url and Airbyte API key

**Root cause:** DEV-07 (Supabase requires postgres_url) and DEV-08 (Airbyte requires configure() with API key + workspace ID) introduced credential requirements that the original Solution Architect prompt did not account for.

**Original prompt (Step 1):** Selected tools based on user preference or defaults, with no mention of what credentials each tool requires.

**Problem:** Without guidance, the LLM generating the execution plan would not know to include CREDENTIAL_REQUEST tasks for the Supabase PostgreSQL connection string or the Airbyte API key + workspace ID. The resulting execution plan would fail at runtime because those credentials would be unavailable when the connector methods are called.

**Fix:** Added a "Credential implications of tool selection" block immediately after the tool selection rules in Step 1:
- Supabase selection → CREDENTIAL_REQUEST task for project URL+key AND postgres_url before first SCHEMA_CREATION/DATA_INGESTION
- Airbyte selection → CREDENTIAL_REQUEST task for API key + workspace ID before first DATA_INGESTION using Airbyte

**File changed:** `metagpt/prompts/bi/bi_solution_architect.py` (Step 1 section)

---

### DEV-12 — bi_analytics_engineer.py TRANSFORMATION prompt: "Use the Editor tool to write SQL" → "Call DbtRunner.write_model()"

**Root cause:** DEV-09 (DbtRunner stores project directory and manages models/ path internally) means using Editor directly to write SQL would require the LLM to know the full absolute path of models/ and would bypass DbtRunner's internal path management.

**Original prompt text (TRANSFORMATION step 1):**
> "Use the Editor tool to write the generated SQL to the appropriate location in the dbt project structure (models/ directory)."

**Problem:** Editor.write(path, content) requires the LLM to supply the full absolute file path. The dbt project directory is set at runtime and stored on the DbtRunner instance — the LLM cannot reliably know this path. Using Editor also bypasses DbtRunner.write_model(), which enforces that the models/ subdirectory exists before writing.

**Fix:** Changed to:
> "Call DbtRunner.write_model(model_name, sql) to save the generated SQL to the dbt project's models directory."

This is consistent with how the thesis describes the pattern: "SQL content is generated by the LLM in the ReAct loop and then passed to write_model()."

**File changed:** `metagpt/prompts/bi/bi_analytics_engineer.py` (TRANSFORMATION task, step 1)

---

### DEV-13 — bi_qa_engineer.py prompt: `generate_validation_report()` parameter names aligned with WriteValidationReport.run()

**Root cause:** At Session 1 time, the prompt was written before WriteValidationReport.run() was implemented. The prompt used shortened parameter names (`structural_results`, `traceability_results`) while the action class used full names (`structural_validation_results`, `traceability_validation_results`).

**Problem:** When `generate_validation_report()` is implemented on BIQAEngineer in Session 7, its parameter names must match both: (a) what the LLM is told to call in the prompt, and (b) what WriteValidationReport.run() expects. The mismatch would require an ugly mapping in the role method.

**Fix:** The prompt is authoritative for what the LLM sees. Updated `bi_qa_engineer.py` to use the full parameter names from WriteValidationReport.run():

| Before | After |
|--------|-------|
| `generate_validation_report(structural_results, traceability_results, ...)` | `generate_validation_report(structural_validation_results, traceability_validation_results, ...)` |

**File changed:** `metagpt/prompts/bi/bi_qa_engineer.py`

---

### DEV-14 — psycopg2-binary added as required package for SupabaseConnector and DataSourceInspector

**Root cause:** Session 2 consistency audit.

Both `SupabaseConnector.connect(postgres_url=...)` and `DataSourceInspector.inspect_postgres()` perform `import psycopg2` at call time. The package was not installed.

**Fix:** `pip install psycopg2-binary` (v2.9.12). Lazy import (inside method bodies) means no import-time failure if psycopg2 is absent, but the tool methods raise `ModuleNotFoundError` at runtime without it.

---

### DEV-10 — `airbyte-api` SDK v0.53.0: `StreamConfigurationsInput` replaces `StreamConfigurations`, `JobTypeEnum.SYNC` replaces string `"sync"`

**Theoretical design:**  
Not specified at this level of detail.

**Implementation:**  
The `airbyte-api` v0.53.0 SDK uses:
- `models.StreamConfigurationsInput` (not `StreamConfigurations`) for connection creation
- `models.JobTypeEnum.SYNC` (not the string `"sync"`) for `JobCreateRequest.job_type`
- `models.ConnectionSyncModeEnum.FULL_REFRESH_OVERWRITE` (not a string) for stream sync mode
- `get_job(job_id=int(job_id))` — `job_id` must be cast to `int`

These were discovered by inspecting the SDK's model signatures at implementation time and corrected in the tool class.

**Why:**  
The SDK uses typed enums and typed IDs rather than bare strings. Using the correct types avoids silent API validation failures at runtime.

---

## Session 3 deviations

*(To be filled in during Session 3)*

---

## Session 4 deviations

*(To be filled in during Session 4)*

---

## Session 5 deviations

*(To be filled in during Session 5)*

---

## Session 6 deviations

*(To be filled in during Session 6)*

---

## Session 7 deviations

*(To be filled in during Session 7)*
