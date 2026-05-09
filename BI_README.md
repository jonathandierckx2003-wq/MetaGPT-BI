# MetaGPT-BI — Agentic BI Architecture

An extension of the MetaGPT multi-agent framework into the Business Intelligence domain. Five specialized BI agents collaborate via a document-driven, publish-subscribe shared message pool to autonomously build a complete BI back-end: from requirements elicitation to a validated, ready-to-use Data Warehouse.

**Thesis:** "A transposition of a multi-agent framework for automated software development to the BI domain"  
Jonathan Dierckx — KU Leuven / UNamur, 2026

---

## How it works

```
You type:   metagpt-bi "I need a weekly sales dashboard."

Agent 1  Alice   BI Requirements Analyst   -> asks you questions -> writes BRD
Agent 2  Bob     BI Data Modeler           -> designs star schema -> Mermaid ERDs
Agent 3  Eve     BI Solution Architect     -> creates DWH Execution Plan (JSON)
Agent 4  Alex    BI Analytics Engineer     -> executes the plan (ELT pipeline)
Agent 5  Edward  BI QA Engineer            -> validates the DWH -> Validation Report

Output:  workspace/runs/<timestamp>/docs/   (all artifacts + LLM cost summary)
```

Each agent is a MetaGPT `RoleZero` ReAct agent. They communicate exclusively via typed messages in a shared message pool — no direct calls between agents. The pipeline is fully driven by the natural language requirement you provide and the answers you give Alice during the elicitation conversation.

---

## Getting started

### Step 1 — Prerequisites

- **Python 3.11 or 3.12** — [python.org](https://www.python.org/downloads/)
- **Node.js** (for Mermaid diagram rendering) — [nodejs.org](https://nodejs.org/)
- **Git** — to clone the repository
- **PowerShell** — included in Windows 10/11

Verify Python is available:
```powershell
python --version   # should print Python 3.11.x or 3.12.x
```

### Step 2 — Get the repository

```powershell
git clone https://github.com/your-org/MetaGPT-BI.git
cd MetaGPT-BI
```

### Step 3 — Run the one-time setup script

```powershell
.\setup_bi.ps1
```

If PowerShell blocks script execution, run this first:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The setup script:
1. Checks Python version
2. Creates and activates a `venv/` virtual environment
3. Installs MetaGPT-BI in editable mode (`pip install -e .`) — registers the `metagpt-bi` command
4. Installs all BI-specific packages (DuckDB, dbt, Supabase, Airbyte, psycopg2, pandas, openpyxl)
5. Creates `workspace/data/` for your source files
6. Copies the LLM config template if `config/config2.yaml` does not exist
7. Verifies all key imports

### Step 4 — Configure your LLM

Edit `config/config2.yaml`:

```yaml
llm:
  api_type: "openai"         # or "azure", "groq", "anthropic", etc.
  model: "gpt-5.4-mini"      # model used for all agents
  api_key: "sk-..."          # your API key
  max_token: 8192
```

Supported providers are documented in [docs/tutorial/usage.md](docs/tutorial/usage.md).

**Cost note:** A full 5-agent pipeline run typically uses 150,000–400,000 tokens. At gpt-5.4-mini pricing, expect $0.05–$0.20 per run. The Validation Feedback Report at the end of each run includes an exact token and cost breakdown.

### Step 5 — Activate the virtual environment

Every time you open a new PowerShell window, activate the venv before using `metagpt-bi`:

```powershell
.\venv\Scripts\Activate.ps1
```

You will see `(venv)` at the start of the prompt when the venv is active.

---

## Running a BI pipeline

### Place your source data files

Put CSV or Excel files in `workspace/data/` before starting:

```
workspace/
  data/
    sales.csv
    customers.csv
    products.csv
```

Alice (Agent 1) will ask for file paths during the elicitation conversation. She will inspect the files automatically using `DataSourceInspector`.

### Start the pipeline

```powershell
metagpt-bi "Describe your BI project in natural language."
```

Examples:
```powershell
metagpt-bi "I need a weekly sales analysis dashboard. I have CSV files with order, customer and product data."
metagpt-bi "I want a cloud BI setup to analyse e-commerce data from an API source."
metagpt-bi "Build me a marketing attribution DWH from our CRM export files."
```

Options:
```powershell
metagpt-bi "..." --rounds 250     # increase round budget (default: 200)
metagpt-bi "..." --run-name demo  # name the run directory (default: timestamp)
metagpt-bi --help
```

### What happens during the run

**Phase 1 — Elicitation (Alice, interactive):**  
Alice asks structured questions. Typical topics:
- Business goals and target audience
- Key metrics and KPIs you want to track
- Data grain (per transaction, per day, per customer…)
- Update frequency (real-time, daily batch, weekly snapshot)
- Historical data range needed
- Data quality concerns or missing fields
- Preferred DWH technology (DuckDB for local, Supabase for cloud)

Answer each question in the terminal. Alice inspects your data files automatically — you do not need to describe the schema manually.

**Phase 2 — Automated pipeline (Bob, Eve, Alex, Edward):**  
After Alice finishes, the remaining four agents run without further input:
- Bob designs the star or snowflake schema and produces Mermaid ERDs
- Eve creates a structured JSON execution plan with typed tasks
- Alex executes the plan step by step: DWH instantiation, schema creation, data ingestion, and SQL transformations via dbt
- Edward validates the built DWH against the BRD and reports ACCEPTED or REJECTED

If a cloud scenario requires credentials (Supabase, Airbyte), Alex will prompt you interactively at the relevant task. Paste the values when asked.

### Where to find the outputs

All artifacts are saved to a timestamped directory — each run is isolated and never overwrites previous ones:

```
workspace/
  runs/
    20260509_143022/
      docs/
        business_requirement_document.md       # Alice's output
        dimensional_model_specification.md     # Bob's output
        conceptual_schema.mermaid + .svg       # Bob's output
        logical_schema.mermaid + .svg          # Bob's output
        execution_plan.json                    # Eve's output
        execution_report.md                    # Alex's output
        validation_feedback_report.md          # Edward's output + LLM cost summary
```

**Accessing the DuckDB warehouse** (DuckDB scenario):
```python
import duckdb
con = duckdb.connect("workspace/dwh.duckdb")
con.execute("SHOW TABLES").fetchall()
```
Or open directly in DBeaver, Tableau, or Power BI via the DuckDB ODBC driver.

**Browsing the dbt lineage** (all scenarios):
```powershell
cd dbt_projects\bi_dwh
dbt docs generate
dbt docs serve      # opens http://localhost:8080
```

---

## Available tools

The following external tool classes are currently implemented in `metagpt/tools/bi/`. Each is decorated with `@register_tool` and appears in MetaGPT's tool registry, making its schema visible to the LLM agents.

### DuckDBExecutor
**File:** `metagpt/tools/bi/duckdb_executor.py`  
**Used by:** Alex (execution), Edward (validation)  
**Purpose:** Full DuckDB interaction — DDL, queries, schema inspection, PK/FK checks.

| Method | Description |
|--------|-------------|
| `connect(db_path)` | Open or create a DuckDB database file |
| `run_ddl(ddl)` | Execute DDL (CREATE TABLE, etc.); retries 3× on transient errors |
| `run_query(sql)` | Execute SELECT; returns list of row dicts |
| `verify_table(table_name)` | Check table existence + return column definitions |
| `list_tables()` | Return all table names in the connected DB |
| `check_pk_uniqueness(table, pk_col)` | Verify no duplicate PK values |
| `check_fk_integrity(fact_table, fk_col, dim_table, pk_col)` | Count orphan rows |

### PandasLoader
**File:** `metagpt/tools/bi/pandas_loader.py`  
**Used by:** Alex (DATA_INGESTION tasks, DuckDB scenario)  
**Purpose:** Load CSV and Excel flat files directly into DuckDB via pandas. DuckDB-specific — cannot target PostgreSQL.

| Method | Description |
|--------|-------------|
| `load_file(file_path, target_table, db_path)` | Read file -> write to DuckDB (CREATE OR REPLACE) |
| `infer_schema(file_path)` | Return column names + dtypes without loading |
| `get_row_count(file_path)` | Return number of data rows |

### DbtRunner
**File:** `metagpt/tools/bi/dbt_runner.py`  
**Used by:** Alex (TRANSFORMATION tasks, all scenarios)  
**Purpose:** Wraps dbt Core CLI. Supports both DuckDB and PostgreSQL (Supabase) profiles. The LLM calls `write_model(model_name, sql)` to write SQL, then `execute_BI_task` to run it.

| Method | Description |
|--------|-------------|
| `write_model(model_name, sql)` | Write LLM-generated SQL to `models/<name>.sql`; auto-inits project if needed |
| `configure_profile(profile_name, target, db_type, ...)` | Write `profiles.yml`; supports `duckdb` and `postgres` |
| `run_model(model_name)` | Run `dbt run --select` to materialise the model |
| `run_tests(model_name?)` | Run `dbt test` for a model or all models |
| `compile_model(model_name)` | Syntax-check without writing to DB |

### SupabaseConnector
**File:** `metagpt/tools/bi/supabase_connector.py`  
**Used by:** Alex (SCHEMA_CREATION, DATA_INGESTION tasks, Supabase scenario), Edward (validation)  
**Purpose:** Full Supabase/PostgreSQL interaction via direct psycopg2 connection. Requires `postgres_url` (Session Pooler URI) for DDL.

| Method | Description |
|--------|-------------|
| `connect(url, key, postgres_url?)` | Connect using project URL + service role key; `postgres_url` required for DDL |
| `run_ddl(ddl)` | Execute DDL; retries 3× |
| `run_query(sql)` | Execute SELECT; returns list of row dicts |
| `load_csv(file_path, table_name, schema?)` | Read CSV with pandas -> bulk-insert via psycopg2 (Scenario C) |
| `verify_table(table_name)` | Check existence + return column definitions |
| `check_pk_uniqueness(table, pk_col)` | Verify no duplicate PK values |
| `check_fk_integrity(fact_table, fk_col, dim_table, pk_col)` | Count orphan rows |

### AirbyteConnector
**File:** `metagpt/tools/bi/airbyte_connector.py`  
**Used by:** Alex (INSTANTIATION, CONNECTION_SETUP, DATA_INGESTION tasks, Airbyte scenario)  
**Purpose:** Airbyte Cloud API interactions — create sources/destinations, trigger and monitor syncs.

| Method | Description |
|--------|-------------|
| `configure(client_id, client_secret, workspace_id, base_url?)` | OAuth2 token exchange + initialise API client |
| `create_destination(destination_config)` | Create Airbyte destination (e.g. Supabase/PostgreSQL) |
| `setup_connection(source_config)` | Create source + connection to existing destination |
| `trigger_sync(connection_id)` | Start a sync job; returns `{job_id, status}` |
| `wait_for_sync(job_id)` | Blocking poll until sync reaches terminal state |
| `list_connections()` | List all connections in the workspace |

### DataSourceInspector
**File:** `metagpt/tools/bi/data_source_inspector.py`  
**Used by:** Alice (data source inspection during elicitation)  
**Purpose:** Schema discovery for various source types. Returns column names, types, row counts, and sample values so Alice can base the BRD on actual data structure.

| Method | Description |
|--------|-------------|
| `inspect_csv(file_path)` | Inspect CSV: row count + column names/dtypes/null counts + sample |
| `inspect_excel(file_path)` | Inspect Excel: per-sheet row count + column info |
| `inspect_duckdb(db_path)` | Inspect DuckDB: all tables with columns + row counts |
| `inspect_postgres(connection_string)` | Inspect PostgreSQL public schema via psycopg2 |
| `inspect_airbyte_source(workspace_id, source_id, client_id, client_secret)` | Discover stream schemas from an existing Airbyte Cloud source |

---

## Adding a new external tool

The architecture is designed to be extensible. Adding a new tool requires **5 steps across 5 files**.

### Step 1 — Write the tool class

Create `metagpt/tools/bi/<tool_name>.py`:

```python
from metagpt.tools.tool_registry import register_tool

@register_tool(tags=["bi", "my_tool"])
class MyTool:
    """One-line description. Key methods: method_one, method_two."""

    def method_one(self, arg: str) -> str:
        """Does X. Args: arg: input string. Returns: result string."""
        ...
```

The docstring is what the LLM sees in the tool schema — write it clearly.

### Step 2 — Add to the agent's `tools` list

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`

```python
tools: list[str] = ["RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner", "MyTool"]
```

This makes the tool schema visible to the LLM via MetaGPT's tool recommender.

### Step 3 — Wire the callable in `_update_tool_execution()`

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`, inside `_update_tool_execution()`:

```python
my_tool = MyTool()
self.tool_execution_map.update({
    "MyTool.method_one": my_tool.method_one,
    "MyTool.method_two": my_tool.method_two,
})
```

Steps 2 and 3 are different: step 2 makes the schema visible; step 3 makes the function callable at dispatch time. **Both are required.**

### Step 4 — Add a dispatch branch in `_dispatch()`

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`, inside `_dispatch()`:

```python
elif tool_name == "MyTool":
    return self._run_my_tool(task_type, tool_args)
```

Add the corresponding `_run_my_tool(self, task_type, tool_args)` private method below.

### Step 5 — Update the relevant agent prompts

This is the step most often forgotten. Tool names and their methods must appear in the right prompt files for each agent that needs to know about them:

**`metagpt/prompts/bi/bi_solution_architect.py`** ← **always required**  
Eve (Agent 3) generates the execution plan. She must know the tool exists and when to use it. Add it to the "Tool selection" section (Step 1 of Eve's EXTRA_INSTRUCTION):
```
- MyTool: Use when [use case]. For [task type] tasks, set tool = "MyTool".
```
Without this, Eve will never include `MyTool` in any execution plan — the tool remains invisible at planning time regardless of how it is registered.

**`metagpt/prompts/bi/bi_analytics_engineer.py`** ← required if the tool needs special handling  
Alex (Agent 4) has task-type-specific dispatch instructions (INSTANTIATION, CONNECTION_SETUP, SCHEMA_CREATION, DATA_INGESTION, TRANSFORMATION). If your tool requires a non-standard execution sequence (e.g. like DbtRunner's mandatory `write_model` before `execute_BI_task`), add a note in the relevant task type section. The "Getting Started" section at the end of the execution report template also lists the tools actually used — update it if the tool produces an artifact the human user needs to access.

**`metagpt/prompts/bi/bi_requirements_analyst.py`** ← required if the tool is for data source inspection  
Alice (Agent 1) uses DataSourceInspector methods during elicitation. If your tool helps inspect a new type of data source, add it to the Core tools section so Alice knows to call it. Also wire it in `bi_requirements_analyst.py`'s `_update_tool_execution()`.

**`metagpt/prompts/bi/bi_qa_engineer.py`** ← required if the tool produces artifacts Edward should validate  
Edward (Agent 5) validates the DWH. If your tool creates tables or files that Edward should check, mention the validation approach in Edward's Phase 1 (structural checks) section.

**Summary:**

| File | Update needed when… |
|------|---------------------|
| `bi_solution_architect.py` | Always — Eve must know the tool name and when to use it |
| `bi_analytics_engineer.py` | Tool requires special sub-steps or produces a user-facing artifact |
| `bi_requirements_analyst.py` | Tool is used by Alice for data source inspection |
| `bi_qa_engineer.py` | Tool produces tables or files that Edward should validate |

---

## PoC scenarios (implemented for the thesis)

The following three scenarios were implemented and tested during the thesis. They can be reproduced by others, but some adaptation may be needed:

- **Smoke tests** (structural unit tests) run anywhere with no adaptation — they require no API key, no cloud accounts, and no specific data files.
- **Live test scripts** (`run_session*.py`) were run on the thesis author's machine and reference specific workspace artifacts from previous sessions. They require re-running earlier sessions first to generate the prerequisite files, and credential injection must be adapted to your own Supabase/Airbyte accounts.
- **Full pipeline via `metagpt-bi`** is the cleanest way to reproduce any scenario from scratch — it generates all artifacts in a fresh per-run directory.

### Scenario A — CSV files -> DuckDB

**Stack:** PandasLoader + DuckDBExecutor + DbtRunner (dbt-duckdb)  
**External accounts:** None  
**Test data:** Three CSV files in `workspace/data/` (customer, product, interaction data)

```powershell
metagpt-bi "I need a BI solution for weekly sales analysis. I have three CSV files in workspace/data/: customer_data.csv, product_details.csv, and interaction_data.csv. I want a local DuckDB warehouse."
```

Expected output: 14-task execution plan (1 INSTANTIATION + 2 SCHEMA_CREATION + 3 DATA_INGESTION + 8 TRANSFORMATION), 11 DuckDB tables, 8 dbt SQL models.

**Live test script** (Session 6): `ClaudeCode_implementation/tests/run_session6_live.py`  
Requires: `workspace/docs/execution_plan.json` (generated by a prior Agent 3 run), `workspace/data/*.csv`.  
No credential adaptation needed, but workspace paths may differ from the original run.

### Scenario B — Airbyte Cloud (Faker API) -> Supabase

**Stack:** AirbyteConnector + SupabaseConnector + DbtRunner (dbt-postgres)  
**External accounts:** Supabase (free tier) + Airbyte Cloud (free tier)  
**Data source:** Airbyte "Sample Data (Faker)" connector — generates synthetic e-commerce data (users, products, purchases)

```powershell
metagpt-bi "I need a BI solution for e-commerce analysis. My data comes from Airbyte Cloud (Sample Data / Faker source). I want to use Supabase as my cloud DWH."
```

Alex will prompt for credentials during CREDENTIAL_REQUEST tasks:
- Supabase project URL, Service Role API key, PostgreSQL Session Pooler URI
- Airbyte Client ID, Client Secret, Workspace ID, Source ID

Expected output: 11-task execution plan, 4 dbt-built dimensional tables in Supabase.

**Live test script** (Session 7): `ClaudeCode_implementation/tests/run_session7_live.py`  
**Adaptation required:** The script uses `_collect_credentials()` which asks for your own Supabase and Airbyte credentials interactively. The pre-built `ClaudeCode_implementation/test_data/execution_plan_supabase.json` references placeholder values that are substituted at runtime — the script is designed to work with any valid credentials, not just the original author's.

### Scenario C — CSV files -> Supabase

**Stack:** SupabaseConnector (load_csv) + DbtRunner (dbt-postgres)  
**External accounts:** Supabase (free tier)  
**Data source:** Same CSV files as Scenario A

```powershell
metagpt-bi "I need a BI solution for sales analysis. I have CSV files in workspace/data/. I want to use Supabase as my DWH."
```

Alex uses `SupabaseConnector.load_csv()` for bulk CSV ingestion into Supabase via psycopg2, then dbt-postgres for transformations.

**Live test script:** No dedicated script — use `metagpt-bi` directly. Scenario C was implemented in Session 9 alongside `bi_team.py` itself.

### Running the smoke tests

All structural unit tests run on any machine with the venv set up — no API key, no cloud accounts, no prior run artifacts needed:

```powershell
# All sessions
python -m pytest ClaudeCode_implementation/tests/ --override-ini="addopts=" -v

# Single session
python -m pytest ClaudeCode_implementation/tests/test_session9_bi_team.py --override-ini="addopts=" -v
```

Test counts per session: Session 3: 13 | Session 4: 13 | Session 5: 9 | Session 6: 32 | Session 7: 27 | Session 8: 37 | Session 9: 31. Total: ~162 tests.

---

## Troubleshooting

**`metagpt-bi` not found after setup**  
Activate the venv first: `.\venv\Scripts\Activate.ps1`. If still missing, run `pip install -e .` inside the venv.

**`airbyte_api` import error after installing new packages**  
`dbt-postgres` can remove `airbyte-api` due to a protobuf version conflict. Fix:
```powershell
pip install "airbyte-api==0.53.0"
```
Verify with: `python -c "import airbyte_api; print('OK')"`.

**Alice goes silent or calls `end` immediately**  
Non-deterministic LLM behaviour. Increase budget (`--rounds 250`) and re-run.

**Supabase connection fails — "could not translate host name"**  
Use the **Session Pooler URI** (port 5432) from the green "Connect" button on the Supabase dashboard. The direct connection string (`db.xxx.supabase.co:5432`) does not resolve on the free tier.

**dbt: "no enabled node in selection set"**  
Alex's ReAct loop detects this and will call `DbtRunner.write_model()` to write the SQL before retrying. This is normal self-correction behaviour.

---

## File structure

```
MetaGPT-BI/
├── bi_team.py                          # Entry point (metagpt-bi command)
├── setup_bi.ps1                        # One-time setup script (Windows PowerShell)
├── setup.py                            # Package setup (registers metagpt-bi console script)
├── config/
│   └── config2.yaml                    # LLM configuration (API key, model)
├── workspace/
│   ├── data/                           # Place source CSV/Excel files here
│   └── runs/                           # Per-run artifact directories (auto-created)
├── dbt_projects/                       # dbt project directories (auto-created by Agent 4)
├── metagpt/
│   ├── bi_task_type.py                 # BITaskType enum (6 task types)
│   ├── actions/bi/                     # Inter-agent message routing action classes
│   ├── prompts/bi/                     # Agent system prompts (EXTRA_INSTRUCTION strings)
│   ├── roles/bi/                       # Agent role classes (5 agents)
│   └── tools/bi/                       # External tool classes (6 tools)
└── ClaudeCode_implementation/
    ├── IMPLEMENTATION_SPEC.md          # Full implementation specification
    ├── Follow-up/
    │   ├── IMPLEMENTATION_PROGRESS.md  # Session-by-session progress log
    │   └── DEVIATIONS_AND_CLARIFICATIONS.md  # Design vs. implementation differences
    ├── test_data/                       # Pre-built execution plans for live test scripts
    └── tests/
        ├── test_session*.py            # Smoke tests (no LLM, no cloud accounts)
        └── run_session*.py             # Live integration test runners
```

---

## Implementation sessions

| Session | What was built |
|---------|---------------|
| 1 | BITaskType enum + 5 prompt files + 5 action classes |
| 2 | 6 tool classes (DuckDBExecutor, PandasLoader, DbtRunner, SupabaseConnector, AirbyteConnector, DataSourceInspector) |
| 3 | BIRequirementsAnalyst (Alice) — live e2e test verified |
| 4 | BIDataModeler (Bob) — live e2e test verified |
| 5 | BISolutionArchitect (Eve) — live e2e test verified |
| 6 | BIAnalyticsEngineer (Alex) — Scenario A live test verified (14 tasks, DuckDB) |
| 7 | Scenario B live test: Airbyte Faker -> Supabase (11 tasks, self-correction demonstrated) |
| 8 | BIQAEngineer (Edward) — live test: REJECTED report (empty fact tables from cross-session contamination, correct behaviour) |
| 9 | `metagpt-bi` CLI + per-run workspace isolation + Scenario C (CSV->Supabase) + Airbyte source inspection during elicitation |

For detailed deviation tracking and implementation notes, see:
- [ClaudeCode_implementation/Follow-up/DEVIATIONS_AND_CLARIFICATIONS.md](ClaudeCode_implementation/Follow-up/DEVIATIONS_AND_CLARIFICATIONS.md)
- [ClaudeCode_implementation/Follow-up/IMPLEMENTATION_PROGRESS.md](ClaudeCode_implementation/Follow-up/IMPLEMENTATION_PROGRESS.md)
