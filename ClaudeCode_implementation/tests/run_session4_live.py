"""
Live integration test for Session 4: BIDataModeler (Agent 2 — Bob).

Run from the REPO ROOT:
    python ClaudeCode_implementation/tests/run_session4_live.py

Requires:
    - config/config2.yaml with a valid LLM API key
    - workspace/docs/business_requirement_document.md produced by Session 3

What to expect:
    No user input needed. Bob runs fully autonomously:
      1. Reads the BRD injected as a pre-published WriteBRD message
      2. Executes the four-step dimensional modeling reasoning loop
      3. Calls generate_data_model() which makes an LLM call and saves:
           workspace/docs/dimensional_model_specification.md
           workspace/docs/conceptual_schema.mermaid  (+ conceptual_schema.svg)
           workspace/docs/logical_schema.mermaid     (+ logical_schema.svg)

If the LLM rate-limits you (HTTP 429), wait ~60 s and re-run.
If it hangs for more than 3 minutes, kill it (Ctrl-C) and re-run.
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
from metagpt.roles.bi.bi_data_modeler import BIDataModeler
from metagpt.schema import Message
from metagpt.team import Team
from metagpt.utils.common import any_to_str

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BRD_PATH = Path("workspace/docs/business_requirement_document.md")
N_ROUND = 20  # generous budget: ~4 reasoning steps + generate_data_model LLM call


async def main():
    print()
    print("=" * 70)
    print("  Live integration test — BIDataModeler (Bob, Agent 2)")
    print("=" * 70)
    print(f"\nLLM  : OpenAI / gpt-5.4-mini  (config/config2.yaml)")
    print(f"Input: {BRD_PATH}")
    print(f"Output:")
    print(f"  workspace/docs/dimensional_model_specification.md")
    print(f"  workspace/docs/conceptual_schema.mermaid  (+ .svg if rendering available)")
    print(f"  workspace/docs/logical_schema.mermaid     (+ .svg if rendering available)")
    print(f"Budget: {N_ROUND} reasoning rounds\n")
    print("-" * 70)

    # Load the BRD produced by Session 3
    if not BRD_PATH.exists():
        print(f"\nERROR: BRD not found at {BRD_PATH}")
        print("Run the Session 3 live test first to produce the BRD:")
        print("  python ClaudeCode_implementation/tests/run_session3_live.py")
        return

    brd_content = BRD_PATH.read_text(encoding="utf-8")
    print(f"BRD loaded: {BRD_PATH}  ({len(brd_content)} chars, {brd_content.count(chr(10))} lines)")
    print("-" * 70)
    print()

    # Assemble the team with only Bob
    team = Team(use_mgx=False)
    team.hire([BIDataModeler()])

    # Inject the BRD as a pre-published WriteBRD message — simulates Alice's output
    team.env.publish_message(Message(
        content=brd_content,
        cause_by=any_to_str(WriteBRD),
        sent_from="Alice",
    ))

    await team.run(n_round=N_ROUND)

    print()
    print("=" * 70)
    expected_files = [
        Path("workspace/docs/dimensional_model_specification.md"),
        Path("workspace/docs/conceptual_schema.mermaid"),
        Path("workspace/docs/logical_schema.mermaid"),
    ]
    all_ok = True
    for path in expected_files:
        if path.exists():
            size = path.stat().st_size
            print(f"  [OK] {path}  ({size} bytes)")
        else:
            print(f"  [MISSING] MISSING: {path}")
            all_ok = False

    # Also report SVG renderings if present
    for svg_path in [
        Path("workspace/docs/conceptual_schema.svg"),
        Path("workspace/docs/logical_schema.svg"),
    ]:
        if svg_path.exists():
            size = svg_path.stat().st_size
            print(f"  [OK] {svg_path}  ({size} bytes)  [rendered]")

    if not all_ok:
        print()
        print("  WARNING: One or more artifacts were NOT created.")
        print("  Bob may not have reached generate_data_model() within the round budget.")
        print("  Try increasing N_ROUND at the top of this script, or re-run.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
