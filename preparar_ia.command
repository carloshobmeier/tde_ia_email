#!/bin/bash
# Foco no macOS: baixa o Qwen3 4B (uma vez) para .local-data/ollama-models.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PYTHON=".venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
"$PYTHON" scripts/prepare_ai.py
status=$?
read -r -p "Pressione Enter para fechar..." _
exit $status
