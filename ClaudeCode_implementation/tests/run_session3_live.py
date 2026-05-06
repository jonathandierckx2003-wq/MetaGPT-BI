"""
Live integration test for Session 3: BIRequirementsAnalyst (Agent 1 — Alice).

Run from the REPO ROOT:
    python ClaudeCode_implementation/tests/run_session3_live.py

Requires:
    - config/config2.yaml with a valid LLM API key
    - Test CSV files in ClaudeCode_implementation/test_data/

What to expect:
    Phase 1 — Alice asks elicitation questions in the terminal one by one.
              Type your answers and press Enter.
    Phase 2 — Alice calls generate_brd() which makes an LLM call and saves
              docs/business_requirement_document.md. No user input needed.

If Cerebras rate-limits you (HTTP 429), just wait ~60 s and the retry will
kick in (MetaGPT's LLM wrapper retries automatically). If it hangs for more
than 2 minutes, kill it (Ctrl-C) and re-run — the CSV files and config are
stateless so no cleanup is needed.
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

from metagpt.roles.bi.bi_requirements_analyst import BIRequirementsAnalyst
from metagpt.team import Team

# ---------------------------------------------------------------------------
# Initial user requirement message
# Mention exact file paths so Llama doesn't have to guess.
# ---------------------------------------------------------------------------
USER_REQUIREMENT = (
    "I need a BI application to analyse the sales performance of my e-commerce store. "
    "I have three CSV data files available:\n"
    "  - ClaudeCode_implementation/test_data/E-commerece sales data 2024.csv "
    "(user interactions: user_id, product_id, interaction_type, timestamp)\n"
    "  - ClaudeCode_implementation/test_data/customer_details.csv "
    "(customer demographics and purchase behaviour)\n"
    "  - ClaudeCode_implementation/test_data/product_details.csv "
    "(product catalogue with names, categories and prices)\n"
    "Please help me define my BI requirements and produce a Business Requirement Document."
)

N_ROUND = 35  # generous budget: ~7 elicitation turns + data inspection calls + BRD generation


async def main():
    print()
    print("=" * 70)
    print("  Live integration test — BIRequirementsAnalyst (Alice, Agent 1)")
    print("=" * 70)
    print(f"\nLLM  : Cerebras / llama3.1-8b  (config/config2.yaml)")
    print(f"Data : ClaudeCode_implementation/test_data/  (3 CSV files)")
    print(f"Output: docs/business_requirement_document.md")
    print(f"Budget: {N_ROUND} reasoning rounds\n")
    print("Alice will ask you questions during Phase 1. Type your answers and")
    print("press Enter. She will produce the BRD automatically in Phase 2.\n")
    print("-" * 70)
    print(f"Initial request sent to Alice:\n  {USER_REQUIREMENT[:120]}...")
    print("-" * 70)
    print()

    # Ensure docs/ exists so the Editor.write call in generate_brd() succeeds
    Path("docs").mkdir(exist_ok=True)

    team = Team()
    team.hire([BIRequirementsAnalyst()])
    team.run_project(USER_REQUIREMENT)
    await team.run(n_round=N_ROUND)

    print()
    print("=" * 70)
    brd_path = Path("docs") / "business_requirement_document.md"
    if brd_path.exists():
        size = brd_path.stat().st_size
        print(f"  BRD saved: {brd_path}  ({size} bytes)")
    else:
        print("  WARNING: docs/business_requirement_document.md was NOT created.")
        print("  Phase 2 may not have been reached within the round budget.")
        print("  Re-run and answer questions more briefly to reach Phase 2 sooner,")
        print("  or increase N_ROUND at the top of this script.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
