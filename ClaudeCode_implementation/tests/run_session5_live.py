"""
Live integration test for Session 5: BISolutionArchitect (Agent 3 — Eve).

Run from the REPO ROOT:
    python ClaudeCode_implementation/tests/run_session5_live.py

Requires:
    - config/config2.yaml with a valid LLM API key
    - workspace/docs/business_requirement_document.md produced by Session 3
    - workspace/docs/dimensional_model_specification.md produced by Session 4
    - workspace/docs/conceptual_schema.mermaid produced by Session 4
    - workspace/docs/logical_schema.mermaid produced by Session 4

What to expect:
    No user input needed. Eve runs fully autonomously:
      1. Reads BRD and data model artifacts injected as pre-published messages
      2. Executes the three-step execution planning reasoning loop
      3. Calls generate_execution_plan() which makes an LLM call and saves:
           workspace/docs/execution_plan.json
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
from pathlib import Path

from metagpt.actions.bi.write_brd import WriteBRD
from metagpt.actions.bi.write_data_model import WriteDataModel
from metagpt.roles.bi.bi_solution_architect import BISolutionArchitect
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

N_ROUND = 20  # generous budget: ~3 reasoning steps + generate_execution_plan LLM call


async def main():
    print()
    print("=" * 70)
    print("  Live integration test — BISolutionArchitect (Eve, Agent 3)")
    print("=" * 70)
    print(f"\nInput artifacts:")
    print(f"  BRD              : {BRD_PATH}")
    print(f"  Spec             : {SPEC_PATH}")
    print(f"  Conceptual schema: {CONCEPTUAL_PATH}")
    print(f"  Logical schema   : {LOGICAL_PATH}")
    print(f"\nOutput:")
    print(f"  workspace/docs/execution_plan.json")
    print(f"\nBudget: {N_ROUND} reasoning rounds\n")
    print("-" * 70)

    # --- Check all input files exist ---
    missing = []
    for p in [BRD_PATH, SPEC_PATH, CONCEPTUAL_PATH, LOGICAL_PATH]:
        if not p.exists():
            missing.append(str(p))

    if missing:
        print("\nERROR: The following required input files are missing:")
        for m in missing:
            print(f"  - {m}")
        print("\nRun the earlier session live tests first:")
        print("  Session 3: python ClaudeCode_implementation/tests/run_session3_live.py")
        print("  Session 4: python ClaudeCode_implementation/tests/run_session4_live.py")
        return

    # --- Load all artifacts ---
    brd_content = BRD_PATH.read_text(encoding="utf-8")
    spec_content = SPEC_PATH.read_text(encoding="utf-8")
    conceptual_content = CONCEPTUAL_PATH.read_text(encoding="utf-8")
    logical_content = LOGICAL_PATH.read_text(encoding="utf-8")

    print(f"BRD loaded       : {len(brd_content)} chars")
    print(f"Spec loaded      : {len(spec_content)} chars")
    print(f"Conceptual loaded: {len(conceptual_content)} chars")
    print(f"Logical loaded   : {len(logical_content)} chars")
    print("-" * 70)
    print()

    # --- Assemble the combined WriteDataModel message (same format as BIDataModeler.generate_data_model()) ---
    combined_data_model = (
        f"## Dimensional Model Specification\n\n{spec_content}\n\n"
        f"---\n\n"
        f"## Conceptual Schema (Mermaid erDiagram)\n\n{conceptual_content}\n\n"
        f"---\n\n"
        f"## Logical Schema (Mermaid erDiagram)\n\n{logical_content}"
    )

    # --- Assemble the team with only Eve ---
    team = Team(use_mgx=False)
    team.hire([BISolutionArchitect()])

    # --- Inject the BRD as a pre-published WriteBRD message (simulates Alice's output) ---
    team.env.publish_message(Message(
        content=brd_content,
        cause_by=any_to_str(WriteBRD),
        sent_from="Alice",
    ))

    # --- Inject the combined data model as a pre-published WriteDataModel message (simulates Bob's output) ---
    team.env.publish_message(Message(
        content=combined_data_model,
        cause_by=any_to_str(WriteDataModel),
        sent_from="Bob",
    ))

    await team.run(n_round=N_ROUND)

    # --- Results summary ---
    print()
    print("=" * 70)
    output_path = Path("workspace/docs/execution_plan.json")
    if output_path.exists():
        size = output_path.stat().st_size
        print(f"  ✓ {output_path}  ({size} bytes)")

        # Validate the JSON is parseable and contains at least one task
        try:
            with open(output_path, encoding="utf-8") as f:
                tasks = json.load(f)
            print(f"  ✓ Valid JSON with {len(tasks)} tasks")

            # Check all tasks have required fields
            required_fields = {"task_id", "dependent_task_ids", "instruction", "task_type"}
            valid_task_types = {
                "INSTANTIATION", "CONNECTION_SETUP", "CREDENTIAL_REQUEST",
                "SCHEMA_CREATION", "DATA_INGESTION", "TRANSFORMATION",
            }
            bad_tasks = []
            for t in tasks:
                missing_fields = required_fields - set(t.keys())
                if missing_fields:
                    bad_tasks.append(f"  Task {t.get('task_id', '?')}: missing {missing_fields}")
                if t.get("task_type") not in valid_task_types:
                    bad_tasks.append(f"  Task {t.get('task_id', '?')}: invalid task_type '{t.get('task_type')}'")

            if bad_tasks:
                print(f"\n  WARNING: Structural issues found in plan:")
                for msg in bad_tasks:
                    print(msg)
            else:
                print(f"  ✓ All tasks have required fields and valid task_types")

            # Print task summary
            print(f"\n  Task breakdown:")
            from collections import Counter
            type_counts = Counter(t.get("task_type", "?") for t in tasks)
            for task_type, count in sorted(type_counts.items()):
                print(f"    {task_type}: {count}")

        except json.JSONDecodeError as e:
            print(f"\n  WARNING: execution_plan.json is not valid JSON: {e}")
    else:
        print(f"  ✗ MISSING: {output_path}")
        print()
        print("  WARNING: execution_plan.json was NOT created.")
        print("  Eve may not have reached generate_execution_plan() within the round budget.")
        print("  Try increasing N_ROUND at the top of this script, or re-run.")

    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
