"""Instala as dependências em pastas do projeto e compila a interface."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


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
    if not venv.exists():
        run([sys.executable, "-m", "venv", str(venv)])
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirements = "requirements-lock.txt" if os.name == "nt" and sys.version_info[:2] == (3, 12) else "requirements.txt"
    run([str(python), "-m", "pip", "install", "-r", requirements, "--cache-dir", str(ROOT / ".local-data/pip-cache"), "--disable-pip-version-check"])
    print("\n[2/3] Preparando a interface...", flush=True)
    run([npm, "ci", "--no-fund", "--no-audit", "--cache", str(ROOT / ".local-data/npm-cache")], ROOT / "frontend")
    print("\n[3/3] Compilando...", flush=True)
    run([npm, "run", "build"], ROOT / "frontend")
    print("\nPronto! Use preparar_ia.bat para baixar a IA (uma vez) e iniciar.bat para abrir o Foco.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Instalação interrompida na etapa acima (código {exc.returncode}). Corrija o erro e execute novamente.")
