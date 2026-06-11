"""GENESIS agents: scout (breadth), scholar (depth), skeptic (verify), conductor,
synthesizer (Phase β: structure verified claims into solution approaches),
architect (Phase γ: structure claims + approach into a build specification).

Each satisfies the ``Agent`` Protocol. Only scholar/skeptic touch facts, and only
via the ledger; conductor, synthesizer and architect assemble from ledger claims
and invent nothing.
"""

from __future__ import annotations

from .architect import Architect
from .conductor import Conductor
from .scholar import Scholar
from .scout import Scout
from .skeptic import Skeptic
from .synthesizer import Synthesizer

__all__ = ["Scout", "Scholar", "Skeptic", "Conductor", "Synthesizer", "Architect"]
