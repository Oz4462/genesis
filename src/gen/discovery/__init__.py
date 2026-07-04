"""GENESIS discovery — the universe-explorer core (GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md).

The honest core loop of the build plan: a human (or Grok) hands in an idea + data; the
engine proposes candidate formulas under DIMENSIONAL constraints (Buckingham-π, the
AI-Feynman insight), fits them, runs every candidate through the EXISTING GENESIS gates
(dimensional consistency C-15, independent recompute C-6, fit/physics consistency,
uncertainty) under the δ-asymmetry, and records every candidate — kept AND rejected — in
a Discovery Graph with provenance. The verdict is honest: ``bestaetigt`` / ``widerlegt`` /
``unentschieden``, never a fabricated discovery.

This is Phase 1 of the build doc (the ``discover_new_formulas`` DoD, Anhang B) plus the
Discovery Graph (4.6 / Anhang C) and the Tournament loop (3.1), validated by the
Rediscovery benchmark (Phase 4 — can it recover Kepler / the ideal gas law from data?).
Everything here is offline, deterministic and numpy/sympy-only; nothing claims a discovery
the gates did not earn.

Exports are lazy (PEP 562) so importing the package is cheap and a missing optional path
never drags weight in.
"""

from __future__ import annotations

__all__ = [
    "Variable",
    "Constant",
    "DiscoveryProblem",
    "Candidate",
    "DiscoveryVerdict",
    "DiscoveryResult",
    "symbolic_regress",
    "discover_new_formulas",
    "dimensional_power_law",
    "judge_candidate",
    "discover",
    "DiscoveryGraph",
    "GraphNode",
    "evolve",
    "TournamentReport",
    "ExplorationController",
    "ExplorationState",
    "ControllerResult",
    "DepthTier",
    "surrogate_score",
    "prefilter",
    "discover_prefiltered",
    "SurrogateRanking",
    "symbiosis_discover",
    "GrokProposer",
    "Proposal",
    "JudgedProposal",
    "SymbiosisResult",
    "CounterfactualWorld",
    "fork_spatial_dimension",
    "fork_constant",
    "fork_from_discovery",
    "gauss_force_exponent",
    "structural_signature",
    "find_analogies",
    "cross_domain_hypotheses",
    "Analogy",
    "CrossDomainHypothesis",
    "annihilate_constant",
    "AnnihilationResult",
    "Axiom",
    "ProofStep",
    "ProofTree",
    "verify_proof",
    "derive",
    "out_of_sample_validate",
    "OutOfSampleResult",
    "pendulum_case",
    "SimulationSpec",
    "SimulationData",
    "SimulatorBackend",
    "InProcessReferenceBackend",
    "BridgeResult",
    "bridge_discover",
    "should_offload",
    "rediscovery_benchmark",
    "BenchmarkCase",
    "kepler_case",
    "ideal_gas_case",
    "discover_multiterm",
    "candidate_term_exponents",
    "Term",
    "MultiTermLaw",
    "evaluate_multiterm_law",
    "multiterm_out_of_sample_validate",
    "MultiTermValidation",
    "discover_transcendental",
    "dimensionless_groups",
    "TranscendentalForm",
    "TranscendentalLaw",
    "RivalForm",
    "discover_rivals",
    "evaluate_rival",
    "propose_resolution",
    "DecisionSpec",
    "propose_resolution_robust",
    "RobustDecisionSpec",
    "discover_correction",
    "CompositionResult",
    "discover_product_law",
    "ProductLaw",
    "discover_product_rivals",
    "ProductRival",
    "evaluate_product_rival",
    "refit_product_rival",
    "product_out_of_sample_validate",
    "ProductValidation",
    "discover_multiplicative_correction",
    "MultiplicativeCorrection",
    "discover_blind_product",
    "BlindProductLaw",
    "discover_blind_rivals",
    "BlindRival",
    "evaluate_blind_rival",
    "refit_blind_rival",
    "blind_product_out_of_sample_validate",
    "discover_additive_argument",
    "AdditiveArgumentLaw",
    "discover_additive_argument_rivals",
    "AdditiveArgumentRival",
    "evaluate_additive_rival",
    "refit_additive_rival",
    "additive_argument_out_of_sample_validate",
    "gp_fit",
    "gp_discover",
    "GPConfig",
    "SymbolicModel",
    "GPVerdict",
    "gp_occam_discover",
    "GPSearchOutcome",
    "OccamRung",
    "PiScaffold",
    "build_pi_scaffold",
    "open_form_benchmark",
    "OpenFormReport",
    "OpenFormCaseResult",
    "additive_freefall_problem",
    "transcendental_sine_problem",
    "gp_noise_redteam_problem",
]


def __getattr__(name: str):
    # Lazy, and — like gen.integration — cached into globals() so a same-named submodule
    # can never shadow a function export.
    _engine_names = ("Variable", "Constant", "DiscoveryProblem", "Candidate",
                     "DiscoveryVerdict", "DiscoveryResult", "symbolic_regress",
                     "discover_new_formulas", "dimensional_power_law", "judge_candidate")
    if name in _engine_names:
        from . import engine as _m
        for n in _engine_names:
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("ExplorationController", "ExplorationState", "ControllerResult", "DepthTier"):
        from . import controller as _m
        for n in ("ExplorationController", "ExplorationState", "ControllerResult", "DepthTier"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("surrogate_score", "prefilter", "discover_prefiltered", "SurrogateRanking"):
        from . import surrogate as _m
        for n in ("surrogate_score", "prefilter", "discover_prefiltered", "SurrogateRanking"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("symbiosis_discover", "GrokProposer", "Proposal", "JudgedProposal", "SymbiosisResult"):
        from . import symbiosis as _m
        for n in ("symbiosis_discover", "GrokProposer", "Proposal", "JudgedProposal", "SymbiosisResult"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("CounterfactualWorld", "fork_spatial_dimension", "fork_constant",
                "fork_from_discovery", "gauss_force_exponent"):
        from . import reality_fork as _m
        for n in ("CounterfactualWorld", "fork_spatial_dimension", "fork_constant",
                  "fork_from_discovery", "gauss_force_exponent"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("structural_signature", "find_analogies", "cross_domain_hypotheses",
                "Analogy", "CrossDomainHypothesis"):
        from . import cosmic_insight as _m
        for n in ("structural_signature", "find_analogies", "cross_domain_hypotheses",
                  "Analogy", "CrossDomainHypothesis"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("annihilate_constant", "AnnihilationResult"):
        from . import assumption_annihilator as _m
        globals()["annihilate_constant"] = _m.annihilate_constant
        globals()["AnnihilationResult"] = _m.AnnihilationResult
        return globals()[name]
    if name in ("Axiom", "ProofStep", "ProofTree", "verify_proof", "derive"):
        from . import first_principles as _m
        for n in ("Axiom", "ProofStep", "ProofTree", "verify_proof", "derive"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("out_of_sample_validate", "OutOfSampleResult"):
        from . import validation as _m
        globals()["out_of_sample_validate"] = _m.out_of_sample_validate
        globals()["OutOfSampleResult"] = _m.OutOfSampleResult
        return globals()[name]
    if name in ("SimulationSpec", "SimulationData", "SimulatorBackend", "InProcessReferenceBackend",
                "BridgeResult", "bridge_discover", "should_offload"):
        from . import universe_bridge as _m
        for n in ("SimulationSpec", "SimulationData", "SimulatorBackend", "InProcessReferenceBackend",
                  "BridgeResult", "bridge_discover", "should_offload"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("DiscoveryGraph", "GraphNode"):
        from . import graph as _m
        globals()["DiscoveryGraph"] = _m.DiscoveryGraph
        globals()["GraphNode"] = _m.GraphNode
        return globals()[name]
    if name == "discover":
        from .run import discover as _discover
        globals()["discover"] = _discover
        return _discover
    if name in ("evolve", "TournamentReport"):
        from . import tournament as _m
        globals()["evolve"] = _m.evolve
        globals()["TournamentReport"] = _m.TournamentReport
        return globals()[name]
    if name in ("rediscovery_benchmark", "BenchmarkCase", "kepler_case", "ideal_gas_case", "pendulum_case",
                "open_form_benchmark", "OpenFormReport", "OpenFormCaseResult", "additive_freefall_problem",
                "transcendental_sine_problem", "gp_noise_redteam_problem"):
        from . import benchmark as _m
        for n in ("rediscovery_benchmark", "BenchmarkCase", "kepler_case", "ideal_gas_case", "pendulum_case",
                  "open_form_benchmark", "OpenFormReport", "OpenFormCaseResult", "additive_freefall_problem",
                  "transcendental_sine_problem", "gp_noise_redteam_problem"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("gp_fit", "gp_discover", "GPConfig", "SymbolicModel", "GPVerdict"):
        from . import symbolic_search as _m
        for n in ("gp_fit", "gp_discover", "GPConfig", "SymbolicModel", "GPVerdict"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("gp_occam_discover", "GPSearchOutcome", "OccamRung", "PiScaffold", "build_pi_scaffold"):
        from . import gp_search as _m
        for n in ("gp_occam_discover", "GPSearchOutcome", "OccamRung", "PiScaffold", "build_pi_scaffold"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_multiterm", "candidate_term_exponents", "Term", "MultiTermLaw",
                "evaluate_multiterm_law", "multiterm_out_of_sample_validate", "MultiTermValidation"):
        from . import multiterm as _m
        for n in ("discover_multiterm", "candidate_term_exponents", "Term", "MultiTermLaw",
                  "evaluate_multiterm_law", "multiterm_out_of_sample_validate", "MultiTermValidation"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_transcendental", "dimensionless_groups", "TranscendentalForm",
                "TranscendentalLaw", "RivalForm", "discover_rivals", "evaluate_rival"):
        from . import transcendental as _m
        for n in ("discover_transcendental", "dimensionless_groups", "TranscendentalForm",
                  "TranscendentalLaw", "RivalForm", "discover_rivals", "evaluate_rival"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("propose_resolution", "DecisionSpec", "propose_resolution_robust", "RobustDecisionSpec"):
        from . import active_resolution as _m
        for n in ("propose_resolution", "DecisionSpec", "propose_resolution_robust", "RobustDecisionSpec"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_correction", "CompositionResult"):
        from . import composition as _m
        for n in ("discover_correction", "CompositionResult"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_product_law", "ProductLaw", "discover_product_rivals", "ProductRival",
                "evaluate_product_rival", "refit_product_rival", "product_out_of_sample_validate",
                "ProductValidation", "discover_multiplicative_correction", "MultiplicativeCorrection"):
        from . import multiplicative as _m
        for n in ("discover_product_law", "ProductLaw", "discover_product_rivals", "ProductRival",
                  "evaluate_product_rival", "refit_product_rival", "product_out_of_sample_validate",
                  "ProductValidation", "discover_multiplicative_correction", "MultiplicativeCorrection"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_blind_product", "BlindProductLaw", "discover_blind_rivals", "BlindRival",
                "evaluate_blind_rival", "refit_blind_rival", "blind_product_out_of_sample_validate"):
        from . import blind_product as _m
        for n in ("discover_blind_product", "BlindProductLaw", "discover_blind_rivals", "BlindRival",
                  "evaluate_blind_rival", "refit_blind_rival", "blind_product_out_of_sample_validate"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    if name in ("discover_additive_argument", "AdditiveArgumentLaw",
                "discover_additive_argument_rivals", "AdditiveArgumentRival",
                "evaluate_additive_rival", "refit_additive_rival",
                "additive_argument_out_of_sample_validate"):
        from . import additive_argument as _m
        for n in ("discover_additive_argument", "AdditiveArgumentLaw",
                  "discover_additive_argument_rivals", "AdditiveArgumentRival",
                  "evaluate_additive_rival", "refit_additive_rival",
                  "additive_argument_out_of_sample_validate"):
            globals()[n] = getattr(_m, n)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
