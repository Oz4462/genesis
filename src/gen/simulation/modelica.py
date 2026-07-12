"""Modelica / OpenModelica adapter — a system / multi-physics simulation seam.

GENESIS's deterministic physics axes (statics, thermal, modal, flight, …) each model ONE
closed-form effect. A SYSTEM model couples several domains together over time — an RC
circuit, a thermal mass with a heat source, a spring-mass-damper, a hydraulic line — and
solves the coupled ODE/DAE. Modelica is the standard acausal language for exactly that,
and OpenModelica (the open compiler/runtime, driven here via ``OMPython``'s
``OMCSessionZMQ``) compiles and simulates such a model.

This module is the import-guarded bridge: give it Modelica source + a model name, it
loads, simulates over a time span, and reads named variables back out of the result —
so a GENESIS-verified component can be handed to a transient multi-physics simulation
WITHOUT GENESIS taking on an un-gated simulation dependency. It is the handoff/cross-check
seam (the analogue of urdf_bridge for dynamics), not a claim that GENESIS itself is a
multi-physics solver.

OpenModelica is an OPTIONAL, EXTERNAL dependency (the ``omc`` compiler + the ``OMPython``
package). Failure is LOUD and typed (``GenesisError``): a missing package/compiler, a
model that fails to load or compile, a simulation that does not produce a result, or a
request for a variable that is not in the result — all surface, never a guessed value.
Determinism: a fixed solver/tolerance and a fixed step count make a run reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import GenesisError


def openmodelica_available() -> bool:
    """True iff the optional ``OMPython`` package can be imported.

    Mirrors ``cad_available`` / ``openfoam_available``: a False is a definitive 'no
    OMPython', so the integration tests can skip-guard cleanly. It does NOT prove the
    ``omc`` compiler is on PATH — the first real :meth:`ModelicaSimulation.connect`
    surfaces that, loudly.
    """
    try:
        import OMPython  # noqa: F401
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class SimulationResult:
    """The outcome of a transient Modelica simulation.

    ``final_values`` maps each requested variable to its value at ``stop_time`` (read out
    of the result, not asserted). ``result_file`` is the path to the raw OpenModelica
    result for any deeper post-processing.
    """

    model: str
    result_file: str
    stop_time: float
    final_values: dict[str, float]


class ModelicaSimulation:
    """A session against OpenModelica via ``OMPython.OMCSessionZMQ``.

    Lifecycle: :meth:`connect` opens the compiler session, :meth:`load_model_string`
    loads Modelica source, :meth:`simulate` compiles+runs it and reads variables back.
    Use as a context manager so the session is always closed.

    No state about a model is invented here: every value returned by :meth:`simulate` is
    read from the OpenModelica result via ``val(var, t)``; a variable absent from the
    result is a loud error.
    """

    def __init__(self) -> None:
        self._omc = None  # type: ignore[assignment]
        self._loaded: set[str] = set()

    def connect(self) -> None:
        """Open the OpenModelica compiler session (lazy import of OMPython).

        Raises:
            GenesisError: ``OMPython`` is not installed, or the ``omc`` session cannot be
                started (e.g. the compiler is not on PATH) — surfaced, never swallowed.
        """
        try:
            from OMPython import OMCSessionZMQ
        except ImportError as exc:  # pragma: no cover - only without OMPython
            raise GenesisError(
                "the Modelica system-simulation adapter needs the optional 'OMPython' "
                "package and the OpenModelica 'omc' compiler; install OMPython "
                "(`pip install OMPython`) and OpenModelica, or use the closed-form "
                "physics axes for a single-effect check."
            ) from exc
        try:
            self._omc = OMCSessionZMQ()
            version = self._omc.sendExpression("getVersion()")
        except Exception as exc:  # noqa: BLE001 - compiler not reachable etc.
            raise GenesisError(
                f"could not start an OpenModelica session (is 'omc' on PATH?): {exc}"
            ) from exc
        if not version:
            raise GenesisError("OpenModelica session started but getVersion() was empty")

    def close(self) -> None:
        """Close the session (best effort)."""
        omc = self._omc
        self._omc = None
        if omc is not None:
            try:
                omc.sendExpression("quit()")
            except Exception:  # noqa: BLE001 - quitting may close the socket first
                pass

    def __enter__(self) -> "ModelicaSimulation":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _require(self):
        if self._omc is None:
            raise GenesisError(
                "ModelicaSimulation is not connected; call connect() (or use it as a "
                "context manager) before loading or simulating."
            )
        return self._omc

    def _eval(self, expr: str):
        """Send an OMC expression, mapping any OMPython transport error to a loud
        GenesisError (so a broken session never bubbles up as an opaque OMC exception)."""
        try:
            return self._require().sendExpression(expr)
        except Exception as exc:  # noqa: BLE001 - OMCSessionException etc. surfaced
            raise GenesisError(f"OpenModelica call failed for {expr[:80]!r}: {exc}") from exc

    def version(self) -> str:
        """The OpenModelica version string (proves the session is live)."""
        return str(self._eval("getVersion()"))

    def load_model_string(self, source: str) -> None:
        """Load Modelica ``source`` into the session (``loadString``).

        Raises GenesisError if OpenModelica rejects the source. Newlines are accepted —
        they are passed through the OMC string API correctly.
        """
        self._require()
        # loadString takes the whole source as one OMC string literal; escape the few
        # characters that would break the literal, keep newlines (OMC accepts them).
        escaped = source.replace("\\", "\\\\").replace('"', '\\"')
        ok = self._eval(f'loadString("{escaped}")')
        if ok is not True:
            errs = self._eval("getErrorString()")
            raise GenesisError(f"OpenModelica failed to load the model: {errs or ok}")

    def simulate(
        self,
        model: str,
        read_vars: list[str],
        *,
        stop_time: float = 1.0,
        start_time: float = 0.0,
        intervals: int = 100,
        tolerance: float = 1e-6,
        work_dir: str | None = None,
    ) -> SimulationResult:
        """Compile + simulate ``model`` over ``[start_time, stop_time]`` and read variables.

        ``read_vars`` are the Modelica variable names whose final values (at ``stop_time``)
        to return — each read from the result via ``val``. A fixed ``intervals`` and
        ``tolerance`` make the run reproducible.

        Raises:
            GenesisError: the model is unknown, the simulation produces no result file,
                or a requested variable is not in the result (no fabricated value).
        """
        if not read_vars:
            raise GenesisError("read_vars must name at least one variable to read out")
        self._require()
        if work_dir is not None:
            wd = work_dir.replace("\\", "\\\\").replace('"', '\\"')
            self._eval(f'cd("{wd}")')

        res = self._eval(
            f"simulate({model}, startTime={start_time}, stopTime={stop_time}, "
            f"numberOfIntervals={intervals}, tolerance={tolerance})"
        )
        result_file = ""
        if isinstance(res, dict):
            result_file = str(res.get("resultFile", ""))
            messages = str(res.get("messages", ""))
        else:  # pragma: no cover - OMC normally returns a record/dict
            messages = str(res)
        if not result_file:
            errs = self._eval("getErrorString()")
            raise GenesisError(
                f"simulating {model!r} produced no result file "
                f"(messages: {messages[:300]}; errors: {str(errs)[:300]})"
            )

        final: dict[str, float] = {}
        for var in read_vars:
            try:
                value = self._eval(f"val({var}, {stop_time})")
            except GenesisError:
                # val() raises inside OMPython for a variable absent from the result —
                # turn that into the precise "variable not found" message.
                raise GenesisError(
                    f"variable {var!r} not found in the result of {model!r}"
                )
            if value is None or (isinstance(value, str) and not value):
                raise GenesisError(
                    f"variable {var!r} not found in the result of {model!r}"
                )
            final[var] = float(value)
        return SimulationResult(
            model=model, result_file=result_file, stop_time=stop_time, final_values=final
        )


# --- a small, self-contained reference model (used by the test) --------------------

#: A first-order decay  der(x) = -x, x(0)=1  →  x(t) = exp(-t). The simplest non-trivial
#: transient model: its closed form is known, so a test can check OpenModelica's transient
#: solver against exp(-stop_time) — a real solve, verified, not asserted.
DECAY_MODEL = """model Decay
  Real x(start = 1.0);
equation
  der(x) = -x;
end Decay;
"""


def simulate_decay(stop_time: float = 1.0, *, work_dir: str | None = None) -> float:
    """Convenience: simulate :data:`DECAY_MODEL` and return ``x(stop_time)``.

    A connected, one-call helper that returns OpenModelica's value of x at ``stop_time``
    (≈ exp(−stop_time)). Opens and closes its own session. Raises GenesisError if
    OpenModelica is unavailable.
    """
    with ModelicaSimulation() as sim:
        sim.load_model_string(DECAY_MODEL)
        out = sim.simulate(
            "Decay", ["x"], stop_time=stop_time, intervals=50, work_dir=work_dir
        )
    return out.final_values["x"]


__all__ = [
    "openmodelica_available",
    "ModelicaSimulation",
    "SimulationResult",
    "DECAY_MODEL",
    "simulate_decay",
]
