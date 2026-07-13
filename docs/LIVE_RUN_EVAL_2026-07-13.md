# Live-Run Evaluation — 2026-07-13

> Generator: **grok-4.5** via real `~/.grok/bin/grok`  
> Verifier: **claude-opus-4-8** via `claude` CLI  
> Environment: PATH prefers real grok binary; `GENESIS_GROK_BINARY` set (wrapper at `~/.local/bin/grok` injects `--agent structured` and breaks headless).

## Infrastructure findings (fixed in this branch)

| Issue | Effect | Fix |
|-------|--------|-----|
| Default model `grok-build` unknown on this CLI | Live start fails | Default → **`grok-4.5`** (also available: `grok-composer-2.5-fast`) |
| Long system+user on `-p` | `OSError: Argument list too long` | GrokCLI uses **`--prompt-file`** when prompt ≥ 4000 chars |
| PATH wrapper `~/.local/bin/grok` | forces structured agent | Prefer real binary via PATH / `GENESIS_GROK_BINARY` |

## Pipeline results (measured)

| Mode | Live LLMs | Exit | Result vs vision |
|------|-----------|------|------------------|
| **report** (Phase α) | grok-4.5 + claude-opus-4-8 | 0 | **Honest empty report** — Wikipedia hits found, Grok extracted **[] claims** because snippets did not *state* T=2π√(L/g); no fabricated claims. Skeptic unused (nothing to verify). **Anti-hallucination works as designed.** |
| **research** (CAS/z3) | none | 0 | `(x+1)² = x²+2x+1` → **SURVIVED_NOVEL**, proof=cas_certified, ladder HARDENED. Math gate path OK. |
| **invent --live** | live council (log: claude-opus-4-8) | 0 | **Original idea** (Krankenhaus-Indoor-Transportroboter 50 kg): **3 Konzepte, 3 δ-physics grounded**, Pareto proxy non-empty, Verdikt OK. γ+ Pareto not attached (honest empty). |
| **spec** (Phase γ live) | grok-4.5 + claude | 0 | Spec empty: “No grounded approach available…” — same honesty when α grounding fails; completeness warnings listed. |
| **horizon-full** | offline engines | 0 | 6 ok · 0 error · 1 skipped; δ⁺ inconclusive honestly; Grenz-Cluster 8/8. |

## Independent idea (created for invent)

**Idee:** *Leiser, wartungsarmer Indoor-Transportroboter für Krankenhausflure: modular, batterieelektrisch, Last bis 50 kg, ehrliche Physik und BOM.*

**Delivered concepts (live invent):**
1. Differential-drive QDD base, &lt;45 dB(A) target — physics_verified, 3 sources  
2. Hot-swap 48 V LiFePO4 cartridge ~8 h — physics_verified  
3. Sealed brushless drivetrain + 2D LiDAR odometry, &gt;10k h service interval — physics_verified  

## Does GENESIS work as envisioned?

| Vision claim | Live verdict |
|--------------|--------------|
| Cross-model generator ≠ verifier | **Yes** (xai vs claude enforced) |
| No claim without source | **Yes** — α returned zero claims rather than inventing pendulum formula |
| Gate over proposal | **Yes** — invent δ-physics gate; empty α/spec when ungrounded |
| Live Grok + Claude path | **Works after adapter/ops fixes**; invent OK; α/spec may stay empty when search snippets lack explicit statements |
| Offline deterministic core | **Yes** — research, horizon-full, demos |

### Gaps / operator notes

1. Point PATH at **`/home/genesis/.grok/bin`** (or set `GENESIS_GROK_BINARY`) for headless live runs.  
2. Use **`--generator grok-4.5`** (not `grok-build` on this machine).  
3. Phase α quality depends on **backend snippets** (Wikipedia/SS) containing explicit claim text — not a silent fail, but can look “empty” for textbook facts.  
4. invent γ+ Pareto attachment still honest-empty on this path.

## Commands to reproduce

```bash
export PATH="/home/genesis/.grok/bin:$PATH"
export GENESIS_GROK_BINARY=/home/genesis/.grok/bin/grok

python -m gen --mode report --generator grok-4.5 --verifier claude-opus-4-8 \
  "What is the closed-form formula for the period of a simple pendulum for small angles?"

python -m gen --mode invent --live --generator grok-4.5 --verifier claude-opus-4-8 \
  "Leiser Indoor-Transportroboter Krankenhaus 50 kg"

python -m gen --mode research "(x+1)**2|x**2+2*x+1"
python -m gen --mode horizon-full
```
