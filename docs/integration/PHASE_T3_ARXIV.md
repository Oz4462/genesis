# Tier-3 — arXiv Discovery Backend (2026-06-14)

> Schließt Gap #2 (dünne Research-Breite): Discovery war nur Semantic Scholar + Wikipedia.

## Was integriert wurde

- **`src/gen/tools/arxiv_backend.py`** — `ArxivBackend` (SearchBackend-Protocol),
  portiert aus ATLAS `hunter/scrape_arxiv.py` (Ozans eigenes Projekt), aber Genesis-adaptiert:
  Transport über injiziertes `HttpGet` (offline-testbar), Atom-Parsing mit stdlib `xml.etree`
  statt `feedparser` (keine neue Dep). Discovery-only, `SearchBackendError` bei Transport/Parse-
  Fehler. Exportiert über `gen.tools`. Einsetzbar als zusätzlicher Eintrag in `Dependencies.backends`.

## Verifikation (Zahlen)

- `tests/test_arxiv_backend.py` 4/4 (offline, scripted Atom): Parsing→Kandidaten, Limit,
  HTTP-Fehler→raise, Bad-XML→raise.
- **Live-Smoke** (`scripts/pov/pov_tier3_arxiv_live.py`, **PASS**): 5 echte Treffer gegen die
  arXiv-API, inkl. 2107.07511 (Angelopoulos & Bates) — exakt das Paper, das Genesis'
  `calibration.py` zitiert.
- **Volle Suite: 863 passed, 19 skipped, 0 Fehler.** ruff: All checks passed.

## Weitere Tier-3-Kandidaten (bewertet, nicht umgesetzt)

- **buch-llm-Detektoren:** Lizenz ist kein Blocker (Ozans Programm), aber die 28 Detektoren
  sind **buch-domänenspezifisch** (Prämissen-Constraints, Voice, Pacing) — geringe Passung für
  Genesis-Specs. Generische (hallucination-filter) wären ein Stretch; bewusst zurückgestellt.
- **PROMETHEUS Z3-Kausal-Gate:** stärker als Korrelation für kausale Claims; braucht z3-solver-Dep
  + Integration → eigene Spec.
- **CHORUS** (synthetische Adversarial-Faktenprüfer) / **AGORA** (Agenten-Budget-Allokation):
  nur bei konkretem Bedarf (Multi-Agent-Skalierung) — je eigene PoV-gegatete Spec.

ATLAS-arXiv wurde als **höchster, sauberster Mehrwert** zuerst umgesetzt (direkter Fit auf Gap #2,
SearchBackend ist eine saubere Protocol-Naht).
