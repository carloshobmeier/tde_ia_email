"""Inicia apenas os serviços locais pertencentes ao Foco."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".local-data"
AI_URL = "http://127.0.0.1:11435"
# Qev opcional, instalado por preparar_qev. Mesmo endereço padrão de backend/config.py.
QEV_DIR = DATA / "qev"
QEV_PORT = 11436
QEV_URL = f"http://127.0.0.1:{QEV_PORT}"


def qev_command():
    """Comando do servidor Qev, ou None se não instalado. Sem gravar requisições (texto de e-mails)."""
    python = QEV_DIR / "runtime" / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    model = QEV_DIR / "models" / "qev-0.8b"
    if not python.exists() or not (model / "qev_config.json").is_file():
        return None
    return [str(python), "-m", "qev", "serve", "--model", str(model), "--backend", "torch",
            "--host", "127.0.0.1", "--port", str(QEV_PORT), "--no-request-log", "--no-warmup"]


def ensure_qev():
    """Inicia o Qev em segundo plano (o modelo leva alguns segundos para carregar)."""
    command = qev_command()
    if command is None:
        return None, None
    try:
        get_json(QEV_URL + "/health")
        return None, None
    except Exception:
        pass
    env = os.environ.copy()
    # Tudo dentro de .local-data/qev e sem rede: o modelo já foi baixado por preparar_qev.
    env.update(HF_HOME=str(QEV_DIR / "hf-cache"), HF_HUB_OFFLINE="1", QEV_HOME=str(QEV_DIR / "home"),
               TOKENIZERS_PARALLELISM="false", PYTORCH_ENABLE_MPS_FALLBACK="1")
    log = (DATA / "qev.log").open("a", encoding="utf-8")
    process = subprocess.Popen(command, env=env, stdout=log, stderr=log, cwd=str(QEV_DIR),
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return process, log

# Ao abrir pelo Finder, o PATH pode não incluir o Homebrew nem o CLI do Ollama.app.
MAC_OLLAMA_PATHS = ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama",
                    "/Applications/Ollama.app/Contents/Resources/ollama",
                    str(Path.home() / "Applications/Ollama.app/Contents/Resources/ollama"))


def launcher(name):
    """Atalho do sistema atual: instalar.bat no Windows, ./instalar.command no macOS/Linux."""
    return f"{name}.bat" if os.name == "nt" else f"./{name}.command"


def find_ollama():
    found = shutil.which("ollama")
    if found or sys.platform != "darwin":
        return found
    return next((path for path in MAC_OLLAMA_PATHS if os.access(path, os.X_OK)), None)


def get_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=2) as response:
        return json.load(response)


def ensure_ollama():
    """Retorna processo/log se criado aqui. Nunca encerra um serviço preexistente."""
    try:
        get_json(AI_URL + "/api/version")
        return None, None
    except Exception:
        pass
    executable = find_ollama()
    if not executable:
        return None, None
    DATA.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_NO_CLOUD="1", OLLAMA_NUM_PARALLEL="1",
               OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_MODELS=str(DATA / "ollama-models"))
    log = (DATA / "ollama.log").open("a", encoding="utf-8")
    process = subprocess.Popen([executable, "serve"], env=env, stdout=log, stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for _ in range(40):
        try:
            get_json(AI_URL + "/api/version")
            return process, log
        except Exception:
            if process.poll() is not None:
                break
            time.sleep(.25)
    process.terminate()
    process.wait(timeout=10)
    log.close()
    return None, None


def stop_owned(process, log):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if log is not None:
        log.close()
