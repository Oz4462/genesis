"""_triggers — gemeinsamer Wortgrenzen-Flug-Trigger der Fach-Pipelines (Schritt 9, #3–#6).

Root cause: mehrere Pipelines prüften ``"flug" in idee_lower`` — der Substring matcht
"Ausflug"/"Flughafen"/"Ausflugsboot" und feuerte den vollen Jetpack-Kanon (bei der
Regulatorik-Pipeline inklusive EASA-Zuordnung und Haftungstexten). Fix: EIN Helfer mit dem
S-2-Wortgrenzen-Regex aus software.py, von allen Pipelines geteilt statt sechs Kopien.

"Drohne" ist bewusst NICHT enthalten (siehe S-2, Commit 5ad4e70): das würde den
Jetpack-Kanon auf ein fremdes Gerät ausdehnen — neue erfundene Provenienz.
"""

from __future__ import annotations

import re

#: Flight trigger (S-2): word-boundary terms only — the bare word "flug", a flight DEVICE
#: (fluggerät/fluggeraet/flugzeug) or "jetpack". Substrings like "Ausflug" or "Flughafen"
#: must NOT match.
_FLIGHT_TRIGGER = re.compile(r"jetpack|fluggerät|fluggeraet|flugzeug|\bflug\b")

#: "fliegen" only as a full word (architekt, #11): "überfliegende" must NOT match.
_FLIEGEN_WORD = re.compile(r"\bfliegen\b")


def is_flight_idea(text: str) -> bool:
    """True iff the idea text names flight/a flight device on word boundaries.

    Case-insensitive (input is lowercased here — callers need no own ``.lower()``).
    Errors: none raised; ``""`` returns False. No factual claim is made here — this
    only selects which deterministic canon template a pipeline uses.
    """
    return _FLIGHT_TRIGGER.search(text.lower()) is not None


def has_fliegen_word(text: str) -> bool:
    """True iff "fliegen" appears as a full word (word boundaries, case-insensitive).

    Used by architekt's "mensch … fliegen" trigger so substrings like
    "überfliegende" do not select the jetpack concept. Errors: none; "" → False.
    """
    return _FLIEGEN_WORD.search(text.lower()) is not None
