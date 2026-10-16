import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FOCO_DATA_DIR", ROOT / ".local-data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DATABASE = DATA / "foco.sqlite3"
MODEL_PATH = DATA / "classifier.joblib"
PORT = int(os.environ.get("FOCO_PORT", "8765"))
ORIGIN = f"http://127.0.0.1:{PORT}"
OLLAMA_URL = os.environ.get("FOCO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen3:4b"
CATEGORIES = ["faculdade", "trabalho", "financeiro", "pessoal", "promocoes"]
PRIORITIES = ["urgente", "normal", "baixa"]
