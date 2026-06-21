"""universe_bridge — the Universe Simulator Bridge (build doc 4.7, Phase 5, deliberately last).

The heaviest, most externally-dependent feature — and the doc is explicit that it only earns
its place once the core loop works, which it now does. This is an ADAPTER: it offloads a
simulation to a backend, then brings the result BACK THROUGH THE GATES (the simulated data is
run through the discovery engine and validated, exactly like real-world data).

The honesty that keeps this from being vapourware: the external HPC / N-body / lattice / CFD
engine is a DECLARED SEAM — a ``SimulatorBackend`` protocol, nothing more. A real engine plugs
in behind it. But the bridge does NOT depend on one existing: the ``InProcessReferenceBackend``
is a small, real, deterministic numpy physics simulation that (a) proves the interface end to
end and (b) is the offline default. So the bridge is fully testable and useful with zero
external infrastructure, and a heavyweight backend is a drop-in, never a hidden requirement.

The loop it closes is the whole point of a "universe explorer": SIMULATE a system, DISCOVER the
law from the simulated data, VERIFY it through the gates. A two-body orbit simulated here is
handed to the engine, which rediscovers Kepler's third law and the gate confirms it — the
external world (here, a physics simulator) is never trusted; its output is gated like anything
else. Offline, deterministic, numpy-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np

from .engine import Constant, DiscoveryProblem, DiscoveryResult, Variable, discover_new_formulas

#: Above this many sweep points the local reference backend is considered too small — the
#: controller's policy then offloads to an external backend (build doc: conductor decides).
DEFAULT_MAX_LOCAL_POINTS = 10_000


@dataclass(frozen=True)
class SimulationSpec:
    """What to simulate: a `system` the backend knows, a `sweep` input (name, unit, values) to
    vary, the `observable` (name, unit) to measure, and `params` (fixed system constants with
    units, e.g. ``{"mu": (1.327e20, "m^3/s^2")}``)."""

    system: str
    sweep: tuple[str, str, tuple[float, ...]]
    observable: tuple[str, str]
    params: dict[str, tuple[float, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationData:
    """A backend's output as a gate-ready ``DiscoveryProblem`` plus provenance (which backend)."""

    problem: DiscoveryProblem
    backend: str
    note: str = ""


@runtime_checkable
class SimulatorBackend(Protocol):
    """The declared seam: any simulator — the in-process reference one or an external HPC /
    N-body / lattice / CFD engine — implements ``run(spec) -> SimulationData``. The bridge
    depends only on this contract, never on a specific engine existing."""

    name: str

    def run(self, spec: "SimulationSpec") -> "SimulationData": ...


# --- the in-process reference backend (proves the interface; the offline default) -----------

def _two_body_orbit(a: np.ndarray, params: dict[str, float]) -> np.ndarray:
    """Kepler two-body period T = 2π·a^(3/2)·mu^(-1/2) — the real gravitational physics."""
    mu = params["mu"]
    return 2.0 * math.pi * a ** 1.5 / math.sqrt(mu)


def _harmonic_oscillator(m: np.ndarray, params: dict[str, float]) -> np.ndarray:
    """Mass-spring period T = 2π·sqrt(m/k) = 2π·m^(1/2)·k^(-1/2)."""
    k = params["k"]
    return 2.0 * math.pi * np.sqrt(m / k)


#: Reference systems the in-process backend can simulate. Each maps a sweep array + params to
#: the observable — real physics, deterministic.
_SYSTEMS = {
    "two_body_orbit": _two_body_orbit,
    "harmonic_oscillator": _harmonic_oscillator,
}


class InProcessReferenceBackend:
    """A small, deterministic numpy physics simulator. It proves the bridge interface and is
    the offline default; a real external HPC engine implements the same ``run`` and drops in."""

    name = "in-process-reference"

    def run(self, spec: SimulationSpec) -> SimulationData:
        fn = _SYSTEMS.get(spec.system)
        if fn is None:
            raise ValueError(f"reference backend cannot simulate {spec.system!r}; "
                             f"known: {sorted(_SYSTEMS)} (an external backend may cover it)")
        sweep_name, sweep_unit, sweep_vals = spec.sweep
        x = np.asarray(sweep_vals, dtype=float)
        y = fn(x, {k: v for k, (v, _u) in spec.params.items()})
        obs_name, obs_unit = spec.observable
        problem = DiscoveryProblem(
            idea=f"Aus Simulation '{spec.system}' ({self.name}) entdeckt",
            target=Variable(obs_name, obs_unit, tuple(y)),
            inputs=(Variable(sweep_name, sweep_unit, tuple(x)),),
            constants=tuple(Constant(k, v, u) for k, (v, u) in spec.params.items()),
            run_id=f"sim:{spec.system}")
        return SimulationData(problem=problem, backend=self.name,
                              note=f"{len(x)} Punkte, System {spec.system}")


def should_offload(spec: SimulationSpec, *, max_local_points: int = DEFAULT_MAX_LOCAL_POINTS) -> bool:
    """The controller's local-vs-offloaded decision: offload when the sweep is larger than the
    local reference backend should handle. Deterministic; the actual offload target is whatever
    ``SimulatorBackend`` the caller passes."""
    return len(spec.sweep[2]) > max_local_points


@dataclass(frozen=True)
class BridgeResult:
    """The bridge outcome: the simulation data, the discovery run over it, the discovered law
    (if any) and its gate verdict — the simulated 'universe' brought back through the gates."""

    data: SimulationData
    discovery: DiscoveryResult
    discovered_law: str | None
    verdict: str


def bridge_discover(
    spec: SimulationSpec,
    backend: SimulatorBackend | None = None,
    *,
    known_laws: dict[str, dict[str, float]] | None = None,
) -> BridgeResult:
    """Run the simulation via `backend` (the in-process reference backend by default, or any
    external ``SimulatorBackend``), then bring the result BACK THROUGH THE GATES: discover the
    law from the simulated data and validate it. The simulator's output is never trusted — it
    is gated like real-world data. Returns the data, the discovery, and the honest verdict."""
    backend = backend if backend is not None else InProcessReferenceBackend()
    data = backend.run(spec)
    discovery = discover_new_formulas(data.problem, known_laws=known_laws)
    best = discovery.validated[0] if discovery.validated else None
    return BridgeResult(
        data=data, discovery=discovery,
        discovered_law=best.candidate.expression if best else None,
        verdict=best.verdict if best else (discovery.all_records[0].verdict if discovery.all_records else "kein Kandidat"))
