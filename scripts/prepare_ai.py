"""Baixa Qwen3 4B para o armazenamento local do projeto."""
import json
from pathlib import Path
import sys
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.runtime import AI_URL, ensure_ollama, stop_owned


def main():
    process, log = ensure_ollama()
    try:
        print("Baixando Qwen3 4B para .local-data/ollama-models (aproximadamente 2,5 GB).", flush=True)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(AI_URL + "/api/pull", data=json.dumps({"model": "qwen3:4b", "stream": True}).encode(), headers={"Content-Type": "application/json"})
        last = ""
        with opener.open(request, timeout=1800) as response:
            for line in response:
                item = json.loads(line)
                if item.get("error"):
                    raise RuntimeError(item["error"])
                percent = int(item.get("completed", 0) / item["total"] * 100) if item.get("total") else None
                status = item.get("status", "") + (f" — {percent}%" if percent is not None else "")
                if status != last:
                    print(status, flush=True)
                    last = status
        print("\nIA pronta. Abra o Foco com iniciar.bat.")
    finally:
        stop_owned(process, log)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Não foi possível preparar o modelo: {exc}\nConfira se o Ollama está instalado e se há acesso à internet.")
