"""Instala o Qev opcional em .local-data/qev: runtime revisado, PyTorch e modelos (cerca de 3 GB).

Versões fixas para reprodutibilidade. Precisa de git, uv e internet só durante a instalação;
depois o Foco inicia o Qev sem rede. Só usa a biblioteca padrão (roda com qualquer Python 3.11+).
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.runtime import QEV_DIR, launcher

RUNTIME_REPO = "https://github.com/loadchange/qev.git"
RUNTIME_COMMIT = "0af3c102dbb239644b46b861f6511e3f75a19527"  # código revisado em 09/11/2026
MODEL_REPO, MODEL_REVISION = "twainsk/qev-0.8b", "1d2a6d7f891daab7483a49c3abe507c0c9d7ea62"
BASE_REPO, BASE_REVISION = "Qwen/Qwen3.5-0.8B", "2fc06364715b967f1860aea9cf38778875588b17"


def run(args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main():
    git, uv = shutil.which("git"), shutil.which("uv")
    if not git or not uv:
        raise SystemExit("O Qev precisa de git e uv: https://git-scm.com e https://docs.astral.sh/uv/")
    runtime = QEV_DIR / "runtime"
    # Links de um teste temporário são substituídos por uma instalação própria do projeto.
    for path in (runtime, QEV_DIR / "models" / "qev-0.8b", QEV_DIR / "hf-cache"):
        if path.is_symlink():
            path.unlink()
    env = {**os.environ, "HF_HOME": str(QEV_DIR / "hf-cache"), "QEV_HOME": str(QEV_DIR / "home")}
    print("\n[1/4] Código do Qev (versão revisada)", flush=True)
    if not (runtime / ".git").exists():
        run([git, "clone", RUNTIME_REPO, str(runtime)])
    run([git, "-C", str(runtime), "fetch", "--quiet", "origin"])
    run([git, "-C", str(runtime), "checkout", "--quiet", RUNTIME_COMMIT])
    print("\n[2/4] Ambiente Python isolado com PyTorch", flush=True)
    run([uv, "sync", "--python", "3.12", "--extra", "torch"], cwd=runtime, env=env)
    hf = runtime / (".venv/Scripts/hf.exe" if os.name == "nt" else ".venv/bin/hf")
    print("\n[3/4] Adaptador do Qev (cerca de 86 MB)", flush=True)
    run([str(hf), "download", MODEL_REPO, "--revision", MODEL_REVISION,
         "--local-dir", str(QEV_DIR / "models" / "qev-0.8b")], env=env)
    print("\n[4/4] Modelo-base Qwen3.5-0.8B (cerca de 1,8 GB)", flush=True)
    run([str(hf), "download", BASE_REPO, "--revision", BASE_REVISION], env=env)
    print(f"\nQev pronto. Abra o Foco com {launcher('iniciar')}: a classificação passa a combinar TF-IDF e Qev.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Instalação do Qev interrompida (código {exc.returncode}). O Foco continua funcionando sem ele.")
