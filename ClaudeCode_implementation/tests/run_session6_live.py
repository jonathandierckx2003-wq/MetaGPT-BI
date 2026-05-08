"""
Live integration test for Session 6: BIAnalyticsEngineer (Agent 4 — Alex).

Run from the REPO ROOT:
    python ClaudeCode_implementation/tests/run_session6_live.py

Requires:
    - config/config2.yaml with a valid LLM API key
    - workspace/docs/execution_plan.json produced by Session 5
    - workspace/docs/business_requirement_document.md produced by Session 3
    - workspace/docs/dimensional_model_specification.md produced by Session 4
    - workspace/docs/logical_schema.mermaid produced by Session 4
    - dbt CLI installed (dbt-duckdb adapter) for TRANSFORMATION tasks

What to expect:
    Minimal user input — only if CREDENTIAL_REQUEST tasks appear in the plan (none
    expected with the standard DuckDB-based plan from Session 5).

    Alex runs through all 14 tasks in dependency order:
      Tasks 1    : INSTANTIATION   — DuckDBExecutor.connect()
      Tasks 2, 6 : SCHEMA_CREATION — DuckDBExecutor.run_ddl() (ddl-as-list joined, DEV-37)
      Tasks 3-5  : DATA_INGESTION  — PandasLoader.load_file() for each CSV
      Tasks 7-14 : TRANSFORMATION  — DbtRunner.write_model() + execute_BI_task()
                                     (dbt project auto-initialized on first TRANSFORMATION)

    Output artifacts:
        workspace/docs/execution_report.md
        dbt_projects/bi_dwh/                (dbt project with compiled models)
        workspace/dwh.duckdb                (populated DWH with all dimensional tables)
"""

import sys
import types


# ---------------------------------------------------------------------------
# semantic_kernel stub — must come before any metagpt import
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
    sk_orch = sys.modules["semantic_kernel.orchestration"]
    sk_orch.sk_function = types.ModuleType("semantic_kernel.orchestration.sk_function")
    azure_mod = sys.modules["semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion"]
    azure_mod.AzureChatCompletion = object


_stub_semantic_kernel()

# ---------------------------------------------------------------------------
# Standard imports (metagpt safe to import now)
# ---------------------------------------------------------------------------
import asyncio
import json
from collections import Counter
from pathlib import Path

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer
from metagpt.schema import Message
from metagpt.team import Team
from metagpt.utils.common import any_to_str

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PLAN_PATH = Path("workspace/docs/execution_plan.json")
BRD_PATH = Path("workspace/docs/business_requirement_document.md")
SPEC_PATH = Path("workspace/docs/dimensional_model_specification.md")
CONCEPTUAL_PATH = Path("workspace/docs/conceptual_schema.mermaid")
LOGICAL_PATH = Path("workspace/docs/logical_schema.mermaid")
REPORT_PATH = Path("workspace/docs/execution_report.md")
DWH_PATH = Path("workspace/dwh.duckdb")

N_ROUND = 80  # generous budget: 14 tasks × ~3 steps each + compilation + report


async def main():
    print()
    print("=" * 70)
    print("  Live integration test — BIAnalyticsEngineer (Alex, Agent 4)")
    print("=" * 70)
    print(f"\nInput artifacts:")
    print(f"  Execution plan  : {PLAN_PATH}")
    print(f"  BRD             : {BRD_PATH}")
    print(f"  Spec            : {SPEC_PATH}")
    print(f"  Logical schema  : {LOGICAL_PATH}")
    print(f"\nExpected outputs:")
    print(f"  {REPORT_PATH}")
    print(f"  {DWH_PATH}  (populated DWH)")
    print(f"  dbt_projects/bi_dwh/  (dbt project with compiled SQL models)")
    print(f"\nBudget: {N_ROUND} reasoning rounds\n")
    print("-" * 70)

    # --- Check required input files ---
    required = [PLAN_PATH, BRD_PATH, LOGICAL_PATH]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("\nERROR: The following required input files are missing:")
        for m in missing:
            print(f"  - {m}")
        print("\nRun the earlier session live tests first:")
        print("  Session 3: python ClaudeCode_implementation/tests/run_session3_live.py")
        print("  Session 4: python ClaudeCode_implementation/tests/run_session4_live.py")
        print("  Session 5: python ClaudeCode_implementation/tests/run_session5_live.py")
        return

    # --- Load and display plan summary ---
    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    try:
        tasks = json.loads(plan_text)
        print(f"Execution plan loaded: {len(tasks)} tasks")
        type_counts = Counter(t.get("task_type", "?") for t in tasks)
        for tt, cnt in sorted(type_counts.items()):
            print(f"  {tt}: {cnt}")
    except json.JSONDecodeError as exc:
        print(f"ERROR: execution_plan.json is not valid JSON: {exc}")
        return
    print()

    # --- Load context artifacts ---
    brd_content = BRD_PATH.read_text(encoding="utf-8") if BRD_PATH.exists() else ""
    spec_content = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    conceptual_content = CONCEPTUAL_PATH.read_text(encoding="utf-8") if CONCEPTUAL_PATH.exists() else ""
    logical_content = LOGICAL_PATH.read_text(encoding="utf-8") if LOGICAL_PATH.exists() else ""

    if brd_content:
        print(f"BRD loaded       : {len(brd_content)} chars")
    if logical_content:
        print(f"Logical schema   : {len(logical_content)} chars")
    print("-" * 70)
    print()

    # --- Assemble combined data model message (same format as BIDataModeler.generate_data_model()) ---
    combined_data_model = (
        f"## Dimensional Model Specification\n\n{spec_content}\n\n"
        f"---\n\n"
        f"## Conceptual Schema (Mermaid erDiagram)\n\n{conceptual_content}\n\n"
        f"---\n\n"
        f"## Logical Schema (Mermaid erDiagram)\n\n{logical_content}"
    )

    # --- Assemble team with only Alex ---
    team = Team(use_mgx=False)
    team.hire([BIAnalyticsEngineer()])

    # --- Inject BRD so Alex has requirements context for SQL generation ---
    if brd_content:
        team.env.publish_message(Message(
            content=brd_content,
            cause_by=any_to_str(WriteBRD),
            sent_from="Alice",
        ))

    # --- Inject data model for SQL generation context (Logical Schema) ---
    if logical_content:
        team.env.publish_message(Message(
            content=combined_data_model,
            cause_by=any_to_str(WriteDataModel),
            sent_from="Bob",
        ))

    # --- Inject execution plan as the trigger message for Alex ---
    team.env.publish_message(Message(
        content=plan_text,
        cause_by=any_to_str(WriteExecutionPlan),
        sent_from="Eve",
    ))

    print("Starting BIAnalyticsEngineer execution loop...")
    print("(Alex will execute all tasks and write workspace/docs/execution_report.md)\n")

    await team.run(n_round=N_ROUND)

    # --- Results summary ---
    print()
    print("=" * 70)
    print("  Results")
    print("=" * 70)

    # Check execution report
    if REPORT_PATH.exists():
        size = REPORT_PATH.stat().st_size
        print(f"\n  [OK] {REPORT_PATH}  ({size} bytes)")
        report_text = REPORT_PATH.read_text(encoding="utf-8")
        # Count task status lines
        complete_count = report_text.count("COMPLETE")
        failed_count = report_text.count("FAILED")
        print(f"       Tasks marked COMPLETE in report: {complete_count}")
        if failed_count:
            print(f"       Tasks marked FAILED in report : {failed_count}  (see report for details)")
    else:
        print(f"\n  [MISSING] {REPORT_PATH}")
        print("  Alex may not have reached publish_execution_report() within the round budget.")
        print("  Try increasing N_ROUND at the top of this script, or re-run.")

    # Check DWH file
    if DWH_PATH.exists():
        size = DWH_PATH.stat().st_size
        print(f"\n  [OK] {DWH_PATH}  ({size:,} bytes)")
        # Quick DuckDB introspection to verify tables
        try:
            import duckdb
            conn = duckdb.connect(str(DWH_PATH), read_only=True)
            tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
            conn.close()
            dim_tables = [t for t in tables if t.lower().startswith("dim_")]
            fact_tables = [t for t in tables if t.lower().startswith("fact_")]
            staging_tables = [t for t in tables if t.lower().startswith("staging_")]
            print(f"       Dimension tables  : {dim_tables}")
            print(f"       Fact tables       : {fact_tables}")
            print(f"       Staging tables    : {staging_tables}")
            if not dim_tables and not fact_tables:
                print("  WARNING: No dimensional/fact tables found — TRANSFORMATION tasks may have failed.")
        except Exception as exc:
            print(f"  WARNING: Could not introspect DWH: {exc}")
    else:
        print(f"\n  [MISSING] {DWH_PATH}  (DuckDB database not created)")

    # Check dbt project
    dbt_project_path = Path("dbt_projects/bi_dwh")
    if dbt_project_path.exists():
        model_files = list((dbt_project_path / "models").glob("*.sql")) if (dbt_project_path / "models").exists() else []
        print(f"\n  [OK] dbt project at {dbt_project_path}/")
        print(f"       SQL models written : {len(model_files)}")
        for m in sorted(model_files):
            print(f"         {m.name}")
    else:
        print(f"\n  [MISSING] dbt project at {dbt_project_path}/")
        print("  TRANSFORMATION tasks may not have been reached yet.")

    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
