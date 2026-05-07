# MetaGPT-BI Implementation Specification
## Agentic BI Architecture — Proof of Concept

This file is the primary specification document for the PoC implementation of the
transposed MetaGPT BI architecture described in the thesis:
"Where AI Adds Value: Designing a BI development Multi-Agent Architecture"
by Jonathan Dierckx (KU Leuven / UNamur, 2025-2026).

The full theoretical design is in `ClaudeCode_implementation/thesis_section_4.2.pdf`.
All designed agent prompts are in `ClaudeCode_implementation/prompts/`.
The academic paper by Hong. et al. presenting the original MetaGPT framework is in  `ClaudeCode_implementation/MetaGPT_paper.pdf/`.

---

## 1. What this PoC implements

This is a transposition of the MetaGPT Software Company multi-agent system into the
Business Intelligence (BI) development domain, using a Design Science Research (DSR)
Exaptation approach. Five specialized BI agents collaborate via a document-driven workflow
and a publish-subscribe shared message pool to autonomously execute a full BI back-end 
development workflow: from requirements elicitation to a ready-to-use Data Warehouse (DWH).

**Workflow (5 phases, one agent per phase):**
1. Requirements Elicitation → produces a Business Requirement Document (BRD)
2. Dimensional Data Modeling → produces Dimensional Model Spec + Conceptual/Logical Schemas
3. Technical Execution Planning → produces a DWH Technical Execution Plan (JSON)
4. Pipeline & DWH Development → executes the plan, produces the DWH + Execution Report
5. Quality Validation → validates the DWH against the BRD, produces a Validation Feedback Report

---

## 2. Architecture principles

- All agents inherit from `metagpt.roles.di.role_zero.RoleZero` (NOT the base `Role` class)
- All agents use the two-part instruction pattern:
  `AGENT_INSTRUCTION = ROLE_INSTRUCTION + EXTRA_INSTRUCTION`
  where `ROLE_INSTRUCTION` is imported from `metagpt.prompts.di.role_zero`
- All agents use the `@register_tool` decorator pattern for tool registration
- Agent 4's primary execution method (`execute_BI_task`) is defined directly on the role
  class as a `@register_tool`-decorated method (similar to Engineer2.write_new_code pattern)
- All external tools are self-contained classes in `metagpt/tools/bi/` decorated with
  `@register_tool`, exposing granular methods (not just one single execute() method)
- Agents communicate via MetaGPT's existing publish-subscribe shared message pool
- DO NOT modify any existing MetaGPT files. Only add new files to integrate them within the 
  existing MetaGPT framework.

---

## 3. Files to create

### 3.1 BITaskType enum
**File:** `metagpt/bi_task_type.py`

Define a `BITaskType` enum with exactly these 6 values:
- `INSTANTIATION` — creating a new DWH/tool instance
- `CONNECTION_SETUP` — establishing connections between stack components
- `CREDENTIAL_REQUEST` — human-in-the-loop checkpoint for credentials
- `SCHEMA_CREATION` — DDL execution to create fact/dimension tables
- `DATA_INGESTION` — loading raw data into staging tables
- `TRANSFORMATION` — running SQL transformations to populate dimensional tables

### 3.2 Prompt files
**Directory:** `metagpt/prompts/bi/`

Create one file per agent role containing the EXTRA_INSTRUCTION string. All prompt content is specified
in the thesis and in `bi_implementation/prompts/`.

- `bi_requirements_analyst.py` — EXTRA_INSTRUCTION
- `bi_data_modeler.py` — EXTRA_INSTRUCTION
- `bi_solution_architect.py` — EXTRA_INSTRUCTION
- `bi_analytics_engineer.py` — EXTRA_INSTRUCTION
- `bi_qa_engineer.py` — EXTRA_INSTRUCTION

### 3.3 Action classes
**Directory:** `metagpt/actions/bi/`

Each action follows the same pattern as existing MetaGPT actions (e.g. write_brd.py
in WriteBRD mirrors the pattern of write_code.py in WriteCode). Some deviations however need to be made,
as specified in the thesis. 

- `write_brd.py` — WriteBRD action (Agent 1)
  - Triggered when: elicitation is complete
  - Input: elicitation conversation history + data source schemas from agent memory
  - Output: BRD markdown document saved via Editor
  - Template: WriteBRD PROMPT_TEMPLATE from prompts file

- `write_data_model.py` — WriteDataModel action (Agent 2)
  - Triggered when: BRD is observed in message pool
  - Input: full BRD content
  - Output: 3 files — dimensional_model_specification.md, conceptual_schema.mermaid,
    logical_schema.mermaid
  - Template: WriteDataModel PROMPT_TEMPLATE from prompts file

- `write_execution_plan.py` — WriteExecutionPlan action (Agent 3)
  - Triggered when: WriteDataModel output observed
  - Input: BRD + dimensional model spec + logical schema
  - Output: docs/execution_plan.json (valid JSON array of tasks conforming to BITaskType schema)
  - Template: WriteExecutionPlan PROMPT_TEMPLATE from prompts file
  - Must validate that output JSON only uses BITaskType enum values

- `write_validation_report.py` — WriteValidationReport action (Agent 5)
  - Triggered when: both validation phases complete
  - Input: structural validation results + traceability validation results +
    BRD sections 4/5/6 + logical schema + execution plan + DWH connection details
  - Output: docs/validation_feedback_report.md
  - Template: WriteValidationReport PROMPT_TEMPLATE from prompts file

Like it is done in the other action files, each action class file must also contain the PROMPT_TEMPLATE 
strings defined for it in the thesis and specified in `bi_implementation/prompts/`.

- `write_brd.py` — WriteBRD PROMPT_TEMPLATE
- `write_data_model.py` — WriteDataModel PROMPT_TEMPLATE
- `write_execution_plan.py` — WriteExecutionPlan PROMPT_TEMPLATE
- `write_validation_report.py` — WriteValidationReport PROMPT_TEMPLATE

### 3.4 Role classes
**Directory:** `metagpt/roles/bi/`

Each role follows the RoleZero pattern. Reference Engineer2 (metagpt/roles/di/engineer2.py)
as the general structural model for all five roles, as well as each role's SoftwareCompany system counterpart.

- `bi_requirements_analyst.py` — BIRequirementsAnalyst(RoleZero)
  - name="Alice", profile="BI Requirements Analyst"
  - tools: ["RoleZero", "Editor", "DataSourceInspector"]
  - watch: UserRequirement
  - todo_action: WriteBRD
  - Special: uses reply_to_human for iterative elicitation conversation
  - SoftwareCompany system reference: metagpt/roles/product_manager.py

- `bi_data_modeler.py` — BIDataModeler(RoleZero)
  - name="Bob", profile="BI Data Modeler"
  - tools: ["RoleZero", "Editor"]
  - watch: WriteBRD output
  - todo_action: WriteDataModel
  - SoftwareCompany system reference: metagpt/roles/architect.py

- `bi_solution_architect.py` — BISolutionArchitect(RoleZero)
  - name="Eve", profile="BI Solution Architect"
  - tools: ["RoleZero", "Editor", "WriteExecutionPlan"]
  - watch: WriteDataModel output (needs BRD + all 3 data model artifacts)
  - todo_action: WriteExecutionPlan
  - SoftwareCompany system reference: metagpt/roles/project_manager.py

- `bi_analytics_engineer.py` — BIAnalyticsEngineer(RoleZero)
  - name="Alex", profile="BI Analytics Engineer"
  - tools: ["Plan", "RoleZero", "BIAnalyticsEngineer", "DuckDBExecutor", "DbtRunner",
    "PandasLoader", "AirbyteConnector", "SupabaseConnector"]
  - watch: WriteExecutionPlan output + WriteValidationReport output
  - todo_action: execute_BI_task (method on role class, NOT a separate Action subclass)
  - max_react_loop: 50
  - Primary method: execute_BI_task(task: dict) -> dict, decorated with @register_tool
  - Overrides _think() to inject execution state into cmd_prompt_current_state
  - IMPORTANT: For TRANSFORMATION tasks, the LLM must generate SQL model code as
    a ReAct reasoning step BEFORE calling DbtRunner — do not push SQL generation
    into the Tool class itself
  - SoftwareCompany system reference: metagpt/roles/di/engineer2.py

- `bi_qa_engineer.py` — BIQAEngineer(RoleZero)
  - name="Edward", profile="BI QA Engineer"
  - tools: ["RoleZero", "DuckDBExecutor", "SupabaseConnector", "Editor"]
  - watch: execute_BI_task output (Execution Report)
  - todo_action: WriteValidationReport
  - validation_round_allowed: 3
  - Read-only DWH access only — never DDL or DML
  - SoftwareCompany system reference: metagpt/roles/qa_engineer.py

### 3.5 Tool classes
**Directory:** `metagpt/tools/bi/`

All tools use @register_tool decorator. Expose GRANULAR methods, not a single execute().
Mechanical retry logic (e.g. connection backoff) stays inside the Tool class.
Semantic reasoning (e.g. interpreting error output) stays in the ReAct loop.

**FULLY IMPLEMENT for PoC:**

- `duckdb_executor.py` — DuckDBExecutor
  - Must allow to connect to and interact with DuckDB : instantiate a DWH, load data into it, query it, read its content, etc.
  - Methods: run_ddl(ddl: str), run_query(sql: str), verify_table(table_name: str),
    check_pk_uniqueness(table: str, pk_col: str), check_fk_integrity(...)
  - Used by: Analytics Engineer (write) + QA Engineer (read-only SELECT only)

- `dbt_runner.py` — DbtRunner
  - Must allow to connect to and interact with dbt : instantiate a dbt transformation project, connect it to data sources and target DWH, perform data transformations with it, etc.
  - Methods: init_project(project_name: str), configure_profile(...),
    write_model(model_name: str, sql: str), compile_model(model_name: str),
    run_model(model_name: str), run_tests(model_name: str), get_results(run_id: str)
  - Note: SQL content is generated by LLM in ReAct loop, then passed to write_model()
  - Used by: Analytics Engineer only

- `pandas_loader.py` — PandasLoader
  - Must allow to connect to and interact with pandas : connect it to data sources, load it into dbt or other transformation tool, etc.
  - Methods: load_file(file_path: str, target_table: str, db_path: str),
    infer_schema(file_path: str), get_row_count(file_path: str)
  - Supports: CSV, Excel (.xlsx), or others
  - Used by: Analytics Engineer only

- `airbyte_connector.py` — AirbyteConnector
  - Must allow to connect to and interact with Airbyte : connect it to data sources, load it into dbt or other transformation tool, etc.
  - Methods: setup_connection(source_config: dict), trigger_sync(connection_id: str),
    get_sync_status(sync_id: str)
  - Supports: CSV, Excel (.xlsx), or others
  - Used by: Analytics Engineer only

- `supabase_connector.py` — SupabaseConnector
  - Must allow to connect to and interact with Supabase : instantiate a DWH, load data into it, query it, read its content, etc.
  - Methods: connect(url: str, key: str), run_query(sql: str), run_ddl(ddl: str), verify_table(table_name: str),
    check_pk_uniqueness(table: str, pk_col: str), check_fk_integrity(...)
  - Used by: Analytics Engineer (write) + QA Engineer (read-only SELECT only)

### 3.6 DataSourceInspector tool
**File:** `metagpt/tools/bi/data_source_inspector.py`
 - Must allow to connect to and data sources to read their structure and inspect them
- Methods: inspect_csv(file_path: str), inspect_duckdb(db_path: str),
  inspect_postgres(connection_string: str) + others if needed
- Returns: dict with table names, column names, data types, row counts
- Used by: BI Requirements Analyst only

### 3.7 Entry point
**File:** `bi_team.py` (at repository root)

Assembles all 5 agents, configures the shared Environment, and runs the pipeline.
Pattern to follow: look at metagpt/team.py for how MetaGPT assembles its Software Company.

```python
import asyncio
from metagpt.team import Team
from metagpt.roles.bi.bi_requirements_analyst import BIRequirementsAnalyst
from metagpt.roles.bi.bi_data_modeler import BIDataModeler
from metagpt.roles.bi.bi_solution_architect import BISolutionArchitect
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer
from metagpt.roles.bi.bi_qa_engineer import BIQAEngineer

async def main(user_requirement: str):
    team = Team()
    team.hire([
        BIRequirementsAnalyst(),
        BIDataModeler(),
        BISolutionArchitect(),
        BIAnalyticsEngineer(),
        BIQAEngineer(),
    ])
    team.run_project(user_requirement)
    await team.run(n_round=20)

if __name__ == "__main__":
    asyncio.run(main("I need a BI application for my weekly sales analysis."))
```

---

## 4. PoC scope boundaries

### In scope (fully implement):
- All 5 agent role classes
- All 4 action classes (+ more if needed for correct functioning)
- BITaskType enum
- All prompt files
- DuckDBExecutor, DbtRunner, PandasLoader, AirbyteConnector, SupabaseConnector tool classes (fully functional)
- DataSourceInspector tool class
- bi_team.py entry point
- End-to-end test with provided CSV test data (see Section 6)
- Any corrections needed to theoretical design for the system to be working (IF SO, INFORM USER !)

---

## 5. Key files to reference from original MetaGPT codebase

DO NOT modify these. Read them as structural references only:

| New file to create | Reference from original codebase |
|---|---|
| Any role class | metagpt/roles/di/engineer2.py or other roles in metagpt/roles |
| Any action class | metagpt/actions/write_code.py or other actions in metagpt/actions|
| Prompt files | metagpt/prompts/di/engineer2.py or other prompts files in metagpt/prompts |
| Tool classes | metagpt/tools/|
| bi_team.py | metagpt/team.py |
| BITaskType enum | metagpt/actions/project_management_an.py (TaskType) |

---

## 6. Test data and PoC scenario

**User input (first message to the system):**
"I need a BI application for my weekly sales analysis. I have CSV files."

**Test dataset:**
Two CSV files in `ClaudeCode_implementation/test_data/`:
- `sales_transactions.csv` — columns: transaction_id, date, product_id, customer_id,
  region, quantity, unit_price, total_amount
- `products.csv` — columns: product_id, product_name, category, subcategory, supplier

**Expected pipeline outcome:**
- Agent 1: elicits requirements, discovers CSV structure, produces BRD
- Agent 2: designs star schema with FACT_SALES + DIM_PRODUCT + DIM_DATE + DIM_REGION
- Agent 3: produces JSON execution plan (INSTANTIATION → SCHEMA_CREATION →
  DATA_INGESTION x2 → TRANSFORMATION x4)
- Agent 4: creates DuckDB DWH instance, creates tables, loads CSVs via pandas,
  generates and runs dbt transformation models with inline tests
- Agent 5: validates DWH, confirms all KPIs computable, produces acceptance report

---

## 7. LLM configuration

Use the same LLM configuration as standard MetaGPT (defined in config/config2.yaml).
The PoC will use claude or Gemini as the underlying LLM.
Ensure your API key is set in the MetaGPT config before running.