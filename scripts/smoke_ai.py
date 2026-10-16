"""Exercita o LLM real com mensagens fictícias; nunca lê e-mails pessoais."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import llm
from backend.db import init_db


async def main():
    init_db()
    message = {"subject": "Revisão do relatório", "sender": "Ana", "received_at": "2026-09-25T10:00:00-03:00", "category": "trabalho",
               "body": "Olá, Carlos. Por favor revise as tabelas do relatório e envie sua revisão até amanhã às 17h. Obrigada, Ana."}
    start = time.perf_counter()
    analysis = await llm.analyze(message)
    elapsed_analysis = time.perf_counter() - start
    print(json.dumps({"task": "analysis", "seconds": round(elapsed_analysis, 2), "result": analysis}, ensure_ascii=False), flush=True)
    assert analysis["action"], "Deve identificar a ação solicitada."
    assert analysis["due_at"] and analysis["due_at"].startswith("2026-09-26"), "Deve resolver amanhã a partir do envio."
    assert analysis["due_evidence"] in message["body"], "Deve preservar evidência literal."
    assert not analysis["due_confirmed"], "A data exige confirmação do usuário."
    start = time.perf_counter()
    draft = await llm.draft(message)
    elapsed_draft = time.perf_counter() - start
    print(json.dumps({"task": "draft", "seconds": round(elapsed_draft, 2), "result": draft}, ensure_ascii=False), flush=True)
    result = {"model": "qwen3:4b", "device": "CPU (num_gpu=0)", "context": 4096,
              "analysis_seconds": elapsed_analysis, "draft_seconds": elapsed_draft, "analysis": analysis, "draft": draft,
              "note": "Teste na máquina de desenvolvimento. Não é um benchmark do i7-1260P de destino."}
    output = Path(__file__).resolve().parent.parent / "artifacts"
    output.mkdir(exist_ok=True)
    (output / "ai-smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == '__main__':
    asyncio.run(main())
