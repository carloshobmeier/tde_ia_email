"""LLM local (Qwen3 4B via Ollama) como detector de golpe. Um prompt (backend.llm.SCAM_PROMPT),
fixado antes: conferido em DEV e medido uma vez em EVAL, como no experimento do Qev.

Com o Foco aberto (Ollama em 127.0.0.1:11435):
  FOCO_OLLAMA_URL=http://127.0.0.1:11435 .venv/bin/python experiments/scam/llm_scam.py
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FOCO_DATA_DIR", tempfile.mkdtemp(prefix="foco-scam-llm-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import llm  # noqa: E402
from backend.db import init_db  # noqa: E402
from emails import DEV, EVAL, report  # noqa: E402


async def run(emails):
    """Usa exatamente o prompt e o esquema do aplicativo (llm.check_scam)."""
    values, started = [], time.perf_counter()
    for _, subject, body in emails:
        message = {"subject": subject, "sender": "desconhecido", "received_at": "2026-11-09T10:00:00-03:00",
                   "category": "pessoal", "body": body}
        flagged, _ = await llm.check_scam(message)
        values.append(1.0 if flagged else 0.0)
    return values, (time.perf_counter() - started) / len(emails)


async def main():
    init_db()
    dev, seconds = await run(DEV)
    report("LLM no desenvolvimento", dev, DEV)
    evaluation, seconds = await run(EVAL)
    report("LLM na avaliação", evaluation, EVAL)
    print(f"{seconds:.1f} s por e-mail ({llm.DEVICE})")


if __name__ == "__main__":
    asyncio.run(main())
