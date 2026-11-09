#!/bin/bash
# Foco no macOS: instala o Qev opcional (cerca de 3 GB) em .local-data/qev.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

PYTHON=".venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
"$PYTHON" scripts/prepare_qev.py
status=$?
read -r -p "Pressione Enter para fechar..." _
exit $status
