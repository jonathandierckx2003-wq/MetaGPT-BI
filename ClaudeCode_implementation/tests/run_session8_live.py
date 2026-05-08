"""
Live integration test for Session 8: BIQAEngineer (Agent 5 — Edward).

Run from the REPO ROOT:
    python ClaudeCode_implementation/tests/run_session8_live.py

Requires:
    - config/config2.yaml with a valid LLM API key
    - workspace/docs/business_requirement_document.md  (Session 3)
    - workspace/docs/dimensional_model_specification.md (Session 4)
    - workspace/docs/conceptual_schema.mermaid          (Session 4)
    - workspace/docs/logical_schema.mermaid             (Session 4)
    - workspace/docs/execution_plan.json                (Session 5)
    - workspace/docs/execution_report.md                (Session 6)
    - workspace/dwh.duckdb                              (Session 6)

What to expect:
    Edward connects to workspace/dwh.duckdb and runs two validation phases:

    Phase 1 (structural + technical):
      For each table in the Logical Schema:
        - Existence check
        - Schema check (columns + types)
        - Data presence check
        - Primary key uniqueness check
        - Foreign key integrity check (fact tables)

    Phase 2 (requirements traceability):
      For each BRD item (queries, KPIs, data sources):
        - Verify required tables/columns exist and contain data
        - Mark as SUPPORTED/UNSUPPORTED, COMPUTABLE/NOT_COMPUTABLE, INGESTED/MISSING

    Then calls BIQAEngineer.generate_validation_report() to produce, save and publish:
        workspace/docs/validation_feedback_report.md

    Expected outcome: ACCEPTED (DWH was verified functional in Session 6)
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
from pathlib import Path

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_report import WriteExecutionReport
from metagpt.roles.bi.bi_qa_engineer import BIQAEngineer
from metagpt.schema import Message
from metagpt.team import Team
from metagpt.utils.common import any_to_str

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BRD_PATH = Path("workspace/docs/business_requirement_document.md")
SPEC_PATH = Path("workspace/docs/dimensional_model_specification.md")
CONCEPTUAL_PATH = Path("workspace/docs/conceptual_schema.mermaid")
LOGICAL_PATH = Path("workspace/docs/logical_schema.mermaid")
DWH_PATH = Path("workspace/dwh.duckdb")
VALIDATION_REPORT_PATH = Path("workspace/docs/validation_feedback_report.md")
FAILED_REPORT_PATH = Path("workspace/docs/failed_validation_report.md")

N_ROUND = 60  # generous budget: Phase 1 (~55 checks) + Phase 2 + generate_validation_report()

# Synthetic DuckDB execution report — used instead of reading from disk because
# workspace/docs/execution_report.md was overwritten by the Session 7 Supabase run.
# The DWH at workspace/dwh.duckdb is intact from Session 6 (11 tables, ~31 MB).
SYNTHETIC_DUCKDB_EXECUTION_REPORT = """\
# Execution Report

## Execution Summary

| Task ID | Status | Summary |
|---|---|---|
| 1 | COMPLETE | DuckDB database initialised at `workspace/dwh.duckdb`. |
| 2 | COMPLETE | Staging schema created: tables staging_customer_raw, staging_interaction_raw, staging_product_raw. |
| 3 | COMPLETE | Loaded workspace/data/customers.csv into staging_customer_raw (500 rows). |
| 4 | COMPLETE | Loaded workspace/data/products.csv into staging_product_raw (200 rows). |
| 5 | COMPLETE | Loaded workspace/data/interactions.csv into staging_interaction_raw (1000 rows). |
| 6 | COMPLETE | Dimensional schema created: dim_category, dim_customer, dim_date, dim_interaction_type, dim_product, fact_customer_summary, fact_interaction, fact_sales. |
| 7 | COMPLETE | dbt project bi_dwh initialised at dbt_projects/bi_dwh. DuckDB profile configured. |
| 8 | COMPLETE | dim_customer dbt model built successfully. |
| 9 | COMPLETE | dim_product dbt model built successfully. |
| 10 | COMPLETE | dim_category dbt model built successfully. |
| 11 | COMPLETE | dim_interaction_type dbt model built successfully. |
| 12 | COMPLETE | dim_date dbt model built successfully. |
| 13 | COMPLETE | fact_interaction and fact_customer_summary dbt models built successfully. |
| 14 | COMPLETE | fact_sales dbt model built successfully. |

### Row Counts / Load Results
- staging_customer_raw: 500 rows loaded from workspace/data/customers.csv.
- staging_product_raw: 200 rows loaded from workspace/data/products.csv.
- staging_interaction_raw: 1000 rows loaded from workspace/data/interactions.csv.

### Transformation Results
All 8 dbt models built successfully:
dim_category, dim_customer, dim_date, dim_interaction_type, dim_product,
fact_customer_summary, fact_interaction, fact_sales.

### Warnings / Non-blocking Issues
None.

## Getting Started — Accessing Your DWH

### DuckDB
The DWH is stored at `workspace/dwh.duckdb`.

**CLI:**
```
duckdb workspace/dwh.duckdb
```

**Python:**
```python
import duckdb
conn = duckdb.connect("workspace/dwh.duckdb", read_only=True)
tables = conn.execute("SHOW TABLES").fetchall()
```

Any SQL-capable BI tool (Tableau, Power BI, DBeaver) can connect via the DuckDB ODBC driver.

### dbt project
Located at `dbt_projects/bi_dwh/`.

**Docs command:**
```bash
cd dbt_projects/bi_dwh && dbt docs generate && dbt docs serve
```

**Local docs URL:** http://localhost:8080

## Final Status

**COMPLETE**
"""


async def main():
    print()
    print("=" * 70)
    print("  Live integration test — BIQAEngineer (Edward, Agent 5)")
    print("=" * 70)
    print(f"\nInput artifacts:")
    print(f"  BRD             : {BRD_PATH}")
    print(f"  Logical schema  : {LOGICAL_PATH}")
    print(f"  Execution report: synthetic (DuckDB scenario, embedded)")
    print(f"  DWH             : {DWH_PATH}")
    print(f"\nExpected output:")
    print(f"  {VALIDATION_REPORT_PATH}")
    print(f"\nBudget: {N_ROUND} reasoning rounds\n")
    print("-" * 70)

    # --- Check required input files ---
    required = [BRD_PATH, LOGICAL_PATH, DWH_PATH]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("\nERROR: The following required input files are missing:")
        for m in missing:
            print(f"  - {m}")
        print("\nRun the earlier session live tests first:")
        print("  Session 3: python ClaudeCode_implementation/tests/run_session3_live.py")
        print("  Session 4: python ClaudeCode_implementation/tests/run_session4_live.py")
        return

    # --- Load artifacts ---
    brd_content = BRD_PATH.read_text(encoding="utf-8")
    spec_content = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    conceptual_content = CONCEPTUAL_PATH.read_text(encoding="utf-8") if CONCEPTUAL_PATH.exists() else ""
    logical_content = LOGICAL_PATH.read_text(encoding="utf-8")
    report_text = SYNTHETIC_DUCKDB_EXECUTION_REPORT

    print(f"BRD loaded            : {len(brd_content):,} chars")
    print(f"Logical schema loaded : {len(logical_content):,} chars")
    print(f"Execution report      : {len(report_text):,} chars (synthetic DuckDB)")

    # Verify DWH tables
    try:
        import duckdb as _duckdb
        _conn = _duckdb.connect(str(DWH_PATH), read_only=True)
        _tables = [r[0] for r in _conn.execute("SHOW TABLES").fetchall()]
        _conn.close()
        print(f"DWH tables            : {_tables}")
    except Exception as exc:
        print(f"WARNING: Could not introspect DWH: {exc}")

    print("-" * 70)
    print()

    # --- Assemble combined data model message (same format as BIDataModeler.generate_data_model()) ---
    # BIQAEngineer._extract_logical_schema() splits on "\n\n---\n\n" and takes parts[2]
    combined_data_model = (
        f"## Dimensional Model Specification\n\n{spec_content}\n\n"
        f"---\n\n"
        f"## Conceptual Schema (Mermaid erDiagram)\n\n{conceptual_content}\n\n"
        f"---\n\n"
        f"## Logical Schema (Mermaid erDiagram)\n\n{logical_content}"
    )

    # --- Assemble team with only Edward ---
    team = Team(use_mgx=False)
    team.hire([BIQAEngineer()])

    # --- Publish prior artifacts so they are available in Edward's memory ---
    # BRD (produced by Alice — Agent 1)
    team.env.publish_message(Message(
        content=brd_content,
        cause_by=any_to_str(WriteBRD),
        sent_from="Alice",
    ))

    # Combined data model (produced by Bob — Agent 2)
    team.env.publish_message(Message(
        content=combined_data_model,
        cause_by=any_to_str(WriteDataModel),
        sent_from="Bob",
    ))

    # Execution report (synthetic DuckDB) — trigger message that activates Edward
    # (BIQAEngineer._watch([WriteExecutionReport]))
    # Note: execution plan is not injected — workspace/docs/execution_plan.json was
    # overwritten by the Session 7 Supabase run; skipping it leaves execution_plan=""
    # in generate_validation_report(), which is handled gracefully by WriteValidationReport.
    team.env.publish_message(Message(
        content=report_text,
        cause_by=any_to_str(WriteExecutionReport),
        sent_from="Alex",
    ))

    print("Starting BIQAEngineer execution loop...")
    print("(Edward will run Phase 1 + Phase 2 validation and write")
    print(" workspace/docs/validation_feedback_report.md)\n")

    await team.run(n_round=N_ROUND)

    # --- Results summary ---
    print()
    print("=" * 70)
    print("  Results")
    print("=" * 70)

    if VALIDATION_REPORT_PATH.exists():
        size = VALIDATION_REPORT_PATH.stat().st_size
        print(f"\n  [OK] {VALIDATION_REPORT_PATH}  ({size:,} bytes)")
        report = VALIDATION_REPORT_PATH.read_text(encoding="utf-8")
        # Outcome detection (REJECTED takes precedence — same logic as generate_validation_report)
        if "REJECTED" in report:
            print("  Outcome: REJECTED")
            print("  (Review the report for details; Edward will re-trigger Alex if rounds remain)")
        elif "ACCEPTED" in report:
            print("  Outcome: ACCEPTED")
            print("  DWH has passed all structural and traceability checks.")
        else:
            print("  Outcome: UNKNOWN (neither ACCEPTED nor REJECTED found in report)")
        # Count PASS/FAIL/SUPPORTED/UNSUPPORTED lines for a quick summary
        pass_count = report.count(": PASS") + report.count("**PASS**")
        fail_count = report.count(": FAIL") + report.count("**FAIL**")
        supported = report.count("SUPPORTED") - report.count("UNSUPPORTED")
        unsupported = report.count("UNSUPPORTED")
        computable = report.count("COMPUTABLE") - report.count("NOT_COMPUTABLE")
        not_computable = report.count("NOT_COMPUTABLE")
        ingested = report.count("INGESTED") - report.count("MISSING")
        missing = report.count("MISSING")
        if pass_count or fail_count:
            print(f"\n  Phase 1 (structural checks):")
            print(f"    PASS : {pass_count}")
            print(f"    FAIL : {fail_count}")
        if supported or unsupported:
            print(f"\n  Phase 2 — queries:")
            print(f"    SUPPORTED   : {supported}")
            print(f"    UNSUPPORTED : {unsupported}")
        if computable or not_computable:
            print(f"\n  Phase 2 — KPIs:")
            print(f"    COMPUTABLE     : {computable}")
            print(f"    NOT_COMPUTABLE : {not_computable}")
        if ingested or missing:
            print(f"\n  Phase 2 — data sources:")
            print(f"    INGESTED : {ingested}")
            print(f"    MISSING  : {missing}")
    elif FAILED_REPORT_PATH.exists():
        size = FAILED_REPORT_PATH.stat().st_size
        print(f"\n  [FAILED] {FAILED_REPORT_PATH}  ({size:,} bytes)")
        print("  Validation exhausted all allowed rounds without acceptance.")
        print("  Review the failed report for persisting issues.")
    else:
        print(f"\n  [MISSING] {VALIDATION_REPORT_PATH}")
        print("  Edward may not have called generate_validation_report() within the round budget.")
        print("  Try increasing N_ROUND at the top of this script, or re-run.")

    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
