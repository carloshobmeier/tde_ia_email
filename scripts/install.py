"""Instala as dependências em pastas do projeto e compila a interface."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.runtime import launcher


def run(args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Instale Python 3.11 ou superior e tente novamente.")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("Instale Node.js 22 ou superior (incluindo npm) e tente novamente.")
    print("\n[1/3] Preparando Python local...", flush=True)
    venv = ROOT / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        # --clear também recria um .venv copiado de outro sistema (ex.: pasta vinda do Windows).
        run([sys.executable, "-m", "venv", "--clear", str(venv)])
    requirements = "requirements-lock.txt" if sys.version_info[:2] == (3, 12) else "requirements.txt"
    run([str(python), "-m", "pip", "install", "-r", requirements, "--cache-dir", str(ROOT / ".local-data/pip-cache"), "--disable-pip-version-check"])
    print("\n[2/3] Preparando a interface...", flush=True)
    run([npm, "ci", "--no-fund", "--no-audit", "--cache", str(ROOT / ".local-data/npm-cache")], ROOT / "frontend")
    print("\n[3/3] Compilando...", flush=True)
    run([npm, "run", "build"], ROOT / "frontend")
    print(f"\nPronto! Use {launcher('preparar_ia')} para baixar a IA (uma vez) e {launcher('iniciar')} para abrir o Foco.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Instalação interrompida na etapa acima (código {exc.returncode}). Corrija o erro e execute novamente.")
