"""Refinador em segundo plano: consulta o Qev sem travar a fila de tarefas.

1. Responde os exemplos de validação/teste (necessários para escolher a combinação).
2. Com todos em cache, agenda um retreino: a combinação é escolhida na validação e as
   mensagens são reclassificadas.
3. Refina as mensagens em lotes pequenos, inclusive as de demonstração "ao vivo". Nunca altera
   correções do usuário nem mensagens editoriais (rótulos e resumo escritos à mão).
Sem Qev instalado ou ainda carregando, apenas espera: o TF-IDF continua classificando.
"""
import asyncio
import time
from . import ml, qev
from .db import connect, rows

BATCH = 8
RESCAN_SECONDS = 300
_last_scan = 0.0


def _answer(text):
    key = qev.text_key(text)
    qev.store(key, qev.predict(text))


def step():
    """Um passo de trabalho; retorna quantos segundos esperar antes do próximo."""
    global _last_scan
    if not qev.installed():
        return 60
    if not qev.online():
        return 10
    samples = ml.evaluation_samples()
    have = qev.cached(qev.text_key(s["text"]) for s in samples)
    todo = [s for s in samples if qev.text_key(s["text"]) not in have][:BATCH]
    if todo:
        for sample in todo:
            _answer(sample["text"])
        return 0
    model = ml.get_model()
    total = len({qev.text_key(s["text"]) for s in samples})
    if total and (model.get("ensemble_samples") != total or model.get("qev_cache_model") != qev.cache_model()):
        from .worker import enqueue  # import tardio: worker -> providers -> mail -> qev
        enqueue("train", "classifier")
        return 5
    if not (qev.new_messages.is_set() or time.monotonic() - _last_scan > RESCAN_SECONDS):
        return 10
    qev.new_messages.clear()
    messages = rows("SELECT id,subject,body FROM messages WHERE corrected=0 AND editorial=0")
    texts = {m["id"]: ml.input_text(m["subject"], m["body"]) for m in messages}
    have = qev.cached(qev.text_key(text) for text in texts.values())
    pending = [m for m in messages if qev.text_key(texts[m["id"]]) not in have]
    for message in pending[:BATCH]:
        _answer(texts[message["id"]])
        prediction = ml.classify(message["subject"], message["body"])
        with connect() as db:
            db.execute("UPDATE messages SET category=?,priority=?,confidence=?,signals=? WHERE id=? AND corrected=0 AND editorial=0",
                       (prediction["category"], prediction["priority"], prediction["confidence"],
                        prediction["signals"], message["id"]))
    if len(pending) > BATCH:
        qev.new_messages.set()  # ainda há fila: continua no próximo passo
        return 0
    _last_scan = time.monotonic()
    return 10


async def run_refiner(stop):
    while not stop.is_set():
        try:
            delay = await asyncio.to_thread(step)
        except Exception:
            delay = 30  # Qev caiu no meio de um lote: tenta de novo depois, sem afetar o restante
        if delay:
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
