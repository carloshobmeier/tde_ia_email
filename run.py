"""python run.py / iniciar.bat: abre o Foco e gerencia seu Ollama local."""
import os
from pathlib import Path
import sys
import threading
import time
import webbrowser
from scripts.runtime import AI_URL, ROOT, ensure_ollama, get_json, stop_owned


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Use Python 3.11 ou mais recente.")
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("Execute instalar.bat primeiro para preparar a interface.")
    try:
        import uvicorn
        import sklearn
    except ImportError:
        raise SystemExit("Execute instalar.bat e abra com iniciar.bat para usar o ambiente virtual.")
    port = int(os.environ.get("FOCO_PORT", "8765"))
    url = f"http://127.0.0.1:{port}"
    try:
        data = get_json(url + "/api/bootstrap")
        if data.get("version"):
            print(f"Foco já está aberto em {url}")
            if "--no-browser" not in sys.argv:
                webbrowser.open(url)
            return
    except Exception:
        pass
    process, log = ensure_ollama()
    os.environ["FOCO_OLLAMA_URL"] = AI_URL
    print(f"\n  FOCO — seu espaço pessoal\n  {url}\n\n  Feche esta janela ou pressione Ctrl+C para encerrar.\n")
    if "--no-browser" not in sys.argv:
        def open_when_ready():
            for _ in range(80):
                try:
                    get_json(url + "/api/bootstrap")
                    webbrowser.open(url)
                    return
                except Exception:
                    time.sleep(.25)
        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        uvicorn.run("backend.main:app", host="127.0.0.1", port=port, access_log=False, log_level="warning")
    finally:
        stop_owned(process, log)


if __name__ == "__main__":
    main()
