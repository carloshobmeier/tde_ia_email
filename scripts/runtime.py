"""Inicia apenas os serviços locais pertencentes ao Foco."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".local-data"
AI_URL = "http://127.0.0.1:11435"


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
    executable = shutil.which("ollama")
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
