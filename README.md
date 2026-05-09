# MetaGPT-BI — Agentic BI Architecture

> **Academic research project — Master's thesis, KU Leuven / UNamur (2026)**  
> This repository extends [MetaGPT](https://github.com/geekan/MetaGPT) (MIT License, © 2024 Chenglin Wu) for the Business Intelligence domain. It is an experimental proof of concept developed in a thesis context and is not a production-ready tool.

---

An extension of the MetaGPT multi-agent framework into the Business Intelligence domain. Five specialized BI agents collaborate via a document-driven, publish-subscribe shared message pool to autonomously build a complete BI back-end: from requirements elicitation to a validated, ready-to-use Data Warehouse.

**Thesis:** "Where AI Adds Value: Designing a BI development Multi-Agent Architecture —  
A Contextual Transposition of Software Engineering Patterns"  
Jonathan Dierckx — Double degree Master's student, UNamur / KU Leuven, 2026

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

Supported providers are documented in the upstream MetaGPT repository: [docs/tutorial/usage.md](docs/tutorial/usage.md).

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

Alice (Agent 1) will ask for file paths during the elicitation conversation and inspect the files automatically.

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
- Data grain (per transaction, per day, per customer...)
- Update frequency (real-time, daily batch, weekly snapshot)
- Historical data range needed
- Data quality concerns or missing fields
- Preferred DWH technology (DuckDB for local, Supabase for cloud)

Answer each question in the terminal. Alice inspects your data files automatically — you do not need to describe the schema manually.

**Phase 2 — Automated pipeline (Bob, Eve, Alex, Edward):**  
After Alice finishes, the remaining four agents run without further input:
- Bob designs the star or snowflake schema and produces Mermaid ERDs
- Eve creates a structured JSON execution plan with typed tasks
- Alex executes the plan: DWH setup, schema creation, data ingestion, and SQL transformations via dbt
- Edward validates the built DWH against the BRD and reports ACCEPTED or REJECTED

If a cloud scenario requires credentials (Supabase, Airbyte), Alex will prompt you interactively at the relevant task.

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

The following external tool classes are implemented in `metagpt/tools/bi/`. Each is decorated with `@register_tool`, making its schema visible to the LLM agents via MetaGPT's tool registry.

### DuckDBExecutor — `metagpt/tools/bi/duckdb_executor.py`
Used by Alex (execution) and Edward (validation). Full DuckDB interaction: DDL, queries, schema inspection, PK/FK integrity checks.

### PandasLoader — `metagpt/tools/bi/pandas_loader.py`
Used by Alex for DATA_INGESTION tasks in the DuckDB scenario. Reads CSV and Excel files and loads them into DuckDB via pandas. DuckDB-specific — cannot target PostgreSQL directly.

### DbtRunner — `metagpt/tools/bi/dbt_runner.py`
Used by Alex for TRANSFORMATION tasks in all scenarios. Wraps dbt Core CLI. Supports both DuckDB (`dbt-duckdb`) and PostgreSQL/Supabase (`dbt-postgres`) profiles. The LLM calls `write_model(model_name, sql)` to write SQL, then `execute_BI_task` to compile and run it.

### SupabaseConnector — `metagpt/tools/bi/supabase_connector.py`
Used by Alex (SCHEMA_CREATION, DATA_INGESTION) and Edward (validation) in Supabase scenarios. Connects via direct psycopg2 for full DDL support. The `load_csv()` method enables bulk CSV ingestion into Supabase without Airbyte.

### AirbyteConnector — `metagpt/tools/bi/airbyte_connector.py`
Used by Alex for INSTANTIATION, CONNECTION_SETUP, and DATA_INGESTION tasks in the Airbyte scenario. Wraps the Airbyte Cloud API with OAuth2 authentication: creates sources and destinations, triggers syncs, and polls for completion.

### DataSourceInspector — `metagpt/tools/bi/data_source_inspector.py`
Used by Alice during elicitation. Inspects local CSV/Excel files, DuckDB databases, PostgreSQL schemas, and Airbyte Cloud sources, returning column names, types, row counts, and samples so Alice can base the BRD on the actual data structure.

---

## Adding a new external tool

The architecture is designed to be extensible. Adding a new tool requires **5 steps across up to 5 files**.

### Step 1 — Write the tool class

Create `metagpt/tools/bi/<tool_name>.py` (follow the `bi/` subdirectory convention — see [Modifications to the original framework](#modifications-to-the-original-framework)):

```python
from metagpt.tools.tool_registry import register_tool

@register_tool(tags=["bi", "my_tool"])
class MyTool:
    """One-line description. Key methods: method_one, method_two."""

    def method_one(self, arg: str) -> str:
        """Does X. Args: arg: input string. Returns: result string."""
        ...
```

### Step 2 — Add to the agent's `tools` list

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`

```python
tools: list[str] = ["RoleZero", "Editor", "BIAnalyticsEngineer", "DbtRunner", "MyTool"]
```

### Step 3 — Wire the callable in `_update_tool_execution()`

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`, inside `_update_tool_execution()`:

```python
my_tool = MyTool()
self.tool_execution_map.update({
    "MyTool.method_one": my_tool.method_one,
    "MyTool.method_two": my_tool.method_two,
})
```

Steps 2 and 3 are different: step 2 makes the schema visible to the LLM; step 3 makes the function callable at dispatch time. **Both are required.**

### Step 4 — Add a dispatch branch in `_dispatch()`

**File:** `metagpt/roles/bi/bi_analytics_engineer.py`, inside `_dispatch()`:

```python
elif tool_name == "MyTool":
    return self._run_my_tool(task_type, tool_args)
```

### Step 5 — Update the relevant agent prompts

This is the step most often forgotten. Tool names must appear in the prompts of every agent that needs to know about them. All BI prompt files are in `metagpt/prompts/bi/`.

| File | Update needed when... |
|------|----------------------|
| `bi_solution_architect.py` | **Always** — Eve (Agent 3) generates the execution plan and must know the tool name and when to use it. Add it to the "Tool selection" section. Without this, the tool will never appear in any execution plan. |
| `bi_analytics_engineer.py` | Tool requires special sub-steps (e.g. DbtRunner needs `write_model` called before `execute_BI_task`) or produces a user-facing artifact mentioned in the Getting Started report section. |
| `bi_requirements_analyst.py` | Tool is used by Alice for data source inspection during elicitation. Also wire it in `bi_requirements_analyst.py`'s `_update_tool_execution()`. |
| `bi_qa_engineer.py` | Tool produces tables or artifacts that Edward (Agent 5) should validate in Phase 1 (structural checks). |

---

## PoC scenarios (implemented for the thesis)

The following three scenarios were built and tested during the thesis. They can be reproduced, with the notes below on what may need adaptation.

- **Smoke tests** run anywhere with no adaptation — no API key, no cloud accounts, no specific data files required.
- **Live test scripts** (`run_session*.py`) were run on the thesis author's machine and reference specific workspace artifacts from prior sessions. They may need path or credential adaptation.
- **Full pipeline via `metagpt-bi`** is the cleanest way to reproduce any scenario from scratch — it generates all artifacts fresh in a new per-run directory.

### Scenario A — CSV files -> DuckDB (no external accounts)

**Stack:** PandasLoader + DuckDBExecutor + DbtRunner (dbt-duckdb)

```powershell
metagpt-bi "I need a BI solution for weekly sales analysis. I have three CSV files in workspace/data/: customer_data.csv, product_details.csv, and interaction_data.csv. I want a local DuckDB warehouse."
```

Expected: 14-task execution plan, 11 DuckDB tables, 8 dbt SQL models.  
Live test script: `ClaudeCode_implementation/tests/run_session6_live.py` (requires prior Agent 3 run to produce `workspace/docs/execution_plan.json`).

### Scenario B — Airbyte Cloud (Faker API) -> Supabase

**Stack:** AirbyteConnector + SupabaseConnector + DbtRunner (dbt-postgres)  
**Required accounts:** [supabase.com](https://supabase.com) (free) + [airbyte.com](https://airbyte.com) (free)

Before running, create a "Sample Data (Faker)" source in your Airbyte workspace and an OAuth application. Alice can inspect the Airbyte source schema during elicitation if you provide the workspace ID, source ID, and OAuth credentials.

```powershell
metagpt-bi "I need a BI solution for e-commerce analysis. My data comes from Airbyte Cloud (Sample Data / Faker source). I want to use Supabase as my cloud DWH."
```

Alex will prompt for Supabase and Airbyte credentials during the CREDENTIAL_REQUEST tasks.  
Live test script: `ClaudeCode_implementation/tests/run_session7_live.py` — credential injection uses `_collect_credentials()` which works with any valid Supabase + Airbyte account; adapt for your own credentials.

**Supabase credential note:** Use the **Session Pooler URI** (port 5432, green "Connect" button on project dashboard). The direct connection (`db.xxx.supabase.co:5432`) does not resolve on the free tier.

### Scenario C — CSV files -> Supabase

**Stack:** SupabaseConnector (load_csv) + DbtRunner (dbt-postgres)  
**Required accounts:** [supabase.com](https://supabase.com) (free)

```powershell
metagpt-bi "I need a BI solution for sales analysis. I have CSV files in workspace/data/. I want to use Supabase as my DWH."
```

No dedicated live test script — use `metagpt-bi` directly. Implemented in Session 9.

### Running the smoke tests

All structural unit tests run on any machine with the venv set up:

```powershell
# All sessions (~162 tests total)
python -m pytest ClaudeCode_implementation/tests/ --override-ini="addopts=" -v

# Single session
python -m pytest ClaudeCode_implementation/tests/test_session9_bi_team.py --override-ini="addopts=" -v
```

Test counts: Session 3: 13 | Session 4: 13 | Session 5: 9 | Session 6: 32 | Session 7: 27 | Session 8: 37 | Session 9: 31

---

## Troubleshooting

**`metagpt-bi` not found after setup**  
Activate the venv first: `.\venv\Scripts\Activate.ps1`. If still missing, run `pip install -e .` inside the venv.

**`airbyte_api` import error after installing new packages**  
`dbt-postgres` can remove `airbyte-api` due to a protobuf version conflict. Fix:
```powershell
pip install "airbyte-api==0.53.0"
```

**Alice goes silent or calls `end` immediately**  
Non-deterministic LLM behaviour. Increase the budget (`--rounds 250`) and re-run.

**Supabase connection fails — "could not translate host name"**  
Use the Session Pooler URI (port 5432) from the green "Connect" button on the Supabase dashboard. The direct connection string does not resolve on the free tier.

**dbt: "no enabled node in selection set"**  
Alex's ReAct loop detects this error and calls `DbtRunner.write_model()` to write the SQL before retrying. This is expected self-correction behaviour.

---

## Modifications to the original framework

All BI-specific code added by this thesis follows a consistent naming convention: every new file is either inside a `bi/` subdirectory within the existing MetaGPT package structure, or carries a `bi_` / `BI_` prefix at the repository root. This makes the additions easy to identify and isolate from the original framework.

### Files added (thesis additions)

```
bi_team.py                          # metagpt-bi entry point (bi_ prefix)
setup_bi.ps1                        # Windows setup script (bi suffix)
metagpt/bi_task_type.py             # BITaskType enum (bi_ prefix)
metagpt/actions/bi/                 # Inter-agent action classes (bi/ subdirectory)
  write_brd.py
  write_data_model.py
  write_execution_plan.py
  write_execution_report.py
  write_validation_report.py
metagpt/prompts/bi/                 # Agent system prompts (bi/ subdirectory)
  bi_requirements_analyst.py
  bi_data_modeler.py
  bi_solution_architect.py
  bi_analytics_engineer.py
  bi_qa_engineer.py
metagpt/roles/bi/                   # Agent role classes (bi/ subdirectory)
  bi_requirements_analyst.py
  bi_data_modeler.py
  bi_solution_architect.py
  bi_analytics_engineer.py
  bi_qa_engineer.py
metagpt/tools/bi/                   # External tool classes (bi/ subdirectory)
  duckdb_executor.py
  dbt_runner.py
  pandas_loader.py
  supabase_connector.py
  airbyte_connector.py
  data_source_inspector.py
ClaudeCode_implementation/          # Implementation docs and tests (separate directory)
```

### Files modified in the original framework

Two files in the original MetaGPT codebase were patched to fix bugs discovered during testing:

| File | Change | Reason |
|------|--------|--------|
| `metagpt/provider/openai_api.py` | Added `max_completion_tokens` parameter handling for gpt-5.x, o3, and o4 models | Newer OpenAI models reject the `max_tokens` parameter |
| `metagpt/utils/role_zero_utils.py` | Added guard in `parse_commands` against malformed JSON responses missing `command_name` | LLM intermittently produces non-command JSON; guard enables self-correction |

All other original MetaGPT files are unchanged. The `setup.py` entry_points section was extended to register `metagpt-bi` as a console script alongside the existing `metagpt` command.

---

## Based on MetaGPT

This project is built on top of [MetaGPT](https://github.com/geekan/MetaGPT), the open-source multi-agent framework by Chenglin Wu and the DeepWisdom team, distributed under the [MIT License](LICENSE).

MetaGPT's original documentation, changelog, and framework documentation are preserved at:
- Upstream README: [docs/METAGPT_README.md](docs/METAGPT_README.md)
- Upstream repository: [https://github.com/geekan/MetaGPT](https://github.com/geekan/MetaGPT)
- Framework usage docs: [docs/tutorial/usage.md](docs/tutorial/usage.md)

The MetaGPT copyright notice is retained in [LICENSE](LICENSE) as required by the MIT License. This thesis extension does not claim ownership of the original framework code.

---

## Acknowledgements

### Claude Code

The implementation of this thesis PoC was carried out with the assistance of [Claude Code](https://claude.ai/code) (Anthropic), an AI-powered CLI that supports multi-step software engineering tasks. Claude Code was used across all 9 implementation sessions to write, test, debug, and document the BI agents, tools, actions, and infrastructure.

The [ClaudeCode_implementation/](ClaudeCode_implementation/) folder is the primary record of how this implementation was performed. It contains:

- **[IMPLEMENTATION_PROGRESS.md](ClaudeCode_implementation/Follow-up/IMPLEMENTATION_PROGRESS.md)** — session-by-session log of what was built, which files were created, and key design choices made in each session.
- **[DEVIATIONS_AND_CLARIFICATIONS.md](ClaudeCode_implementation/Follow-up/DEVIATIONS_AND_CLARIFICATIONS.md)** — numbered DEV-XX entries documenting every place where the implementation diverged from the original thesis design, with the reason and the resolution.
- **[tests/](ClaudeCode_implementation/tests/)** — unit and integration smoke tests (162 tests across 7 sessions) plus live pipeline test scripts for all three PoC scenarios.

Readers interested in the implementation methodology — including how AI-assisted coding was managed at this scale — are encouraged to consult those files alongside the thesis text itself.

### Thesis context

This repository is the software artefact accompanying the thesis "Where AI Adds Value: Designing a BI development Multi-Agent Architecture — A Contextual Transposition of Software Engineering Patterns" submitted in partial fulfilment of the requirements for the Double degree Master's programme at UNamur and KU Leuven (2026). The thesis provides the full theoretical motivation, design decisions, and evaluation that underpin the PoC implemented here.

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
| 8 | BIQAEngineer (Edward) — live test: REJECTED report correctly produced |
| 9 | `metagpt-bi` CLI + per-run workspace isolation + Scenario C (CSV->Supabase) + Airbyte source inspection during elicitation |

For detailed implementation notes and design decisions, see:
- [ClaudeCode_implementation/Follow-up/IMPLEMENTATION_PROGRESS.md](ClaudeCode_implementation/Follow-up/IMPLEMENTATION_PROGRESS.md)
- [ClaudeCode_implementation/Follow-up/DEVIATIONS_AND_CLARIFICATIONS.md](ClaudeCode_implementation/Follow-up/DEVIATIONS_AND_CLARIFICATIONS.md)
