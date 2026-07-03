# Heute Abend: GitHub-Start (Schritt für Schritt)

## 1. Lokal Git initialisieren (im genesis/-Ordner)
```bash
cd genesis
git init
git add .
git commit -m "chore: GENESIS Fundament — Phase alpha Skelett + Vision

Anti-Halluzinations-Gate als reine Funktion, 7/7 Tests gruen.
Claim ohne Quelle strukturell unmoeglich (Code + DB-Constraint).
Selbstkontrolle: bestanden"
```

## 2. Privates Repo auf GitHub anlegen
- Auf github.com: New repository → Name z. B. `genesis` → **Private** → ohne
  README/gitignore (haben wir schon) → Create.
- Dann lokal verbinden (URL von GitHub einsetzen):
```bash
git branch -M main
git remote add origin git@github.com:<dein-user>/genesis.git
git push -u origin main
```

## 3. Phase-Branch für die Arbeit
```bash
git checkout -b phase/alpha
```

## 4. Claude Code starten (lokal im genesis/-Ordner)
Sag Claude Code sinngemaess:
> Lies CLAUDE.md, docs/VISION.md, docs/phases/PHASE_ALPHA.md und arbeite
> docs/CLAUDE_CODE_AUFTRAG_001.md ab. Halte §0 strikt ein: Selbstkontrolle nach
> jeder Aufgabe, Halluzinationspruefung bei Agenten/Subagenten, Skills situativ
> nutzen. Committe nach jeder bestandenen Aufgabe auf task/*-Branch.

## 5. Erst oeffentlich machen, wenn Phase alpha gruen ist
A3 (Falle abgefangen) + A4 (Abstention) bestanden → dann Repo auf Public.
Vorher: privat bleiben.

## Wichtig
- KEINE API-Keys committen. .gitignore schuetzt .env — trotzdem vor jedem Push
  kurz `git status` / `git diff --staged` pruefen.
- Ein Commit = eine bestandene Selbstkontrolle.
