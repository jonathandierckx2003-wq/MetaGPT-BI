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

### DEV-36 — WriteExecutionPlan PROMPT_TEMPLATE strengthened with explicit schema example + tool name list; _validate_plan() checks required fields; graceful error return in generate_execution_plan()

**Discovered during:** Session 5 live test.

**Problem:**
The first live test run produced a plan with wrong field names: `title` instead of `instruction`, `description` instead of (not needed), `dependencies` instead of `dependent_task_ids`, and `tooling` (list) instead of `tool` (string) + `tool_args` (dict). The LLM relied on the role-level instruction to recall the schema, but apparently did not fully recall the exact field names during the action-level LLM call inside `WriteExecutionPlan.run()`.

Additionally, `_validate_plan()` only checked `task_type` values — it did not catch the missing required fields, so the validator passed the malformed plan without error.

**Implementation:**

Three changes:

1. **`metagpt/actions/bi/write_execution_plan.py` — PROMPT_TEMPLATE:**
   - Added a `## Required JSON schema — exact field names` section with two concrete example tasks showing the exact field names, and a list of valid tool names (`DuckDBExecutor`, `PandasLoader`, `DbtRunner`, `SupabaseConnector`, `AirbyteConnector`) to use in the `tool` field.
   - Added a `CRITICAL` warning at the end: "Use EXACT field names shown above — task_id, dependent_task_ids, instruction, task_type, tool, tool_args. Every task except CREDENTIAL_REQUEST must have a specific tool name and concrete tool_args."

2. **`metagpt/actions/bi/write_execution_plan.py` — `_validate_plan()`:**
   - Now checks for required fields (`task_id`, `dependent_task_ids`, `instruction`, `task_type`) on every task.
   - Checks that non-CREDENTIAL_REQUEST tasks have a non-null `tool` field.
   - Accumulates all errors and raises a single `ValueError` with all violations listed.
   - Log message updated: "validated N tasks, all required fields and task_types are valid."

3. **`metagpt/roles/bi/bi_solution_architect.py` — `generate_execution_plan()`:**
   - Wrapped `WriteExecutionPlan.run()` in `try/except ValueError`.
   - On validation failure, returns a descriptive error string (not a crash), so the LLM can see what went wrong and retry `generate_execution_plan()`.

**Live test re-run after fix:** 14 tasks, all with correct field names, valid task_types, and specific tool names (DuckDBExecutor × 3, PandasLoader × 3, DbtRunner × 8). Validation passed.

**Files changed:** `metagpt/actions/bi/write_execution_plan.py`, `metagpt/roles/bi/bi_solution_architect.py`, `ClaudeCode_implementation/tests/run_session5_live.py` (Unicode fix)

---

## Session 5 → Session 6 pre-logged concern

### DEV-37 — `tool_args.ddl` in SCHEMA_CREATION tasks is a JSON array, not a string (pre-logged for Session 6)

**Discovered during:** Session 5 live test re-run (2026-05-07).

**Observation:**
The LLM-generated execution plan (14 tasks) structures both SCHEMA_CREATION tasks with `tool_args.ddl` as a JSON array of DDL strings — one string per table — rather than a single concatenated DDL string:

```json
{
  "task_id": "2",
  "task_type": "SCHEMA_CREATION",
  "tool": "DuckDBExecutor",
  "tool_args": {
    "db_path": "workspace/dwh.duckdb",
    "ddl": [
      "CREATE TABLE IF NOT EXISTS staging_interaction_raw (...);",
      "CREATE TABLE IF NOT EXISTS staging_customer_raw (...);",
      "CREATE TABLE IF NOT EXISTS staging_product_raw (...);"
    ]
  }
}
```

**Problem:**
`DuckDBExecutor.run_ddl(ddl: str)` expects a single SQL string. Passing a list will cause a DuckDB API error at runtime.

**`_validate_plan()` impact:**
The validator does not inspect `tool_args` structure — it only checks `task_id`, `dependent_task_ids`, `instruction`, `task_type` presence and `tool` non-nullness. The array passes validation silently.

**Planned fix (to implement in Session 6 — `_run_duckdb` in `execute_BI_task`):**
When dispatching DuckDBExecutor SCHEMA_CREATION tasks, check the type of `ddl`:
```python
ddl = tool_args.get("ddl") or tool_args.get("sql") or ""
if isinstance(ddl, list):
    ddl = "\n".join(ddl)
```
This handles both formats (string and list) transparently, so the LLM's grouping behaviour does not break execution.

**Files to change in Session 6:** `metagpt/roles/bi/bi_analytics_engineer.py` (`_run_duckdb` helper)

---

## Session 5 closure — cross-session consistency fixes

### DEV-38 — Missing `WriteExecutionReport` action class (Session 1 gap)

**Discovered during:** Session 5 cross-session consistency audit.

**Problem:**
Session 1 created 4 action classes corresponding to the 4 inter-agent handoffs:
- WriteBRD → triggers Agent 2
- WriteDataModel → triggers Agent 3
- WriteExecutionPlan → triggers Agent 4
- WriteValidationReport → Agent 5 → may re-trigger Agent 4

The 5th handoff — Agent 4 (Alex) → Agent 5 (Edward) — was missing an action class. Without `WriteExecutionReport`, BIAnalyticsEngineer has no `cause_by` type to publish on its execution report message, and BIQAEngineer has nothing to `_watch([...])` for. The Agent 4 → 5 handoff would be silently broken.

**Implementation:**
Created `metagpt/actions/bi/write_execution_report.py` — a simple marker `Action` subclass with `name = "WriteExecutionReport"`. No `run()` method or PROMPT_TEMPLATE needed: BIAnalyticsEngineer writes the execution report directly using Editor (the LLM composes it from its ReAct loop context) and then calls `publish_execution_report()` on the role class. The action class serves only as the `cause_by` message routing type.

Additionally, `bi_analytics_engineer.py` prompt (Step 3) updated to instruct Alex to call `BIAnalyticsEngineer.publish_execution_report()` after saving the report.

**Files created:** `metagpt/actions/bi/write_execution_report.py`
**Files changed:** `metagpt/prompts/bi/bi_analytics_engineer.py` (Step 3 + On receiving Validation Feedback Report section)

---

### DEV-39 — Multiple DEV-24 non-compliance fixes across BI agent prompt files (Session 5 closure audit)

**Discovered during:** Session 5 cross-session consistency audit.

**Background:**
DEV-24 (Session 3) established that all tool calls in BI agent prompt files must use fully-qualified `ClassName.method_name` format (e.g. `RoleZero.ask_human`, not `ask_human`). DEV-24 was applied to `bi_requirements_analyst.py` and a note was added: "must be applied to all BI agent prompt files in Sessions 4–7." However, several files still had bare (unqualified) method names.

**Issues found and fixed:**

| File | Occurrence | Before | After |
|------|-----------|--------|-------|
| `bi_analytics_engineer.py` | All INSTANTIATION/CONNECTION_SETUP/SCHEMA_CREATION/DATA_INGESTION task dispatch instructions (×4) | `Call execute_BI_task(task)` | `Call BIAnalyticsEngineer.execute_BI_task(task)` |
| `bi_analytics_engineer.py` | TRANSFORMATION task dispatch instruction (×2) | `calling execute_BI_task` / `call execute_BI_task(task)` | `calling BIAnalyticsEngineer.execute_BI_task` / `call BIAnalyticsEngineer.execute_BI_task(task)` |
| `bi_qa_engineer.py` | Phase 3 report generation instruction | `Call generate_validation_report(...)` | `Call BIQAEngineer.generate_validation_report(...)` |
| `bi_solution_architect.py` | CREDENTIAL_REQUEST task type description | `use reply_to_human to ask the user` | `use RoleZero.ask_human to ask the user` |
| `bi_data_modeler.py` | Core tools section | `Editor: For the creation and saving of the three output artifacts as files.` | `BIDataModeler.generate_data_model(): For writing and saving the three output artifacts to the project docs folder.` |

**Why the unqualified names cause failure:**
RoleZero's command dispatcher looks up commands by `"ClassName.method_name"` key in `tool_execution_map`. A bare `"execute_BI_task"` key is not registered — only `"BIAnalyticsEngineer.execute_BI_task"` is. When the LLM outputs the bare name, the dispatcher raises `Command execute_BI_task not found`, causing the LLM to produce malformed retry output and potentially crashing the run (DEV-26 guard notwithstanding).

**Files changed:** `metagpt/prompts/bi/bi_analytics_engineer.py`, `metagpt/prompts/bi/bi_qa_engineer.py`, `metagpt/prompts/bi/bi_solution_architect.py`, `metagpt/prompts/bi/bi_data_modeler.py`

---

## Session 6 deviations

### DEV-40 — `getattr` pattern required for lazy-init methods called from Pydantic `model_validator(mode="after")`

**Discovered during:** Session 6 smoke test (AttributeError during `BIAnalyticsEngineer()` instantiation).

**Problem:**
`RoleZero` uses a `@model_validator(mode="after")` named `set_tool_execution` that calls `_update_tool_execution()`. Pydantic's `model_validator(mode="after")` fires during `validate_python()`, which is invoked inside `super().__init__(**kwargs)`. This means `_update_tool_execution()` is called **before** the code in `BIAnalyticsEngineer.__init__()` after the `super()` call has run. When `_get_dbt_runner()` was implemented as `if self._dbt_runner is None:`, Python raises `AttributeError: 'BIAnalyticsEngineer' object has no attribute '_dbt_runner'` because Pydantic's `__getattr__` raises on missing attributes (unlike a normal Python object which would return `None` for an uninitialised attribute).

```
# Timeline at BIAnalyticsEngineer() instantiation:
1. super().__init__(**kwargs)  # calls Pydantic's validate_python
2.   → @model_validator(mode="after") fires
3.     → _update_tool_execution() called
4.       → _get_dbt_runner() called
5.         → self._dbt_runner   ← AttributeError! (not set yet)
6. # These lines are NEVER REACHED in the first call:
7. self._dbt_runner = None      ← too late
8. self._duckdb_executor = None ← too late
```

**Implementation:**
`_get_dbt_runner()` and `_get_duckdb_executor()` use `getattr(self, "_dbt_runner", None)` (and the equivalent for `_duckdb_executor`) instead of `self._dbt_runner`. `getattr` with a default never triggers `__getattr__` and safely returns `None` when the attribute doesn't exist yet. Once Pydantic's validator creates the instance (and sets `extra="allow"` attributes), the `DbtRunner()` and `DuckDBExecutor()` instances are assigned on `self` and are re-used on all subsequent calls.

Additionally, `self._dbt_runner = None` and `self._duckdb_executor = None` initialisations were removed from `__init__` — they would have reset already-created instances to `None` on the call after `super().__init__()`.

**Why:**
`Role` model config is `ConfigDict(extra="allow")`, so setting `self._dbt_runner = DbtRunner()` inside `_get_dbt_runner()` is stored correctly. The `getattr` guard is the minimum fix: it handles both the "not yet set" case (during `model_validator`) and the "already set" case (normal post-init calls) without any structural change to the lazy-init pattern.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-41 — `todo_action` corrected from `WriteExecutionPlan` to `WriteExecutionReport`

**Theoretical design (pre-logged in memory notes):**
The pre-session design notes had `todo_action = any_to_name(WriteExecutionPlan)` — pointing at the action that triggers this role (the plan it consumes).

**Problem:**
Every other BI role sets `todo_action` to the action class corresponding to what the role **produces**, not what triggers it:
- BIRequirementsAnalyst: `todo_action = "WriteBRD"` (produces BRD)
- BIDataModeler: `todo_action = "WriteDataModel"` (produces data model)
- BISolutionArchitect: `todo_action = "WriteExecutionPlan"` (produces execution plan)
- BIQAEngineer (Session 7): `todo_action = "WriteValidationReport"` (produces validation report)

`WriteExecutionPlan` is the action that triggers BIAnalyticsEngineer (Agent 4), not what it produces. What Agent 4 produces is the execution report, typed as `WriteExecutionReport`.

**Implementation:**
`todo_action` corrected to `any_to_name(WriteExecutionReport)` = `"WriteExecutionReport"`, consistent with all other BI roles.

**Why:**
`todo_action` controls what action/task the agent considers its primary objective. Using the trigger action instead of the produced action would mislabel Alex's primary goal and could affect downstream MetaGPT internals that inspect `todo_action` for task management.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-42 — dbt project auto-initialization inside `_run_dbt()` (Option A)

**Theoretical design:**
The Session 5 execution plan (14 tasks) was expected to include explicit INSTANTIATION and CONNECTION_SETUP tasks for dbt: `dbt init bi_dwh` → `dbt configure_profile`. The LLM-generated plan does not include any dbt setup tasks — it jumps directly from DuckDB SCHEMA_CREATION to 8 TRANSFORMATION tasks using DbtRunner.

**Problem:**
`DbtRunner.run_model(model_name)` requires that `_project_dir` is already set on the instance (via `init_project()` or `attach_project()`). Without a preceding setup task, the first TRANSFORMATION call would raise `RuntimeError: No dbt project directory set. Call init_project() or attach_project() first.`

Two options were considered:
- **Option B** (explicit): Add dbt INSTANTIATION/CONNECTION_SETUP tasks to the execution plan. Requires changing Agent 3's prompt to always include these tasks, and the plan becomes harder to read without them being necessary for user understanding.
- **Option A** (transparent): Detect `dbt._project_dir is None` inside `_run_dbt()` and auto-init transparently before the first TRANSFORMATION call.

**Implementation (Option A — confirmed with user):**
`_run_dbt()` checks `if dbt._project_dir is None` before processing any TRANSFORMATION task. If true, it calls `init_project("bi_dwh")` and `configure_profile(profile_name="bi_dwh", target_name="dev", db_type="duckdb", db_path=abs_db_path)`. The `db_path` is resolved to an absolute path (`Path(db_path).resolve()`) before being written to `profiles.yml`, because dbt's working directory during profile reads is the project directory, not the repo root — relative paths in `profiles.yml` would fail.

```python
if dbt._project_dir is None:
    project_name = "bi_dwh"
    dbt.init_project(project_name)
    abs_db_path = str(Path(db_path).resolve()) if db_path else db_path
    dbt.configure_profile(profile_name=project_name, target_name="dev",
                          db_type="duckdb", db_path=abs_db_path)
```

The auto-init runs at most once per BIAnalyticsEngineer instance: after `init_project()`, `dbt._project_dir` is set, so subsequent TRANSFORMATION tasks skip the init block.

**Why:**
The LLM's job is to execute tasks, not to invent setup tasks that weren't in the plan. Transparent auto-init makes the architecture robust to the case where the execution plan omits dbt setup tasks (which is the actual plan produced by Session 5). This is analogous to how `_run_duckdb()` auto-connects when `executor._conn is None` — self-healing dispatch rather than strict task pre-condition enforcement.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-43 — Adding a new Tool class requires 5 steps, not 3 as described in the thesis

**Theoretical design (thesis section 4.2.3.4, lines 527–530):**
> "To add a new tool to the system, a developer must thus only write its corresponding class file in metagpt/tools, add its name to the role's tools attribute list to make it available to the BI Analytics Engineer. It's also important not to forget to add it's name into the BI Solution Architect prompt so that the tool can actually be added as a value in the 'tool' attribute of tasks listed in the DWH Technical Execution Plan."

The thesis therefore describes 3 steps:
1. Write the Tool class with `@register_tool` in `metagpt/tools/bi/`
2. Add the tool name to `BIAnalyticsEngineer.tools`
3. Add the tool name to the BI Solution Architect prompt (`bi_solution_architect.py`)

**Implementation reality:**
The current implementation requires 2 additional steps that the thesis does not mention:

4. Add an `elif tool_name == "NewToolName":` branch in `_dispatch()` in `bi_analytics_engineer.py` — so the router knows what to call for the new tool.
5. Add the tool's bound methods to `tool_execution_map` in `_update_tool_execution()` in `bi_analytics_engineer.py` — so the LLM can call the tool's methods directly (e.g. `NewTool.method_name`) from the ReAct loop if needed.

**Assessment:**
Steps 4 and 5 are genuinely small: step 4 is one `elif` block (~5 lines), step 5 is a few dict entries. "Minimal changes" (the thesis's claim) is still accurate — but the thesis text is incomplete. The 5-step reality should replace the 3-step description in the thesis.

An alternative design using an `execute(task_type, tool_args)` method on each tool class would make dispatch fully dynamic (eliminating step 4), but this couples tool classes to the BI task type concept, changes the tool class interface for all 5 existing tools, and adds complexity for no runtime benefit in a PoC. The 5-step manual approach was therefore kept as-is.

**What to update in thesis section 4.2.3.4:**
Replace the 3-step description with a 5-step version that explicitly mentions editing `_dispatch()` and `_update_tool_execution()` in `bi_analytics_engineer.py`. Emphasize that steps 4 and 5 are small targeted additions (not structural changes), consistent with the "minimal changes" claim.

**Files that would change for a new tool:** `metagpt/tools/bi/<new_tool>.py` (new file), `metagpt/roles/bi/bi_analytics_engineer.py` (two small additions), `metagpt/prompts/bi/bi_solution_architect.py` (one line in the tool selection section).

---

## PoC limitations (tracked for thesis "Future Work" section)

### LIM-01 — PandasLoader is DuckDB-specific; no generic cross-adapter ingestion tool

**What works:**
- DuckDB scenario: `PandasLoader.load_file()` loads CSV/Excel into DuckDB directly via `duckdb.connect()`.
- Supabase scenario: `AirbyteConnector` handles all ingestion (API/file source → Supabase destination). PandasLoader is not used.
- dbt is already multi-adapter: `DbtRunner.configure_profile(db_type="duckdb"|"postgres")` supports both DuckDB and Supabase/PostgreSQL — just requires the right dbt adapter installed (`dbt-duckdb` or `dbt-postgres`).

**What doesn't work:**
`PandasLoader` cannot load flat files into PostgreSQL/Supabase. There is no generic "CSV → any DWH" ingestion tool. Each scenario must use the tools appropriate for its DWH:
- DuckDB scenario: `DuckDBExecutor` + `PandasLoader` + `DbtRunner(duckdb)`
- Supabase scenario: `SupabaseConnector` + `AirbyteConnector` + `DbtRunner(postgres)`

**Why acceptable for PoC:**
In the Supabase scenario, Airbyte is the intended ingestion layer (it connects to API/file sources and loads into the destination DWH). PandasLoader exists as a lightweight shortcut for the DuckDB PoC scenario only. The BI Solution Architect's tool selection logic already handles this: it picks tools per scenario based on user preference.

**Future work recommendation (for thesis section 5.2):**
A `GenericLoader` tool class (backed by pandas + SQLAlchemy) could support multiple destination backends (DuckDB, PostgreSQL, BigQuery, etc.) via a connection string abstraction. This would make flat-file ingestion DWH-agnostic and eliminate the PandasLoader/SupabaseConnector split for simple CSV scenarios.

**What to add to thesis section 4.2 / 5.2:**
Acknowledge that PandasLoader is DuckDB-specific and that cross-adapter flat-file ingestion is left as a future extension. Frame Airbyte as the intended ingestion tool for cloud DWH scenarios (Supabase, BigQuery, etc.), consistent with real enterprise ELT practice.

---

### DEV-44 — Four dbt-related fixes discovered during live test runs 1 and 2

**Discovered during:** Session 6 live integration test (runs 1 and 2 failed; run 3 was the first full success).

**Background:**
The initial implementation compiled fine and passed all 32 smoke tests, but failed in live execution because the LLM's reasoning about dbt setup steps differed from expectations, and two subtle dbt CLI behaviours were not handled.

---

**Fix 1 — `DbtRunner.write_model` auto-init (DbtRunner, discovered in run 1):**

**Problem:** In live run 1, the LLM called `DbtRunner.init_project("ecommerce_dwh", project_dir="workspace")` manually (because `init_project` was in `tool_execution_map`). This created the project in the wrong location and with the wrong name. In live run 2 (after removing `init_project` from the map), the LLM correctly called `DbtRunner.write_model(model_name, sql)` directly before `execute_BI_task` — but `write_model` required `_project_dir` to be set and raised `RuntimeError: No dbt project attached`.

**Fix:** Added lazy init at the top of `write_model()` in `dbt_runner.py`:
```python
if self._project_dir is None:
    self.init_project("bi_dwh")
```
This ensures the dbt project is scaffolded automatically the first time `write_model` is called, regardless of whether an INSTANTIATION/CONNECTION_SETUP task for dbt was included in the execution plan.

**Files changed:** `metagpt/tools/bi/dbt_runner.py`

---

**Fix 2 — Absolute `--profiles-dir` path in all DbtRunner CLI calls (DbtRunner, discovered in run 1):**

**Problem:** All three `_run_dbt()` calls that pass `--profiles-dir` used `str(self._project_dir)` which was a relative path (e.g. `dbt_projects/bi_dwh`). When dbt runs, it changes its working directory internally. The relative path was resolved relative to the changed CWD — producing an invalid path like `dbt_projects/bi_dwh/dbt_projects/bi_dwh` — and dbt raised "Path does not exist".

**Fix:** Changed to `str(self._project_dir.resolve())` in `compile_model`, `run_model`, and `run_tests`. `Path.resolve()` returns the absolute path, which is CWD-independent.

**Files changed:** `metagpt/tools/bi/dbt_runner.py`

---

**Fix 3 — `run_model` raises `RuntimeError` on silent "no enabled node" dbt exit (DbtRunner, discovered in run 2):**

**Problem:** When a model file has not been written yet (i.e. `write_model` was not called), `dbt run --select model_name` exits with return code **0** but prints `"no enabled node in selection set"` or `"does not match any enabled nodes"` in stdout. The existing code only checked `returncode != 0` for failure detection, so the silent non-execution was treated as success. All 8 TRANSFORMATION tasks appeared to complete successfully, but no dbt models were actually materialised.

**Fix:** Added a post-run check in `run_model`:
```python
combined = (result["stdout"] + result["stderr"]).lower()
if "no enabled node" in combined or "does not match any enabled nodes" in combined:
    raise RuntimeError(
        f"dbt found no model named '{model_name}'. "
        "Ensure DbtRunner.write_model was called first to create the SQL file."
    )
```
The error message explicitly instructs the LLM to call `write_model` first, enabling self-correction.

**Files changed:** `metagpt/tools/bi/dbt_runner.py`

---

**Fix 4 — `init_project` and `attach_project` removed from `tool_execution_map` + TRANSFORMATION "MANDATORY sub-steps" prompt guard (bi_analytics_engineer.py, discovered in runs 1 and 2):**

**Problem (run 1):** `DbtRunner.init_project` was present in `tool_execution_map`, so the LLM could call it directly. It did — with wrong arguments (`project_name="ecommerce_dwh"`, `project_dir="workspace"`) — creating the dbt project in the wrong location with the wrong name before the auto-init logic in `_run_dbt` could run.

**Problem (run 2):** After removing `init_project`/`attach_project` from the map, a second issue emerged: the LLM skipped `DbtRunner.write_model()` for all TRANSFORMATION tasks and called `BIAnalyticsEngineer.execute_BI_task(task)` directly. With Fix 1 in place, `write_model` auto-inits the project, but the model SQL was never written — so all 8 dbt runs found no model file (Fix 3 now catches this and raises an error).

**Root cause:** The TRANSFORMATION steps in the prompt said "Generate the SQL... Call DbtRunner.write_model... Call execute_BI_task" but did not make these feel mandatory. The LLM could interpret "generate the SQL" as a mental step only.

**Fix — remove from map:**
```python
# Removed from tool_execution_map in _update_tool_execution():
# "DbtRunner.init_project": dbt.init_project,   ← removed
# "DbtRunner.attach_project": dbt.attach_project, ← removed
```
This prevents the LLM from calling these methods directly and forces all dbt project setup to go through auto-init in `_run_dbt` / `write_model`.

**Fix — prompt MANDATORY sub-steps:**
The TRANSFORMATION task dispatch section in `bi_analytics_engineer.py` prompt was rewritten with an explicit mandatory header and explicit ordering:
```
**MANDATORY sub-steps — execute in this exact order, do not skip any:**
1. Generate the SQL... Call DbtRunner.write_model(model_name, sql) — the dbt project is
   initialized automatically, do NOT call DbtRunner.init_project or DbtRunner.attach_project.
2. Call BIAnalyticsEngineer.execute_BI_task(task) to compile and run the model and its tests.
   If this returns an error saying the model was not found, it means write_model was not called
   first — go back to step 1.
3. If any test fails: diagnose, fix with DbtRunner.write_model again, then retry execute_BI_task.
4. Mark complete only after successful completion and all tests pass.
```

Additionally, the plain table reference instruction was added: "SQL must reference staging tables as plain table names (e.g. `FROM staging_interaction_raw`), NOT as `ref()` or `source()` calls, since those tables were loaded directly by PandasLoader."

The Step 3 report-generation section also received an explicit 3-step MANDATORY sequence:
```
**MANDATORY — execute these three steps in this exact order before calling end:**
1. Call `Editor.write(path="docs/execution_report.md", content=<your_full_report_markdown>)` to save the report to disk.
2. Call `BIAnalyticsEngineer.publish_execution_report()` — this reads the file you just saved and publishes it to trigger the QA Engineer.
3. Only after publish_execution_report() returns successfully, call end.
```
This fixes a run 2 issue where the LLM composed the report as text in its reasoning output but did not call `Editor.write` before calling `publish_execution_report`.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py` (tool_execution_map), `metagpt/prompts/bi/bi_analytics_engineer.py` (TRANSFORMATION sub-steps + Step 3 guard)

---

**Summary of all 4 fixes:**

| Fix | File | Nature |
|-----|------|--------|
| write_model auto-init | `dbt_runner.py` | Lazy project init — handles LLM calling write_model before execute_BI_task sets up dbt |
| Absolute `--profiles-dir` | `dbt_runner.py` | Path resolution — prevents CWD-relative path failure during dbt CLI execution |
| RuntimeError on "no enabled node" | `dbt_runner.py` | Silent failure detection — forces LLM to write model SQL before running dbt |
| Remove init/attach from map + MANDATORY sub-steps | `bi_analytics_engineer.py` + `bi_analytics_engineer.py` (prompt) | Guard against LLM bypassing write_model or manually re-initialising the dbt project |

---

### DEV-45 — Tools list uses only `BIAnalyticsEngineer` + `DbtRunner`, not all external tool classes

**Theoretical design (thesis Table 6, section 4.2.3.4):**
The thesis lists the following in the `tools` attribute for BIAnalyticsEngineer:
```
RoleZero, Editor, BIAnalyticsEngineer.execute_BI_task, DuckDBExecutor, DbtRunner,
AirbyteConnector, PandasLoader, SupabaseConnector + any tools for additional external services
```
This lists all five external tool classes alongside `execute_BI_task`.

**Implementation:**
```python
tools: list[str] = ["RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner"]
```
Only `DbtRunner` is listed as an external tool class. `DuckDBExecutor`, `PandasLoader`, `AirbyteConnector`, and `SupabaseConnector` are NOT in the tools list.

**Why:**
The thesis tools list appears to reflect the original EXTRA_INSTRUCTION design (DEV-05), where the LLM was supposed to call each tool class directly. Under that design, the LLM would call `DuckDBExecutor.connect()` or `PandasLoader.load_file()` directly, so all tool classes needed to be in the tools list and in `tool_execution_map`.

The implemented architecture follows the dispatch-router design from the thesis body text (also DEV-05): the LLM calls `execute_BI_task(task)` as the single entry point, which internally routes to the correct tool. The LLM never directly calls `DuckDBExecutor.connect()` or `PandasLoader.load_file()` — those are called in Python by `_run_duckdb` and `_run_pandas` respectively. So there is no need to register them in `tool_execution_map` or list them in `tools`.

`DbtRunner` is the exception: TRANSFORMATION tasks require the LLM to call `DbtRunner.write_model(model_name, sql)` directly (to write the SQL before dispatching), so DbtRunner methods must be in both the tools list and `tool_execution_map`. This is consistent with the TRANSFORMATION MANDATORY sub-steps prompt (DEV-44).

`BIAnalyticsEngineer` in the tools list exposes `execute_BI_task` and `publish_execution_report` (via `@register_tool(include_functions=[...])`).

**What to update in thesis:**
Correct Table 6's tools list to match: `["RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner"]`. Explain that the dispatch-router design removes the need to list individual tool classes — only DbtRunner requires direct LLM access because write_model must be called before execute_BI_task in TRANSFORMATION tasks.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py` (tools list)

---

## Session 7 deviations

### DEV-46 — `_run_airbyte()` DATA_INGESTION: `trigger_sync()` return value not extracted before `wait_for_sync()`

**Bug found:** `_run_airbyte()` in `bi_analytics_engineer.py` called `connector.trigger_sync(connection_id)` and immediately passed the return value to `connector.wait_for_sync(job_id)`. But `trigger_sync()` returns a dict `{"job_id": ..., "status": ...}`, not a bare string. `wait_for_sync()` expects a string job_id, causing a type error at runtime.

**Fix:** Extract `job_id` from the dict before calling `wait_for_sync()`:
```python
trigger_result = connector.trigger_sync(connection_id)
job_id = str(trigger_result["job_id"])
return str(connector.wait_for_sync(job_id))
```

**Why:** Implementation error in the original `_run_airbyte()` code — `trigger_sync()` was modelled after a two-step API (trigger → poll), but the return type was not checked when writing the dispatch method.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-47 — `AirbyteConnector` lacked `create_destination()` method; `_run_airbyte()` had no INSTANTIATION handler

**Theoretical design:** The spec and thesis describe INSTANTIATION tasks for Airbyte (configure client + create destination). The `setup_connection()` method already existed but required a `destination_id` for a pre-existing destination — there was no way to create the destination via API.

**Implementation:**
1. Added `AirbyteConnector.create_destination(destination_config: dict) -> dict` — uses the Airbyte API Platform v2 `POST /destinations` endpoint. Expects `destination_name`, `destination_definition_id`, and `destination_connection_config` in the config dict. Known definition ID for PostgreSQL/Supabase: `25c5221d-dce2-4163-ade9-739ef790f503`. If the API call fails (wrong definition ID, network error, permissions), raises `RuntimeError` with a MANUAL FALLBACK message instructing the human user to create the destination in the Airbyte Cloud UI and supply the `destination_id`.

2. Added `INSTANTIATION` case to `_run_airbyte()` — dispatches to `connector.create_destination()` passing `tool_args` (or `tool_args["destination_config"]` if nested).

**Why:** Without `create_destination()`, the Supabase scenario would require manual Airbyte UI setup before the execution plan could run. The human fallback message ensures robustness if the API call fails.

**Design note (Gap 1 fallback):** Per the user's direction, the fallback error message from `create_destination()` provides clear step-by-step instructions for manually creating the destination in Airbyte Cloud UI. The agent (Alex) will observe this error in the ReAct loop and forward the instructions to the human user via `RoleZero.ask_human`.

**Files changed:** `metagpt/tools/bi/airbyte_connector.py`, `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-48 — `_run_dbt()` CONNECTION_SETUP extended to support postgres profile configuration

**Theoretical design:** The thesis and spec describe tool extensibility as a goal. The `_run_dbt()` CONNECTION_SETUP path previously only called `attach_project(project_dir)` — it had no way to configure a postgres profile for the Supabase scenario.

**Implementation:** Added a `db_type='postgres'` branch in `_run_dbt()` CONNECTION_SETUP:
- If `tool_args["db_type"] == "postgres"`, auto-init the project if needed, then call `dbt.configure_profile(db_type="postgres", ...)` with postgres credentials from `tool_args`.
- If `db_type` is absent, the existing `attach_project()` path is used (DuckDB scenario).

The TRANSFORMATION branch's auto-configure guard already checks if `profiles.yml` exists before writing a DuckDB profile — so this CONNECTION_SETUP task must run before the first TRANSFORMATION task in the Supabase plan, ensuring the postgres profile is written and the DuckDB auto-configure is skipped.

**Limitation (Gap 3 — noted for thesis):** The `_run_dbt()` auto-configure in the TRANSFORMATION branch hardcodes `db_type="duckdb"`. This means if no CONNECTION_SETUP task configures the postgres profile first, TRANSFORMATION tasks would silently fall back to DuckDB config. This is an extensibility limitation: adding support for a new DWH backend requires both (a) a new `_run_<tool>()` method in `bi_analytics_engineer.py` and (b) awareness of the profile configuration order in the execution plan. This is documented as a design limitation in the thesis Limitations section (ref: DEV-43 on extensibility steps).

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-49 — `airbyte-api` package removed during `dbt-postgres` installation due to `protobuf` conflict; reinstalled manually

**Issue found during Session 7 smoke tests:** Installing `dbt-postgres` upgraded `protobuf` to version 6.33.6. This was incompatible with `airbyte-api 0.53.0`'s `grpcio-tools` dependency (which required `protobuf<5.0`). The pip resolver removed `airbyte-api` from the environment as a result. This caused `ModuleNotFoundError: No module named 'airbyte_api'` during the Session 7 smoke tests.

**Fix:** Manually reinstalled `airbyte-api==0.53.0` after dbt-postgres installation. The two packages now coexist with a `protobuf` conflict warning (not error) — `grpcio-tools 1.62.3` warns about incompatible `protobuf 6.33.6`, but `airbyte_api` itself imports cleanly since it doesn't directly use the conflicting gRPC features at runtime.

**Note for future installations:** When installing new packages, verify `airbyte_api` still imports: `python -c "import airbyte_api; print('OK')"`. If it fails, run `pip install "airbyte-api==0.53.0"` to restore it.

**Files changed:** Python environment only (no code changes)

---

### LIM-01 update — Airbyte with cloud API sources (Faker) IS supported; original limitation was specific to local CSV files

**Original LIM-01:** PandasLoader is DuckDB-specific; Supabase scenario must use AirbyteConnector for ingestion.

**Update (Session 7):** The original concern about Airbyte not supporting local CSV files was correct for Airbyte Cloud — Airbyte Cloud only supports cloud-to-cloud connectors and cannot ingest local filesystem files. However, Airbyte CAN be used with cloud API sources such as the built-in "Sample Data (Faker)" connector. Session 7 tests the Airbyte Faker → Supabase scenario, which is a fully cloud-native, Airbyte-supported scenario. LIM-01 is therefore refined as follows:

- **Airbyte Cloud + local CSV files**: NOT supported (as originally noted). Use PandasLoader (DuckDB only) or a direct PostgreSQL loader instead.
- **Airbyte Cloud + cloud API sources (Faker, S3, GCS, APIs)**: SUPPORTED, as demonstrated in Session 7.
- **PandasLoader + Supabase/PostgreSQL**: NOT implemented. PandasLoader uses DuckDB's native DataFrame ingestion. For PostgreSQL targets, a `PostgresLoader` tool class would be needed (future improvement).

**Files changed:** None (documentation only)

---

## Session 7 live test deviations

### DEV-50 — Credential pre-injection + placeholder substitution pattern

**Discovered during:** Session 7 planning (DEV-50 was pre-logged; implementation confirmed correct during live run).

**Problem:**
`team.run()` is a batch async loop with no stdin injection mechanism between rounds. When CREDENTIAL_REQUEST tasks tried to collect credentials from inside the agent loop (via `RoleZero.ask_human`), the agent would pause, wait for stdin, block the entire async loop, and then resume — but `ask_human` in an async context proved unreliable for multi-value credential collection. The run also had no way to pass collected values back into subsequent task `tool_args` (which contained literal placeholder strings like `"AIRBYTE_CLIENT_ID_FROM_TASK_2"`).

**Implementation:**

Three changes to `BIAnalyticsEngineer`:

1. **`inject_credentials(credentials: dict[str, str])`** — public method called by the run script before `team.run()`. Stores credential values keyed by placeholder name (e.g. `"AIRBYTE_CLIENT_ID_FROM_TASK_2": "abc-123"`).

2. **`_substitute_placeholders(obj)`** — recursive resolver. Before each task dispatch, `tool_args` is passed through this method. It handles:
   - Direct key lookup in `self._credentials` (e.g. `"SUPABASE_PROJECT_URL_FROM_TASK_1"` → project URL string).
   - Pattern `"KEY_FROM_TASK_N"` — looks up task N's stored result dict for a field whose name matches the prefix (e.g. `"DESTINATION_ID_FROM_TASK_4"` → `self._task_results["4"]["destination_id"]`).
   - Recursive traversal of nested dicts and lists — all placeholder strings are resolved regardless of nesting depth.
   - Non-matching strings returned unchanged.

3. **`_extract_task_result(task_id, result)`** — after each successful dispatch, parses the result string as a dict (via `ast.literal_eval` then `json.loads`) and stores it in `self._task_results[task_id]`. This enables downstream tasks to reference results like `destination_id` or `connection_id` via the `_FROM_TASK_N` placeholder pattern.

4. **CREDENTIAL_REQUEST task handling** — `_dispatch()` now returns an immediate acknowledgment string `"CREDENTIAL_REQUEST acknowledged. N credential value(s) available in system memory."` for `CREDENTIAL_REQUEST` tasks, instead of attempting any tool dispatch. Credentials are already loaded; these tasks act purely as dependency gates.

5. **Run script** (`run_session7_live.py`) — `_collect_credentials()` function collects all Supabase + Airbyte credentials interactively from stdin before the `team.run()` call. Collected values are injected via `alex.inject_credentials(credentials)`. CREDENTIAL_REQUEST task instructions are overridden in the plan to tell the LLM not to call `ask_human` for these tasks.

**Why:**
Collecting credentials outside the agent loop (before `team.run()`) and injecting them deterministically avoids the stdin-in-async-loop problem. The placeholder substitution system makes the execution plan JSON self-documenting — every `tool_args` value is either a literal or a named placeholder, making it clear which values depend on user input or prior task results.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`, `ClaudeCode_implementation/tests/run_session7_live.py`

---

### DEV-51 — execution_plan_supabase.json: `api_key` → `client_id`/`client_secret`; task 5 `source_definition_id` → `source_type: "faker"`; Supabase/Airbyte credential instructions corrected

**Discovered during:** Session 7 live test runs (multiple Task 4 and Task 5 failures).

**Problems:**

1. **Task 2 (CREDENTIAL_REQUEST):** Original instruction asked for only `api_key` + `workspace_id` for Airbyte. Airbyte Cloud uses OAuth2 application credentials: separate `client_id` and `client_secret`. Updated to ask for three values: Client ID, Client Secret, Workspace ID, with step-by-step navigation to Airbyte Cloud > User Settings > Applications.

2. **Tasks 4/5/6 `tool_args`:** All contained `"api_key": "AIRBYTE_API_KEY_FROM_TASK_2"`. Replaced with two fields: `"client_id": "AIRBYTE_CLIENT_ID_FROM_TASK_2"`, `"client_secret": "AIRBYTE_CLIENT_SECRET_FROM_TASK_2"`.

3. **Task 5 `source_config`:** Had `"source_definition_id": "e1ead99e-0f8e-4f56-a8e7-5f6c2bb0a7e6"` — this UUID was stale. Airbyte Cloud Public API v1 returns HTTP 404 `STANDARD_SOURCE_DEFINITION` for all standard connectors accessed via `definitionId`. Replaced with `"source_type": "faker"` (see DEV-58).

4. **Task 1 (CREDENTIAL_REQUEST):** Supabase navigation instructions referred to wrong UI path. Corrected: PostgreSQL URI is obtained from the green "Connect" button on the main project dashboard (not Project Settings), Connection method = "Session pooler", Type = "URI", port 5432. Direct connection (`db.xxx.supabase.co:5432`) does not resolve on free-tier Supabase — Session pooler URI (`*.pooler.supabase.com:5432`) is required.

**Files changed:** `ClaudeCode_implementation/test_data/execution_plan_supabase.json`

---

### DEV-55 — AirbyteConnector.configure() reworked: manual OAuth2 token exchange replaces SDK auth

**Discovered during:** Session 7 live test, Task 4 — `AirbyteAPI.__init__() got an unexpected keyword argument 'api_key'`.

**Root cause (three compounding issues):**

1. **Original implementation** called `AirbyteAPI(api_key=api_key)` directly. The `airbyte-api` 0.53.0 SDK does not accept `api_key` as a keyword argument to `AirbyteAPI.__init__()` — it requires `security=Security(...)`.

2. **First fix attempt** used `Security(bearer_auth=api_key)` where `api_key` was a raw API key string. This produced HTTP 401 Unauthorized from the Airbyte API — Airbyte Cloud Applications do not issue raw Bearer tokens; they issue OAuth2 `client_id` + `client_secret` pairs that must be exchanged for a token via the token endpoint.

3. **Second fix attempt** used `Security(client_credentials=SchemeClientCredentials(client_id=..., client_secret=...))`. The SDK's built-in OAuth2 client-credentials flow still returned HTTP 401 — the SDK's internal token exchange used an incorrect token URL or request format.

**Final implementation (manual OAuth2 exchange):**
```python
def configure(self, client_id: str, client_secret: str, workspace_id: str, base_url: str | None = None) -> str:
    api_base = (base_url or "https://api.airbyte.com/v1").rstrip("/")
    token_url = f"{api_base}/applications/token"

    resp = requests.post(
        token_url,
        json={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Airbyte token exchange failed (HTTP {resp.status_code}): {resp.text}. ...")

    access_token = resp.json().get("access_token") or resp.json().get("accessToken")
    self._client = AirbyteAPI(security=Security(bearer_auth=access_token), server_url=api_base)
    self._workspace_id = workspace_id
```

This POSTs directly to `/applications/token` with `grant_type: "client_credentials"`, extracts the `access_token`, then passes it as a `Security(bearer_auth=access_token)` Bearer token to the SDK. This bypasses the SDK's unreliable built-in OAuth2 handling entirely.

**Signature change:** `configure(api_key, workspace_id, base_url?)` → `configure(client_id, client_secret, workspace_id, base_url?)`. The `api_key` parameter is replaced by two separate parameters matching the Airbyte Cloud Applications model.

**Impact:** `_run_airbyte()` in `bi_analytics_engineer.py` updated to pass `client_id=` and `client_secret=` instead of `api_key=`.

**Files changed:** `metagpt/tools/bi/airbyte_connector.py`, `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-56 — AirbyteConnector.trigger_sync(): HTTP 409 "already running" recovery

**Discovered during:** Session 7 live test, Task 6 second attempt — HTTP 409 after first sync attempt succeeded but polling crashed.

**Problem:**
The first `trigger_sync()` call succeeded (sync job started), but `wait_for_sync()` crashed due to the `get_sync_status()` wrong-kwarg bug (DEV-57). The agent's ReAct loop retried `trigger_sync()`, which returned HTTP 409 `"A sync is already running for this connection"`. The retry loop was stuck: every `trigger_sync()` returned 409 with an exception, but the running job's `job_id` was not returned.

**Implementation:**
```python
except Exception as exc:
    if "409" in str(exc) or "already running" in str(exc).lower():
        list_resp = client.jobs.list_jobs(
            request=lj.ListJobsRequest(connection_id=connection_id, limit=1)
        )
        jobs = list_resp.jobs_response.data if list_resp.jobs_response else []
        if jobs:
            running = jobs[0]
            return {"job_id": running.job_id, "status": running.status}
    raise
```

When a 409 is caught, `list_jobs(connection_id=connection_id, limit=1)` fetches the currently running job and returns its `job_id` in the same `{"job_id": ..., "status": ...}` format as a successful `create_job()`. The caller (`wait_for_sync()`) then polls the running job normally without triggering a duplicate.

**Note:** `list_jobs()` also requires a `ListJobsRequest` wrapper (not bare kwargs) — discovered alongside DEV-57.

**Files changed:** `metagpt/tools/bi/airbyte_connector.py`

---

### DEV-57 — AirbyteConnector.get_sync_status(): `GetJobRequest` wrapper required

**Discovered during:** Session 7 live test, Task 6 — `Jobs.get_job() got an unexpected keyword argument 'job_id'`.

**Problem:**
The original `get_sync_status()` called:
```python
resp = client.jobs.get_job(job_id=int(job_id))
```
The `airbyte-api` SDK does not accept bare `job_id=` as a keyword argument to `get_job()`. It requires a `GetJobRequest` wrapper object:
```python
import airbyte_api.api.getjob as gj
resp = client.jobs.get_job(request=gj.GetJobRequest(job_id=int(job_id)))
```

The same pattern applies to `list_jobs()` — it requires `ListJobsRequest(connection_id=...)` (see DEV-56).

**Implementation:** Fixed to use `gj.GetJobRequest(job_id=int(job_id))` wrapper. Also added `job_id` integer cast since `job_id` is stored/passed as a string.

Additionally, `get_sync_status()` now normalises the status value:
```python
status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
```
This handles both enum and string status representations from the SDK.

**Files changed:** `metagpt/tools/bi/airbyte_connector.py`

---

### DEV-58 — AirbyteConnector.setup_connection(): `definitionId` replaced by `source_type` + `_SOURCE_TYPE_MAP` + typed `SourceFaker` config

**Discovered during:** Session 7 live test, Task 5 — HTTP 404 `STANDARD_SOURCE_DEFINITION` error when creating Faker source via `definitionId`.

**Problem:**
The original `setup_connection()` passed `definition_id="e1ead99e-0f8e-4f56-a8e7-5f6c2bb0a7e6"` (the Faker source definition UUID) via:
```python
models.SourceCreateRequest(
    ...
    definition_id=definition_id,
)
```
Airbyte Cloud Public API v1 dropped support for `definitionId` for standard connectors (those bundled with Airbyte Cloud). All standard connectors must now be created via a typed connector configuration object (e.g. `SourceFaker`) passed to the `configuration` field — not via `definitionId`. The API returns HTTP 404 with error code `STANDARD_SOURCE_DEFINITION` for any `definitionId` that maps to a standard connector.

**Implementation:**

Added `_SOURCE_TYPE_MAP` class attribute:
```python
_SOURCE_TYPE_MAP: dict[str, str] = {
    "faker": "SourceFaker",
}
```

Updated `setup_connection()` to check `source_config["source_type"]`. If the type is in the map, it builds a typed configuration object using `dataclasses.fields()` to filter only valid fields:
```python
if src_type in self._SOURCE_TYPE_MAP:
    cls_name = self._SOURCE_TYPE_MAP[src_type]
    cfg_cls = getattr(models, cls_name)
    valid_fields = {f.name for f in dataclasses.fields(cfg_cls)}
    filtered = {k: v for k, v in cfg_params.items() if k in valid_fields}
    configuration = cfg_cls(**filtered)
    definition_id = None
else:
    configuration = cfg_params
    definition_id = source_config.get("source_definition_id")
```

**Execution plan impact (DEV-51):** Task 5 `source_config` in `execution_plan_supabase.json` updated from `"source_definition_id": "e1ead99e-..."` to `"source_type": "faker"`.

**Extensibility:** To support a new standard Airbyte connector, add its lowercase `source_type` string → SDK class name mapping to `_SOURCE_TYPE_MAP`. Non-standard or private connectors continue to use the `source_definition_id` path.

**Files changed:** `metagpt/tools/bi/airbyte_connector.py`, `ClaudeCode_implementation/test_data/execution_plan_supabase.json`

---

## Session 7 live test results

**Date:** 2026-05-08  
**All 11 tasks completed successfully.** Execution report saved to `workspace/docs/execution_report.md`.

**Live test task outcomes:**

| Task | Type | Result |
|------|------|--------|
| 1 | CREDENTIAL_REQUEST | Acknowledged — 9 credential values loaded |
| 2 | CREDENTIAL_REQUEST | Acknowledged — 9 credential values loaded |
| 3 | INSTANTIATION (SupabaseConnector) | Connected to Supabase at `ilxlvrxrdonbizshtlam.supabase.co` |
| 4 | INSTANTIATION (AirbyteConnector) | Destination `Supabase DWH` created (ID: `d843a17c-...`) |
| 5 | CONNECTION_SETUP (AirbyteConnector) | Faker source + connection created (connection_id: `a115119f-...`) |
| 6 | DATA_INGESTION (AirbyteConnector) | Sync job `83467384` succeeded; streams: users, products, purchases |
| 7 | CONNECTION_SETUP (DbtRunner postgres) | Profile configured for Supabase public schema |
| 8 | TRANSFORMATION (dim_customer) | Model corrected (removed unavailable `company` column); built as view |
| 9 | TRANSFORMATION (dim_product) | Model corrected (removed unavailable `name` column); built as view |
| 10 | TRANSFORMATION (dim_date) | Built successfully |
| 11 | TRANSFORMATION (fact_purchases) | Model corrected (schema alignment); built as view |

**Self-correction behaviour (Tasks 8, 9, 11):** The LLM-generated SQL initially referenced columns that differed from the actual Faker schema. Alex's ReAct loop detected the dbt runtime errors, rewrote the SQL via `DbtRunner.write_model()`, and retried successfully — demonstrating the correction loop working as designed.

---

## Session 8 deviations

### DEV-59 — `generate_validation_report()` exposed with 2 parameters instead of 6

**Theoretical design:**  
The thesis and `IMPLEMENTATION_SPEC.md` specify `generate_validation_report()` with 6 parameters: `structural_validation_results`, `traceability_validation_results`, `brd_summary`, `logical_schema`, `execution_plan`, `dwh_connection_details`.

**Implementation:**  
Only 2 parameters are exposed in the `@register_tool` interface: `structural_validation_results` and `traceability_validation_results`. The other 4 reference artifacts (`brd_summary`, `logical_schema`, `execution_plan`, `dwh_connection_details`) are retrieved from `self.rc.memory` internally using `_get_from_memory()`, following the DEV-28 pattern.

The Agent 5 prompt file (`metagpt/prompts/bi/bi_qa_engineer.py`) was updated in Session 8 to reflect this: the Core tools section lists the 2-parameter signature; Phase 3 specifies the 2-parameter call with a `**MANDATORY**` guard ("You MUST call BIQAEngineer.generate_validation_report() before calling end"); the correction cycle section was also updated to use the 2-parameter form.

**Why:**  
Passing four large documents (BRD ~5 KB, logical schema ~3 KB, execution plan ~8 KB, execution report ~5 KB) as JSON string arguments to an LLM-driven tool call would consume an additional ~21 KB of tokens per call in both the outgoing tool call and the LLM's reasoning context. These documents are already in the shared message pool; retrieving them from memory avoids double-token consumption and eliminates the risk of truncation for longer documents. This is the same rationale as DEV-28 (applied to `generate_brd`, `generate_data_model`, `publish_execution_plan`, `publish_execution_report`).

---

### DEV-60 — `validation_round_allowed` is a configurable Pydantic field, not a hard-coded constant

**Theoretical design:**  
`IMPLEMENTATION_SPEC.md` specifies a fixed maximum of 3 correction rounds before the pipeline stops with a failed validation report. The thesis does not specify a number.

**Implementation:**  
`validation_round_allowed: int = 3` is declared as a Pydantic field on `BIQAEngineer`, defaulting to 3. It can be overridden at instantiation time: `BIQAEngineer(validation_round_allowed=5)`.

**Why:**  
The number of allowed correction rounds is a deployment-time tuning parameter, not a hard-wired architectural constant. Making it configurable allows users running the BI pipeline programmatically (e.g. in `bi_team.py`) to adjust the budget without modifying the source code. The default of 3 preserves the spec's intent.

---

### DEV-61 — Exhausted-rounds report saved to `failed_validation_report.md` without publishing

**Theoretical design:**  
The thesis states that if all correction rounds are exhausted, the pipeline stops and the human user can consult the final Validation Feedback Report. It does not explicitly specify the file path or whether the message should be published.

**Implementation:**  
When `_validation_round >= validation_round_allowed` and the outcome is REJECTED, the report is saved to `workspace/docs/failed_validation_report.md` instead of `workspace/docs/validation_feedback_report.md`, and `publish_message()` is **not** called.

**Why:**  
`BIAnalyticsEngineer` watches for `WriteValidationReport` messages. If the exhausted-rounds report were published with `cause_by=WriteValidationReport`, Alex would be re-triggered for a correction cycle that cannot succeed (the round limit has already been reached). Saving to a distinct path and suppressing publication ensures Alex is never re-triggered, the pipeline stops cleanly, and the human user can inspect the failure report at its known location.

---

## Session 9 pre-logged items

### LIM-02 — CSV → Supabase scenario not supported; to be resolved in Session 9

**Current state:**  
The two implemented scenarios use matched ingestion–target pairs:
- Scenario A: local CSV files → DuckDB (via `PandasLoader`, DuckDB-specific)
- Scenario B: Airbyte Faker API → Supabase (via `AirbyteConnector`)

A third scenario — local CSV files → Supabase/PostgreSQL — is not supported because `PandasLoader` writes directly into DuckDB using `duckdb.read_csv_auto()` and cannot target a PostgreSQL database.

**Resolution planned for Session 9:**  
Add `SupabaseConnector.load_csv(file_path, table_name, schema="public")` method that:
1. Reads the CSV file with pandas (`pd.read_csv(file_path)`)
2. Creates the target table in Supabase via `run_ddl()` (inferring column types from the DataFrame)
3. Bulk-inserts rows using `psycopg2.extras.execute_values()` over the existing `self._conn` direct PostgreSQL connection
4. Returns the row count

One additional line needed in `BIAnalyticsEngineer._dispatch()`: route `DATA_INGESTION` tasks with `tool: "SupabaseConnector"` to `SupabaseConnector.load_csv()`. The existing `tool: "PandasLoader"` path for DuckDB is unchanged.

This gives a complete scenario matrix:

| Scenario | Ingestion tool | Target DWH | Status |
|----------|---------------|-----------|--------|
| A | PandasLoader.load_file() | DuckDB | ✅ Tested (Session 6) |
| B | AirbyteConnector (Faker API) | Supabase | ✅ Tested (Session 7) |
| C | SupabaseConnector.load_csv() | Supabase | ➕ Session 9 |

**Files to change:** `metagpt/tools/bi/supabase_connector.py` (add method), `metagpt/roles/bi/bi_analytics_engineer.py` (one dispatch line).

---

### LIM-03 — Agent 1 cannot inspect Airbyte sources during elicitation; schema discovery deferred to Agent 4

**Current state:**  
`DataSourceInspector` has `inspect_csv()`, `inspect_postgres()`, and `inspect_api()` (generic HTTP). For Airbyte-sourced data, Agent 1 (Alice) cannot discover the stream schema during Phase 1 elicitation because:
1. The Airbyte source may not yet exist in the workspace at elicitation time.
2. Even if it does, querying Airbyte's catalog API (`GET /v1/sources/{sourceId}/discover_schema`) requires an OAuth token and a source ID that Alice does not currently obtain.

As a result, the BRD for Airbyte scenarios is written based on the user's verbal description of the data, and actual schema validation happens at Agent 4's execution time (DATA_INGESTION tasks).

**Improvement planned for Session 9:**  
Add `DataSourceInspector.inspect_airbyte_source(workspace_id, source_id, client_id, client_secret)` that:
1. Exchanges `client_id`/`client_secret` for a Bearer token (reusing the OAuth logic already in `AirbyteConnector.configure()`)
2. Calls `GET /v1/sources/{source_id}/discover_schema`
3. Returns a structured schema dict: `{stream_name: [{field, type}, ...]}`

**Pre-condition for Scenario B:** The Airbyte Faker source must already exist in the user's Airbyte Cloud workspace at elicitation time. It can be created in one click in the Airbyte Cloud UI ("Add source → Sample Data (Faker)") or by running Agent 4's INSTANTIATION task first. The source created in Session 7 (`connection_id: a115119f-c7a0-40c3-87d0-68ab4f99bd6d`) may still exist.

**Alice's elicitation flow with this improvement:**  
If the user says "I have data accessible through Airbyte", Alice recognises the source type and asks for workspace ID, client ID, client secret, and source ID. She then calls `DataSourceInspector.inspect_airbyte_source()` and receives the actual stream schemas to base the BRD on.

**Files to change:** `metagpt/tools/bi/data_source_inspector.py` (add method), `metagpt/prompts/bi/bi_requirements_analyst.py` (add inspect_airbyte_source to the Core tools section).

---

### NOTE — README: adding a new external tool requires 5 steps including prompt updates

When documenting how to extend the system in the README (planned post-Session 9), the developer instructions for adding a new external tool must include **all five** of the following steps:

1. **Write the tool class** in `metagpt/tools/bi/<tool_name>.py` and decorate with `@register_tool` if the LLM should call it directly.
2. **Add to the agent's `tools` list** in the role class (e.g. `metagpt/roles/bi/bi_analytics_engineer.py`) — this makes the tool's schema visible to the LLM via `TOOL_REGISTRY`.
3. **Wire the callable** in `_update_tool_execution()` in the same role class — without this the RoleZero dispatcher cannot find the method even if the LLM selects it.
4. **Update `_dispatch()` / `execute_BI_task()`** if the tool handles a new task type or a new ingestion/execution path for Agent 4.
5. **Update the agent's prompt** (`metagpt/prompts/bi/bi_<agent>.py`) — add the tool name and its key methods to the "Core tools" section. This is the step most likely to be forgotten, and without it the LLM will not know the tool exists at reasoning time even if it appears in the schema registry.

Steps 2 and 3 are often confused: step 2 makes the schema available, step 3 makes the callable available. Both are required.

---

### NOTE — Session 9 e2e tests must start from a clean workspace

**Problem:** Sessions 6, 7, and 8 all write to the same `workspace/` directory. By the end of Session 8, `workspace/` contains a mix of DuckDB artifacts (from Session 6), Supabase artifacts (from Session 7 which overwrote Session 6), and the REJECTED validation report (from Session 8). Running Session 9's full pipeline tests against this contaminated state would produce misleading results.

**Two complementary solutions to implement in Session 9:**

1. **Per-run workspace isolation in `bi_team.py`** (see workspace isolation note above): each `bi_team.py` invocation creates a fresh `workspace/runs/<timestamp_or_run_name>/` subdirectory. Editor and all agents write there. No cross-run contamination possible by design.

2. **Workspace reset utility**: the Session 9 e2e test scripts (and the `bi_team.py` help text) should document how to reset the workspace to a clean state before a fresh run:
   - If using per-run isolation: no reset needed — just start a new run.
   - If re-running with the default `workspace/` path: delete or archive `workspace/docs/`, `workspace/dwh.duckdb`, `dbt_projects/bi_dwh/` before starting. The `workspace/data/` CSV files are source data and should be left in place.

**What "clean" means per scenario:**

| Artifact | DuckDB scenario | Supabase scenario |
|----------|----------------|------------------|
| `workspace/docs/` | delete all .md and .json files | delete all .md and .json files |
| `workspace/dwh.duckdb` | delete | not applicable |
| `dbt_projects/bi_dwh/` | delete | delete |
| Supabase tables | not applicable | drop via Supabase Studio or psql |
| `workspace/data/*.csv` | keep (source data) | keep (Scenario C only) |

---

## Session 9 deviations

### DEV-62 — `publish_execution_report()` hardcoded path replaced with `config.workspace.path`

**Discovered during:** Session 9 implementation of per-run workspace isolation.

**Problem:**
`BIAnalyticsEngineer.publish_execution_report()` contained a hardcoded `Path("workspace") / "docs" / "execution_report.md"` path. When `bi_team.py` sets `config.workspace.path = workspace/runs/<timestamp>/`, MetaGPT's Editor writes all artifacts to the per-run directory — but `publish_execution_report()` was still looking for the report at the root `workspace/docs/` path. The file would not exist there, and the QA Engineer would never be triggered.

**Implementation:**
Changed the path to:
```python
report_path = Path(config.workspace.path) / "docs" / "execution_report.md"
```
This matches the path used by MetaGPT's Editor when `config.workspace.path` is set to the per-run directory by `bi_team.py`. For test scripts that do not call `_setup_workspace()`, `config.workspace.path` defaults to `workspace/` — preserving backward compatibility.

**Why:**
Per-run isolation is a key Session 9 feature. Without this fix, every run after the first would fail silently: the execution report would be written to the correct per-run path, but `publish_execution_report()` would report "Report file not found" and never publish to the shared message pool, leaving the QA Engineer idle.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`

---

### DEV-63 — `ask_human` override added to BIAnalyticsEngineer; CREDENTIAL_REQUEST updated to interactive thesis design

**Theoretical design:**
The thesis design specified that during a CREDENTIAL_REQUEST task, Agent 4 (Alex) would ask the user interactively for credentials (API keys, project URLs) during the pipeline run — including providing sign-up links and instructions if the user does not yet have an account.

**Problem:**
DEV-50 (Session 7) changed CREDENTIAL_REQUEST handling to a pre-injection / placeholder-substitution pattern because `ask_human` in the async `team.run()` loop proved unreliable for multi-value credential collection. This was documented as a practical PoC compromise. However, for the full `bi_team.py` entry point (the thesis demo), the interactive design should be supported.

`BIAnalyticsEngineer` did not override `ask_human`, so it inherited the RoleZero default which returns "Not in MGXEnv, command will not be executed." in terminal mode.

**Implementation:**
1. **`ask_human` override added to `BIAnalyticsEngineer`** — same pattern as DEV-15 (BIRequirementsAnalyst):
   ```python
   async def ask_human(self, question: str) -> str:
       print(f"\n[Alex - BI Analytics Engineer]: {question}\n")
       loop = asyncio.get_running_loop()
       response = await loop.run_in_executor(None, input, "Your response: ")
       return response.strip()
   ```

2. **`metagpt/prompts/bi/bi_analytics_engineer.py` CREDENTIAL_REQUEST section updated:**
   - Step 1: Call `RoleZero.ask_human` with a clearly worded message (system, credential type, where to find it; include sign-up URL and steps if account creation is needed).
   - Step 3: Store the received value in working memory.
   - Step 4: Call `BIAnalyticsEngineer.execute_BI_task(task)` to mark complete.
   - Step 5: Pass actual collected values in subsequent task `tool_args` — NOT placeholder strings.
   - Constraint #5 updated to note that pre-injection (non-interactive) mode (DEV-50 pattern) also works: `execute_BI_task` returns an acknowledgment if credentials were pre-loaded.

**Why:**
The thesis design is the primary demo path; pre-injection (DEV-50) remains available as a robustness fallback for test scripts. The `ask_human` override ensures the interactive path actually works in terminal mode. The two designs are compatible: if credentials are pre-injected, `execute_BI_task` handles CREDENTIAL_REQUEST acknowledgment transparently; if not, the LLM calls `ask_human` and the user provides them live.

**Files changed:** `metagpt/roles/bi/bi_analytics_engineer.py`, `metagpt/prompts/bi/bi_analytics_engineer.py`

---

### LIM-02 — RESOLVED: `SupabaseConnector.load_csv()` implemented (CSV → Supabase scenario)

**Original limitation (pre-logged in Session 8):**
No tool could load local CSV files into a Supabase/PostgreSQL target. Scenario C (CSV → Supabase) was therefore unsupported.

**Resolution (Session 9):**
`SupabaseConnector.load_csv(file_path, table_name, schema="public")` implemented:
1. Reads CSV with pandas `pd.read_csv(file_path)`.
2. Infers PostgreSQL column types from pandas dtypes (`int` → `BIGINT`, `float` → `DOUBLE PRECISION`, `bool` → `BOOLEAN`, `datetime` → `TIMESTAMP`, else → `TEXT`).
3. Creates the table if it does not exist via `run_ddl()` (`CREATE TABLE IF NOT EXISTS`).
4. Bulk-inserts all rows via `psycopg2.extras.execute_values(page_size=500)` over the existing direct PostgreSQL connection.
5. Returns a confirmation string with row count.

Additionally, `BIAnalyticsEngineer._run_supabase()` routes `DATA_INGESTION` tasks to `connector.load_csv()`:
```python
if task_type == "DATA_INGESTION":
    load_result = connector.load_csv(
        file_path=tool_args.get("file_path", ""),
        table_name=tool_args.get("target_table", tool_args.get("table_name", "")),
        schema=tool_args.get("schema", "public"),
    )
    return f"{result} | {load_result}"
```

**Complete scenario matrix after Session 9:**

| Scenario | Ingestion tool | Target DWH | Status |
|----------|---------------|-----------|--------|
| A | PandasLoader.load_file() | DuckDB | ✅ Tested (Session 6) |
| B | AirbyteConnector (Faker API) | Supabase | ✅ Tested (Session 7) |
| C | SupabaseConnector.load_csv() | Supabase | ✅ Implemented (Session 9) |

**Files changed:** `metagpt/tools/bi/supabase_connector.py`, `metagpt/roles/bi/bi_analytics_engineer.py`

---

### LIM-03 — RESOLVED: `DataSourceInspector.inspect_airbyte_source()` implemented; wired into Alice's elicitation

**Original limitation (pre-logged in Session 8):**
Agent 1 (Alice) could not inspect Airbyte sources during elicitation. The BRD for Airbyte scenarios was based on verbal description only.

**Resolution (Session 9):**
`DataSourceInspector.inspect_airbyte_source(workspace_id, source_id, client_id, client_secret, base_url="https://api.airbyte.com/v1")` implemented:
1. Exchanges `client_id` / `client_secret` for a Bearer token via `POST {api_base}/applications/token` — reuses the same OAuth2 flow as `AirbyteConnector.configure()` (DEV-55).
2. Calls `POST {api_base}/sources/{source_id}/discover_schema` to retrieve the catalog.
3. Parses the catalog: for each stream, builds a `{field_name: type}` dict, resolving JSON Schema `["string", "null"]` array types by picking the non-null type.
4. Returns `{"source_id": ..., "workspace_id": ..., "streams": {stream_name: [{name, type}, ...]}}`.

**Pre-condition:** The Airbyte source must already exist in the user's workspace. Alice asks for `workspace_id`, `source_id`, `client_id`, and `client_secret` before calling this method.

**Wired into Alice's `tool_execution_map`:**
```python
"DataSourceInspector.inspect_airbyte_source": inspector.inspect_airbyte_source,
```

**`bi_requirements_analyst.py` prompt updated:** Added `inspect_airbyte_source` to the Core tools section with its signature and usage guidance; updated the data sources elicitation topic to mention Airbyte sources.

**Design note:** The pre-condition (source must already exist) is a limitation inherent to the Airbyte Cloud API — Alice cannot create a source during elicitation. This is documented as expected in the thesis: the user creates the Airbyte source first (one click in Airbyte Cloud UI), then provides the IDs to Alice for schema discovery.

**Files changed:** `metagpt/tools/bi/data_source_inspector.py`, `metagpt/roles/bi/bi_requirements_analyst.py`, `metagpt/prompts/bi/bi_requirements_analyst.py`

---

### NOTE — bi_team.py LLM cost summary

**New feature (Session 9):**
`bi_team.py` now appends a `## LLM Cost Summary` markdown table to the validation feedback report (or failed validation report) after `team.run()` completes. The summary is also printed to the terminal. Values are read from MetaGPT's `CostManager`:

```python
cm = team.cost_manager
prompt_tokens = cm.total_prompt_tokens
completion_tokens = cm.total_completion_tokens
total_cost_usd = cm.total_cost
```

This gives the human user a direct cost estimate at the end of each pipeline run, visible in both the terminal output and the final artifact delivered by the QA Engineer.

**Files changed:** `bi_team.py`

---

### NOTE — README thesis title corrected; Claude Code acknowledgement section added (Session 9 continuation)

**Thesis title correction:**
The short thesis description in `README.md` was updated from a working description to the final official title and subtitle:
> "Where AI Adds Value: Designing a BI development Multi-Agent Architecture —  
> A Contextual Transposition of Software Engineering Patterns"  
> Jonathan Dierckx — Double degree Master's student, UNamur / KU Leuven, 2026

**Acknowledgements section added to README.md:**
Two new subsections under a dedicated "Acknowledgements" heading (placed between "Based on MetaGPT" and "Implementation sessions"):

1. **Claude Code** — states that the implementation was AI-assisted via [Claude Code](https://claude.ai/code) (Anthropic), and directs readers to `ClaudeCode_implementation/` for the full record of how the implementation was performed (IMPLEMENTATION_PROGRESS.md, DEVIATIONS_AND_CLARIFICATIONS.md, tests/).
2. **Thesis context** — provides the full title, programme, and institutions for readers wanting the full academic framing.

**Files changed:** `README.md` (documentation only — no code changes)

---

### LIM-04 — Architecture is one-shot and full-load; no orchestration, scheduling, or incremental refresh

**Nature:** Architectural scope limitation — relevant for the thesis Limitations and Future Work sections.

**What the PoC does:**
Each `metagpt-bi` invocation runs the full five-agent pipeline exactly once, producing a complete DWH snapshot in a new isolated workspace directory (`workspace/runs/<timestamp>/`). All source data is loaded in full on every run.

**What the PoC does NOT do:**

| Missing capability | What a production BI system would have |
|-------------------|----------------------------------------|
| Scheduled / automatic refresh | An orchestrator (Airflow, Prefect, dbt Cloud) that re-triggers the pipeline on a defined schedule |
| Incremental loading | Watermark-based or change-data-capture logic so only new/changed rows are loaded; the PoC always does full table replacements |
| DWH lifecycle management | Schema migration, versioned reruns against an existing warehouse, idempotent partial updates |
| Monitoring and alerting | Pipeline failure notifications, data freshness SLA checks, row-count anomaly detection |
| DWH update / refresh | Each run creates a new warehouse; there is no "refresh the existing DWH" mode |

**Why acceptable for PoC:**
The thesis evaluates whether the multi-agent architecture can autonomously *design and build* a BI back-end — not whether it can *operate* one. The one-shot nature is a deliberate scope boundary. The refresh frequency is captured in the BRD and execution plan as metadata, but the actual scheduling is explicitly out of scope.

**How it could be extended (for Future Work section):**
The dbt project generated by Alex is a standard dbt project. It can be wrapped with any standard orchestration tool post-generation (e.g. an Airflow DAG that runs `dbt run` on a schedule) without any changes to the agent architecture. Incremental loading would require either (a) prompting Eve to include watermark logic in the execution plan, or (b) a post-processing step that rewrites the generated dbt models as incremental models.

**What to update in thesis:**
Add to the Limitations section: the architecture produces a one-shot, full-load DWH build and does not include an operational refresh cycle. Frame it as a scope boundary of the PoC, not an architectural constraint of the multi-agent approach itself.
