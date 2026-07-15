# About GENESIS

**GENESIS** (*Generative Engine for Networked Ideation, Synthesis & Specification*) is an **anti-hallucination engineering system**: a human provides an idea; GENESIS researches, verifies, computes, and packages a **buildable, sourced specification** — without inventing facts.

---

## One-line pitch

> Sources over claims · recomputed physics over guessed numbers · honest gaps over invented answers.

---

## What it is

GENESIS is **not** a chatbot that drafts a design and hopes. The core is a **verifier-first pipeline**:

| Pillar | Meaning |
|--------|---------|
| **Ledger claims** | Every fact is a `Claim` with provenance; unsourced claims cannot be constructed |
| **Gates** | Phases end only when hard code checks pass — not when a model “sounds sure” |
| **Recomputed numbers** | Physics and design quantities are re-derived, not trusted from prose |
| **Abstention** | “I don’t know” is a valid, preferred output |
| **Offline-first** | Full demos and CI run without cloud; live LLMs are optional |

### Three product arms

1. **Specify** — idea → research (α) → options (β) → specification (γ) → physics gate (δ) → package  
2. **Discover** — data / conjecture → SINDy / proof loop → law with uncertainty labels (*theorem* / *refuted* / *candidate*)  
3. **Invent** — field → safety gate → council → novelty → δ-physics → Pareto → STL/BOM  

---

## Who it is for

- **Inventors and builders** who need auditable specs, not slideware  
- **Engineers** who want δ-physics, BOM, DFM, and honest manufacturing gaps in one loop  
- **Researchers** who need discovery labels that don’t launder z3 limits into “theorems”  
- **Teams using AI coding agents** who want the *same* anti-hallucination bar on the product they ship  

---

## What’s strong today (2026-07)

| Area | Highlights |
|------|------------|
| **HORIZON φ→Ω** | Seams (ε), memory fabric (ζ), Pareto (γ⁺), reality (δ⁺), coverage, **Ω enforced by default** |
| **Manufacturing** | Advanced DFM (FDM/CNC/laser/PCB), cost bands, G-code (profile/pocket/face), CadQuery via isolated venv |
| **Realization packages** | Structured BOM (mech+elec), harness/netlist section, drawing index with explicit `drawing_gap` |
| **Live knowledge** | OpenAlex, arXiv, Wikidata density, materials; PatentsView key-gated; `genesis --mode sources` |
| **Platform caps** | Proof package, readiness ladder, teacher notes, community evidence on assess/bundle/realize |
| **CI** | GitHub Actions green on Python **3.11** and **3.12** (ruff + full pytest) |

Full narrative: **[README.md](README.md)** · Living truth: **[docs/STATUS.md](docs/STATUS.md)**

---

## Design principles (product law)

1. No factual output without a source  
2. Verification is a gate, not a suggestion  
3. Cross-model skepticism when live (generator ≠ verifier family)  
4. Abstention is success  
5. Deterministic offline path; live is opt-in  
6. Stack-agnostic core (`core/interfaces.py`); externals behind adapters  
7. No invented lab measurements or private field data  
8. Public literature is **agent-sourced** (e.g. OpenAlex) — users are not asked to fill community JSON ledgers  

---

## What it is *not* (honest)

GENESIS does **not** claim:

- Multi-axis freeform CAM as production-ready  
- Full GD&T PDF / DXF sign-off packages (drawings remain an index with `drawing_gap`)  
- A production vector DB (Qdrant/pgvector) as default  
- Invented private lab replications or 15 TB bulk “The Well” downloads  

Depth is tracked as **L0–L4** in STATUS: *wired* ≠ *factory certified*.

---

## Stack snapshot

| Layer | Choices |
|-------|---------|
| Language | Python ≥ 3.11 |
| Core math | numpy · sympy · scipy · mpmath |
| Gates / SMT | z3 (optional extra) |
| CAD (optional) | CadQuery in **isolated** venv · build123d path |
| Ledger | In-memory default · Postgres optional |
| Live models | CLI adapters (e.g. Grok / Claude) when `--live` |
| License | **MIT** |

---

## Repository

| | |
|--|--|
| **Code** | https://github.com/Oz4462/genesis |
| **CI** | https://github.com/Oz4462/genesis/actions |
| **Entry** | `pip install -e ".[dev,smt]"` then `genesis --help` |
| **Long docs** | [README.md](README.md) (detailed English home page) |

---

## One paragraph for bios / org profiles

> **GENESIS** is an open-source, offline-first anti-hallucination engine that turns ideas into verified engineering specifications. Every claim is sourced, every number is recomputed, and every phase ends at a hard gate — not a confident-sounding model answer. It supports specify, discover, and invent workflows, with HORIZON completion certificates, manufacturing DFM/G-code, and realization packages (BOM, harness, drawings). MIT licensed. Python ≥ 3.11.

---

*Last aligned with product campaign A–F and README long-form (2026-07-15).*
