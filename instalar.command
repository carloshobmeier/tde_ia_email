#!/bin/bash
# Foco no macOS: clique duas vezes no Finder ou rode ./instalar.command no Terminal.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 3.12 é a versão validada (requirements-lock.txt); 3.11+ funciona com requirements.txt.
PYTHON=""
for candidate in python3.12 python3.13 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Instale Python 3.11 ou superior (3.12 recomendado):"
  echo "  brew install python@3.12   ou   https://www.python.org/downloads/macos/"
  read -r -p "Pressione Enter para fechar..." _
  exit 1
fi

echo "Usando $("$PYTHON" --version) em $(command -v "$PYTHON")"
"$PYTHON" scripts/install.py
status=$?
if [ $status -ne 0 ]; then
  echo
  echo "A instalação precisa de atenção. Confira a mensagem acima."
fi
read -r -p "Pressione Enter para fechar..." _
exit $status
