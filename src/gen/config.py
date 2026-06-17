"""GENESIS configuration + reproducibility hash (PHASE_ALPHA §7, A5).

The config is plain, frozen dataclasses so it is trivially serializable and
hashable. ``config_hash`` is a stable SHA-256 over the canonical JSON form: the
same configuration always yields the same hash, which (together with run_id and
the ledger) is what makes a run reproducible (acceptance criterion A5).

YAML loading is optional and lazy — the package never hard-depends on PyYAML.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Models:
    generator: str = "claude-opus-4-8"   # scout + scholar — Claude (Max) via the claude CLI (OAuth)
    verifier: str = "grok-composer-2.5-fast"  # skeptic — Grok (Max) via the grok CLI (OAuth); MUST differ from generator family
    judge: str | None = None             # optional second judge on dissent


@dataclass(frozen=True)
class PhaseAlphaConfig:
    confidence_threshold: float = 0.7
    max_refine_rounds: int = 3
    require_independent_source: bool = True
    min_sources_for_verified: int = 2
    models: Models = field(default_factory=Models)
    search_backends: tuple[str, ...] = ("semantic_scholar",)


@dataclass(frozen=True)
class PhaseBetaConfig:
    """Phase β (solution space). Inherits α thresholds, adds β specifics.

    `min_grounded_approaches` is the MEASUREMENT threshold for acceptance B2 (when a
    solved problem should yield alternatives) — NOT a gate condition. GATE β enforces
    grounding, never a minimum count, so it can never force the system to invent
    alternatives (PHASE_BETA.md §7).
    """

    confidence_threshold: float = 0.7
    min_grounded_approaches: int = 2
    max_refine_rounds: int = 3
    require_verified_grounding: bool = True
    models: Models = field(default_factory=Models)


@dataclass(frozen=True)
class PhaseGammaConfig:
    """Phase γ (specification). Inherits α/β thresholds, adds γ specifics.

    `derivation_tolerance` is the relative tolerance for the gate's independent
    recompute of DERIVED values (C-6) and for eq-constraints (C-13).
    `require_grounded_approach` keeps the β chain hard: a specification that
    asserts content must be anchored in a grounded Approach (PHASE_GAMMA.md §8).
    """

    confidence_threshold: float = 0.7
    max_refine_rounds: int = 3
    derivation_tolerance: float = 1e-9
    require_grounded_approach: bool = True
    models: Models = field(default_factory=Models)


@dataclass(frozen=True)
class Config:
    phase_alpha: PhaseAlphaConfig = field(default_factory=PhaseAlphaConfig)
    phase_beta: PhaseBetaConfig = field(default_factory=PhaseBetaConfig)
    phase_gamma: PhaseGammaConfig = field(default_factory=PhaseGammaConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Config":
        data = data or {}
        pa = data.get("phase_alpha", {})
        a_models = Models(**{**asdict(Models()), **(pa.get("models") or {})})
        a_fields = {**asdict(PhaseAlphaConfig()), **{k: v for k, v in pa.items() if k != "models"}}
        a_fields["models"] = a_models
        sb = a_fields.get("search_backends")
        if isinstance(sb, str):
            sb = (sb,)  # a single backend name is a 1-tuple, never exploded into characters
        elif sb is None:
            sb = ()
        elif isinstance(sb, (list, tuple)):
            sb = tuple(sb)
        else:
            raise TypeError(
                "phase_alpha.search_backends must be a string or list of strings, "
                f"got {type(sb).__name__}"
            )
        a_fields["search_backends"] = sb

        pb = data.get("phase_beta", {})
        b_models = Models(**{**asdict(Models()), **(pb.get("models") or {})})
        b_fields = {**asdict(PhaseBetaConfig()), **{k: v for k, v in pb.items() if k != "models"}}
        b_fields["models"] = b_models

        pg = data.get("phase_gamma", {})
        g_models = Models(**{**asdict(Models()), **(pg.get("models") or {})})
        g_fields = {**asdict(PhaseGammaConfig()), **{k: v for k, v in pg.items() if k != "models"}}
        g_fields["models"] = g_models

        return Config(
            phase_alpha=PhaseAlphaConfig(**a_fields),
            phase_beta=PhaseBetaConfig(**b_fields),
            phase_gamma=PhaseGammaConfig(**g_fields),
        )


def default_config() -> Config:
    return Config()


def config_hash(config: Config) -> str:
    """Stable SHA-256 of the canonical config — the reproducibility anchor (A5)."""
    canonical = json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_yaml(path: str) -> Config:
    """Load config from YAML (lazy PyYAML import). Raises if PyYAML is missing."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "load_yaml requires PyYAML. Install it, or use default_config()/from_dict()."
        ) from exc
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config.from_dict(data)
