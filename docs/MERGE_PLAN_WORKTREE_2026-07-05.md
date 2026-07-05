# Merge-Plan: `worktree-claude-orchestrator` → `main` (Owner-Vorlage)

> Dry-Run durchgeführt 2026-07-05 (~04:50) in einer isolierten Probe-Kopie (`--no-commit`,
> danach abgebrochen — **nichts wurde real gemerged**). Der Merge selbst bleibt owner-gated.

## Inhalt des Branches (15 Commits unmerged)
Humanoid **TP1 Energie & Thermik** (fertig, `test_humanoid_energy.py`) + **TP2 Struktur-Härtung**
(fertig, `test_humanoid_structure.py`, Worktree-Suite 1743/0/61) + Specs/Plan-Dokumente +
Quellen-Notiz Dauerfestigkeit (`4fa05cd`).

## Konfliktkarte (5 Dateien, alle klein)

| Datei | Konflikt | Empfohlene Auflösung |
|---|---|---|
| `src/gen/core/state.py` | beide Äste fügten `Specification.seam_certificate` hinzu (nur Kommentar-Wortlaut differiert) | **main-Fassung behalten** (semantisch identisch; main-Kommentar nennt capstone-Beispiel) |
| `src/gen/pipeline.py` | main = Fallback **+ Auto-Cost-Seam-Drop-Fix**; Worktree = nur Fallback | **main-Fassung** (Superset; enthält den Latent-Bug-Fix `76e5dfd`) |
| `src/gen/simulation/runner.py` | beide entfernten den toten `base_artifact`-Block; Worktree ergänzt Erklär-Kommentar | **Worktree-Fassung** (Kommentar dokumentiert das Warum) |
| `docs/BUILD_LOG.md` | beide appendeten Einträge | **Union**, chronologisch (beide Blöcke behalten) |
| `uv.lock` | add/add (beide checkten sie unabhängig ein) | **main-Fassung**, danach `uv lock`/`uv sync --check` als Beleg |

## Nach dem Merge (Pflicht-Checks)
1. `physics_selection.py`: Worktree-TP1 registriert ein **overtemperature-Recipe** → den Eintrag
   `"overtemperature"` aus `MANUAL_ONLY_VALIDATORS` **entfernen** (der Registry-Test
   `test_every_validator_has_recipe_or_is_documented_manual_only` schlägt sonst fehl — gewollt:
   die Whitelist darf nicht rotten).
2. Volle Suite: erwartet ≈ 2079 + ~35 Humanoid-Tests, 0 failed; `ruff check src tests` clean.
3. `gen --mode humanoid` Smoke (beide Humanoide `physics_verified`, jetzt mit 15 Checks je).
4. CLAUDE.md Fokus-Absatz 1 (TP2 unmerged) auf „gemerged" nachführen.

## Kommando-Skizze (erst nach Owner-Go)
```bash
git merge --no-ff worktree-claude-orchestrator   # Konflikte laut Tabelle auflösen
uv run pytest tests/ -q && uv run ruff check src tests
git worktree remove .claude/worktrees/claude-orchestrator   # danach Branch behalten oder löschen
```
