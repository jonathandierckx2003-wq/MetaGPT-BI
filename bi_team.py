#!/usr/bin/env python
"""bi_team.py — Entry point for the MetaGPT-BI Agentic BI Architecture PoC.

Assembles all five BI agents and runs the full multi-agent pipeline:
  Agent 1  Alice   BI Requirements Analyst   -> produces BRD
  Agent 2  Bob     BI Data Modeler           -> produces Dimensional Model
  Agent 3  Eve     BI Solution Architect     -> produces Execution Plan (JSON)
  Agent 4  Alex    BI Analytics Engineer     -> executes plan, produces Execution Report
  Agent 5  Edward  BI QA Engineer            -> validates DWH, produces Validation Report

Usage
-----
    python bi_team.py "I need a BI solution for my weekly sales analysis. I have CSV files."
    python bi_team.py "I want a cloud BI setup" --rounds 250
    python bi_team.py "..." --run-name my_run_001

Per-run workspace isolation
----------------------------
Each invocation creates a timestamped subfolder under workspace/runs/:
    workspace/runs/YYYYMMDD_HHMMSS/docs/   # all markdown, JSON and mermaid artifacts
    workspace/runs/YYYYMMDD_HHMMSS/        # execution_report.md, validation reports

Passing --run-name overrides the timestamp with a custom directory name.

Source data (CSV files)
-----------------------
Place raw CSV / Excel / DuckDB files in workspace/data/ before starting.
Alice will ask for the file paths during the elicitation conversation.

Cloud scenarios (Supabase / Airbyte)
--------------------------------------
For scenarios that require cloud accounts (Supabase DWH, Airbyte Cloud ingestion),
Alice will discover from the conversation which tools are needed.  Agent 4 (Alex)
will then call RoleZero.ask_human to collect credentials interactively during the
CREDENTIAL_REQUEST tasks in the Execution Plan.

LLM configuration
-----------------
Configured via config/config2.yaml.  See README.md for details.
"""

import argparse
import asyncio
import sys
import types
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# semantic_kernel stub — must come before any metagpt import (same as all
# live test scripts — required because metagpt.roles.di.role_zero imports
# from semantic_kernel which may not be installed in this environment).
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
# MetaGPT imports (safe after stub)
# ---------------------------------------------------------------------------
from metagpt.config2 import config                                         # noqa: E402
from metagpt.roles.bi.bi_requirements_analyst import BIRequirementsAnalyst  # noqa: E402
from metagpt.roles.bi.bi_data_modeler import BIDataModeler                  # noqa: E402
from metagpt.roles.bi.bi_solution_architect import BISolutionArchitect       # noqa: E402
from metagpt.roles.bi.bi_analytics_engineer import BIAnalyticsEngineer       # noqa: E402
from metagpt.roles.bi.bi_qa_engineer import BIQAEngineer                     # noqa: E402
from metagpt.team import Team                                                 # noqa: E402
from metagpt.logs import logger                                               # noqa: E402


# ---------------------------------------------------------------------------
# Default budget — generous enough for a full 5-agent pipeline.
# The team stops early when all agents go idle, so a high value is safe.
# Rough estimate: Agent 1 ~15 rounds, Agent 2 ~3, Agent 3 ~2,
#                 Agent 4 ~60 (14 tasks × ~4 steps), Agent 5 ~25.
# ---------------------------------------------------------------------------
DEFAULT_N_ROUND = 200


def _setup_workspace(run_name: str | None) -> Path:
    """Create the per-run workspace directory and configure config.workspace.path."""
    tag = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = (Path("workspace") / "runs" / tag).resolve()
    (run_dir / "docs").mkdir(parents=True, exist_ok=True)
    config.workspace.path = run_dir
    logger.info(f"Run workspace: {run_dir}")
    return run_dir


async def main(user_requirement: str, n_round: int, run_name: str | None) -> None:
    run_dir = _setup_workspace(run_name)

    print()
    print("=" * 70)
    print("  MetaGPT-BI — Agentic BI Architecture")
    print("=" * 70)
    print(f"\n  Run workspace : {run_dir}")
    print(f"  Round budget  : {n_round}")
    print(f"  Requirement   : {user_requirement[:80]}{'...' if len(user_requirement) > 80 else ''}")
    print()
    print("  Agents:")
    print("    Agent 1  Alice   BI Requirements Analyst")
    print("    Agent 2  Bob     BI Data Modeler")
    print("    Agent 3  Eve     BI Solution Architect")
    print("    Agent 4  Alex    BI Analytics Engineer")
    print("    Agent 5  Edward  BI QA Engineer")
    print()
    print("  Alice will begin the elicitation conversation shortly.")
    print("  Respond to her questions when prompted.")
    print("-" * 70)
    print()

    team = Team(use_mgx=False)
    team.hire([
        BIRequirementsAnalyst(),
        BIDataModeler(),
        BISolutionArchitect(),
        BIAnalyticsEngineer(),
        BIQAEngineer(),
    ])

    # DEV-71: Editor.working_dir defaults to the global DEFAULT_WORKSPACE_ROOT and is
    # not updated when config.workspace.path changes. Point each agent's editor to the
    # per-run directory so all artifacts land in workspace/runs/<run_name>/docs/.
    # DEV-77: DbtRunner._dbt_projects_dir overrides DEFAULT_DBT_PROJECTS_DIR so that
    # dbt models and profiles also land inside the per-run directory for all scenarios.
    for role in team.env.roles.values():
        role.editor.working_dir = run_dir
        if isinstance(role, BIAnalyticsEngineer):
            role._get_dbt_runner()._dbt_projects_dir = run_dir / "dbt_project"

    team.run_project(user_requirement)
    await team.run(n_round=n_round)

    # --- Cost summary -------------------------------------------------------
    cm = team.cost_manager
    prompt_tokens = cm.total_prompt_tokens
    completion_tokens = cm.total_completion_tokens
    total_tokens = prompt_tokens + completion_tokens
    total_cost_usd = cm.total_cost
    model_name = getattr(config.llm, "model", "unknown")

    cost_section = (
        "\n\n---\n\n"
        "## LLM Cost Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Model | {model_name} |\n"
        f"| Prompt tokens | {prompt_tokens:,} |\n"
        f"| Completion tokens | {completion_tokens:,} |\n"
        f"| Total tokens | {total_tokens:,} |\n"
        f"| Estimated cost | ${total_cost_usd:.4f} USD |\n"
    )

    # Append cost section to the validation feedback report so it appears in
    # the final artifact delivered to the human user.
    for report_name in ("validation_feedback_report.md", "failed_validation_report.md"):
        report_path = run_dir / "docs" / report_name
        if report_path.exists():
            existing = report_path.read_text(encoding="utf-8")
            report_path.write_text(existing + cost_section, encoding="utf-8")
            break

    # --- Final terminal summary ---------------------------------------------
    print()
    print("=" * 70)
    print("  Pipeline complete.")
    print()
    print("  Artifacts saved to:")
    docs_dir = run_dir / "docs"
    if docs_dir.exists():
        for artifact in sorted(docs_dir.iterdir()):
            print(f"    {artifact.relative_to(Path.cwd())}")
    print()
    print("  LLM cost summary:")
    print(f"    Model              : {model_name}")
    print(f"    Prompt tokens      : {prompt_tokens:,}")
    print(f"    Completion tokens  : {completion_tokens:,}")
    print(f"    Total tokens       : {total_tokens:,}")
    print(f"    Estimated cost     : ${total_cost_usd:.4f} USD")
    print("=" * 70)
    print()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bi_team.py",
        description="MetaGPT-BI Agentic BI Architecture — full multi-agent pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "user_requirement",
        help=(
            "Initial user requirement message. Alice will refine it through "
            "the elicitation conversation. "
            'Example: "I need a BI solution for weekly sales analysis. I have CSV files."'
        ),
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_N_ROUND,
        metavar="N",
        help=f"Maximum reasoning rounds for the team (default: {DEFAULT_N_ROUND}).",
    )
    parser.add_argument(
        "--run-name",
        metavar="NAME",
        default=None,
        help=(
            "Custom name for the run workspace directory under workspace/runs/. "
            "Defaults to a YYYYMMDD_HHMMSS timestamp."
        ),
    )
    return parser.parse_args()


def cli_entry():
    """Console script entry point — registered as `metagpt-bi` command by setup.py."""
    args = _parse_args()
    asyncio.run(main(
        user_requirement=args.user_requirement,
        n_round=args.rounds,
        run_name=args.run_name,
    ))


if __name__ == "__main__":
    cli_entry()
