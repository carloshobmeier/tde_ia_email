#!/bin/bash
# Experimento: Qev zero-shot sozinho e combinado ao TF-IDF, no corpus sintético do Foco.
# Instala o Qev como o aplicativo (scripts/prepare_qev.py, versões fixas em .local-data/qev)
# e grava os resultados em artifacts/qev-*.json. macOS/Linux; no Windows, Git Bash ou WSL.
# Argumento opcional, repassado ao Qev: --device cpu
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$ROOT/.venv/Scripts/python.exe"
"$PY" "$ROOT/scripts/prepare_qev.py"

WORK="$ROOT/.local-data/qev"
QPY="$WORK/runtime/.venv/bin/python"; [ -x "$QPY" ] || QPY="$WORK/runtime/.venv/Scripts/python.exe"
export HF_HOME="$WORK/hf-cache" HF_HUB_OFFLINE=1 QEV_HOME="$WORK/home"
mkdir -p "$ROOT/artifacts"
CHECKPOINT="$WORK/models/qev-0.8b"

echo "Qev sozinho (zero-shot)"
"$QPY" "$ROOT/experiments/qev/qev_email_eval.py" --project "$ROOT" --checkpoint "$CHECKPOINT" \
  --out "$ROOT/artifacts/qev-results.json" "$@"
echo "Probabilidades por e-mail para a combinação"
"$QPY" "$ROOT/experiments/qev/qev_dump_probs.py" --project "$ROOT" --checkpoint "$CHECKPOINT" \
  --out "$ROOT/artifacts/qev-probs.json" "$@"
echo "Combinação TF-IDF + Qev (ambiente do projeto)"
"$PY" "$ROOT/experiments/qev/ensemble_eval.py" --qev-probs "$ROOT/artifacts/qev-probs.json" \
  --out "$ROOT/artifacts/qev-ensemble.json"
