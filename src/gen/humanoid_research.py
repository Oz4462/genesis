"""
Thin re-export shim for backward compatibility.

The canonical implementation lives in:
    gen.humanoids.humanoid_research

This allows:
    python -m gen.humanoid_research
    from gen import humanoid_research
    from gen.humanoid_research import HumanoidResearchModule
"""

from .humanoids.humanoid_research import (  # noqa: F401
    HUMANOID_TAXONOMY,
    HumanoidResearchModule,
    build_taxonomy,
    create_module,
    # Phase5 / autonomous / y features for full CLI + "from gen import" exposure
    chat_loop,
    continuous_autonomous_loop,
    LongBackgroundJob,
    start_or_resume_long_job,
    get_long_job_status,
    promote_best_variant_to_aethon,
    schedule_long_background,
    HumanoidResearcher,
    autonomous_research_agent,
    run_resurrection_workflow,
    get_scheduler_status,
    get_promoted_aethon,
    _quick_evaluate,
)

__all__ = [
    "HumanoidResearchModule",
    "create_module",
    "build_taxonomy",
    "HUMANOID_TAXONOMY",
    "chat_loop",
    "continuous_autonomous_loop",
    "LongBackgroundJob",
    "start_or_resume_long_job",
    "get_long_job_status",
    "promote_best_variant_to_aethon",
    "schedule_long_background",
    "HumanoidResearcher",
    "autonomous_research_agent",
    "run_resurrection_workflow",
    "schedule_long_background",
    "get_scheduler_status",
    "get_promoted_aethon",
    "_quick_evaluate",
]
