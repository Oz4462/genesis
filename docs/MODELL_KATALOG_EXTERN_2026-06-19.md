# Externe Science-/Discovery-Modelle — Download- & Lizenz-Katalog für GENESIS

> Tiefe, belegte Suche (2026-06-19, 5 parallele Rechercheteams, ~80 Systeme) nach KI-Modellen und
> -Werkzeugen, die GENESIS als **Verifizierer/Orakel, Datenquelle oder nachgebaute Methode** einbauen
> kann. Fokus: **was ist wirklich herunterladbar — und kommerziell nutzbar?**
> Jede Verfügbarkeits-/Lizenzangabe ist quellen-belegt.

---

## 0 · Die Kern-Erkenntnis (die wichtigste der ganzen Suche)

**Für fast jedes nicht-kommerzielle Google-Modell existiert eine offene, kommerziell nutzbare
Alternative eines anderen Labors — oft mit besserer Lizenz.** GENESIS kann also einen **vollständig
kommerziell nutzbaren Stack** aus permissiv lizenzierten (Apache/MIT/BSD) Weltklasse-Verifizierern +
der Erfindungs-Schleife bauen und Googles Nicht-Kommerziell-Gates komplett umgehen.

| Gesperrt bei Google | Offene kommerzielle Alternative |
|---|---|
| AlphaFold 3 (nicht-kommerziell, Gewichte gated) | **Boltz-2 (MIT)**, **Chai-1 (Apache)**, **Protenix (Apache)**, **OpenFold3 (Apache)** |
| GraphCast/GenCast (NC-Gewichte) | **MS Aurora (MIT)**, **ECMWF AIFS (CC-BY)**, **NVIDIA FourCastNet 3 (Apache)** |
| GNoME-Daten (CC-BY-NC) | **Materials Project (CC-BY)** + **ORB/MatterSim/CHGNet/MatterGen (Apache/MIT/BSD)** |
| AlphaEvolve (geschlossen) | **OpenEvolve (Apache)**, **ShinkaEvolve (Apache, von Sakana!)** |
| AlphaProof (geschlossen) | **Goedel-Prover-V2 (Apache, offene Gewichte)**, **Kimina (Apache)**, **LeanDojo (MIT)** |
| AlphaGenome (NC) | (für Regulatorik noch keine saubere offene Alternative — selten) |

**Mythos-Korrektur:** „AlphaFold 3 ist Apache-2.0 open source" ist **falsch** — Code ist CC-BY-NC-SA
4.0, Gewichte sind gated + nur akademisch. Gleiche Falle bei GraphCast/GenCast: Code Apache, **Gewichte
nicht-kommerziell**.

---

## 1 · Google DeepMind — was wirklich nutzbar ist

**Kommerziell-OK (herunterladen & in ein Produkt bauen):**
- **AlphaFold-Datenbank** — 200M+ Strukturen, **CC-BY 4.0** ([Download](https://alphafold.com/download)). Das offenste Google-Science-Asset.
- **AlphaFold 2** — Apache-Code + **CC-BY 4.0-Gewichte** ([GitHub](https://github.com/google-deepmind/alphafold)).
- **AlphaGeometry 1** — Apache + CC-BY-Gewichte ([GitHub](https://github.com/google-deepmind/alphageometry)).
- **AlphaDev / AlphaTensor / AlphaTensor-Quantum** — Apache, mit den entdeckten Algorithmen.
- **AlphaChip** (`circuit_training`) — Apache + Pretrained-Checkpoint.
- **FunSearch** — Apache (du bringst das LLM) ([GitHub](https://github.com/google-deepmind/funsearch)).
- **Ithaca / Aeneas** (Epigraphik) — Apache + Gewichte.
- **AlphaEarth / Satellite Embedding** — **CC-BY 4.0**-Daten ([Earth Engine](https://developers.google.com/earth-engine/datasets/publisher/google)).
- **WeatherNext** historische Vorhersagedaten (>48h) — CC-BY 4.0.
- **Gemma 4** (offenes LLM) — **Apache 2.0**; TxGemma (Drug-Discovery-Variante) — HAI-DEF-Terms (kommerziell erlaubt, gated).

**Herunterladbar ABER nicht-kommerziell (Forschung/akademisch):**
- **AlphaFold 3** — Code CC-BY-NC-SA + gated Gewichte (akademisch, dürfen nicht weitergegeben werden) ([Terms](https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md)).
- **AlphaGenome** (DNA-Regulatorik) — Apache-Code, aber **Gewichte + API nicht-kommerziell** ([HF](https://huggingface.co/google/alphagenome-all-folds)).
- **GraphCast & GenCast** — Apache-Code, **CC-BY-NC-SA-Gewichte** ([GitHub](https://github.com/google-deepmind/graphcast)).
- **GNoME**-Materialdatenbank — **CC-BY-NC 4.0**-Daten; Modellgewichte nie veröffentlicht ([GitHub](https://github.com/google-deepmind/materials_discovery)).

**Geschlossen / nur API / intern (gar nicht herunterladbar):**
- **AlphaProteo** (Protein-Binder-Design), **IsoDDE** (Isomorphic, proprietär), **AlphaQubit** (Quanten-Fehlerkorrektur), **AI Co-Scientist** (nur Trusted-Tester), **Gemini Deep Think**, **Lyria** (Musik, API), **WeatherNext**-Modell-Inferenz (Vertex-EAP), **AlphaProof**-System (nur die Beweis-Outputs sind offen).

---

## 2 · Offene, kommerziell nutzbare Alternativen je Domäne

### Biologie / Protein (Verifizierer & Generatoren — sauber kommerziell)
| Modell | Funktion | Lizenz (Code/Gewichte) | Kommerziell |
|---|---|---|---|
| **Boltz-1 / Boltz-2** | AF3-Klasse Struktur + Bindungsaffinität | **MIT / MIT** | ✅ ([GitHub](https://github.com/jwohlwend/boltz)) |
| **Chai-1** | Multimodale Strukturvorhersage | **Apache-2.0 / Apache** | ✅ ([GitHub](https://github.com/chaidiscovery/chai-lab)) |
| **Protenix** (ByteDance) | trainierbare AF3-Reproduktion | **Apache-2.0** | ✅ ([GitHub](https://github.com/bytedance/Protenix)) |
| **OpenFold3** | AF3-Reproduktion (Preview) | **Apache-2.0** | ✅ ([HF](https://huggingface.co/OpenFold/OpenFold3)) |
| **RoseTTAFold All-Atom** | Protein+NA+Ligand-Struktur | **BSD** | ✅ ([GitHub](https://github.com/baker-laboratory/RoseTTAFold-All-Atom)) |
| **ESMFold + ESM-2** | MSA-freie Faltung + Protein-LM | **MIT** | ✅ ([GitHub](https://github.com/facebookresearch/esm)) |
| **RFdiffusion / -AllAtom / 2** | de-novo Protein/Enzym-Design | **BSD / BSD / MIT** | ✅ ([GitHub](https://github.com/RosettaCommons/RFdiffusion)) |
| **ProteinMPNN / LigandMPNN** | Sequenz-Design (inverse folding) | **MIT** | ✅ |
| **DiffDock / -L** | Protein-Ligand-Docking | **MIT** | ✅ ([GitHub](https://github.com/gcorso/DiffDock)) |
| **NVIDIA BioNeMo** (Framework) | GPU-Bio-Modell-Plattform | **Apache** (pro Modell/NIM prüfen) | ✅* |

**Nicht kommerziell** (trotz Download): ESM3-open / ESM C 600M (Cambrian-NC), HelixFold3 (Baidu-NC). Chai-2 gar nicht released.
**Sauberer Bio-Pipeline-Stack (alles MIT/BSD/Apache):** ESMFold/Boltz-2/Chai-1 (falten) → RFdiffusion (Backbones) → LigandMPNN/ProteinMPNN (Sequenzen) → Boltz-2/DiffDock (validieren/docken).

### Materialien / Chemie (Energie-/Kraft-Orakel + Generatoren)
| Modell | Funktion | Lizenz | Kommerziell |
|---|---|---|---|
| **Orbital ORB** (v3/OrbMol) | universelles Potenzial | **Apache-2.0** | ✅ ([GitHub](https://github.com/orbital-materials/orb-models)) |
| **MS MatterSim** | universelles Potenzial (0–5000K) | **MIT** | ✅ ([GitHub](https://github.com/microsoft/mattersim)) |
| **CHGNet** | Potenzial + Ladung/Magmom | **BSD-3** | ✅ ([GitHub](https://github.com/CederGroupHub/chgnet)) |
| **M3GNet / MatGL** | Potenzial + Eigenschafts-Prädiktoren | **BSD-3** | ✅ |
| **MACE-MP-0 / MPA-0** (nur diese) | Foundation-Potenzial | **MIT** | ✅ (OMAT/OFF/MH-Checkpoints = ASL-NC!) |
| **MS MatterGen** | generative Kristalle | **MIT (+Daten)** | ✅ ([GitHub](https://github.com/microsoft/mattergen)) |
| **REINVENT 4** | generative Moleküle | **Apache-2.0** | ✅ ([GitHub](https://github.com/MolecularAI/REINVENT4)) |
| **ALIGNN / JARVIS** (NIST) | Eigenschafts-Prädiktoren + Daten | **MIT / public-domain** | ✅ |
| **Materials Project + MPtrj** | Referenzdaten + Trainingssatz | **CC-BY 4.0** | ✅ |
| **Meta OMat24 / UMA / OMol25** | SOTA-Potenziale + Datensätze | FAIR-Lizenz (komm. *mit Auflagen*; Daten CC-BY) | ⚠️ (China/Russland/Belarus ausgeschlossen) |

**Nicht kommerziell:** GNoME-Daten (CC-BY-NC), MACE-OMAT/MATPES/OFF23/MH (ASL). SevenNet = GPL (intern OK, Vorsicht beim Vertrieb).

### Wetter / Klima / Erde (Datenquelle/Verifizierer)
| Modell | Funktion | Lizenz | Kommerziell |
|---|---|---|---|
| **MS Aurora** | Atmosphären-Foundation (Wetter/Luft/Welle) | **MIT** | ✅ ([HF](https://huggingface.co/microsoft/aurora)) |
| **ECMWF AIFS-Single** | operationelles Globalmodell | **CC-BY 4.0** | ✅ ([HF](https://huggingface.co/ecmwf/aifs-single-1.0)) |
| **NVIDIA FourCastNet 3** | probabilistisches Globalmodell | **Apache-2.0** | ✅ ([HF](https://huggingface.co/nvidia/fourcastnet3)) |
| **NVIDIA Atlas** | Ensemble Mittelfrist (schlägt GenCast) | NVIDIA Open Model License | ✅ ([HF](https://huggingface.co/nvidia/atlas-era5)) |
| **NVIDIA StormScope / CorrDiff** | Nowcasting / Downscaling | NVIDIA OML | ✅ |
| **MS ClimaX** | Klima-Foundation-Backbone | **MIT** | ✅ |
| **IBM/NASA Prithvi-WxC** | Wetter×Klima-Foundation | **CDLA-Permissive-2.0** | ✅ |
| **Clay** | Erdbeobachtungs-Embeddings | **Apache-2.0** | ✅ ([HF](https://huggingface.co/made-with-clay/Clay)) |
| **IBM/NASA Prithvi-EO-2.0** | Geo-Foundation (Satellit) | **Apache-2.0** | ✅ |
| **Major TOM** | offene EO-Datensätze/Embeddings | CC-BY / CC-BY-SA | ✅ |

**Nicht kommerziell:** GraphCast/GenCast, Pangu-Weather, FengWu, FuXi (alle CC-BY-NC-SA), Aardvark (NC-ND).

### Erfindungs-/Entdeckungs-Schleife (das, was GENESIS *nachbauen* sollte)
| Werkzeug | Rolle | Lizenz | Kommerziell |
|---|---|---|---|
| **OpenEvolve** | AlphaEvolve-Loop (MAP-Elites+Inseln+LLM) | **Apache-2.0** | ✅ ([GitHub](https://github.com/algorithmicsuperintelligence/openevolve)) **bestes Skelett** |
| **ShinkaEvolve** (Sakana) | Sample-effizienter Evolve-Loop + WebUI | **Apache-2.0** | ✅ ([GitHub](https://github.com/SakanaAI/ShinkaEvolve)) |
| **CodeEvolve** | offener AlphaEvolve-Nachbau | **Apache-2.0** | ✅ |
| **PySR** | Symbolic Regression (Standard) | **Apache-2.0** | ✅ ([GitHub](https://github.com/MilesCranmer/PySR)) |
| **PhySO** | physikalische SR (mit Einheiten) | **MIT** | ✅ ([GitHub](https://github.com/WassimTenachi/PhySO)) |
| **LLM-SR** | LLM-geführte SR | **MIT** | ✅ |
| **PySINDy** | DGL-/Dynamik-Entdeckung | **MIT** | ✅ ([GitHub](https://github.com/dynamicslab/pysindy)) |
| **Lean 4 + Mathlib** | formaler Beweis-Kernel | **Apache-2.0** | ✅ |
| **LeanDojo / ReProver** | Lean-Gerüst + neuronaler Beweiser | **MIT** | ✅ ([GitHub](https://github.com/lean-dojo/LeanDojo)) |
| **Goedel-Prover-V2** | SOTA Lean-Beweiser (offene Gewichte!) | **Apache-2.0** | ✅ ([HF](https://huggingface.co/Goedel-LM/Goedel-Prover-V2-32B)) |
| **Kimina-Prover** | Lean-Beweiser | **Apache-2.0** | ✅ |
| **Ax + BoTorch** | Bayes-Opt / Experiment-Design | **MIT** | ✅ ([GitHub](https://github.com/meta-pytorch/botorch)) |
| **Atlas + Olympus** | Experiment-Planer (self-driving lab) | **MIT** | ✅ |
| **STORM** (Stanford) | zitierte Literatur-/Prior-Art-Synthese | **MIT** | ✅ ([GitHub](https://github.com/stanford-oval/storm)) |
| **Agent Laboratory / SciAgentsDiscovery** | End-to-End-Forschungs-/Hypothesen-Agenten | **MIT / Apache** | ✅ |

**Ausschließen / Lizenz prüfen:** Sakana **AI-Scientist** v1/v2 (RAIL-restriktiv — nicht sauber kommerziell; *ShinkaEvolve* derselben Firma ist dagegen Apache), Google AI co-scientist (geschlossen), Zochi (nur Showcase-Repo), pysisso (archiviert+NC → stattdessen die Apache-SISSO-Engine), DeepSeek-Prover-V2-Gewichte (RAIL-artig, aber kommerziell erlaubt).

---

## 3 · Der empfohlene GENESIS-Stack (vollständig kommerziell, permissiv)

Alles Apache/MIT/BSD, alles herunterladbar, je Loop-Stufe:

- **Erfindungs-Loop (Kern):** **OpenEvolve** oder **ShinkaEvolve** (Apache) — die AlphaEvolve-Engine; Claude/Grok als Generatoren, GENESIS-Engine als Evaluator.
- **Gesetzes-Entdeckung:** **PySR** + **PhySO** (Einheiten!) + **PySINDy** (DGL) — Apache/MIT.
- **Zertifizieren (Mathe):** **Lean 4 + Mathlib** + **LeanDojo** + **Goedel-Prover-V2** (Apache, offene Gewichte).
- **Experiment-Wahl (active_resolution-Upgrade):** **Ax/BoTorch** + **Atlas** (MIT) — die rigorose T-Optimalität/EIG aus der vorigen Recherche.
- **Domänen-Verifizierer (als Orakel anrufen):**
  - **Bio:** Boltz-2/Chai-1 + RFdiffusion + LigandMPNN (MIT/BSD/Apache)
  - **Materialien:** ORB/MatterSim + MatterGen + Materials Project (Apache/MIT/CC-BY)
  - **Wetter/Erde:** Aurora/AIFS + Clay (MIT/CC-BY/Apache)
- **Prior-Art/Literatur:** **STORM** (MIT) + PatentsView/Google-Patents-Embeddings (aus der Neuheits-Recherche).

Damit wird GENESIS' schwächste Erdung (Bio/Materialien/Klima) durch **Weltklasse-Modelle** tief — ohne sie zu bauen, ohne Lizenz-Hürde, ohne Google-NC-Gate.

---

## 4 · Wichtige Lizenz-Fallstricke (vor Produktivnutzung beachten)
- **„Code offen" ≠ „Gewichte kommerziell"** — bei MACE, GraphCast, AlphaFold3, AlphaGenome divergieren Code- und Gewichts-Lizenz. Immer die *Gewichts-/Daten*-Lizenz prüfen.
- **Trainingsdaten-Lizenz separat** — Wettermodelle erben ERA5/Copernicus/MERRA-2/GOES-Bedingungen; bei Weitergabe von Outputs zusätzlich beachten.
- **Meta-FAIR-Lizenz** schließt bestimmte Länder aus (China/Russland/Belarus) und verlangt Click-Through.
- **GPL (SevenNet) / RAIL (DeepSeek-Prover, Sakana AI-Scientist)** — nutzbar, aber mit Pflichten; vor Vertrieb juristisch prüfen.
- **NVIDIA Open Model License** erlaubt kommerziell, hat aber Patent-/Indemnity-Klauseln.

---

*Belege: alle Links inline. Diese Datei ergänzt `FORSCHUNG_AUTONOMES_ERFINDEN_2026-06-19.md` (Methoden)
und `INVENTOR_ARCHITEKTUR.md` (Plan). Nächster Schritt: entscheiden, welche dieser Bausteine wir als
erstes anbinden (Empfehlung: OpenEvolve-Loop + PySR/PySINDy zuerst, dann ein Bio- oder Materials-Verifizierer
als erstes Domänen-Plugin).*
