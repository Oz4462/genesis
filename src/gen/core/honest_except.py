"""Honest exception capture for pipeline seams (audit B3).

Replace bare ``except Exception: pass`` with ``note_exception`` so failures
become gap notes / stderr lines instead of silent swallows. The verification
core still fails loud; this is the pipeline-boundary discipline.
"""

from __future__ import annotations

import sys
from typing import Any


def note_exception(
    context: str,
    exc: BaseException,
    *,
    gaps: list[str] | None = None,
    stream: Any = None,
) -> str:
    """Format and record an exception as an honest gap note.

    Returns the note string. Appends to ``gaps`` when provided; always writes
    a short line to stderr (or ``stream``) so CI logs see it.
    """
    msg = f"{context}: {type(exc).__name__}: {exc}"
    if gaps is not None:
        gaps.append(msg)
    out = stream if stream is not None else sys.stderr
    try:
        print(f"[honest-except] {msg}", file=out)
    except Exception:
        pass
    return msg
