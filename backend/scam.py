"""Alerta de golpe em segundo plano, com o LLM local.

Verifica uma mensagem por vez (as mais recentes primeiro, dos últimos 30 dias), então uma
análise pedida pelo usuário espera no máximo uma verificação. Mensagens editoriais da
demonstração não são verificadas. O resultado é só um alerta: o usuário pode desmarcá-lo.
O Qev foi avaliado para esta tarefa e não serviu (0 de 10 golpes; ver docs/AVALIACAO.md).
"""
import asyncio
from . import llm
from .db import connect, rows

WINDOW_DAYS = 30
# COALESCE: sem ele, "scam=1" é NULL nas mensagens não verificadas e "NOT ..." esconderia todas as urgentes.
SCAM_SQL = "(COALESCE(m.scam,0)=1 AND m.scam_dismissed=0)"


async def step():
    """Verifica uma mensagem; retorna quantos segundos esperar antes do próximo passo."""
    if not (await llm.health())["ready"]:
        return 30
    pending = rows("SELECT id,subject,sender,received_at,category,body FROM messages "
                   "WHERE scam IS NULL AND editorial=0 AND julianday(received_at)>=julianday('now',?) "
                   "ORDER BY julianday(received_at) DESC LIMIT 1", (f"-{WINDOW_DAYS} days",))
    if not pending:
        return 5
    message = pending[0]
    try:
        flagged, reason = await llm.check_scam(message)
        values = (1 if flagged else 0, reason if flagged else None)
    except llm.AIError:
        if not (await llm.health())["ready"]:
            return 30  # Ollama caiu: tenta de novo depois, sem marcar a mensagem
        values = (-1, None)  # saída inválida para esta mensagem: não repete para sempre
    with connect() as db:
        db.execute("UPDATE messages SET scam=?,scam_reason=? WHERE id=? AND scam IS NULL", (*values, message["id"]))
    return 0


async def run_scam_checker(stop):
    while not stop.is_set():
        try:
            delay = await step()
        except Exception:
            delay = 30
        if delay:
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
