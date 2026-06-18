#!/usr/bin/env bash
# grok_review.sh — cross-model drift / hallucination / correctness review via the Grok Build CLI.
#
# The per-tour skeptic of the GENESIS Universe-Explorer build: it hands new code + claims to a
# DIFFERENT model family (xAI grok-build, never the build model itself) and asks it to find
# drift (does the implementation match the description?), over-claim/hallucination (does a
# docstring/test assert more than the code proves?), and correctness errors (math/dimensions).
# Its findings are advisory — they are self-verified before any action (Grok = proposal, never
# truth), exactly the project's own discipline.
#
# Usage:
#   bash scripts/grok_review.sh <file-with-code-and-claims>
#   git diff | bash scripts/grok_review.sh            # review the working diff
#   bash scripts/grok_review.sh                        # read from stdin
#
# Env: GROK_BIN (default /c/Users/Ozan/.grok/bin/grok), GROK_MODEL (default grok-build).
set -euo pipefail

GROK="${GROK_BIN:-/c/Users/Ozan/.grok/bin/grok}"
MODEL="${GROK_MODEL:-grok-build}"   # the build model — NEVER grok-composer

if [[ "${1:-}" == "--model" ]]; then MODEL="$2"; shift 2; fi
INPUT_FILE="${1:-}"

payload="$(mktemp)"; prompt="$(mktemp)"
trap 'rm -f "$payload" "$prompt"' EXIT

if [[ -n "$INPUT_FILE" && -f "$INPUT_FILE" ]]; then cat "$INPUT_FILE" > "$payload"; else cat > "$payload"; fi

{
  echo "Du bist ein ADVERSARIALER Cross-Model-Reviewer fuer GENESIS, eine Anti-Halluzinations-"
  echo "Engine fuer Physik-/Mathematik-Entdeckung (KEIN Trading, kein Finanz-Kontext)."
  echo "Pruefe den folgenden NEUEN CODE + CLAIMS streng auf drei Dinge:"
  echo "  1) DRIFT      - weicht die Implementierung von ihrer Beschreibung/Doku ab?"
  echo "  2) UEBERCLAIM - behauptet ein Docstring/Kommentar/Test mehr, als der Code wirklich beweist?"
  echo "  3) KORREKTHEIT- ist Mathematik, Dimensionen oder Logik falsch?"
  echo "Sei knapp und konkret. Format pro Fund: 'SCHWERE | DATEI/STELLE | BEFUND'."
  echo "Wenn du nichts findest, antworte exakt: KEIN DRIFT."
  echo "----- CODE + CLAIMS -----"
  cat "$payload"
} > "$prompt"

# Run grok-build headless and strip the CLI's MCP/connection chatter so only the verdict remains.
timeout "${GROK_TIMEOUT:-180}" "$GROK" -p "$(cat "$prompt")" --model "$MODEL" 2>&1 \
  | grep -vaiE "Transport channel closed|AuthRequired|MCP|Connecting|Initializing|tool call|^warning|^\s*$" \
  || true
