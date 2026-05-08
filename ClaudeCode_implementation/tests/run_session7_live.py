"""
Session 7 live integration test — Airbyte Faker -> Supabase + dbt-postgres scenario.

Scenario:
  - Data source : Airbyte Cloud "Sample Data (Faker)" connector (users/products/purchases)
  - DWH         : Supabase (PostgreSQL)
  - Transform   : dbt-postgres (dim_customer, dim_product, dim_date, fact_purchases)

Pre-requisites:
  - A free Supabase project at https://supabase.com
  - A free Airbyte Cloud account at https://cloud.airbyte.com
  - pip install dbt-postgres (already done in Session 7 setup)

The BIAnalyticsEngineer (Alex) is pre-loaded with the 11-task Supabase execution plan
from ClaudeCode_implementation/test_data/execution_plan_supabase.json.
Credentials are collected interactively before the agent session begins (DEV-50).
Alex will:
  1. Mark CREDENTIAL_REQUEST tasks complete (credentials already loaded)
  2. Connect to Supabase via SupabaseConnector
  3. Create Airbyte destination + Faker connection via AirbyteConnector
  4. Trigger the Faker -> Supabase sync
  5. Configure dbt-postgres profile
  6. Generate and run 4 dbt models (dim_customer, dim_product, dim_date, fact_purchases)
  7. Save and publish the Execution Report

Usage:
    python ClaudeCode_implementation/tests/run_session7_live.py

Post-run checks are printed at the end; verify Supabase tables via the Supabase Studio
SQL editor or any PostgreSQL client.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

# Ensure the repo root is in the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.actions.bi.write_execution_plan import WriteExecutionPlan
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer
from metagpt.schema import Message
from metagpt.team import Team

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLAN_PATH = REPO_ROOT / "ClaudeCode_implementation" / "test_data" / "execution_plan_supabase.json"
BRD_PATH = REPO_ROOT / "workspace" / "docs" / "business_requirement_document.md"
DATA_MODEL_PATH = REPO_ROOT / "workspace" / "docs" / "dimensional_model_specification.md"
LOGICAL_SCHEMA_PATH = REPO_ROOT / "workspace" / "docs" / "logical_schema.mermaid"
REPORT_PATH = REPO_ROOT / "workspace" / "docs" / "execution_report.md"

# Generous round budget: 11 tasks × ~4 steps each + CREDENTIAL_REQUEST turns + dbt compilation
N_ROUND = 100


def _load_text(path: Path, label: str) -> str:
    if not path.exists():
        print(f"  [MISSING] {label}: {path}")
        return f"[{label} not available]"
    print(f"  [OK] {label}: {path}")
    return path.read_text(encoding="utf-8")


def _build_combined_data_model(spec: str, logical: str) -> str:
    """Replicate the WriteDataModel combined-message format for BISolutionArchitect -> memory."""
    conceptual_placeholder = "erDiagram\n  (conceptual schema not needed for this session)"
    return (
        f"## Dimensional Model Specification\n\n{spec}"
        f"\n\n---\n\n## Conceptual Schema\n\n{conceptual_placeholder}"
        f"\n\n---\n\n## Logical Schema\n\n{logical}"
    )


def _collect_credentials() -> dict[str, str]:
    """Interactively collect Supabase and Airbyte credentials before the agent session.

    DEV-50: team.run() is a batch loop with no stdin injection mechanism. Collecting
    credentials here and injecting them into Alex's _credentials dict before run() avoids
    the infinite reply_to_human loop that occurred when CREDENTIAL_REQUEST tasks tried to
    collect credentials from inside the agent loop.

    Returns a dict keyed by the placeholder strings used in execution_plan_supabase.json.
    """
    print("\n" + "=" * 70)
    print("CREDENTIAL COLLECTION")
    print("Credentials are collected here and injected into Alex before the run.")
    print("=" * 70)

    print("\n--- Supabase (https://supabase.com) ---")
    print("  Go to: Project Settings > General for the Project URL.")
    print("  Go to: Project Settings > API for the anon public key.")
    print("  Go to: Project Settings > Database > Connection string > URI")
    print("  IMPORTANT: Choose 'Session' mode (port 5432) from the dropdown —")
    print("  NOT 'Transaction' mode (port 6543). Session mode supports all SQL")
    print("  features that dbt needs. Replace [YOUR-PASSWORD] with your db password.")
    print("  Session pooler URI format:")
    print("    postgresql://postgres.<ref>:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres")
    supabase_url = input("\n  Project URL (e.g. https://abc.supabase.co): ").strip().rstrip("/")
    supabase_anon_key = input("  Anon public key: ").strip()
    supabase_pg_uri = input("  PostgreSQL URI (Session pooler, port 5432): ").strip()

    # Parse the postgres URI to extract host, user, password.
    # URI format: postgresql://USER:PASSWORD@HOST:PORT/DB
    uri_m = re.match(
        r"(?:postgresql|postgres)://([^:@]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)",
        supabase_pg_uri,
    )
    if uri_m:
        db_user = uri_m.group(1)
        db_password = uri_m.group(2)
        db_host = uri_m.group(3)
    else:
        db_user = db_password = db_host = ""

    # Detect if the user pasted the format example literally instead of their real URI
    if "REGION" in supabase_pg_uri or "PASSWORD" in supabase_pg_uri or "<" in supabase_pg_uri:
        print("\n  [ERROR] The URI still contains placeholder text (REGION, PASSWORD, or <...>).")
        print("  Go to: Supabase Dashboard → Settings → Database → Connection string")
        print("  Select 'Session' mode and COPY the actual URI — do not type it manually.")
        supabase_pg_uri = input("  Re-enter the actual PostgreSQL URI: ").strip()
        uri_m = re.match(
            r"(?:postgresql|postgres)://([^:@]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)",
            supabase_pg_uri,
        )
        if uri_m:
            db_user = uri_m.group(1)
            db_password = uri_m.group(2)
            db_host = uri_m.group(3)

    # Sanity-check extracted values
    for label, val, fallback_prompt in [
        ("host", db_host, "  PostgreSQL host (e.g. aws-0-eu-west-2.pooler.supabase.com): "),
        ("user", db_user, "  PostgreSQL user (e.g. postgres.abc): "),
        ("password", db_password, "  DB password: "),
    ]:
        if not val:
            print(f"  [WARN] Could not extract {label} from URI. Enter it manually:")
            if label == "host":
                db_host = input(fallback_prompt).strip()
            elif label == "user":
                db_user = input(fallback_prompt).strip()
            else:
                db_password = input(fallback_prompt).strip()

    print(f"\n  Parsed: host={db_host}  user={db_user}")

    print("\n--- Airbyte Cloud (https://cloud.airbyte.com) ---")
    print("  To get your API key:")
    print("    Click your user avatar (bottom-left) > User Settings > Applications")
    print("    > Create application. Copy the generated client secret / API key.")
    print("  To get your workspace ID:")
    print("    Click Workspace Settings (top-right gear icon). The ID appears in")
    print("    the URL: app.airbyte.com/workspaces/<workspace_id>/settings")
    print("    There is also a copy button next to it.")
    airbyte_api_key = input("\n  API key: ").strip()
    airbyte_workspace_id = input("  Workspace ID: ").strip()

    credentials = {
        "SUPABASE_PROJECT_URL_FROM_TASK_1": supabase_url,
        "SUPABASE_ANON_KEY_FROM_TASK_1": supabase_anon_key,
        "SUPABASE_POSTGRES_URL_FROM_TASK_1": supabase_pg_uri,
        "SUPABASE_DB_HOST_FROM_TASK_1": db_host,
        "SUPABASE_DB_USER_FROM_TASK_1": db_user,
        "SUPABASE_DB_PASSWORD_FROM_TASK_1": db_password,
        "AIRBYTE_API_KEY_FROM_TASK_2": airbyte_api_key,
        "AIRBYTE_WORKSPACE_ID_FROM_TASK_2": airbyte_workspace_id,
    }
    print(f"\n  {len(credentials)} credential values loaded.")
    return credentials  # 8 values (added SUPABASE_DB_USER_FROM_TASK_1 vs prior 7)


async def main():
    print("=" * 70)
    print("Session 7 — Live Integration Test")
    print("Scenario: Airbyte Faker → Supabase + dbt-postgres")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Validate input files
    # ------------------------------------------------------------------
    print("\n[1] Checking input files...")
    if not PLAN_PATH.exists():
        print(f"  [ERROR] execution_plan_supabase.json not found at {PLAN_PATH}")
        sys.exit(1)

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    task_type_counts: dict[str, int] = {}
    for t in plan:
        tt = t.get("task_type", "UNKNOWN")
        task_type_counts[tt] = task_type_counts.get(tt, 0) + 1
    print(f"  [OK] execution_plan_supabase.json — {len(plan)} tasks:")
    for tt, cnt in sorted(task_type_counts.items()):
        print(f"       {tt}: {cnt}")

    brd_content = _load_text(BRD_PATH, "BRD (from Session 3)")
    spec_content = _load_text(DATA_MODEL_PATH, "Dimensional model spec (from Session 4)")
    logical_content = _load_text(LOGICAL_SCHEMA_PATH, "Logical schema (from Session 4)")

    # ------------------------------------------------------------------
    # Collect credentials before building the plan message (DEV-50)
    # The CREDENTIAL_REQUEST task instructions are then rewritten so the
    # LLM calls execute_BI_task() instead of trying to ask the human.
    # ------------------------------------------------------------------
    print("\n[2a] Collecting credentials (required before agent session starts)...")
    credentials = _collect_credentials()

    # Rewrite CREDENTIAL_REQUEST task instructions in the plan so the LLM
    # never attempts to call ask_human or reply_to_human for these tasks.
    for task in plan:
        if task.get("task_type") == "CREDENTIAL_REQUEST":
            task["instruction"] = (
                "Credentials for this service have already been collected by the orchestration "
                "layer before this session started and are stored in system memory. "
                "Call BIAnalyticsEngineer.execute_BI_task(task) with this exact task object "
                "to acknowledge completion. Do NOT call ask_human or reply_to_human."
            )

    # ------------------------------------------------------------------
    # Assemble messages
    # ------------------------------------------------------------------
    print("\n[2b] Assembling pre-published messages for BIAnalyticsEngineer...")

    brd_message = Message(
        content=brd_content,
        cause_by="metagpt.actions.bi.write_brd.WriteBRD",
        sent_from="Alice",
    )
    data_model_message = Message(
        content=_build_combined_data_model(spec_content, logical_content),
        cause_by="metagpt.actions.bi.write_data_model.WriteDataModel",
        sent_from="Bob",
    )
    plan_message = Message(
        content=json.dumps(plan, indent=2),
        cause_by="metagpt.actions.bi.write_execution_plan.WriteExecutionPlan",
        sent_from="Eve",
    )

    # ------------------------------------------------------------------
    # Build team and run
    # ------------------------------------------------------------------
    print("\n[3] Starting BIAnalyticsEngineer (Alex) with Supabase execution plan...")
    print(f"    Budget: {N_ROUND} rounds")
    print()

    alex = BIAnalyticsEngineer()
    alex.inject_credentials(credentials)
    team = Team(use_mgx=False)
    team.hire([alex])

    env = team.env
    env.publish_message(brd_message)
    env.publish_message(data_model_message)
    env.publish_message(plan_message)

    await team.run(n_round=N_ROUND)

    # ------------------------------------------------------------------
    # Post-run checks
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("[4] Post-run verification")
    print("=" * 70)

    # Check execution report
    if REPORT_PATH.exists():
        report_size = REPORT_PATH.stat().st_size
        report_text = REPORT_PATH.read_text(encoding="utf-8")
        complete_count = report_text.count("COMPLETE")
        print(f"\n[OK] {REPORT_PATH.name}  ({report_size:,} bytes)")
        print(f"     Tasks marked COMPLETE in report: {complete_count}")
    else:
        print(f"\n[MISSING] {REPORT_PATH.name} — execution report was not saved")

    # Check dbt project
    dbt_project_dir = REPO_ROOT / "dbt_projects" / "bi_dwh"
    if dbt_project_dir.exists():
        sql_models = list((dbt_project_dir / "models").glob("*.sql")) if (dbt_project_dir / "models").exists() else []
        print(f"\n[OK] dbt project at {dbt_project_dir.relative_to(REPO_ROOT)}/")
        if sql_models:
            print(f"     SQL models written : {len(sql_models)}")
            for m in sorted(sql_models):
                print(f"       {m.name}")
    else:
        print("\n[MISSING] dbt project not found — TRANSFORMATION tasks may not have run")

    # Remind user to check Supabase
    print()
    print("To verify tables in Supabase:")
    print("  1. Go to your Supabase project → Table Editor, or")
    print("  2. Use the SQL editor: SELECT table_name FROM information_schema.tables")
    print("     WHERE table_schema = 'public';")
    print()
    print("Expected tables:")
    print("  Staging (loaded by Airbyte): users, products, purchases")
    print("  Dimensional (built by dbt) : dim_customer, dim_product, dim_date, fact_purchases")
    print()
    print("To view dbt lineage and docs:")
    dbt_rel = dbt_project_dir.relative_to(REPO_ROOT)
    print(f"  cd {dbt_rel} && dbt docs generate && dbt docs serve")
    print("  Then open http://localhost:8080")
    print()


if __name__ == "__main__":
    asyncio.run(main())
