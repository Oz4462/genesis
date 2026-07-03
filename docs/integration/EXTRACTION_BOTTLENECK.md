# Live-Extraktion: Befund + nächster Hebel (2026-06-14)

> Handoff aus der Diagnose, warum Live-Läufe inkonsistent verifizierte Claims liefern.

## Symptom

3 Live-α-Läufe (qwen3.5:9b/gemma4:12b, gleiche Frage „speed of light"): claims **1 / 0 / 0**.
Audit verifizierte jedes Mal; die Verdrahtung ist nicht das Problem.

## Diagnose (evidenz-gestützt, nicht geraten)

1. **Backend-Probe:** Wikipedia liefert die `Speed_of_light`-Summary (mit 299792458),
   arXiv 3 Treffer → **Discovery funktioniert**.
2. **num_ctx-Hypothese WIDERLEGT** (`scripts/pov/verify_num_ctx_fix.py`):
   - Kurz-Kontrolle (nur der Fakt, num_ctx=8192): extrahiert = **True** → Modell ist fähig.
   - Lange Quelle ~3955 Tokens, Fakt am Ende: num_ctx=2048 → **0/2**, num_ctx=8192 → **0/2**.
   - Der Fakt ist bei 8192 IM Fenster und wird trotzdem nicht extrahiert → **nicht num_ctx**,
     sondern „lost-in-the-middle"/Distraktion: qwen3.5:9b extrahiert aus langen, verrauschten
     Quellen mit dem strikten Extraktions-Prompt unzuverlässig.

## Root Cause

**Extraktions-Robustheit** des kleinen Generator-Modells (9B) auf realen, langen/verrauschten
Quellen + striktem deutschem Exact-Quote-Prompt. Nicht: Fenstergröße, nicht: Verdrahtung,
nicht: grundsätzliche Modellfähigkeit (Kurz-Quelle klappt).

## Defensive Härtung (umgesetzt, aber NICHT der Fix)

`OllamaLLM` setzt jetzt explizit `num_ctx` (Default 8192, konfigurierbar) statt Ollamas
kleinem Default (~2048). Verhindert *echte* Trunkierung bei Quellen >2048 Tokens — sinnvoll,
aber adressiert das beobachtete claims=0 nicht (s. o.). Getestet (`test_llm_ollama.py`).

## Nächster Hebel (Reihenfolge: billigstes zuerst)

1. **Größeres Extraktionsmodell** (lokal vorhanden: `qwen3:14b`, `qwen2.5:14b`,
   `mistral-small:24b`) als Generator in `build_live` — kein Training, Minuten. Erwartung:
   robuster auf langen Quellen. **Zuerst messen.**
2. **Prompt-Härtung** des scholar-Extraktions-Prompts (der strikte deutsche Exact-Quote-Prompt
   ist für 9B evtl. zu hart; z. B. Quelle vorab auf relevante Passagen kürzen/chunken).
3. **Fine-Tune** (3B QLoRA, WSL, GTX 1080 Ti Pascal — fp16/sdpa, kein bf16/flash-attn,
   GPU-Stunden) — nur wenn 1+2 nicht reichen. Datensatz: `goldset` + scholar-Prompt-Paare.

Hardware-Fakt für 3: 11 GB Pascal (CC 6.1) → 9B-Fine-Tune unrealistisch; nur 3B/1.5B QLoRA.
