import asyncio
import json
import sqlite3
import uuid
from .db import connect, rows, now
from . import llm, ml
from .providers import synchronize, ProviderError


def enqueue(kind, target):
    job_id = str(uuid.uuid4())
    with connect() as db:
        try:
            db.execute("INSERT INTO jobs(id,kind,target,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (job_id, kind, target, now(), now()))
        except sqlite3.IntegrityError:
            job_id = db.execute("SELECT id FROM jobs WHERE kind=? AND target=? AND status IN ('queued','running')", (kind, target)).fetchone()[0]
    return {"id": job_id}


async def execute(job):
    kind, target = job["kind"], job["target"]
    if kind == "sync":
        return await synchronize(target)
    if kind == "train":
        result = await asyncio.to_thread(ml.train)
        # Atualiza apenas previsões automáticas; preserva as escolhas do usuário e os exemplos editoriais.
        def reclassify():
            for message in rows("SELECT m.id,m.subject,m.body FROM messages m JOIN accounts a ON a.id=m.account_id WHERE m.corrected=0 AND a.demo=0"):
                prediction = ml.classify(message["subject"], message["body"])
                with connect() as db:
                    db.execute("UPDATE messages SET category=?,priority=?,confidence=?,signals=? WHERE id=? AND corrected=0",
                               (prediction["category"], prediction["priority"], prediction["confidence"], prediction["signals"], message["id"]))
        await asyncio.to_thread(reclassify)
        return result
    found = rows("SELECT * FROM messages WHERE id=?", (target,))
    if not found:
        raise ValueError("A mensagem foi removida.")
    message = found[0]
    if kind == "analyze":
        analysis = await llm.analyze(message)
        with connect() as db:
            db.execute("UPDATE messages SET analysis=?,analysis_source='ollama',analyzed_at=? WHERE id=?",
                       (json.dumps(analysis, ensure_ascii=False), now(), target))
        return {"message_id": target}
    if kind.startswith("draft:"):
        content = await llm.draft(message, kind.split(":", 1)[1])
        with connect() as db:
            db.execute("UPDATE messages SET draft=? WHERE id=?", (content, target))
        return {"message_id": target}
    raise ValueError("Tipo de tarefa desconhecido.")


async def run_worker(stop):
    while not stop.is_set():
        jobs = rows("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1")
        if not jobs:
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass
            continue
        job = jobs[0]
        with connect() as db:
            db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (now(), job["id"]))
        try:
            result = await execute(job)
            status, error = "done", None
        except (llm.AIError, ProviderError, ValueError) as exc:
            status, error, result = "failed", str(exc), None
        except Exception:
            status, error, result = "failed", "Não foi possível concluir a tarefa. Seus dados foram preservados; tente novamente.", None
        with connect() as db:
            db.execute("UPDATE jobs SET status=?,error=?,result=?,updated_at=? WHERE id=?",
                       (status, error, json.dumps(result), now(), job["id"]))
