#!/bin/bash
# Foco no macOS: abre o aplicativo em http://127.0.0.1:8765. Ctrl+C ou fechar a janela encerra.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -x ".venv/bin/python" ]; then
  echo "Execute instalar.command primeiro."
  read -r -p "Pressione Enter para fechar..." _
  exit 1
fi

.venv/bin/python run.py "$@"
status=$?
if [ $status -ne 0 ]; then
  read -r -p "Pressione Enter para fechar..." _
fi
exit $status
