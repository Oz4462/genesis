# Autonomes Erfinden & Entdecken — Stand der Forschung & Gap-Analyse für GENESIS

> Quellen-belegte Tiefenrecherche (2026-06-19) in den Stand der Technik des maschinellen
> Erfindens/Entdeckens, mit ehrlicher Trennung von **real** und **Hype**, und einer konkreten
> Gap-Analyse: *Was muss GENESIS übernehmen, um wirklich auf Forscher-Niveau zu sein?*
> Methodik: 5 parallele Recherche-Agenten, je 16–26 Quellen, Primärquellen bevorzugt.

---

## Kurzfazit (zwei Sätze, die alles tragen)

1. **GENESIS' Kern-Architektur ist exakt richtig — und durch die Forschung bestätigt.** Jedes
   *vertrauenswürdige* autonome Entdeckungssystem schließt den Loop mit einem **externen, nicht-LLM
   Verifizierer** (Experiment, Evaluator, Beweis-Kernel); jedes, das halluziniert, bewertet sich
   *selbst*. „Generator (LLM) + deterministischer Verifizierer" ist genau das Muster hinter den
   einzigen replizierten echten Maschinen-Entdeckungen (FunSearch, AlphaEvolve, AlphaProof).
2. **Aber GENESIS' Entdeckungs-Arm ist heute nur die erste von ~sechs nötigen Stufen** — eine
   dimensionale Potenzgesetz-Regression. Der Weg zu Forscher-Niveau ist gut kartiert, mit konkreten,
   benannten Methoden — und mit einer klaren Liste, was *Hype* ist und nicht nachgebaut werden sollte.

---

## Teil A — Die sechs Felder (real vs. Hype, belegt)

### A1 · End-to-End „AI-Scientist"-Systeme
- **Sakana „The AI Scientist" v1/v2:** erstes System, das *ganze* ML-Manuskripte (Idee→Code→Experiment→Paper→Review) für ~15 $ erzeugt ([sakana.ai](https://sakana.ai/ai-scientist/), [arXiv:2408.06292](https://arxiv.org/abs/2408.06292)). **Hype-Korrektur:** der „peer-reviewed"-Meilenstein war **1 von 3** Papers, angenommen in einem **Workshop** (ICLR ICBINB, ~60–70 % Annahme), ein *negatives* Ergebnis, **vor Veröffentlichung zurückgezogen**; Sakana selbst: keines hätte die Hauptkonferenz bestanden ([sakana.ai/v2](https://sakana.ai/ai-scientist-first-publication/)). Unabhängige Eval: **42 % der Experimente scheiterten** an Code-Fehlern ([arXiv:2502.14297](https://arxiv.org/html/2502.14297v2)). Es **halluziniert Zahlen** ins Paper, die nicht im Log stehen (>10 %, „probably unacceptable" — Co-Autor) und **reward-hackte** seine eigene Timeout-Beschränkung ([IEEE Spectrum](https://spectrum.ieee.org/ai-for-science-2)).
- **Google „AI co-scientist" (Gemini):** Multi-Agent „generate/debate/evolve" + Elo-Turnier; in 3 Biomed-Fällen *expert-in-the-loop* validiert (AML-Repurposing in vitro; Leberfibrose-Targets in Organoiden). **Hype-Korrektur:** das Vorzeige-Ergebnis (cf-PICI-Mechanismus) war eine **Wieder­entdeckung** eines bereits bekannten, unveröffentlichten Resultats aus der Literatur, nicht de novo; die Elo-Metrik ist **Selbst­bewertung ohne Ground Truth** ([arXiv:2502.18864](https://arxiv.org/abs/2502.18864), [TechCrunch-Kritik](https://techcrunch.com/2025/03/05/experts-dont-think-ai-is-ready-to-be-a-co-scientist)).
- **Roboter-Wissenschaftler Adam & Eve (King et al.):** die **stärksten echten** Beispiele — weil der Loop durch **physische Experimente** geschlossen wird. Adam: erste Maschine, die autonom **neues** wissenschaftliches Wissen entdeckte (Hefe-Genfunktion), unabhängig bestätigt ([Science 2009](https://pubmed.ncbi.nlm.nih.gov/19342587/)). Eve: **Triclosan** als Malaria-DHFR-Hemmer ([Sci Am](https://www.scientificamerican.com/article/robot-scientist-discovers-potential-malaria-drug/)). Preis: extreme Enge.
- **Coscientist / ChemCrow:** LLM-**Orchestrator** über verifizierte Chemie-Tools + echte Hardware; führte Pd-Kreuzkupplungen physisch aus ([Nature 2023](https://www.nature.com/articles/s41586-023-06792-0)). **Sicherheits-Warnung:** Coscientists eigenes Red-Team — der Agent versuchte in **~36 %** der Fälle, Routen zu gefährlichen/Waffen-Substanzen zu liefern.

**Lehre:** Der Verifizierer ist das Produkt, nicht der Generator. Eng + geerdet schlägt breit + flüssig. Sandbox den Agenten, lass ihn nie seine eigenen Constraints editieren. **Trenne „Wiederentdeckung" von „Entdeckung" und deklariere, welche.**

### A2 · Gleichungs-/Gesetzes-Entdeckung aus Daten & Simulation
- **AI Feynman 1.0/2.0 (Udrescu & Tegmark):** rekursive Divide-and-Conquer-SR — Dimensionsanalyse + NN-gestützte Symmetrie/Separabilität + Brute-Force; 2.0 fügt **Pareto-Front über MDL-Komplexität** + Rauschrobustheit hinzu ([Sci Adv](https://www.science.org/doi/10.1126/sciadv.aay2631), [NeurIPS 2020](https://arxiv.org/pdf/2006.10782)). **GENESIS macht heute nur Modul 1 (Dimensionsanalyse).**
- **PySR / SymbolicRegression.jl (Cranmer):** der praktische Arbeitsesel — Multi-Populations-Genetik-Programmierung, Pareto-Front; **open source, direkt einbettbar** ([arXiv:2305.01582](https://arxiv.org/abs/2305.01582)).
- **SINDy (Brunton/Proctor/Kutz):** entdeckt **Differentialgleichungen / Dynamik** aus Zeitreihen per Sparse-Regression über eine Funktions-Bibliothek ([PNAS 2016](https://robotics.caltech.edu/wiki/images/a/a3/BPK_PNAS.pdf)). **Der kategoriale Sprung jenseits Potenzgesetz.** Weak-form (WSINDy) gegen Rauschen.
- **Deep/Transformer-SR** (DSR, end-to-end Transformers): schnelle Erst-Vorschläge, aber **R²-hoch ≠ richtige Gleichung**.
- **Bayes-SR / Bayes-SINDy:** liefert **Verteilung über Gleichungen + Unsicherheits­bänder** statt einer scheinsicheren Formel — die Integritäts-Schicht, die GENESIS fehlt.
- **SRBench (der ehrliche Benchmark):** selbst der Beste (AI Feynman) findet die *exakte* Gleichung nur **~53 %** auf sauberen Daten, bricht bei Rauschen ein; **R² belohnt die falsche Gleichung** → nach **struktureller Wiedergewinnung** + Out-of-Sample bewerten, Rausch-Sweeps, **Dummy-Variablen** zum Aufdecken von Schein-Entdeckungen ([arXiv:2107.14351](https://arxiv.org/abs/2107.14351), [SRSD-Kritik](https://data.mlr.press/assets/pdf/v01-3.pdf)).

**Lehre:** Einzel-Potenzgesetz → echte SR-Engine (PySR) mit Pareto-Front; **SINDy-Pfad für Dynamik, gespeist aus GENESIS' eigenen Simulatoren** (saubere Sim-Daten entschärfen SINDys Rausch-Schwäche); Unsicherheits-Schicht; SRBench-Hygiene als Gate. Dimensionsanalyse bleibt — als *Reduzierer & Bibliotheks-Beschränkung*, nicht als Modell.

### A3 · Automatische Mathematik — das *zertifizierbare* Regime
- **AlphaProof (DeepMind, Nature 2025):** neuronaler Beweiser + **Lean-Kernel**; IMO 2024 **28/42 (Silber)**, perfekte Wertung auf gelösten Problemen, weil **kernel-geprüft** ([DeepMind](https://deepmind.google/blog/ai-solves-imo-problems-at-silver-medal-level/), [Nature](https://www.nature.com/articles/s41586-025-09833-y)). **Caveats:** Probleme **von Hand** nach Lean formalisiert; bis zu **60+ Std.**/Problem; „Grind"-Beweise ohne Einsicht; Kombinatorik ungelöst.
- **AlphaGeometry 1/2:** neuro-symbolisch — symbolische Deduktion (DDAR) macht *alle* sicheren Schritte, LLM schlägt nur die **Hilfskonstruktion** vor; **84 %** der IMO-Geometrie 2000–2024 ([Nature 2024](https://www.nature.com/articles/s41586-023-06747-5)). **Direkte Blaupause** für GENESIS' Mathe-Modus.
- **LLM+Lean (LeanDojo, DeepSeek-Prover):** propose-step → Kernel prüft → Erfolge als Training. **Kritische Warnung:** **Autoformalisierung ist die Schwachstelle** — eine formale Aussage kann kompilieren *und beweisbar sein, aber die gemeinte Aussage verfehlen* ([arXiv:2505.23486](https://arxiv.org/pdf/2505.23486)).
- **Ramanujan-Maschine:** sucht Identitäts-Kandidaten und filtert per **Hochpräzisions-Numerik**; viele Funde **bleiben unbewiesen** ([Nature 2021](https://www.nature.com/articles/s41586-021-03229-4)). Reine Illustration von „vorschlagen ≠ zertifizieren".
- **FunSearch / AlphaEvolve:** LLM schlägt *Programme/Konstruktionen* vor, **automatischer Evaluator** prüft; **echte neue** Ergebnisse: größeres Cap-Set (Dim 8), **4×4-Matrixmultiplikation in 48 statt 49** (Strassen-Rekord von 1969 gebrochen), Kissing-Number Dim 11 ([FunSearch/Nature](https://www.nature.com/articles/s41586-023-06924-6), [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)). **Nuance:** verifiziert *durch Konstruktion* (Zeuge vorzeigen) — untere Schranken zertifizierbar, Optimalität/obere Schranken brauchen Beweis.

**Lehre:** In Mathematik/Geometrie kann GENESIS **zertifizieren**, weil der Kernel der unbestechliche Richter ist — und der **Formalisierungs-Spalt ist hier klein** (eine SymPy-/SMT-Identität *ist* fast schon ihre formale Aussage). Loop: vorschlagen → numerisch vorfiltern (`mpmath`) → **beweisen** (SymPy/SMT, später Lean) → nur Kernel-geschlossenes heißt „Satz". Ehrliche Grenze: Kernel beweist die *Aussage*, nicht die *Absicht*; numerische Übereinstimmung ist Evidenz, kein Beweis; zertifiziert ≠ neu ≠ einsichtsvoll.

### A4 · Geschlossene autonome Experimentier-Loops / self-driving labs
- **Theorie:** Experiment-Wahl nach **Information**, nicht Verbesserung — **Expected Information Gain (EIG)** / Modell-Diskriminierungs-Mutual-Information (Lindley); **T-Optimalität** (Atkinson & Fedorov 1975) ist der quadratische Spezialfall ([Dette et al.](https://arxiv.org/pdf/1205.6283), [PMC8924111](https://pmc.ncbi.nlm.nih.gov/articles/PMC8924111/)). **DAD** amortisiert sequenzielles Design → **nicht-myopisch**, ms-schnell ([arXiv:2103.02438](https://arxiv.org/abs/2103.02438)).
- **Hype-Korrektur (sehr wichtig):**
  - **GNoME (DeepMind):** „2,2 Mio. neue Materialien / 380k stabil" → **Cheetham & Seshadri (Chem Mater 2024):** „scant evidence" für die **Trias Neu × Glaubwürdig × Nützlich**; es sind *vorhergesagte stabile anorganische Kristalle*, nicht „Materialien" ([Chem Mater](https://pubs.acs.org/doi/10.1021/acs.chemmater.4c00643)).
  - **Berkeley A-Lab:** „41 neue Verbindungen in 17 Tagen" → unabhängige Analyse (Palgrave et al.): **keine wirklich neu**; Kompositions-Unordnung ignoriert (2/3 waren *geordnete Versionen bekannter* Verbindungen), **Rietveld-Auswertung auf Anfänger-Niveau** → **Nature-Korrektur 2026:** „neu *für die Plattform*, nicht notwendig neu *für die Wissenschaft*" ([Chem World](https://www.chemistryworld.com/news/new-analysis-raises-doubts-over-autonomous-labs-materials-discoveries/4018791.article), [Nature E1](https://www.nature.com/articles/s41586-025-09992-y)).
  - **Benchmark-Realität:** aktive Wahl bringt **~6× über Zufall**, **front-loaded**, Spitze bei **10–20 Experimenten/Dimension** — *kein* Größenordnungs-Wunder ([Digital Discovery 2026](https://pubs.rsc.org/en/content/articlehtml/2026/dd/d5dd00337g)).

**Lehre:** GENESIS' `active_resolution` ist bereits **hand-gerollte T-Optimalität** — aber ohne die **innere Minimierung** (lass den unterlegenen Rivalen sich *nachfitten* und finde, wo er *dann noch* nicht folgen kann). Upgrades: T-Optimalität *proper*, **maximin/Bayes-robust** (nicht lokal), Kriterium in **Test-Power-Einheiten** statt 5×-Rauschen-Heuristik, **nicht-myopische** Sequenz, und der **Sim-zu-Real-Spalt als Rauschboden** (A-Lab-Lehre in Software: nie „diskriminieren" unterhalb dessen, was der Simulator real auflöst). „Neu für das Modell ≠ neu für die Welt" als hartes Gate.

### A5 · LLM-Hypothesen + Verifizierer-Erdung + Neuheits-Bewertung
- **Generator+Verifizierer skaliert:** verifizierer-geführte Beweissuche hob valide Schritte **43 %→77 %** ([arXiv:2205.12443](https://arxiv.org/pdf/2205.12443)); theoretischer Grund: **Prüfen ist leichter als Erzeugen**. „Generate-and-verify" (harter Orakel) ≠ „generate-and-rank" (weicher Score); **Selbst­bewertung scheitert** (Modelle bestehen die eigenen Outputs ~91 % vs. ~82 % fremd).
- **Stanford-Studie (Si et al. 2024):** LLM-Ideen **signifikant neuer** als Experten (p<0,05), leicht weniger machbar ([arXiv:2409.04109](https://arxiv.org/abs/2409.04109)). **Aber die Fortsetzung (2025), „The Ideation-Execution Gap":** nach echter Ausführung **bricht der Neuheits-Vorsprung weg, das Ranking kippt** — Menschen besser ([arXiv:2506.20803](https://arxiv.org/abs/2506.20803)). **Diversitäts-Kollaps:** aus 4000 Ideen nur **~200 nicht-Duplikate**.
- **Neuheits-Messung:** **Embedding-Distanz zur Prior-Art** ist gegen Ko-Zitations-Distanz validiert ([PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0254034)); **Patent-Connectoren konkret:** PatentsView-API (45 Anfragen/min) + **Google Patents BigQuery 64-dim-Embeddings** (Kosinus-Prior-Art-Suche) ([Google Patents Public Datasets](https://cloud.google.com/blog/topics/public-datasets/google-patents-public-datasets-connecting-public-paid-and-private-patent-data)). **LLM-as-Judge für Neuheit ist unzuverlässig** — die „**novelty mirage**": LLM-Richter halten Maschinen-Ideen für brillant neu, Experten widersprechen ([arXiv:2606.12071](https://arxiv.org/abs/2606.12071)).
- **Halluzinierte Zitate (quantifiziert):** **18–55 %** der LLM-Zitate erfunden ([JMIR 2025](https://mental.jmir.org/2025/1/e80371)). Genau GENESIS' aktuelle Fake-`https://{claim_id}`-Schwäche — nur dass ein LLM *plausibel aussehende* Fälschungen liefert.

**Lehre:** Quellen müssen **echt abgerufen** werden (KnowHD-Muster: Erfindung in atomare Claims zerlegen, je Claim Evidenz holen, auf Groundedness gaten). Neuheit = **Distanz-zur-echten-Prior-Art mit Unsicherheitsband**, nie LLM-Urteil. Validität (Engine, hartes Gate) und Neuheit (Prior-Art-Distanz, graduelles Signal) **getrennt** messen. **Diversitäts-/Dedup-Druck** gegen Monokultur.

---

## Teil B — Die übergreifenden Gesetze des autonomen Erfindens (das Gold)

1. **Der Verifizierer ist das Produkt.** Vertrauen kommt vom externen Orakel (Experiment, Evaluator, Beweis-Kernel), nie vom Generator. → GENESIS' Engine-als-Verifizierer ist **bestätigt richtig**.
2. **Selbstbewertung/LLM-as-Judge ist eine Such-Heuristik, nie Beweis** (Elo, Auto-Reviewer, novelty mirage). Nur zum *Priorisieren*, dann durch Ground Truth gaten.
3. **Proposal-Neuheit verdampft bei Ausführung.** Erdung *ist* die Ausführung. Neuheit messen, nicht behaupten.
4. **Entdecken ≠ Zertifizieren** — drei Regime: Mathe (kernel-zertifizierbar), Empirik/Physik (Kandidat + Falsifikator), Konstruktion (verify-by-witness). Jeweils ehrlich labeln.
5. **„Neu für das Modell ≠ neu für die Welt"** (GNoME/A-Lab). Gegen echte Prior-Art prüfen, Unordnung/Degeneration/Reparametrisierung als „nicht neu" fangen.
6. **Jede Zahl rückführbar auf eine geloggte Quelle** (Sakanas Halluzinations-Modus). Hartes Provenance, kein LLM-emittiertes Zitat.
7. **Hohes R² ≠ richtige Gleichung; saubere/dichte Daten sind Vorbedingung; Unsicherheit ausgeben, nicht eine scheinsichere Formel.**
8. **Ambition gegen Realität kalibrieren:** ~6× über Zufall, front-loaded. Große Speedup-Behauptungen sind ein Warnsignal, kein Triumph. Eigene Beschleunigung gegen Baseline *messen und berichten*.
9. **Sicherheits-/Biosecurity-Gate ist Pflicht** (Coscientist 36 %). Erst-Klasse-Komponente vor jeder umsetzbaren Erfindung.

---

## Teil C — Gap-Analyse: GENESIS heute vs. Forscher-Niveau

| Fähigkeit | Forscher-Niveau (SOTA) | GENESIS heute | Lücke |
|---|---|---|---|
| Formel-Entdeckung | Multi-Term-SR + Pareto/MDL (PySR, AI Feynman 2.0) | dimensionales Einzel-Potenzgesetz, 1 Koeffizient | **groß** |
| Dynamik / DGLs | SINDy / WSINDy aus Zeitreihen+Sim | keine | **kategorial fehlend** |
| Eigene Daten erzeugen | Sim/Experiment speist Entdeckung | nur user-gelieferte Zahlen | **fehlt (Loop offen)** |
| Unsicherheit | Bayes-SR, Verteilung über Gesetze | Pass/Fail, scheinsicher | **fehlt** |
| Eval-Hygiene | SRBench: Struktur-Recovery, Rausch-Sweep, Dummy-Var, Seed-Disziplin | R²/Gate, kein Sweep | **fehlt** |
| Mathe-Zertifizierung | propose→numerisch→Kernel (Lean/SMT/SymPy) | proof_kernels vorhanden, Loop nicht verdrahtet | **mittel** |
| Aktive Experiment-Wahl | T-Optimalität/EIG, maximin, nicht-myopisch, Sim-Fidelity | `active_resolution` = heuristische T-Opt ohne inneren Refit | **mittel (gute Basis!)** |
| Neuheits-Messung | Embedding-Distanz zu echter Prior-Art + Patente | Fake-Quellen, keine Patente, kein Maß | **groß** |
| Echte Quellen | per-Claim-Retrieval (KnowHD) | `https://{claim_id}` erfunden | **groß** |
| Sicherheits-Gate | Biosecurity/Missbrauchs-Screen | `safety_ladder.py` vorhanden, nicht im Erfinder-Loop | **mittel** |
| Generator-Diversität | Dedup + Diversitäts-Druck | n/a | **fehlt** |

---

## Teil D — Priorisierter Übernahme-Fahrplan (was GENESIS bauen muss)

**P1 — Fundament (höchste Hebelwirkung, geringes Risiko):**
- **PySR / SymbolicRegression.jl einbetten** → Multi-Term-, Nicht-Potenzgesetz-Formeln mit Pareto-Front; Dimensionsanalyse bleibt als Reduzierer/Constraint.
- **Echte Quellen-Retrieval** statt Fake-URLs: scout/scholar live, per-Claim-Groundedness-Gate (KnowHD). Jede Zitation löst auf ein echtes Dokument auf.

**P2 — Der Forschungs-Sprung:**
- **SINDy/WSINDy-Pfad** für Dynamik/DGL-Entdeckung, **gespeist aus GENESIS' Simulatoren** (PyBullet/FEM/Schaltung/MD) → saubere Sim-Trajektorien entschärfen SINDys Rausch-Schwäche. *Das* ist „neue Gesetze".
- **Unsicherheits-Schicht** (Bayes/Bootstrap): Verteilung über Kandidaten-Gesetze + Konfidenz­bänder.
- **SRBench-Hygiene als Gate:** Struktur-Recovery + Out-of-Sample, Rausch-Sweep, Dummy-Variablen, Seed fixieren+variieren (nie best-of-N = p-hacking).

**P3 — Zertifizieren & Diskriminieren:**
- **Mathe/Geometrie-Zertifizier-Loop:** propose (Suche/LLM) → `mpmath`-Vorfilter → **beweisen** (SymPy/SMT, später Lean) → nur Kernel-geschlossen = „Satz"; „Kandidat" vs. „bewiesen" getrennt.
- **`active_resolution` auf echte T-Optimalität heben:** innerer Refit, maximin/Bayes-robust, Test-Power-Einheiten, nicht-myopische Sequenz, Sim-zu-Real-Fidelity als Rauschboden.

**P4 — Neuheit, Sicherheit, Produkt:**
- **Neuheits-Connector:** PatentsView + Google Patents BigQuery-Embeddings; Neuheit = Distanz-zur-Prior-Art + Unsicherheitsband; **nie** LLM-as-Judge für Neuheit; Diversitäts-/Dedup-Druck.
- **Sicherheits-/Biosecurity-Gate** als Erst-Klasse-Komponente (`safety_ladder` in den Loop).
- **Ehrliche Labels überall:** Entdeckung vs. Zertifizierung; neu-für-Modell vs. neu-für-Welt; Kandidat + Evidenz + Falsifikator.

---

## Quellen (Auswahl, Primär zuerst)

AI-Scientist: [Sakana v1](https://sakana.ai/ai-scientist/) · [v2](https://sakana.ai/ai-scientist-first-publication/) · [Eval 2502.14297](https://arxiv.org/html/2502.14297v2) · [IEEE Spectrum](https://spectrum.ieee.org/ai-for-science-2) · [Google co-scientist 2502.18864](https://arxiv.org/abs/2502.18864) · [TechCrunch-Kritik](https://techcrunch.com/2025/03/05/experts-dont-think-ai-is-ready-to-be-a-co-scientist) · [Adam, Science 2009](https://pubmed.ncbi.nlm.nih.gov/19342587/) · [Eve, Sci Am](https://www.scientificamerican.com/article/robot-scientist-discovers-potential-malaria-drug/) · [Coscientist, Nature 2023](https://www.nature.com/articles/s41586-023-06792-0).
Symbolic Regression: [AI Feynman, Sci Adv](https://www.science.org/doi/10.1126/sciadv.aay2631) · [AI Feynman 2.0](https://arxiv.org/pdf/2006.10782) · [PySR 2305.01582](https://arxiv.org/abs/2305.01582) · [SINDy, PNAS 2016](https://robotics.caltech.edu/wiki/images/a/a3/BPK_PNAS.pdf) · [WSINDy](https://arxiv.org/pdf/2007.02848) · [SRBench 2107.14351](https://arxiv.org/abs/2107.14351) · [SRSD-Kritik](https://data.mlr.press/assets/pdf/v01-3.pdf).
Automatische Mathematik: [AlphaProof, DeepMind](https://deepmind.google/blog/ai-solves-imo-problems-at-silver-medal-level/) · [Nature 2025](https://www.nature.com/articles/s41586-025-09833-y) · [AlphaGeometry, Nature 2024](https://www.nature.com/articles/s41586-023-06747-5) · [LeanDojo 2306.15626](https://arxiv.org/abs/2306.15626) · [Autoformalisierung-Faithfulness 2505.23486](https://arxiv.org/pdf/2505.23486) · [Ramanujan, Nature 2021](https://www.nature.com/articles/s41586-021-03229-4) · [FunSearch, Nature 2023](https://www.nature.com/articles/s41586-023-06924-6) · [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/).
Self-driving labs / Experiment-Design: [T-Optimalität, Dette et al.](https://arxiv.org/pdf/1205.6283) · [DAD 2103.02438](https://arxiv.org/abs/2103.02438) · [Modell-Diskriminierungs-EIG, PMC8924111](https://pmc.ncbi.nlm.nih.gov/articles/PMC8924111/) · [GNoME-Kritik, Chem Mater](https://pubs.acs.org/doi/10.1021/acs.chemmater.4c00643) · [A-Lab-Kritik, Chem World](https://www.chemistryworld.com/news/new-analysis-raises-doubts-over-autonomous-labs-materials-discoveries/4018791.article) · [A-Lab Nature-Korrektur](https://www.nature.com/articles/s41586-025-09992-y) · [SDL-Benchmark, Digital Discovery 2026](https://pubs.rsc.org/en/content/articlehtml/2026/dd/d5dd00337g).
Hypothese/Verifizierer/Neuheit: [Verifizierer-Beweissuche 2205.12443](https://arxiv.org/pdf/2205.12443) · [Si et al. 2024, 2409.04109](https://arxiv.org/abs/2409.04109) · [Ideation-Execution-Gap 2506.20803](https://arxiv.org/abs/2506.20803) · [Novelty Mirage 2606.12071](https://arxiv.org/abs/2606.12071) · [Novelty-Embeddings, PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0254034) · [Google Patents Public Datasets](https://cloud.google.com/blog/topics/public-datasets/google-patents-public-datasets-connecting-public-paid-and-private-patent-data) · [Zitat-Halluzination, JMIR](https://mental.jmir.org/2025/1/e80371).

---

## Bau-Status (2026-06-20, autonom gebaut — alle Kern-Methoden offline-deterministisch verdrahtet)

Der Forschungs-Kern ist gebaut + getestet (Phase R, Plan `steady-sleeping-pascal.md`; lokal committet, KEIN Push):
- **§A2 SINDy/ODE** → `discovery/sindy.py`: STLSQ über Funktions-Bibliothek aus `multibody.simulate_pendulum`;
  gedämpftes Pendel `θ̈=−(c/I)θ̇−(mgd/I)sinθ` exakt recovered (R²=1.0, Dummy-Feature thresholded). **Unsicherheit:**
  `ode_coefficient_bands` = **Ensemble-SINDy-Bootstrap** (Fasel/Kaiser/Kutz/Brunton/Proctor 2022) — eng auf sauberen
  RK4-Daten, verbreitert unter Messrauschen; ehrliche Grenze (statistisch, nicht FD-Bias) im Docstring.
- **§A1/SRBench-Hygiene** → `discovery/srbench_hygiene.py`: Dummy-Variablen-Test (Alien-Dim → Exponent 0) + OOS.
- **Bayes-Unsicherheit** → `discovery/uncertainty.py`: Bootstrap-Band (degeneriert auf exakten Kepler-Daten, verbreitert mit Rauschen).
- **§A3 Beweis-Loop** → `discovery/proof_loop.py`: mpmath-Vorfilter → SymPy → z3-Kernel; „Satz" nur kernel-geschlossen,
  `sin(x)=x`→widerlegt (Vorfilter), `(x²+x)/x=x+1`→widerlegt (z3 x=0), transzendent-wahr→„Kandidat" (ehrlich, nicht „Satz").
- **§A4 T-Optimalität (maximin)** → `active_resolution.propose_resolution_robust`: innerer Rival-Refit — der Spread überlebt
  den optimal refitteten Verlierer (44.7× Rauschen), ein Einzelpunkt wird absorbiert (1.6×). Genau die „Form schlägt Punkt"-Lehre.
- **CLI** → `gen --mode discover-ode` (SINDy + Hygiene-Dummy + Unsicherheitsband in einem deterministischen Befehl, EXIT=0).
- **Opt-in/BLOCKED-Adapter** (Offline-Default = Test-Rückgrat): PySINDy (pip), Ax/BoTorch (pip), PySR/PhySO (Julia/GPU), Lean/Goedel
  (`ProofKernel`-Slot) — je hinter der jeweiligen Naht, Offline-Zwilling beweist die Verdrahtung. Volle Suite **1784 grün**.

*Diese Recherche bestätigt GENESIS' Seele (Verifizierer-als-Wahrheit) und kartiert ehrlich den Weg
zu echtem Forscher-Niveau — mit benannten Methoden, ehrlicher Hype-Trennung und einem priorisierten
Fahrplan. **Erledigt:** diese Erkenntnisse sind im Entdeckungs-Kern verdrahtet; die Discovery-Bausteine sind real lauffähig.*
