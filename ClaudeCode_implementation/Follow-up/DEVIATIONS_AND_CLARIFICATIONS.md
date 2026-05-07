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

The CREDENTIAL_REQUEST and Execution Report instructions are also tightened: CREDENTIAL_REQUEST now says "Do not call execute_BI_task. Instead, call RoleZero.ask_human..." (clarifying the exception; further corrected from `reply_to_human` to `ask_human` in DEV-19), and the Execution Report step specifies `docs/execution_report.md` as the explicit save path.

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

### DEV-15 — `ask_human` and `reply_to_human` overridden for terminal stdin/stdout

**Theoretical design:**  
The thesis specifies that BIRequirementsAnalyst uses `reply_to_human` (later corrected to `ask_human` in DEV-03) for the elicitation dialogue with the business user.

**Problem:**  
`RoleZero.ask_human` and `RoleZero.reply_to_human` both check `isinstance(self.rc.env, MGXEnv)` and return "Not in MGXEnv, command will not be executed." when not running in the MetaGPT cloud UI environment. Since the PoC runs as a standalone terminal script, both would silently do nothing, making elicitation impossible.

**Implementation:**  
Both methods are overridden in `BIRequirementsAnalyst`:
- `ask_human(question)`: prints the question to stdout, then reads a response from stdin via `asyncio.get_running_loop().run_in_executor(None, input, "Your response: ")` (non-blocking wrapper around the blocking `input()` call).
- `reply_to_human(content)`: prints to stdout and returns the content. No stdin read since this is a one-way broadcast, not an elicitation turn.

**Why:**  
The override is the minimum change needed to make elicitation work in the terminal PoC. In a production deployment (MGXEnv or another UI), the overrides could be removed to restore the upstream behaviour. This deviation affects only BIRequirementsAnalyst in Session 3; the other four agents do not need elicitation-style conversation, so no equivalent override is needed there.

**File changed:** `metagpt/roles/bi/bi_requirements_analyst.py`

---

### DEV-16 — Explicit `_watch([UserRequirement])` required in `__init__` for all RoleZero-based BI agents

**Theoretical design:**  
The thesis specifies that BIRequirementsAnalyst watches `UserRequirement`. This is implicitly assumed to "just work" by the framework.

**Problem discovered during Session 3:**  
`RoleZero` sets `observe_all_msg_from_buffer = True`. This flag causes `Role.__init__` to skip the automatic `_watch([UserRequirement])` call:
```python
# in Role.__init__:
if not self.observe_all_msg_from_buffer:
    self._watch(kwargs.pop("watch", [UserRequirement]))
```
With `observe_all_msg_from_buffer = True`, `rc.watch` stays empty. In `_observe()`, the filter is:
```python
self.rc.news = [n for n in news if (n.cause_by in self.rc.watch or self.name in n.send_to) ...]
```
With `rc.watch = {}`, no messages ever match, so `_observe()` returns 0, `run()` returns early, and the agent never acts.

**Implementation:**  
Each BI role class must explicitly call `self._watch([...])` in its `__init__`, after calling `super().__init__(**kwargs)`. Applies to all 5 agents:
- BIRequirementsAnalyst: `self._watch([UserRequirement])`
- BIDataModeler (Session 4): `self._watch([WriteBRD])`
- BISolutionArchitect (Session 5): `self._watch([WriteDataModel])`
- BIAnalyticsEngineer (Session 6): `self._watch([WriteExecutionPlan, WriteValidationReport])`
- BIQAEngineer (Session 7): `self._watch([...execution report action...])`

**Why:**  
`observe_all_msg_from_buffer = True` (RoleZero default) means all messages are stored in memory for awareness, but the `rc.news` filter still governs which messages actually trigger the agent to react. An explicit `_watch` call is the only way to populate `rc.watch` in RoleZero mode.

**Files changed:** `metagpt/roles/bi/bi_requirements_analyst.py` (and all subsequent BI role files in Sessions 4–7)

---

### DEV-17 — DataSourceInspector imported in bi_requirements_analyst.py to ensure tool registry registration

**Theoretical design:**  
Not specified.

**Problem:**  
`DataSourceInspector` is decorated with `@register_tool` in `metagpt/tools/bi/data_source_inspector.py`. The decorator only registers the class when the module is imported. If `bi_requirements_analyst.py` is imported without a prior import of `data_source_inspector.py`, `TOOL_REGISTRY.has_tool("DataSourceInspector")` returns False, and `BM25ToolRecommender` emits a warning and skips DataSourceInspector from the recommended tools, making it invisible to the LLM.

**Implementation:**  
Added `import metagpt.tools.bi.data_source_inspector  # noqa: F401` at the top of `bi_requirements_analyst.py`. This ensures DataSourceInspector is always registered when the role is imported, regardless of import order.

**Why:**  
The same pattern will apply to all other BI tool classes used by the other agents — each role class imports its tool classes to guarantee registration. This is a common Python pattern for plugin/registry architectures.

**File changed:** `metagpt/roles/bi/bi_requirements_analyst.py`

---

### DEV-18 — WriteDataModel.run() returns a parsed dict (not a raw string); PROMPT_TEMPLATE uses XML delimiters

**Theoretical design / original implementation:**  
`WriteDataModel.run(brd_content)` called `self._aask(prompt)` and returned the raw LLM response string. The PROMPT_TEMPLATE instructed the LLM to "Use the Editor tool to write and save the three deliverables as separate files."

**Problem discovered during Session 3 cross-session audit:**  
`Action._aask()` makes a single LLM call and returns the text content of the response. The LLM cannot execute tool calls (like Editor) from inside that call — there is no ReAct loop inside `_aask()`. The instruction to "use the Editor tool" inside the PROMPT_TEMPLATE was therefore unreachable: the LLM would produce the file contents inline in its text response but nothing would be saved.

Furthermore, `generate_data_model()` (the `@register_tool` method on `BIDataModeler` that wraps this action) needs to save three separate files to three separate paths. A single raw string return value cannot carry three distinct artifacts reliably.

**Implementation:**  
Two changes to `metagpt/actions/bi/write_data_model.py`:

1. **PROMPT_TEMPLATE** — replaced the "Use the Editor tool" instruction with a structured output format block that instructs the LLM to wrap each artifact in XML-style tags:
   ```
   <dimensional_model_specification>...</dimensional_model_specification>
   <conceptual_schema>...</conceptual_schema>
   <logical_schema>...</logical_schema>
   ```

2. **`run()` return type** — changed from `str` to `dict`. After calling `_aask()`, `run()` applies a regex (`_TAG_PATTERN`) to extract the three tagged sections and returns:
   ```python
   {
       "dimensional_model_specification": "...",
       "conceptual_schema": "...",
       "logical_schema": "...",
   }
   ```
   A fallback (raw text under `dimensional_model_specification`, empty strings for the other two keys) is included for cases where the LLM does not produce the expected tags, so `generate_data_model()` can log and handle the failure gracefully rather than crashing on a `KeyError`.

**Why:**  
The `generate_data_model()` method on `BIDataModeler` is responsible for saving the three artifacts to their respective paths via `self.editor.write()`. It needs the content of each artifact separately. Structured XML tags are the standard MetaGPT pattern for extracting multiple structured outputs from a single LLM call (cf. `extract_content` utilities elsewhere in the codebase).

**Files changed:** `metagpt/actions/bi/write_data_model.py`

---

### DEV-19 — CREDENTIAL_REQUEST in bi_analytics_engineer.py: `reply_to_human` → `ask_human`

**Theoretical design / original implementation (DEV-05):**  
The CREDENTIAL_REQUEST task type in `metagpt/prompts/bi/bi_analytics_engineer.py` said:
> "Do not call execute_BI_task. Instead, call RoleZero.reply_to_human with a clearly worded message specifying exactly which credential is needed and for which system. Wait for the human response."

**Problem discovered during Session 3 cross-session audit:**  
`reply_to_human` is a one-way broadcast — it sends content to the human but does NOT block and wait for a response. `ask_human` is the correct method: it sends a message and blocks (via `run_in_executor` in the terminal PoC, via the MGXEnv mechanism in production) until the human replies.

If the prompt says `reply_to_human`, the LLM will call it, immediately proceed to the next step, and the "Wait for the human response" instruction will be ignored because there is no mechanism to actually receive that response. The credential will never be stored.

**Implementation:**  
Changed step 1 of CREDENTIAL_REQUEST from:
> "call RoleZero.reply_to_human with a clearly worded message..."

to:
> "call RoleZero.ask_human with a clearly worded message..."

Also removed the now-redundant "Wait for the human response." sentence (step 2 previously), since `ask_human` blocks by design — the wait is implicit.

**Why:**  
`ask_human` is the only RoleZero method that returns the human's input to the caller. `reply_to_human` has no return path for human input. Using the wrong method here would cause every CREDENTIAL_REQUEST task to silently fail to collect the credential, causing all downstream tasks that depend on it to fail.

**Files changed:** `metagpt/prompts/bi/bi_analytics_engineer.py`

---

### DEV-20 — `Team(use_mgx=False)` required for BI PoC; MGXEnv crashes without a TeamLeader role

**Prior assumption:**  
Architectural note #3 stated "Team() uses MGXEnv by default — no special setup needed."

**Problem discovered during live test (Session 3):**  
`MGXEnv.publish_message` calls `self.get_role(TEAMLEADER_NAME)` (TEAMLEADER_NAME = "Mike") on every message. If no TeamLeader role has been hired, the call returns `None`, and the subsequent `tl.profile` access raises:
```
AttributeError: 'NoneType' object has no attribute 'profile'
```
The BI team has five domain agents (Alice, Bob, Eve, Alex, QA Engineer) and no TeamLeader, so `MGXEnv` cannot be used as-is.

**Implementation:**  
All BI runner scripts (live tests and the final `bi_team.py`) must instantiate `Team(use_mgx=False)`, which creates a plain `Environment` instead of `MGXEnv`. The plain `Environment.publish_message` has no TeamLeader dependency.

The `ask_human` and `reply_to_human` overrides on `BIRequirementsAnalyst` (DEV-15) already handle terminal I/O independently of MGXEnv, so nothing is lost by switching to the plain environment for the PoC.

**Files changed:** `ClaudeCode_implementation/tests/run_session3_live.py` (and all future runner scripts + `bi_team.py`)

---

### DEV-21 — External tool class methods must be manually wired into `tool_execution_map` in `_update_tool_execution`

**Theoretical design / prior assumption:**  
Registering a class with `@register_tool` was assumed to make its methods callable from the RoleZero ReAct loop.

**Problem discovered during live test (Session 3):**  
`TOOL_REGISTRY` only stores LLM-readable schemas (docstrings, parameter names) for use by `BM25ToolRecommender`. The actual callable methods must separately be wired into `tool_execution_map`, which is what the RoleZero dispatcher uses at runtime. Without wiring, the dispatcher raises `Command DataSourceInspector.inspect_csv not found`.

**Implementation:**  
Each BI role class must override `_update_tool_execution()` and populate `self.tool_execution_map` with every external tool method it needs. For classes that require instantiation (e.g. `DataSourceInspector`, `DuckDBExecutor`), the instance is created inside `_update_tool_execution` and its bound methods are added.

**Pattern (applies to all 5 BI agents):**
```python
def _update_tool_execution(self):
    inspector = DataSourceInspector()
    self.tool_execution_map.update({
        "BIRequirementsAnalyst.generate_brd": self.generate_brd,
        "DataSourceInspector.inspect_csv": inspector.inspect_csv,
        ...
    })
```

**Files changed:** `metagpt/roles/bi/bi_requirements_analyst.py` (and all subsequent BI role files in Sessions 4–7)

---

### DEV-22 — `_quick_think` overridden in BIRequirementsAnalyst to always return `(None, "TASK")`

**Theoretical design:**  
Not specified. Assumed default RoleZero `_quick_think` behaviour was appropriate.

**Problem discovered during live test (Session 3):**  
RoleZero's `_quick_think` uses an LLM call to classify the user's intent as QUICK, AMBIGUOUS, TASK, or SEARCH. On the initial BI project request, the LLM sometimes classifies it as AMBIGUOUS — which short-circuits the full ReAct loop via `if quick_rsp: return quick_rsp`, causing Alice to call `reply_to_human` once with a clarifying note and then go idle instead of entering the structured elicitation loop.

**Implementation:**  
`_quick_think` is overridden to unconditionally return `(None, "TASK")`:
```python
async def _quick_think(self):
    return None, "TASK"
```
This forces every invocation into the full think-act cycle, which is the correct behaviour for a multi-turn structured elicitation agent.

**Files changed:** `metagpt/roles/bi/bi_requirements_analyst.py`

---

### DEV-23 — `DataSourceInspector.inspect_csv` truncates sample strings and skips entirely-null columns

**Theoretical design:**  
Not specified at this level of detail.

**Problem discovered during live test (Session 3):**  
`product_details.csv` contains 27 columns, many with verbose text (full product descriptions, Amazon URLs). The raw `inspect_csv` output for this file was ~5,000 tokens, pushing the total per-request context above Groq's 12k free-tier limit. Entirely-null columns (e.g. `Upc Ean Code` with 9,968/10,002 nulls) contributed sample values of `['nan', 'nan', ...]` with no useful schema information.

**Implementation:**  
Two changes to `inspect_csv` in `metagpt/tools/bi/data_source_inspector.py`:
1. Skip columns where `null_count == len(full_df)` (entirely null — no schema value)
2. Truncate each sample string to 60 characters before adding to the output

**Why:**  
Keeps the schema summary compact enough to stay within context limits without losing any information that matters for BRD writing. Product descriptions and image URLs at full length add no value for requirements analysis.

**Files changed:** `metagpt/tools/bi/data_source_inspector.py`

---

### DEV-24 — All tool call references in BI agent prompts must use `ClassName.method_name` format

**Theoretical design / original prompts:**  
Phase 1 of `bi_requirements_analyst.py` said `using ask_human` (bare method name). Phase 2 said `Call generate_brd(...)` (bare method name).

**Problem discovered during live test (Session 3):**  
The RoleZero command dispatcher looks up commands by key in `tool_execution_map`. Keys are registered as `"ClassName.method_name"` (e.g. `"RoleZero.ask_human"`, `"BIRequirementsAnalyst.generate_brd"`). When the LLM outputs `"command_name": "ask_human"` (bare name), the key is not found and the dispatcher raises `Command ask_human not found`. The LLM then tries alternative JSON formats, producing malformed output that crashes the parser with `KeyError: 'command_name'`.

**Implementation:**  
All tool call references in every BI agent prompt file updated to use the fully-qualified `ClassName.method_name` format. For `bi_requirements_analyst.py`:
- `using ask_human` → `using RoleZero.ask_human`
- `Call generate_brd(...)` → `Call BIRequirementsAnalyst.generate_brd(...)`

**Files changed:** `metagpt/prompts/bi/bi_requirements_analyst.py` (and must be applied to all BI agent prompt files in Sessions 4–7)

---

### DEV-25 — `max_completion_tokens` required for gpt-5.x and newer OpenAI models

**Theoretical design / prior assumption:**  
MetaGPT's OpenAI provider uses `max_tokens` for all models. This was assumed to work for any OpenAI model.

**Problem discovered during live test (Session 3):**  
GPT-5.x models (and other newer OpenAI models including o3/o4 series) reject the `max_tokens` parameter with:
```
openai.BadRequestError: 400 - 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.
```
MetaGPT's `_cons_kwargs` in `openai_api.py` only had a special case for `o1-` models (which pops `max_tokens`), not for `gpt-5.x`.

**Implementation:**  
Added an `elif` branch in `_cons_kwargs` after the existing `o1-` check:
```python
elif "gpt-5" in self.model or "o3" in self.model or "o4" in self.model:
    kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
```

**Why:**  
OpenAI's newer model API contracts use `max_completion_tokens` to account for reasoning tokens. This fix is forward-compatible: as more model families adopt this parameter, they can be added to the condition. The existing `o1-` case behaviour (dropping max_tokens without substitution) is preserved.

**Files changed:** `metagpt/provider/openai_api.py`

---

### DEV-26 — `parse_commands` hardened against commands missing `command_name` key

**Theoretical design / prior assumption:**  
The JSON repair function in `parse_commands` was assumed to always produce valid command structures.

**Problem discovered during live test (Session 3):**  
When gpt-5.4-mini occasionally outputs plain text instead of a JSON command block (intermittent), `parse_code` fails to extract a JSON block, falls through to the repair LLM call, and the repair LLM produces a JSON object describing the content (e.g. `{"message": "...", "formatted_json": {...}}`) rather than a command list. This dict has no `command_name` key, so the subsequent list comprehension at line 137 of `role_zero_utils.py` crashes with `KeyError: 'command_name'`.

**Implementation:**  
Added a guard after the existing `isinstance(commands, dict)` normalisation in `parse_commands`:
```python
valid = [cmd for cmd in commands if isinstance(cmd, dict) and "command_name" in cmd]
if not valid:
    return (
        "Your last response was not formatted as a JSON command block. "
        'You must always respond with a JSON list of commands, e.g.: '
        '[{"command_name": "RoleZero.ask_human", "args": {"question": "..."}}]',
        False,
        command_rsp,
    )
commands = valid
```
When `ok=False` is returned, `_act` adds the error message to memory as a `UserMessage`, and the LLM sees it on the next round and self-corrects to proper JSON format.

**Files changed:** `metagpt/utils/role_zero_utils.py`

---

### DEV-27 — MetaGPT's Editor writes to `workspace/` subdirectory, not the current working directory

**Theoretical design / prior assumption:**  
`self.editor.write(path="docs/file.md", content=...)` was assumed to write directly to `<repo_root>/docs/file.md`.

**Discovered during live test (Session 3):**  
The BRD file was logged as saved to `docs\business_requirement_document.md` but was not found there. It was actually written to `workspace\docs\business_requirement_document.md`. MetaGPT's Editor class resolves relative paths under a `workspace/` directory that it creates and manages automatically.

**Implementation:**  
- Removed the explicit `brd_path.parent.mkdir(parents=True, exist_ok=True)` call from `generate_brd()` — Editor manages directory creation inside workspace/ itself. Adding `mkdir` creates a spurious `docs/` folder in the repo root.
- Updated the test runner file-existence check to look in `workspace/docs/` first, then fall back to `docs/`.

**Impact on future sessions:**  
All BI agents' `generate_*()` methods (Sessions 4–7) must NOT call `Path(...).mkdir()` before `editor.write()`. The Editor handles workspace directory creation. Final artifact paths will be `workspace/docs/<filename>` for all agents.

**Files changed:** `metagpt/roles/bi/bi_requirements_analyst.py`, `ClaudeCode_implementation/tests/run_session3_live.py`

---

## Session 4 deviations

### DEV-28 — `generate_data_model()` retrieves BRD from memory instead of accepting it as a parameter

**Theoretical design:**
The original EXTRA_INSTRUCTION for Agent 2 (updated in DEV-06) instructs the LLM to call `generate_data_model(brd_content)`, passing the full BRD text as an argument.

**Problem:**
Passing the entire BRD markdown (~16,000 characters / ~4,000 tokens) as a literal string inside a JSON function-call argument would:
1. Double the token consumption (BRD is already in the LLM context from memory).
2. Risk truncation: the LLM might cut off the BRD text when serialising it into the JSON command.
3. Introduce a fragile copy-paste step with no benefit — the canonical BRD is already in `self.rc.memory`.

**Implementation:**
`generate_data_model()` takes no arguments. Internally it iterates `reversed(self.rc.memory.get())` to find the most recent message with `cause_by == any_to_str(WriteBRD)` and uses its `content` as the BRD. An error string is returned if no such message is found.

The EXTRA_INSTRUCTION Step 4 is updated from:
```
Call generate_data_model(brd_content) to write and save the three deliverables...
```
to:
```
Call BIDataModeler.generate_data_model() to write and save the three deliverables...
```
(This also applies DEV-24 — fully-qualified class prefix — which was not yet applied to Agent 2's prompt.)

**Files changed:** `metagpt/roles/bi/bi_data_modeler.py`, `metagpt/prompts/bi/bi_data_modeler.py`

---

### DEV-29 — Mermaid schemas rendered to SVG via `mermaid_to_file()` after text save

**Theoretical design:**
The thesis notes that the `.mermaid` files "can be rendered to visual files using external drivers such as mermaidcli or Playwright/Pyppeteer that are installed together with the MetaGPT system." The spec and prompts only specify saving `.mermaid` text files; no rendering step is defined.

**Implementation:**
`generate_data_model()` calls a private `_render_mermaid_schemas()` helper after saving the `.mermaid` text files. This helper calls MetaGPT's `mermaid_to_file()` for both schemas, using the engine configured in `config.mermaid.engine` (default: `"nodejs"`, using `mmdc` from `@mermaid-js/mermaid-cli`). Output SVG files are saved to `workspace/docs/conceptual_schema.svg` and `workspace/docs/logical_schema.svg`.

The helper is wrapped in a broad `try/except`: if the engine is unavailable or rendering fails for any reason, a warning is logged and execution continues normally. The `.mermaid` text files are always saved regardless.

**Discovery during smoke test:** `mmdc` (mermaid-cli) is already installed on the development machine (`C:\Users\jonat\AppData\Roaming\npm\mmdc`), so rendering works out of the box.

**Why:** The rendered SVG files give the human user (and downstream agents, if needed) immediately viewable diagrams without requiring a separate rendering step. The graceful fallback ensures the agent does not break in environments without mmdc.

**Files changed:** `metagpt/roles/bi/bi_data_modeler.py`

---

### DEV-31 — `write_data_model.py`: strip Mermaid code fences and strengthen erDiagram requirement

**Discovered during:** Session 4 live test.

**Problem 1 — code fences in LLM output (rendering failure):**
Despite the PROMPT_TEMPLATE saying "Do NOT wrap in ```mermaid code fences", the LLM wrapped both Mermaid schemas in ` ```mermaid ... ``` ` markdown code blocks. `mmdc` received the raw text starting with ` ```mermaid ` and raised `UnknownDiagramError: No diagram type detected`. The `.mermaid` files were saved with fences included, and the SVG renderer failed to produce valid diagrams.

**Problem 2 — LLM used `classDiagram` for the logical schema:**
The logical schema was produced in Mermaid `classDiagram` syntax (using `class` keywords) instead of `erDiagram`. Both schemas must use `erDiagram` per the spec and prompt instructions.

**Fix 1 — defensive code-fence stripping in `write_data_model.py`:**
Added `_strip_mermaid_fences(text)` helper that removes ` ``` ` / ` ```mermaid ` + ` ``` ` wrappers from the extracted Mermaid text. Applied to both `conceptual_schema` and `logical_schema` values returned by `run()`. This is a defensive post-processing step: even if the LLM ignores the instruction, the saved `.mermaid` files and the SVG rendering receive clean Mermaid code.

**Fix 2 — strengthened PROMPT_TEMPLATE:**
The output format instructions for both Mermaid artifacts now include an explicit block at the top:
```
CRITICAL MERMAID RULES:
- Use Mermaid erDiagram syntax ONLY. Do NOT use classDiagram, sequenceDiagram, or any other diagram type.
- Do NOT wrap the Mermaid code in ```mermaid code fences or any other code block markers.
- Output raw Mermaid code only, starting directly with the word `erDiagram` on the first line.
```

**Files changed:** `metagpt/actions/bi/write_data_model.py`

---

### DEV-32 — `reply_to_human` overridden in BIDataModeler for terminal visibility

**Discovered during:** Session 4 live test.

**Problem:**
Bob's status announcements (plan update + completion notice) produce "Not in MGXEnv, command will not be executed." because `RoleZero.reply_to_human` only works inside MGXEnv. DEV-15 intentionally restricted the override to BIRequirementsAnalyst, noting the other agents don't need elicitation. However, Bob's completion announcements are completely invisible in terminal runs, making the output harder to follow.

**Implementation:**
Added `reply_to_human(content)` override to BIDataModeler — same pattern as DEV-15 in BIRequirementsAnalyst: prints `[Bob - BI Data Modeler]: {content}` to stdout and returns the content.

**Files changed:** `metagpt/roles/bi/bi_data_modeler.py`

---

### DEV-33 — MANDATORY guard added to Step 4 prompt to prevent premature `end` command

**Discovered during:** Session 4 live test re-run (verification of DEV-31 fix).

**Problem:**
During the re-run of the Session 4 live test, the LLM called `end` in round 1 without ever calling `BIDataModeler.generate_data_model()`. The model interpreted writing a plan description as completing the task, then called `end` to finalize. The original EXTRA_INSTRUCTION Step 4 says "Call BIDataModeler.generate_data_model()" but does not explicitly forbid calling `end` first.

This is non-deterministic: the first live test run (different random seed) correctly called `generate_data_model()`. The second run did not.

**Implementation:**
Added an explicit mandatory guard sentence at the end of Step 4 in `bi_data_modeler.py`:
```
**MANDATORY: You MUST call BIDataModeler.generate_data_model() before calling end. Do not call end without first completing this step.**
```

**Why:**
The RoleZero `_quick_think` override (DEV-22) prevents the QUICK/AMBIGUOUS classification shortcuts but does not prevent the LLM from calling `end` prematurely inside the `_act` phase. The guard makes the mandatory ordering explicit at the LLM instruction level.

A second issue was also discovered during the verified re-run: after `generate_data_model()` completed, the LLM tried to self-review the saved artifacts by calling `Editor.read` with an absolute path `/workspace/docs/...`. On Windows this resolves to `C:\workspace\...` (not `C:\Users\jonat\MetaGPT-BI\workspace\...`), causing a `FileNotFoundError`. The MANDATORY guard was therefore extended to also prohibit post-generation review: "Once generate_data_model() returns successfully, call end immediately — do not attempt to read, review, or edit the saved files afterward."

**Files changed:** `metagpt/prompts/bi/bi_data_modeler.py`

---

### DEV-30 — (Pre-logged from Session 4 cross-session audit) `WriteExecutionPlan.run()` parameter pattern must follow DEV-28

**Root cause:** Session 4 cross-session impact analysis.

**Problem:**
`WriteExecutionPlan.run(brd_content, dimensional_model_specification, logical_schema)` (Session 1 file) takes three large document strings as parameters. If BISolutionArchitect calls `WriteExecutionPlan.run()` directly from the ReAct loop (as originally designed in DEV-04), the LLM would have to serialise all three documents (~6,000–8,000 tokens combined) as literal string arguments in a JSON command. This is the exact same double-token / truncation problem that DEV-28 solved for Bob's `generate_data_model()`.

**Planned fix (to implement in Session 5):**
Add a `generate_execution_plan()` wrapper method on `BISolutionArchitect`, following the same pattern as `generate_data_model()` on `BIDataModeler`:
- Takes no parameters.
- Internally retrieves BRD content (from the WriteBRD message in memory), dimensional model spec, and logical schema (from the WriteDataModel message in memory).
- Calls `WriteExecutionPlan.run(brd_content, dimensional_model_specification, logical_schema)` with retrieved content.
- Saves result to `docs/execution_plan.json` via `editor.write()`.
- Publishes `Message(cause_by=any_to_str(WriteExecutionPlan))` to trigger BIAnalyticsEngineer.

Consequent changes needed in Session 5:
- `BISolutionArchitect` tools list: add `"BISolutionArchitect"` (remove `"WriteExecutionPlan"` as callable entry point).
- `bi_solution_architect.py` prompt: replace `"Use Editor to write and save the JSON plan to docs/execution_plan.json"` with `"Call BISolutionArchitect.generate_execution_plan()"`.
- `WriteExecutionPlan` keeps its current signature (still needed for the internal LLM call with the full document context).

**Files to change in Session 5:** `metagpt/roles/bi/bi_solution_architect.py` (new file), `metagpt/prompts/bi/bi_solution_architect.py`

---

## Session 5 deviations

### DEV-34 — `bi_solution_architect.py` prompt: "Use Editor" → `BISolutionArchitect.generate_execution_plan()` + MANDATORY guard (confirms DEV-30)

**Root cause:** DEV-30 (pre-logged in Session 4): `WriteExecutionPlan.run()` takes three large document strings as parameters; if called directly from the ReAct loop, the LLM would need to serialise ~6,000–8,000 tokens as literal JSON arguments.

**Problem:**
The original `bi_solution_architect.py` EXTRA_INSTRUCTION output format section said:
> "Use Editor to write and save the JSON plan to docs/execution_plan.json."

This contradicts the DEV-30 decision to add a `generate_execution_plan()` wrapper that retrieves documents from memory internally. The Core tools section also listed "Editor" as the only tool, which would have prompted the LLM to call Editor directly.

**Implementation (Session 5):**

Two changes to `metagpt/prompts/bi/bi_solution_architect.py`:

1. **Core tools section** — updated from:
   ```
   1. Editor: For saving the final JSON execution plan as a file.
   ```
   to:
   ```
   1. BISolutionArchitect.generate_execution_plan(): For writing and saving the final JSON execution plan to the project docs folder.
   ```

2. **Output format section** — updated from:
   ```
   Use Editor to write and save the JSON plan to docs/execution_plan.json. After saving, inform the user that the execution plan is complete and provide a brief human-readable summary of the planned tasks and their sequence.
   ```
   to:
   ```
   Call BISolutionArchitect.generate_execution_plan() to write and save the JSON plan. After saving, inform the user that the execution plan is complete and provide a brief human-readable summary of the planned tasks and their sequence.

   **MANDATORY: You MUST call BISolutionArchitect.generate_execution_plan() before calling end. Once generate_execution_plan() returns successfully, call end immediately — do not attempt to read, review, or edit the saved file afterward.**
   ```

The MANDATORY guard is the same pattern as DEV-33 (BIDataModeler) — prevents premature `end` calls and post-generation self-review attempts.

**Files changed:** `metagpt/prompts/bi/bi_solution_architect.py`

---

### DEV-35 — `BISolutionArchitect` tools list: `["RoleZero", "Editor", "BISolutionArchitect"]` (replaces `WriteExecutionPlan`)

**Theoretical design (DEV-02 / DEV-04):**
DEV-02 noted that Agent 3 tools were `["RoleZero", "Editor", "WriteExecutionPlan"]` (WriteExecutionPlan registered directly as a callable tool via `@register_tool`). DEV-04 confirmed this pattern and implemented `@register_tool(include_functions=["run"])` on `WriteExecutionPlan`.

**Problem (identified in DEV-30):**
Exposing `WriteExecutionPlan.run(brd_content, dimensional_model_specification, logical_schema)` as a directly callable tool in the ReAct loop would require the LLM to serialise the three large document strings as JSON arguments — the same double-token / truncation problem as DEV-28.

**Implementation (Session 5):**
`BISolutionArchitect.generate_execution_plan()` is the single entry point for the LLM. It retrieves documents from memory internally and calls `WriteExecutionPlan.run()` from Python — not from the LLM's JSON command. The tools list therefore uses `"BISolutionArchitect"` (for the `@register_tool`-decorated `generate_execution_plan` method) instead of `"WriteExecutionPlan"`:

```python
tools: list[str] = ["RoleZero", "Editor", "BISolutionArchitect"]
```

`WriteExecutionPlan` retains its `@register_tool(include_functions=["run"])` decorator (it was already implemented this way in Session 1) but is not listed in the role's tools — it is called internally, not by the LLM.

**Why:**
Consistent with the Agent 1 and Agent 2 pattern (BIRequirementsAnalyst, BIDataModeler both list their own class name in tools for the `@register_tool`-decorated method). The LLM calls `generate_execution_plan()`; Python handles the rest.

**Files changed:** `metagpt/roles/bi/bi_solution_architect.py` (tools list)

---

## Session 6 deviations

*(To be filled in during Session 6)*

---

## Session 7 deviations

*(To be filled in during Session 7)*
