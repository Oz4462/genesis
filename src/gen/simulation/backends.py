"""backends — the SimulatorBackend seam: pluggable physics simulators behind one interface (TC4).

A simulator is GENESIS' honest data source for the discovery arm (SINDy reads CLEAN trajectories, never the
closed form it is trying to recover). This seam lets the IN-HOUSE deterministic simulator be the offline
default while an external process-/library-oracle simulator (MuJoCo Apache-2.0, ngspice, ...) is an opt-in,
import-guarded adapter — exactly the offline-first / external-opt-in discipline (CLAUDE.md §6, INVENTOR §10¾).

Every backend maps a :class:`PendulumSpec` to a ``multibody.Trajectory`` that ``discovery.sindy.discover_ode``
can consume. The offline ``MultibodyPendulumBackend`` wraps the verified RK4 ``simulate_pendulum``. The
external ``MujocoPendulumBackend`` is import-guarded: ``available()`` is False without the tool and
``simulate`` raises :class:`SimulatorUnavailable` — a clean skip, never a fabricated trajectory.
"""

from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..core.errors import GenesisError
from .multibody import STANDARD_GRAVITY, Trajectory, simulate_pendulum


class SimulatorUnavailable(GenesisError):
    """An external simulator backend was asked to run but its tool is not installed. Loud and honest — the
    caller skips this backend (or falls back to the offline default), never gets a faked trajectory."""

    def __init__(self, tool: str) -> None:
        super().__init__(f"simulator backend tool {tool!r} is not installed "
                         f"(opt-in dependency; the offline MultibodyPendulumBackend is the default)")


@dataclass(frozen=True)
class PendulumSpec:
    """A damped pendulum to simulate — the seam's input. ``damping`` is the linear coefficient c in the
    damping torque τ = −c·ω; the equation of motion is ``I·θ̈ = −c·ω − m·g·d·sinθ``. Physical magnitudes must
    be positive (no silent default for a physical quantity)."""

    theta0: float
    inertia: float
    mass: float
    com_distance: float
    omega0: float = 0.0
    damping: float = 0.0
    duration: float = 12.0
    dt: float = 0.004
    g: float = STANDARD_GRAVITY

    def __post_init__(self) -> None:
        if not (self.inertia > 0 and self.mass > 0 and self.com_distance > 0):
            raise ValueError("inertia, mass, and com_distance must be positive")
        if not (self.duration > 0 and self.dt > 0):
            raise ValueError("duration and dt must be positive")


@runtime_checkable
class SimulatorBackend(Protocol):
    """A pluggable physics simulator: maps a :class:`PendulumSpec` to a trajectory the discovery arm reads."""

    name: str

    def simulate(self, spec: PendulumSpec) -> Trajectory:
        ...


class MultibodyPendulumBackend:
    """The offline default: the verified in-house RK4 ``simulate_pendulum`` (deterministic, no dependency).
    Satisfies :class:`SimulatorBackend`."""

    name = "multibody"

    def simulate(self, spec: PendulumSpec) -> Trajectory:
        c = spec.damping
        return simulate_pendulum(
            spec.theta0, spec.omega0, lambda t, th, om: -c * om,
            inertia=spec.inertia, mass=spec.mass, com_distance=spec.com_distance,
            duration=spec.duration, dt=spec.dt, g=spec.g)


class MujocoPendulumBackend:
    """An external process-/library-oracle simulator adapter (MuJoCo, Apache-2.0) behind the same seam.

    Import-guarded: ``available()`` reports whether MuJoCo is importable; ``simulate`` raises
    :class:`SimulatorUnavailable` when it is not, so the backend SKIPS cleanly rather than fabricating a
    trajectory. When MuJoCo is present it builds a single-hinge pendulum MJCF and integrates it; energy is
    the closed-form ``½·I·ω² + m·g·d·(1−cosθ)`` from the spec (MuJoCo's geom inertia differs from a point
    mass, so the two backends agree on structure, not bit-for-bit — that is the honest point of a seam).

    STATUS: the live MuJoCo path is BLOCKED here (MuJoCo not installed in this environment); the tested
    contract is the clean absent-skip. Install ``mujoco`` (pip, Apache-2.0) to exercise the live path."""

    name = "mujoco"

    @staticmethod
    def available() -> bool:
        return importlib.util.find_spec("mujoco") is not None

    def simulate(self, spec: PendulumSpec) -> Trajectory:
        if not self.available():
            raise SimulatorUnavailable("mujoco")
        import mujoco

        length = 2.0 * spec.com_distance  # com at half-length of a uniform rod
        xml = (
            f'<mujoco><option gravity="0 0 -{spec.g}" timestep="{spec.dt}"/>'
            f'<worldbody><body pos="0 0 0">'
            f'<joint name="hinge" type="hinge" axis="0 1 0" damping="{spec.damping}"/>'
            f'<geom type="capsule" fromto="0 0 0 0 0 -{length}" size="0.02" mass="{spec.mass}"/>'
            f'</body></worldbody></mujoco>'
        )
        model = mujoco.MjModel.from_xml_string(xml)
        data = mujoco.MjData(model)
        data.qpos[0] = spec.theta0
        data.qvel[0] = spec.omega0

        n = int(spec.duration / spec.dt)
        ts: list[float] = []
        thetas: list[float] = []
        omegas: list[float] = []
        energies: list[float] = []
        for i in range(n):
            th = float(data.qpos[0])
            om = float(data.qvel[0])
            ts.append(i * spec.dt)
            thetas.append(th)
            omegas.append(om)
            energies.append(0.5 * spec.inertia * om * om
                            + spec.mass * spec.g * spec.com_distance * (1.0 - math.cos(th)))
            mujoco.mj_step(model, data)
        return Trajectory(t=ts, theta=thetas, omega=omegas, energy=energies)


def default_backend() -> SimulatorBackend:
    """The offline default simulator backend (in-house RK4). Use this unless an external backend is explicitly
    selected and ``available()``."""
    return MultibodyPendulumBackend()


__all__ = [
    "PendulumSpec", "SimulatorBackend", "SimulatorUnavailable",
    "MultibodyPendulumBackend", "MujocoPendulumBackend", "default_backend",
]
