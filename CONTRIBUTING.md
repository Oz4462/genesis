# Mitarbeit an GENESIS

> Kurz, damit die Struktur von Tag eins sauber ist. Diese Regeln gelten auch für
> Claude Code beim Bauen.

## Grundsatz
Ein Commit = ein abgeschlossener, selbstkontrollierter Schritt. Die
Commit-Historie ist die Beweiskette des Projekts (siehe `docs/VISION.md §7`).
Niemals „großer Sammel-Commit am Ende".

## Branch-Strategie (schlank)
- `main` — immer grün. Hier landet nur, was alle Tests besteht und die
  Selbstkontrolle (`docs/CLAUDE_CODE_AUFTRAG_001.md §0.2`) bestanden hat.
- `phase/<name>` — Arbeit an einer Phase, z. B. `phase/alpha`, `phase/beta`.
- `task/<kurzname>` — eine einzelne Aufgabe, z. B. `task/ledger-store`.
  Wird nach Merge gelöscht.

Fluss: `task/*` → (Tests grün + Selbstkontrolle) → `phase/*` → (Phasen-Akzeptanz
erfüllt) → `main`.

## Commit-Nachrichten
Format:
```
<typ>(<bereich>): <kurz, imperativ>

<optional: was + warum, nicht wie>
Selbstkontrolle: bestanden | Punkte: <was offen war>
```
Typen: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`.

Beispiel:
```
feat(ledger): InMemory- und Postgres-Store mit Quellenzwang

Drei Schichten Quellenzwang: Konstruktor, Store, DB-Constraint.
Selbstkontrolle: bestanden
```

## Pflicht vor jedem Commit
- [ ] `pytest -q` grün
- [ ] Keine Secrets im Diff (`.env`, Keys, Tokens) — `.gitignore` schützt, aber prüfen
- [ ] Faktische Outputs laufen über das Ledger (kein Fakt ohne Quelle)
- [ ] `docs/BUILD_LOG.md` aktualisiert
- [ ] Bei neuer Tätigkeitsart: passendes Skill geprüft/genutzt
      (`docs/CLAUDE_CODE_AUFTRAG_001.md §0.4`)

## Was NICHT ins Repo gehört
API-Keys, `.env`, Zugangsdaten, große Laufzeit-Artefakte (`runs/`, Checkpoints).
Im Zweifel: nicht committen, in `.gitignore` ergänzen.

## Setup (lokal)
```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest            # weitere Deps kommen mit den Aufgaben
pytest -q                     # muss grün sein, bevor du startest
```

## Ehrlichkeit
Eine dokumentierte Lücke ist wertvoll. Eine versteckte ist ein Risiko fürs ganze
Projekt. Wenn etwas nicht funktioniert: in `docs/BUILD_LOG.md` ehrlich notieren,
nicht überdecken.
