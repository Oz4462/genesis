"""humanoid_researcher — Deeply integrated Genesis Agent for AETHON / Next-Gen Humanoid research & evolution.

This is the "tiefe Integration" of the humanoid_research module:
- Implements the standard Agent protocol (run(state) -> state).
- Uses the same LLM stack (make_llm) as the rest of Genesis.
- Leverages process_dream, ledger, evolve_more_on_axes, full_pipeline.
- Gap-driven, claim-backed, fully automated.
- Usable by Conductor, as part of councils, or directly.

When the user talks in the dedicated chat, or the autonomous loop runs,
this agent is what actually executes the research + evolution + pipeline work.
"""

from __future__ import annotations

from typing import Any

from ..core.interfaces import Agent
from ..core.state import RunState, Question
from ..humanoids.humanoid_research import (
    create_module,
    HumanoidResearcher as _CoreResearcher,
)


class HumanoidResearcher(Agent):
    """Genesis-native agent for humanoid evolution.

    Responsibilities:
    - Interpret research/evolution requests (via LLM or dream).
    - Drive iterative evolution on specific axes (hands, power, structure, ...).
    - Trigger full Genesis pipeline on evolved specs.
    - Record everything as Claims.
    - Feed results back into state (for Conductor / inventor etc.).

    This makes the entire humanoid capability feel like talking to Genesis itself.
    """

    name = "humanoid_researcher"

    def __init__(self):
        self._mod = create_module()
        self._core = _CoreResearcher()

    async def run(self, state: RunState) -> RunState:
        """Main entry point following the Agent protocol.

        Expects either:
        - state.question.raw containing a natural language request about humanoid evolution, or
        - existing evolved data in state.

        It will:
        1. Use the core researcher (LLM) to create a plan.
        2. Execute evolution + pipeline.
        3. Attach results and claims to state.
        4. Return updated state.
        """
        question_text = ""
        if hasattr(state, "question") and state.question:
            question_text = getattr(state.question, "raw", "") or ""

        # If no question, look for a "humanoid_dream" or similar in state (LUMEN style)
        if not question_text and hasattr(state, "extra") and isinstance(state.extra, dict):
            question_text = state.extra.get("humanoid_request", "") or state.extra.get("dream", "")

        if not question_text:
            # Honest abstain if nothing to do
            if not hasattr(state, "humanoid_researcher_notes"):
                state.humanoid_researcher_notes = []
            state.humanoid_researcher_notes.append("No humanoid request found in state — abstaining.")
            return state

        # Use the deeply integrated core researcher for planning
        try:
            plan = await self._core.interpret_and_plan(question_text)
        except Exception:
            # Fallback simple plan
            plan = {
                "axes": ["hands_tendon", "power_cabling", "structure_shank"],
                "run_pipeline": True,
                "research_focus": question_text[:200],
            }

        # Execute using the automation (evolution + full pipeline)
        exec_result = self._core.execute_plan(plan)

        # Record in state
        if not hasattr(state, "humanoid_evolution_results"):
            state.humanoid_evolution_results = []
        state.humanoid_evolution_results.append(exec_result)

        if not hasattr(state, "humanoid_researcher_notes"):
            state.humanoid_researcher_notes = []
        state.humanoid_researcher_notes.append(
            f"Executed plan for: {question_text[:100]}... -> axes={plan.get('axes')}, pipeline={plan.get('run_pipeline')}"
        )

        # Attach evolved spec if produced (so downstream agents/inventor can use it)
        if "pipeline" in exec_result and exec_result["pipeline"].get("evolved_spec_available"):
            # Try to surface the latest evolved spec for the rest of the pipeline
            try:
                from ..humanoids.genesis_humanoid import build_aethon
                # The module already did the build; we can note it
                state.evolved_humanoid_spec = exec_result.get("pipeline")
            except Exception:
                pass

        return state

    # Convenience for direct use outside full RunState (e.g. from chat)
    async def research_and_evolve(self, request: str) -> dict:
        """Direct entry for the chat / autonomous modes."""
        plan = await self._core.interpret_and_plan(request)
        return self._core.execute_plan(plan)
